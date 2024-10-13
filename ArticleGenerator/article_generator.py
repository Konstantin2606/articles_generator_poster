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
import csv

class ArticleGenerator:
    def __init__(self, data_folder, api_key_file, output_folder, prompt_file, min_chars, model_name="gpt-4o-mini", language="English", log_output=None):
        self.data_folder = Path(data_folder).resolve()
        self.api_key_file = Path(api_key_file).resolve()
        self.output_folder = Path(output_folder).resolve()
        self.prompt_file = Path(prompt_file).resolve()
        self.min_chars = min_chars
        self.model_name = model_name
        self.language = language
        self.log_output = log_output

        self.api_keys = self.load_api_keys()
        self.current_key_index = 0

    def log(self, message):
        if self.log_output:
            self.log_output(message)
        print(message)

    def load_api_keys(self):
        if not self.api_key_file.exists():
            raise FileNotFoundError(f"API key file not found: {self.api_key_file}")
        with open(self.api_key_file, 'r') as file:
            keys = [line.strip() for line in file.readlines() if line.strip()]
        self.log(f'Loaded {len(keys)} API keys')
        return keys

    def set_GPT(self):
        self.client = OpenAI(api_key=self.next_api_key())
        self.log(f'Set GPT model to {self.model_name}')

    def clean_text(self, text):
        return re.sub(r'[^a-zA-Zа-яА-Я0-9\s.,!?\'"()\-–:;]', '', text)

    def sanitize_filename(self, filename, max_length=50):
        sanitized = re.sub(r'[\/:*?"<>|]', '', filename)
        return sanitized[:max_length].strip()

    def remove_content_after_trigger(self, text, trigger="---"):
        trigger_index = text.find(trigger)
        if trigger_index != -1:
            self.log(f"Trigger '{trigger}' found. Removing content after it.")
            return text[:trigger_index].strip()
        return text

    async def generate_article_single_request(self, image_downloader):
        try:
            self.set_GPT()
            prompt = self.read_prompt()
            keywords_data = self.read_keywords(self.data_folder)  # Теперь возвращает словарь {название сайта: {название файла: текст}}
            min_required_chars = int(self.min_chars * 0.6)

            async with aiohttp.ClientSession() as session:
                for site, texts in keywords_data.items():
                    # Создаем основную папку для сайта
                    site_folder = os.path.join(self.output_folder, site)
                    os.makedirs(site_folder, exist_ok=True)
                    
                    for text_file_name, text_content in texts.items():
                        self.log(f"Generating article for site '{site}' with text from file '{text_file_name}'.")

                        # Создаем подпапку для статьи с именем текстового файла внутри папки сайта
                        article_folder = os.path.join(site_folder, text_file_name)
                        os.makedirs(article_folder, exist_ok=True)

                        # Формируем промпт с текстом из файла
                        prompt_with_text = f"{prompt}\nUse the following content as a basis for the article:\n\n{text_content}\n\nGenerate content with the specified parameters."

                        max_tokens = min(int(self.min_chars / 5), 4096)
                        formatted_article = self.generate_article_with_retries(prompt_with_text, min_required_chars, max_tokens)

                        if formatted_article:
                            # Сохраняем сгенерированную статью в подпапке статьи
                            output_file = os.path.join(article_folder, "article.txt")
                            with open(output_file, 'w', encoding='utf-8') as file:
                                file.write(formatted_article)

                            self.log(f"Article saved to {output_file}")

                            # Скачиваем изображение и сохраняем его в подпапке статьи
                            await image_downloader.download_random_image(session, [text_file_name], article_folder)

        except Exception as e:
            self.log(f"Error generating article: {e}")



    def generate_article_with_retries(self, prompt_with_keywords, min_required_chars, max_tokens, retry_count=2):
        generated_texts = []
        for attempt in range(retry_count):
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "system", "content": f"You are an expert in generating SEO-optimized articles in {self.language}."},
                        {"role": "user", "content": prompt_with_keywords}],
                max_tokens=max_tokens
            )

            result = response.choices[0].message.content
            cleaned_article = self.clean_text(result)
            
            # Применение триггера для обрезки текста
            truncated_article = self.remove_content_after_trigger(cleaned_article, trigger="---")
            
            if len(truncated_article) >= min_required_chars:
                generated_texts.append(truncated_article)
                self.log(f"Generated article {attempt + 1} meets minimum character requirement: {len(truncated_article)} characters.")
                # Возвращаем первый успешный результат и пропускаем уникальность
                return truncated_article
            else:
                self.log(f"Generated article {attempt + 1} too short, retrying...")

        # Закомментировано на время для тестирования без уникализации текста
        # unique_text = self.get_most_unique_text(generated_texts)
        # return unique_text
        self.log("No article met the character requirement after retries.")
        return None  # Если ни одна попытка не соответствует требованиям


    def get_most_unique_text(self, generated_texts):
        if len(generated_texts) > 1:
            return min(generated_texts, key=lambda txt: self.calculate_similarity(generated_texts[0], txt))
        return generated_texts[-1]

    def calculate_similarity(self, text1, text2):
        return len(set(text1.split()).intersection(set(text2.split()))) / len(set(text1.split()))

    def read_keywords(self, base_folder):
        """
        Читает текстовые файлы из подпапок, возвращая содержимое с названием файлов.
        base_folder - папка с подпапками (сайтами), в которых находятся текстовые файлы.
        """
        keywords = {}
        base_folder = Path(base_folder)

        if not base_folder.exists():
            raise FileNotFoundError(f"Base folder not found: {base_folder}")
        
        self.log(f"Reading text files from folder: {base_folder}")

        for site_folder in base_folder.iterdir():
            if site_folder.is_dir():  # Проверяем, что это папка
                site_name = site_folder.name
                self.log(f"Processing site folder: {site_name}")

                # Обрабатываем каждый текстовый файл
                texts = {}
                for text_file in site_folder.glob("*.txt"):
                    with text_file.open('r', encoding='utf-8') as file:
                        text_content = file.read().strip()
                        texts[text_file.stem] = text_content  # Используем stem (имя файла без расширения)

                keywords[site_name] = texts  # Записываем все тексты и имена файлов для сайта

        self.log(f'Parsed {len(keywords)} unique sites with text data from folders.')
        return keywords


    def read_prompt(self):
        with open(self.prompt_file, 'r', encoding='utf-8') as file:
            return file.read().strip()

    def next_api_key(self):
        if not self.api_keys:
            raise ValueError("No API keys available.")
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self.log(f'Switching to API key {self.current_key_index}')
        return key


