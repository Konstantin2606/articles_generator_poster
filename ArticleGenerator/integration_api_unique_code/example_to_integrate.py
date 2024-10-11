import requests
import json

API_URL = 'https://content-watch.ru/public/api/'

def check_text(api_key, text, test=0, ignore=''):
    """Отправляет запрос на проверку уникальности текста."""
    payload = {
        'key': api_key,
        'text': text,
        'test': test,
        'ignore': ignore
    }
    response = requests.post(API_URL, data=payload)
    return response.json()

def check_url(api_key, url):
    """Отправляет запрос на проверку уникальности страницы."""
    payload = {
        'action': 'CHECK_URL',
        'key': api_key,
        'url': url
    }
    response = requests.post(API_URL, data=payload)
    return response.json()

def get_balance(api_key):
    """Отправляет запрос на получение баланса аккаунта."""
    payload = {
        'action': 'GET_BALANCE',
        'key': api_key
    }
    response = requests.post(API_URL, data=payload)
    return response.json()

def parse_response(response):
    """Обрабатывает и выводит ответ от API."""
    if 'error' not in response:
        print('Ошибка запроса')
    elif response['error']:
        print(f"Возникла ошибка: {response['error']}")
    else:
        # Инициализация значений по умолчанию
        response = {**{'text': '', 'percent': '100.0', 'highlight': [], 'matches': []}, **response}
        print(f"Уникальность текста: {response['percent']}%")

        # Подсветка совпадений (эмуляция подсветки в CLI)
        if response['highlight']:
            highlighted_text = highlight_words(response['text'], response['highlight'])
            print("Текст с подсветкой совпадений:\n", highlighted_text)

        # Вывод совпадений
        if response['matches']:
            print("Совпадения:")
            for match in response['matches']:
                print(f"URL: {match['url']}, Процент совпадений: {match['percent']}%")

def highlight_words(text, highlight_array):
    """Эмулирует подсветку совпадений в тексте."""
    words = text.split(" ")
    for indices in highlight_array:
        if isinstance(indices, list) and len(indices) == 2:
            start, end = indices
            words[start] = f"<b>{words[start]}"
            words[end] = f"{words[end]}</b>"
        elif isinstance(indices, int):
            words[indices] = f"<b>{words[indices]}</b>"
    return " ".join(words)


# Пример использования функций:
api_key = "123456789012345"  # Укажите ваш API ключ
text_to_check = "текст на проверку"
url_to_check = "https://example.com"

# Проверка текста
print("Проверка текста:")
response = check_text(api_key, text_to_check)
parse_response(response)

# Проверка страницы
print("\nПроверка страницы:")
response = check_url(api_key, url_to_check)
parse_response(response)

# Запрос баланса
print("\nБаланс аккаунта:")
balance_response = get_balance(api_key)
print(f"Баланс: {balance_response.get('balance', 'Не удалось получить баланс')}")
