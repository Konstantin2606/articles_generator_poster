import requests
from youtube_transcript_api import YouTubeTranscriptApi
from googleapiclient.discovery import build

# Инициализация API-клиента YouTube
def get_youtube_service(api_key):
    return build("youtube", "v3", developerKey=api_key)

# Поиск видео по ключевым словам
def search_youtube_video(api_key, query, max_results=1):
    youtube = get_youtube_service(api_key)
    search_response = youtube.search().list(
        q=query,
        part="id,snippet",
        type="video",
        maxResults=max_results
    ).execute()
    
    video_ids = [item["id"]["videoId"] for item in search_response["items"]]
    return video_ids

# Получение субтитров для видео с возможностью выбора языка
def get_video_transcript(video_id, language='en'):
    try:
        # Пробуем получить субтитры на указанном языке, по умолчанию — английский
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[language])
        transcript_text = " ".join([item['text'] for item in transcript])
        return transcript_text
    except Exception as e:
        print(f"Ошибка при получении субтитров: {e}")
        return None

# Основная функция
def get_transcript_by_keyword(api_key, query, language='en'):
    video_ids = search_youtube_video(api_key, query)
    if video_ids:
        video_id = video_ids[0]  # Берем первый результат
        transcript = get_video_transcript(video_id, language)
        if transcript:
            return transcript
        else:
            print("Субтитры недоступны.")
    else:
        print("Видео не найдено.")

# Пример использования
api_key = "api-youtube"
query = "business, sport"  # Укажите ключевое слово для поиска
language = 'en'  # Укажите язык субтитров, например, 'ru' для русского или оставьте 'en' по умолчанию
transcript = get_transcript_by_keyword(api_key, query, language)
if transcript:
    print("Субтитры видео:")
    print(transcript)

