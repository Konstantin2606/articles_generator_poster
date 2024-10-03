import os
import random
import time
import re
from openai import OpenAI
from pathlib import Path
import sys

def resource_path(relative_path):
    """Возвращает правильный путь к ресурсу, поддерживая как исполняемые файлы, так и обычные скрипты"""
    if getattr(sys, 'frozen', False):  # Если приложение скомпилировано
        base_path = Path(sys._MEIPASS)
    else:  # Если это обычный скрипт
        base_path = Path(__file__).parent
    return base_path / relative_path

class ArticleGenerator:
    def __init__(self, data_folder, api_key_file, output_folder, prompt_file, min_chars, model_name="gpt-4o-mini", language="English", log_output=None):
        self.data_folder = Path(data_folder).resolve()  # Преобразуем в абсолютный путь
        self.api_key_file = Path(api_key_file).resolve()  # Преобразуем в абсолютный путь
        self.output_folder = Path(output_folder).resolve()  # Преобразуем в абсолютный путь
        self.prompt_file = Path(prompt_file).resolve()  # Преобразуем в абсолютный путь
        self.min_chars = min_chars
        self.model_name = model_name
        self.language = language
        self.log_output = log_output

        self.api_keys = self.load_api_keys()  # Загружаем API-ключи
        self.current_key_index = 0

    def log(self, message):
        """Метод для вывода логов"""
        if self.log_output:
            self.log_output(message)
        print(message)

    def load_api_keys(self):
        # Убедимся, что файл существует перед его открытием
        if not self.api_key_file.exists():
            raise FileNotFoundError(f"API key file not found: {self.api_key_file}")

        # Чтение файла с API ключами
        with open(self.api_key_file, 'r') as file:
            keys = [line.strip() for line in file.readlines() if line.strip()]
        
        self.log(f'Loaded {len(keys)} API keys')
        return keys
    
    def next_api_key(self):
        if not self.api_keys:
            raise ValueError("No API keys available.")
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self.log(f'Switching to API key {self.current_key_index}')
        return key

    def set_GPT(self):
        if self.model_name == "deepseek-chat":
            self.client = OpenAI(api_key=self.next_api_key(), base_url="https://api.deepseek.com")
        else:
            self.client = OpenAI(api_key=self.next_api_key())
        self.log(f'Set GPT model to {self.model_name}')

    def read_prompt(self):
        with open(self.prompt_file, 'r', encoding='utf-8') as file:
            prompt = file.read().strip()
        return prompt

    def chat_with_openai(self, prompt, retries=0):
        if retries > 3:
            self.log("Reached retry limit.")
            return None

        messages = [
            {"role": "system", "content": f"You are an expert in generating SEO-optimized articles in {self.language}."},
            {"role": "user", "content": prompt}
        ]
        try:
            self.log(f'Sending request to {self.model_name} with prompt: {prompt}')
            response = self.client.chat.completions.create(model=self.model_name, messages=messages)
            self.log(f'Received response from {self.model_name}')
            return response
        except Exception as e:
            self.log(f"Switching API key due to error: {str(e)}")
            self.set_GPT()
            return self.chat_with_openai(prompt, retries + 1)

    def extract_headline(self, text):
        """Извлечение заголовка из первого предложения, если после точки есть пробел"""
        first_sentence_end = text.find(".")
        
        # Проверяем, есть ли пробел после точки
        if first_sentence_end != -1 and (first_sentence_end + 1 < len(text)) and text[first_sentence_end + 1] == " ":
            # Есть пробел после точки — это заголовок
            headline = text[:first_sentence_end + 1].strip()  # Включаем точку
            remaining_text = text[first_sentence_end + 1:].strip()
            return headline, remaining_text
        else:
            # Либо нет точки, либо текст после точки идет слитно — трактуем весь текст как основной контент
            return None, text.strip()

    def sanitize_filename(self, filename, max_length=10):
        """Удаление недопустимых символов и сокращение длины файла"""
        # Убираем недопустимые символы и ограничиваем длину
        sanitized = re.sub(r'[\/:*?"<>|]', '', filename)  # Убираем недопустимые символы
        sanitized = sanitized.replace('\n', ' ').strip()  # Убираем переносы строк и лишние пробелы
        return sanitized[:max_length].strip()  # Ограничиваем длину до max_length символов

    def generate_article_single_request(self):
        """Генерация статьи одним запросом для каждого набора ключевых слов"""
        try:
            self.set_GPT()
            self.log(f'Using model: {self.model_name}')

            prompt = self.read_prompt()
            keywords_data = self.read_keywords(self.data_folder)

            # Для каждой строки из файла с ключевыми словами генерируем статью
            for site, keywords_sets in keywords_data.items():
                for keywords in keywords_sets:
                    self.log(f"Generating article for site '{site}' with keywords: {keywords}")

                    site_folder = os.path.join(self.output_folder, site)
                    if not os.path.exists(site_folder):
                        os.makedirs(site_folder)

                    keyword_string = ', '.join(keywords)
                    prompt_with_keywords = f"{prompt}\nInclude the following keywords: {keyword_string}\nFirst line should be a headline."

                    approx_tokens = int(self.min_chars / 5)
                    max_tokens = min(approx_tokens, 4096)

                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=[{"role": "system", "content": f"You are an expert in generating SEO-optimized articles in {self.language}."},
                                  {"role": "user", "content": prompt_with_keywords}],
                        max_tokens=max_tokens
                    )

                    result = response.choices[0].message.content

                    # Разделение заголовка и текста
                    headline, remaining_content = self.extract_headline(result)

                    if headline:
                        # Если заголовок найден
                        sanitized_headline = self.sanitize_filename(headline, max_length=10)  # Сокращаем до 10 символов
                        formatted_article = f"{headline}\n\n{remaining_content}"

                        # Создаем папку с названием заголовка внутри папки сайта
                        headline_folder = os.path.join(site_folder, sanitized_headline)
                        if not os.path.exists(headline_folder):
                            os.makedirs(headline_folder)

                        output_file = os.path.join(headline_folder, "article.txt")
                    else:
                        # Если заголовок не найден, сохраняем весь текст как есть
                        sanitized_headline = "Unnamed_Article"
                        formatted_article = result
                        headline_folder = os.path.join(site_folder, sanitized_headline)
                        if not os.path.exists(headline_folder):
                            os.makedirs(headline_folder)

                        output_file = os.path.join(headline_folder, "article.txt")

                    # Сохранение статьи
                    with open(output_file, 'w', encoding='utf-8') as file:
                        file.write(formatted_article)
                    self.log(f"Article saved to {output_file}")

        except Exception as e:
            self.log(f"Error generating article in single request: {e}")

    def read_keywords(self, keyword_file):
        """Прочитать файл с ключевыми словами, поддерживая несколько строк с одинаковым сайтом"""
        with open(keyword_file, 'r', encoding='utf-8') as file:
            lines = file.readlines()  # Чтение всех строк файла

        keywords = {}
        self.log(f"Reading keywords from file: {keyword_file}")
        for idx, line in enumerate(lines):
            self.log(f"Processing line {idx + 1}: {line.strip()}")
            parts = line.strip().split('|')  # Убираем пробелы в начале и конце строки
            if len(parts) == 2:  # Если в строке два элемента
                site = parts[0].strip()  # Убираем лишние пробелы вокруг названия сайта
                keywords_list = [kw.strip() for kw in parts[1].split(',')]  # Разделяем ключевые слова по запятым

                # Если сайт уже существует в словаре, добавляем к существующим ключевым словам
                if site in keywords:
                    keywords[site].append(keywords_list)
                else:
                    keywords[site] = [keywords_list]  # Создаем список списков для ключевых слов
            else:
                self.log(f"Skipping line {idx + 1} due to incorrect format: {line.strip()}")

        self.log(f'Parsed {len(keywords)} unique sites with keywords from file.')
        return keywords
