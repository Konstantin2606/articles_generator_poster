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
        # Удаляем только не типичные символы, оставляем пробелы и переносы строк
        cleaned_text = re.sub(r'[^a-zA-Zа-яА-Я0-9\s.,!?\'"()\-–:;]', '', text)
        return cleaned_text

    def sanitize_filename(self, filename, max_length=50):
        """Удаление недопустимых символов и сокращение длины имени файла"""
        sanitized = re.sub(r'[\/:*?"<>|]', '', filename)  # Убираем недопустимые символы
        sanitized = sanitized.replace('\n', ' ').strip()  # Убираем переносы строк и лишние пробелы
        return sanitized[:max_length].strip()  # Ограничиваем длину до max_length символов

    def remove_content_after_trigger(self, text, trigger="---"):
        """Удаляет текст после строки с триггером"""
        trigger_index = text.find(trigger)
        if trigger_index != -1:
            self.log(f"Trigger '{trigger}' found. Removing content after it.")
            return text[:trigger_index].strip()  # Удаляем все после триггера и возвращаем текст до него
        return text


    async def generate_article_single_request(self, image_downloader):
        """Генерация статьи одним запросом для каждого набора ключевых слов и скачивание изображения"""
        try:
            self.set_GPT()
            self.log(f'Using model: {self.model_name}')

            prompt = self.read_prompt()
            keywords_data = self.read_keywords(self.data_folder)

            # Рассчитываем минимальный объем текста, с которым будем работать (60% от min_chars)
            min_required_chars = int(self.min_chars * 0.6)

            async with aiohttp.ClientSession() as session:
                for site, keywords_sets in keywords_data.items():
                    for keywords in keywords_sets:
                        self.log(f"Generating article for site '{site}' with keywords: {keywords}")

                        first_keywords = ' '.join(keywords[:3])
                        sanitized_keywords = self.sanitize_filename(first_keywords, max_length=30)

                        site_folder = os.path.join(self.output_folder, site)
                        if not os.path.exists(site_folder):
                            os.makedirs(site_folder)

                        keyword_string = ', '.join(keywords)
                        prompt_with_keywords = f"{prompt}\nInclude the following keywords: {keyword_string}\nGenerate content according to the following parameters."

                        # Начальные параметры токенов для генерации
                        approx_tokens = int(self.min_chars / 5)
                        max_tokens = min(approx_tokens, 4096)

                        article_generated = False
                        generation_attempts = 0

                        # Пока не сгенерируем текст достаточного объема, продолжаем перегенерацию
                        while not article_generated:
                            generation_attempts += 1
                            response = self.client.chat.completions.create(
                                model=self.model_name,
                                messages=[{"role": "system", "content": f"You are an expert in generating SEO-optimized articles in {self.language}."},
                                        {"role": "user", "content": prompt_with_keywords}],
                                max_tokens=max_tokens
                            )

                            result = response.choices[0].message.content

                            # Логируем количество символов до очистки текста
                            self.log(f"Generated article length before cleaning: {len(result)} characters on attempt {generation_attempts}.")

                            # Возвращаем очистку текста
                            cleaned_article = self.clean_text(result)

                            # Логируем количество символов после очистки текста
                            self.log(f"Generated article length after cleaning: {len(cleaned_article)} characters on attempt {generation_attempts}.")

                            # Удаление текста после триггера "---"
                            trigger = "---"
                            if trigger in cleaned_article:
                                cleaned_article = cleaned_article.split(trigger)[0].strip()
                                self.log(f"Text truncated after trigger '{trigger}'.")

                            # Проверяем объем текста
                            if len(cleaned_article) >= min_required_chars:
                                article_generated = True  # Достаточный объем текста
                            else:
                                # Увеличиваем количество запрашиваемых токенов для следующего запроса
                                self.log(f"Generated text is too short (only {len(cleaned_article)} chars), retrying with more tokens...")
                                max_tokens += int(self.min_chars / 10)  # Увеличиваем на 10% от min_chars
                                if max_tokens > 8192:  # Ограничим максимальное количество токенов для модели
                                    self.log("Exceeded maximum token limit for generation, stopping...")
                                    break

                        if article_generated:
                            # Сохраняем весь текст после очистки, без обрезки
                            formatted_article = cleaned_article

                            headline_folder = os.path.join(site_folder, sanitized_keywords)
                            if not os.path.exists(headline_folder):
                                os.makedirs(headline_folder)

                            output_file = os.path.join(headline_folder, "article.txt")

                            # Логируем количество символов в окончательном тексте перед сохранением
                            self.log(f"Final article length before saving: {len(formatted_article)} characters.")

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



    async def download_random_image(self, session, keywords, output_folder):
        """Пытается загрузить изображение для каждого ключевого слова, пока не найдет новое изображение"""
        if not keywords:
            self.log_function("No keywords provided, skipping image download.")
            return
        
        # Пробегаем по каждому ключевому слову
        for keyword in keywords:
            self.log_function(f"Trying to download images for keyword: {keyword}")
            
            # Пытаемся загрузить изображение для ключевого слова
            success = await self.download_images_for_keyword(session, keyword, output_folder)
            
            if success:
                self.log_function(f"Successfully downloaded an image for keyword: {keyword}")
                return  # Успешно скачали изображение, выходим из функции

        # Если для всех ключевых слов изображения уже загружены или произошли ошибки
        self.log_function("All images for all keywords are already downloaded or no suitable images found.")

