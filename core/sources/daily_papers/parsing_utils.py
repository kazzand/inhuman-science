import requests
import json
import os

from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from core.telegram_utils import send_error_msg


DATA_FILE = "top_links.json"
DATE_FORMAT = "%Y-%m-%d"


def get_links_of_todays_papers(min_likes=10):
    url = "https://huggingface.co/papers"

    # Send a GET request to the URL
    response = requests.get(url)

    soup = BeautifulSoup(response.content, "html.parser")

    # Find all divs with the specified class
    divs = soup.find_all("a", class_="shadow-alternate-sm peer relative block h-56 w-full cursor-pointer overflow-hidden rounded-xl bg-white md:h-64")
    likes = soup.find_all("div", class_="shadow-alternate flex h-14 w-12 gap-1 rounded-xl flex-none cursor-pointer select-none flex-col items-center justify-center self-start border-gray-300 bg-white dark:bg-gray-850")
    links, likes_v = [], []
    for div, like in zip(divs, likes):
        like_v = like.find("div", class_="leading-none").text.strip()
        if like_v.isdigit() and int(like_v) >= min_likes:
            links.append(div['href'])
            likes_v.append(int(like_v))
    return links, likes_v

def load_pdf(ending, output_file="arxiv_paper.pdf"):
    base_url = "https://arxiv.org/pdf/"
    if "papers" in ending:
        ending = ending.replace("/papers/", "")
    url = os.path.join(base_url, ending)

    try:
        response = requests.get(url)
        response.raise_for_status()

        with open(os.path.join("data", output_file), "wb") as file:
            file.write(response.content)

        return url
    except Exception as e:
        pass
        send_error_msg(f"Failed to download the PDF: {e}")