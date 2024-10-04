import os
import re
import random
import aiohttp
import asyncio
import sqlite3
import logging
from pathlib import Path
from openai import OpenAI
import urllib.parse  # Добавляем импорт urllib для работы с кодировкой URL

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
        """Загрузка API-ключей из файла"""
        if not self.api_key_file.exists():
            raise FileNotFoundError(f"API key file not found: {self.api_key_file}")

        with open(self.api_key_file, 'r') as file:
            keys = [line.strip() for line in file.readlines() if line.strip()]

        self.log(f'Loaded {len(keys)} API keys')
        return keys

    def set_GPT(self):
        """Установка модели GPT в зависимости от выбора пользователя"""
        self.client = OpenAI(api_key=self.next_api_key())
        self.log(f'Set GPT model to {self.model_name}')

    def clean_text(self, text):
        """Функция для очистки текста от лишних символов"""
        # Удаляем все незначащие символы и оставляем только разрешенные для статей символы
        cleaned_text = re.sub(r'[^a-zA-Zа-яА-Я0-9\s.,!?\'"()\-–:;]', '', text)
        # Убираем лишние пробелы
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        return cleaned_text

    def sanitize_filename(self, filename, max_length=50):
        """Удаление недопустимых символов и сокращение длины имени файла"""
        sanitized = re.sub(r'[\/:*?"<>|]', '', filename)  # Убираем недопустимые символы
        sanitized = sanitized.replace('\n', ' ').strip()  # Убираем переносы строк и лишние пробелы
        return sanitized[:max_length].strip()  # Ограничиваем длину до max_length символов

    def trim_incomplete_sentence(self, text):
        """Обрезает текст до последнего полного предложения"""
        last_sentence_match = re.search(r'(.+[.!?])[^.!?]*$', text)
        if last_sentence_match:
            return last_sentence_match.group(1)  # Возвращаем текст до конца последнего завершенного предложения
        return text  # Если не нашли завершенных предложений, возвращаем текст как есть

    async def generate_article_single_request(self, image_downloader):
        """Генерация статьи одним запросом для каждого набора ключевых слов и скачивание изображения"""
        try:
            self.set_GPT()
            self.log(f'Using model: {self.model_name}')

            prompt = self.read_prompt()
            keywords_data = self.read_keywords(self.data_folder)

            async with aiohttp.ClientSession() as session:
                for site, keywords_sets in keywords_data.items():
                    for keywords in keywords_sets:
                        self.log(f"Generating article for site '{site}' with keywords: {keywords}")

                        # Получаем первые три ключевых слова и используем их для названия папки
                        first_keywords = ' '.join(keywords[:3])
                        sanitized_keywords = self.sanitize_filename(first_keywords, max_length=30)

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

                        # Чистим текст
                        cleaned_article = self.clean_text(result)

                        # Обрезаем незавершенное предложение
                        trimmed_article = self.trim_incomplete_sentence(cleaned_article)

                        # Разделение заголовка и текста
                        headline, remaining_content = self.extract_headline(trimmed_article)

                        if headline:
                            sanitized_headline = self.sanitize_filename(headline, max_length=10)
                            formatted_article = f"{headline}\n\n{remaining_content}"

                            # Создаем папку по первым трем ключевым словам
                            headline_folder = os.path.join(site_folder, sanitized_keywords)
                            if not os.path.exists(headline_folder):
                                os.makedirs(headline_folder)

                            output_file = os.path.join(headline_folder, "article.txt")
                        else:
                            sanitized_headline = "Unnamed_Article"
                            formatted_article = trimmed_article

                            headline_folder = os.path.join(site_folder, sanitized_keywords)
                            if not os.path.exists(headline_folder):
                                os.makedirs(headline_folder)

                            output_file = os.path.join(headline_folder, "article.txt")

                        # Сохраняем статью
                        with open(output_file, 'w', encoding='utf-8') as file:
                            file.write(formatted_article)

                        self.log(f"Article saved to {output_file}")

                        # Загрузка изображения
                        await image_downloader.download_random_image(session, keywords, headline_folder)

        except Exception as e:
            self.log(f"Error generating article: {e}")

    def read_keywords(self, keyword_file):
        """Чтение файла с ключевыми словами"""
        with open(keyword_file, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        keywords = {}
        self.log(f"Reading keywords from file: {keyword_file}")
        for idx, line in enumerate(lines):
            self.log(f"Processing line {idx + 1}: {line.strip()}")
            parts = line.strip().split('|')
            if len(parts) == 2:
                site = parts[0].strip()
                keywords_list = [kw.strip() for kw in parts[1].split(',')]

                if site in keywords:
                    keywords[site].append(keywords_list)
                else:
                    keywords[site] = [keywords_list]
            else:
                self.log(f"Skipping line {idx + 1} due to incorrect format: {line.strip()}")

        self.log(f'Parsed {len(keywords)} unique sites with keywords from file.')
        return keywords

    def read_prompt(self):
        with open(self.prompt_file, 'r', encoding='utf-8') as file:
            prompt = file.read().strip()
        return prompt

    def next_api_key(self):
        if not self.api_keys:
            raise ValueError("No API keys available.")
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self.log(f'Switching to API key {self.current_key_index}')
        return key

    def extract_headline(self, text):
        """Извлечение заголовка из первого предложения, если после точки есть пробел"""
        first_sentence_end = text.find(".")

        if first_sentence_end != -1 and (first_sentence_end + 1 < len(text)) and text[first_sentence_end + 1] == " ":
            headline = text[:first_sentence_end + 1].strip()  # Включаем точку
            remaining_text = text[first_sentence_end + 1:].strip()
            return headline, remaining_text
        else:
            return None, text.strip()


class ImageDownloaderPix:
    def __init__(self, api_key, base_image_path, log_function=logging.info):
        self.api_key = api_key
        self.base_image_path = base_image_path
        self.log_function = log_function

    async def download_random_image(self, session, keywords, output_folder):
        """Загружает случайное изображение с Pixabay по заданным ключевым словам"""
        random_keyword = random.choice(keywords)
        encoded_keyword = urllib.parse.quote(random_keyword)
        url = f'https://pixabay.com/api/?key={self.api_key}&q={encoded_keyword}&per_page=3'

        try:
            self.log_function(f"Requesting image for keyword: {random_keyword}")
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                if 'hits' in data and data['hits']:
                    image_url = data['hits'][0]['largeImageURL']
                    await self.download_image(session, image_url, output_folder, random_keyword)
                else:
                    self.log_function(f"No images found for keyword: {random_keyword}")
        except Exception as e:
            self.log_function(f"Error downloading image: {e}")

    async def download_image(self, session, image_url, output_folder, keyword):
        """Загружает изображение и сохраняет его с именем, включающим ключевое слово и случайное число"""
        random_number = random.randint(1000, 9999)
        image_extension = os.path.splitext(image_url)[1]  # Получаем расширение файла (например, .jpg, .png)
        image_filename = f"{keyword}_{random_number}{image_extension}"  # Формируем имя файла
        image_path = os.path.join(output_folder, image_filename)

        try:
            async with session.get(image_url) as response:
                response.raise_for_status()
                image_data = await response.read()
                with open(image_path, 'wb') as image_file:
                    image_file.write(image_data)
                self.log_function(f"Image saved: {image_path}")
        except Exception as e:
            self.log_function(f"Failed to download image: {e}")


# Example usage:
if __name__ == '__main__':
    api_key = "your_pixabay_api_key"
    database_path = "path_to_your_database.db"
    base_image_path = "path_to_image_storage"
    
    # Создание экземпляров ArticleGenerator и ImageDownloaderPix
    downloader = ImageDownloaderPix(api_key, base_image_path)
    article_generator = ArticleGenerator(data_folder="data_folder", api_key_file="api_key_file", 
                                         output_folder="output_folder", prompt_file="prompt_file", 
                                         min_chars=500)

    # Запуск генерации статей и загрузки изображений
    asyncio.run(article_generator.generate_article_single_request(downloader))
