import os
import sys
import aiohttp
import asyncio
import sqlite3
import logging
from aiohttp import BasicAuth
from pathlib import Path

def resource_path(relative_path):
    """Возвращает правильный путь к ресурсу, поддерживая как исполняемые файлы, так и обычные скрипты"""
    if getattr(sys, 'frozen', False):  # Если приложение скомпилировано
        base_path = Path(sys._MEIPASS)
    else:  # Если это обычный скрипт
        base_path = Path(__file__).parent
    return base_path / relative_path

class WordPressPoster:
    def __init__(self, base_folder, credentials_file, db_file, batch_size=5, pause_between_batches=10, logger=None):
        self.base_folder = resource_path(base_folder)
        self.credentials_file = resource_path(credentials_file)
        self.db_file = resource_path(db_file)
        self.batch_size = batch_size
        self.pause_between_batches = pause_between_batches
        self.sites_credentials = self.load_site_credentials()
        self._is_running = True
        self.create_database()
        self.logger = logger or logging.getLogger(__name__)  # Использование переданного логгера или создание нового

        # Счетчики для логов
        self.published_count = 0
        self.skipped_count = 0
        self.total_articles = 0

    def log(self, message, level=logging.INFO):
        """Логгирование с учетом уровней"""
        if self.logger:
            if level == logging.ERROR:
                self.logger.error(message)
            elif level == logging.WARNING:
                self.logger.warning(message)
            else:
                self.logger.info(message)

    def stop(self):
        """Метод для остановки работы"""
        self._is_running = False

    def create_database(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS posts (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            site TEXT,
                            article TEXT,
                            posted INTEGER
                        )''')
        conn.commit()
        conn.close()

    def load_site_credentials(self):
        sites = {}
        with open(self.credentials_file, "r", encoding="utf-8") as file:
            for line in file:
                site, login, password = line.strip().split("|")
                sites[site] = {"login": login, "password": password}
        return sites

    def is_posted(self, site, article):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT posted FROM posts WHERE site=? AND article=?", (site, article))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def mark_as_posted(self, site, article):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO posts (site, article, posted) VALUES (?, ?, 1)", (site, article))
        conn.commit()
        conn.close()

    async def upload_image(self, session, site, username, password, image_path):
        wp_media_url = f"https://{site}/wp-json/wp/v2/media"
        headers = {'Content-Disposition': f'attachment; filename={os.path.basename(image_path)}'}
        try:
            with open(image_path, 'rb') as image_file:
                data = image_file.read()
                
            async with session.post(wp_media_url, headers=headers, data=data, 
                                    auth=BasicAuth(username, password), 
                                    params={'media_type': 'image'}) as response:
                if response.status == 201:
                    json_response = await response.json()
                    self.log(f"Изображение успешно загружено на {site}: {json_response['id']}", logging.INFO)
                    return json_response['id']
                else:
                    error_message = await response.text()
                    self.log(f"Ошибка загрузки изображения на {site}: {response.status}, {error_message}", logging.ERROR)
                    return None
        except Exception as e:
            self.log(f"Ошибка при загрузке изображения на {site}: {str(e)}", logging.ERROR)
            return None

    async def publish_post(self, session, site, username, password, title, content, image_path=None):
        if not self._is_running:
            return

        wp_site_url = f"https://{site}/wp-json/wp/v2/posts"
        post_data = {"title": title, "content": content, "status": "publish"}

        if image_path:
            image_id = await self.upload_image(session, site, username, password, image_path)
            if image_id:
                post_data["featured_media"] = image_id

        try:
            async with session.post(wp_site_url, json=post_data, auth=BasicAuth(username, password)) as response:
                if response.status == 201:
                    self.log(f"Пост '{title}' успешно опубликован на {site}", logging.INFO)
                    self.published_count += 1
                    return True
                else:
                    error_message = await response.text()
                    self.log(f"Ошибка публикации '{title}' на {site}: {response.status}, {error_message}", logging.ERROR)
                    return False
        except Exception as e:
            self.log(f"Ошибка запроса на {site}: {str(e)}", logging.ERROR)
            return False

    async def process_article(self, session, site, credentials, article):
        if not self._is_running:
            return

        article_path = os.path.join(self.base_folder, site, article)
        
        if self.is_posted(site, article):
            self.log(f"Статья '{article}' уже была опубликована, пропуск", logging.INFO)
            self.skipped_count += 1
            return

        self.log(f"Найдена новая статья: {article}", logging.INFO)
        
        txt_file = None
        image_file = None
        
        for file in os.listdir(article_path):
            if file.endswith(".txt"):
                txt_file = os.path.join(article_path, file)
            elif file.lower().startswith("main_img") and file.lower().endswith((".jpg", ".png")):
                image_file = os.path.join(article_path, file)
        
        if txt_file:
            with open(txt_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                post_title = lines[0].strip()
                post_content = ''.join(lines[1:]).strip()

            success = await self.publish_post(session, site, credentials['login'], credentials['password'], post_title, post_content, image_file)
            
            if success:
                self.mark_as_posted(site, article)
        else:
            self.log(f"Текстовый файл для статьи {article} не найден", logging.ERROR)

    async def process_batch(self, session, site, credentials, articles):
        if not self._is_running:
            return

        tasks = []
        for article in articles:
            self.log(f"Начата обработка статьи: {article}", logging.INFO)
            task = asyncio.create_task(self.process_article(session, site, credentials, article))
            tasks.append(task)
        
        await asyncio.gather(*tasks)

    async def process_sites_with_batches(self):
        async with aiohttp.ClientSession() as session:
            for site, credentials in self.sites_credentials.items():
                if not self._is_running:
                    break
                
                site_path = os.path.join(self.base_folder, site)
                
                if os.path.isdir(site_path):
                    self.log(f"Обработка сайта: {site}", logging.INFO)
                    
                    all_articles = [article for article in os.listdir(site_path) if os.path.isdir(os.path.join(site_path, article))]
                    total_articles = len(all_articles)

                    if total_articles == 0:
                        self.log(f"На сайте {site} не найдено статей для обработки.", logging.INFO)
                        continue
                    
                    self.log(f"Найдено {total_articles} статей на {site}", logging.INFO)
                    self.total_articles = total_articles

                    for i in range(0, total_articles, self.batch_size):
                        if not self._is_running:
                            break
                        
                        batch_articles = all_articles[i:i + self.batch_size]
                        self.log(f"Обрабатывается батч {i // self.batch_size + 1}: {len(batch_articles)} статей", logging.INFO)
                        
                        await self.process_batch(session, site, credentials, batch_articles)
                        
                        if i + self.batch_size < total_articles:
                            self.log(f"Пауза перед следующим батчем на {self.pause_between_batches} секунд", logging.INFO)
                            await asyncio.sleep(self.pause_between_batches)

            self.log(f"Обработка завершена. Всего статей: {self.total_articles}, опубликовано: {self.published_count}, пропущено: {self.skipped_count}", logging.INFO)
