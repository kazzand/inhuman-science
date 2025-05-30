import os
import requests

TOKEN = os.getenv("TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ERROR_CHAT_ID = os.getenv("ERROR_CHAT_ID")

def send_post(image_url, post_text, paper_link):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    data = {
        "chat_id": CHANNEL_ID,
        "photo": image_url,  # Указываем ссылку на изображение
        "caption": post_text + f'\n\n<a href="{paper_link}">Статья</a>',
        "parse_mode": "HTML",
        "disable_notification": True,
    }
    requests.post(url, data=data)


def send_error_msg(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": ERROR_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"  # Supports bold, italic, links, etc.
    }
    requests.post(url, data=data)


def send_post_in_chat(image_url, post_text, paper_link):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    data = {
        "chat_id": ERROR_CHAT_ID,
        "photo": image_url,  # Указываем ссылку на изображение
        "caption": post_text + f'\n\n<a href="{paper_link}">Статья</a>',
        "parse_mode": "HTML",
        "disable_notification": True,
    }
    requests.post(url, data=data)