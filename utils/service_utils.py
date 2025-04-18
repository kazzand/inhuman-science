import requests
import os

ERROR_CHAT_ID = os.getenv("ERROR_CHAT_ID")
TOKEN = os.getenv("TOKEN")

def send_error_msg(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": ERROR_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"  # Supports bold, italic, links, etc.
    }
    requests.post(url, data=data)