class ImageDownloaderPix:
    def __init__(self, api_key, base_image_path, log_function=None):
        self.api_key = api_key
        self.base_image_path = base_image_path
        self.log_function = log_function or print
        self.max_retries = 3  # Количество повторных попыток
        self.delay = 5  # Задержка между запросами
        self.csv_file = os.path.join('settings', 'downloaded_images.csv')  # Путь к CSV-файлу в папке settings

        # Список User-Agent для ротации
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:88.0) Gecko/20100101 Firefox/88.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:88.0) Gecko/20100101 Firefox/88.0"
        ]

        # Проверка существования папки для settings
        os.makedirs('settings', exist_ok=True)

        # Проверка существования CSV файла, если его нет, создаем с заголовками
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['query', 'filename', 'url'])  # Заголовки для файла CSV

    def get_random_user_agent(self):
        """Возвращает случайный User-Agent из списка."""
        return random.choice(self.user_agents)

    def image_already_downloaded(self, image_tags):
        """Проверяет, были ли изображения уже загружены по тегам"""
        self.log_function(f"Checking if image with tags '{image_tags}' has already been downloaded.")
        
        if not os.path.exists(self.csv_file):
            self.log_function("CSV file does not exist. Proceeding with download.")
            return False

        with open(self.csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # Пропускаем заголовок
            for row in reader:
                # Проверяем, что строка содержит достаточно колонок
                if len(row) < 4:
                    self.log_function(f"Invalid row format in CSV: {row}, skipping...")
                    continue
                
                # Сравниваем теги (четвертая колонка в CSV)
                if row[3] == image_tags:
                    self.log_function(f"Image with tags '{image_tags}' already downloaded.")
                    return True  # Изображение с такими тегами уже загружено
        self.log_function(f"Image with tags '{image_tags}' has not been downloaded yet.")
        return False


    def write_to_csv(self, query, filename, image_url, image_tags, image_type):
        """Записывает информацию об изображении в CSV файл."""
        self.log_function(f"Writing image data to CSV: {self.csv_file} | Query: {query}, Filename: {filename}, URL: {image_url}, Tags: {image_tags}, Type: {image_type}")
        
        with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([query, filename, image_url, image_tags, image_type])
        self.log_function(f"Successfully wrote image data to CSV.")


    async def download_images_for_keyword(self, session, keyword, output_folder):
        """Загружает изображения для заданного ключевого слова"""
        self.log_function(f"Starting image search for keyword: {keyword}")
        
        encoded_keyword = urllib.parse.quote(keyword)
        url = f'https://pixabay.com/api/?key={self.api_key}&q={encoded_keyword}&per_page=5'

        for attempt in range(self.max_retries):
            try:
                user_agent = self.get_random_user_agent()
                self.log_function(f"Requesting images for keyword: {keyword} (Attempt {attempt + 1}) with User-Agent: {user_agent}")

                headers = {'User-Agent': user_agent}

                async with session.get(url, headers=headers) as response:
                    self.log_function(f"Received response with status code: {response.status}")
                    
                    if response.status == 502:
                        self.log_function(f"Received 502 Bad Gateway. Retrying in {self.delay} seconds...")
                        await asyncio.sleep(self.delay)
                        continue

                    if response.status == 429:
                        self.log_function(f"Received 429 Too Many Requests. Waiting for 10 seconds...")
                        await asyncio.sleep(10)
                        continue

                    response.raise_for_status()
                    data = await response.json()

                    self.log_function(f"Received data: {data}")
                    
                    # Проверяем, что полученные данные содержат ключ 'hits' и что там есть результаты
                    if 'hits' in data and isinstance(data['hits'], list):
                        if len(data['hits']) == 0:
                            self.log_function(f"No images found for keyword: {keyword}.")
                            return False

                        for hit in data['hits']:
                            # Логируем полный 'hit', чтобы точно видеть данные
                            self.log_function(f"Processing hit: {hit}")

                            image_tags = hit.get('tags', None)  # Безопасно получаем теги
                            image_url = hit.get('largeImageURL', None)  # Безопасно получаем URL
                            image_type = hit.get('type', None)  # Безопасно получаем тип изображения

                            # Проверяем, чтобы теги и URL были корректными
                            if not image_tags or not image_url:
                                self.log_function("Missing image tags or URL, skipping this hit...")
                                continue

                            # Проверяем, были ли изображения с такими тегами уже загружены
                            if not self.image_already_downloaded(image_tags):
                                await self.download_image(session, image_url, output_folder, keyword, image_tags, image_type)
                                return True  # Успешно скачали изображение
                        self.log_function(f"All images for keyword '{keyword}' are already downloaded by tags.")
                        return False
                    else:
                        self.log_function(f"No valid 'hits' found in the response for keyword: {keyword}. Data received: {data}")
                        return False
            except aiohttp.ClientError as e:
                self.log_function(f"Network error occurred: {e}. Retrying in {self.delay} seconds...")
                await asyncio.sleep(self.delay)
            except Exception as e:
                self.log_function(f"Unexpected error occurred: {e}")
                break
        return False


    async def download_image(self, session, image_url, output_folder, keyword, image_tags, image_type):
        """Загружает изображение и сохраняет его с именем, включающим ключевое слово"""
        self.log_function(f"Starting download for image with tags '{image_tags}' from URL: {image_url}")
        
        random_number = random.randint(1000, 9999)
        image_extension = os.path.splitext(image_url)[1]  # Получаем расширение файла (например, .jpg, .png)
        image_filename = f"{keyword}_{random_number}{image_extension}"  # Формируем имя файла
        image_path = os.path.join(output_folder, image_filename)

        try:
            async with session.get(image_url) as response:
                self.log_function(f"Downloading image: {image_filename}")
                response.raise_for_status()
                image_data = await response.read()
                with open(image_path, 'wb') as image_file:
                    image_file.write(image_data)
                self.log_function(f"Image saved: {image_path}")

                # Сохраняем информацию об изображении в CSV, включая URL
                self.write_to_csv(keyword, image_filename, image_url, image_tags, image_type)
                self.log_function(f"Image information saved to CSV: {self.csv_file}")
        except aiohttp.ClientError as e:
            self.log_function(f"Failed to download image {image_filename}: {e}")
        except Exception as e:
            self.log_function(f"Unexpected error during image download: {e}")



    async def download_random_image(self, session, filenames, output_folder):
        """
        Загружает изображение для указанного имени файла, представляющего текст.
        filenames - список имен файлов для использования в качестве названия картинки.
        """
        if not filenames:
            self.log_function("No filenames provided, skipping image download.")
            return

        for filename in filenames:
            self.log_function(f"Trying to download images for filename: {filename}")
            
            # Используем имя файла как ключевое слово для изображения
            success = await self.download_images_for_keyword(session, filename, output_folder)
            
            if success:
                self.log_function(f"Successfully downloaded an image for filename: {filename}")
                return
        self.log_function("All images for all filenames are already downloaded or no suitable images found.")
