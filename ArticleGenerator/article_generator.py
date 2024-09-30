import os
import random
import time
import re
from openai import OpenAI


class ArticleGenerator:
    def __init__(self, data_folder, api_key_file, output_folder, prompt_file, min_chars, model_name="gpt-4o-mini", language="English", log_output=None):
        self.data_folder = data_folder
        self.api_key_file = api_key_file
        self.output_folder = output_folder
        self.prompt_file = prompt_file
        self.min_chars = min_chars
        self.model_name = model_name
        self.language = language
        self.log_output = log_output  # Добавим этот параметр для логирования

        self.api_keys = self.load_api_keys()
        self.current_key_index = 0

    def log(self, message):
        """Метод для вывода логов"""
        if self.log_output:
            self.log_output(message)
        print(message)

    def load_api_keys(self):
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
        if retries > 3:  # Лимит попыток
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

    def clean_text(self, text):
        # Убираем нежелательные символы, такие как скобки и странные символы, кроме допустимых знаков препинания
        # Оставляем точки, запятые, кавычки, восклицательные и вопросительные знаки, двоеточие, точки с запятой, дефисы, апострофы.
        cleaned_text = re.sub(r'[�\[\]\{\}\(\)]+', '', text)
        
        # Убираем эмодзи и другие специальные символы, оставляя только буквы, цифры, знаки препинания и пробелы
        cleaned_text = re.sub(r'[^\w\s.,!?;:"\'\-]', '', cleaned_text)
        
        # Удаляем повторяющиеся пробелы
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        
        # Обрезаем начальные и конечные пробелы
        cleaned_text = cleaned_text.strip()
        
        return cleaned_text

    def generate_article(self, prompt, keywords, output_file):
        try:
            self.set_GPT()
            self.log(f'Using model: {self.model_name}')

            total_chars = 0
            article_content = ""

            while total_chars < self.min_chars:
                keyword_string = ', '.join(keywords)
                prompt_with_keywords = f"{prompt}\nInclude the following keywords in the text: {keyword_string}\nThe first line should be a headline."

                response = self.chat_with_openai(prompt_with_keywords)
                if response is None:
                    self.log("Failed to generate text after multiple retries.")
                    return

                result = response.choices[0].message.content
                cleaned_result = self.clean_text(result)

                if total_chars + len(cleaned_result) > self.min_chars:
                    article_content += cleaned_result[:self.min_chars - total_chars]
                    break
                else:
                    article_content += cleaned_result
                    total_chars += len(cleaned_result)

                time.sleep(1)

            with open(output_file, 'w', encoding='utf-8') as file:
                file.write(article_content)
            self.log(f"Article saved to {output_file}")

        except Exception as e:
            self.log(f"An error occurred during article generation: {e}")

    def generate_articles(self):
        keywords_data = self.read_keywords(self.data_folder)
        prompt = self.read_prompt()

        for site, keywords in keywords_data.items():
            site_folder = os.path.join(self.output_folder, site)
            if not os.path.exists(site_folder):
                os.makedirs(site_folder)

            article_title = f"SEO_Article_{random.randint(1000, 9999)}"
            article_folder = os.path.join(site_folder, article_title)

            if not os.path.exists(article_folder):
                os.makedirs(article_folder)

            output_file = os.path.join(article_folder, "article.txt")
            self.generate_article(prompt, keywords, output_file)

    def read_keywords(self, keyword_file):
        """Прочитать файл с ключевыми словами"""
        with open(keyword_file, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        keywords = {}
        for line in lines:
            parts = line.split('|')
            if len(parts) == 2:
                site = parts[0].strip()
                keywords_list = [kw.strip() for kw in parts[1].split(',')]
                keywords[site] = keywords_list
        return keywords
