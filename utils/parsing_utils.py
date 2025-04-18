import requests
import json
import os

from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from .service_utils import send_error_msg


DATA_FILE = "top_links.json"
DATE_FORMAT = "%Y-%m-%d"


def get_links_of_todays_papers(min_likes=10):
    url = "https://huggingface.co/papers"

    # Send a GET request to the URL
    response = requests.get(url)

    soup = BeautifulSoup(response.content, "html.parser")

    # Find all divs with the specified class
    divs = soup.find_all("a", class_="shadow-alternate-sm peer relative block h-56 w-full cursor-pointer overflow-hidden rounded-xl border bg-white dark:border-gray-700 md:h-64")
    likes = soup.find_all("div", class_="shadow-alternate flex h-14 w-12 gap-1 rounded-xl flex-none cursor-pointer select-none flex-col items-center justify-center self-start border-gray-300 bg-white dark:bg-gray-850")
    links, likes_v = [], []
    for div, like in zip(divs, likes):
        like_v = like.find("div", class_="leading-none").text.strip()
        if like_v.isdigit() and int(like_v) >= min_likes:
            links.append(div['href'])
            likes_v.append(int(like_v))
    return links, likes_v


def update_top_links(links, likes, return_n_tops = 0):
    """
    Updates the stored dictionary with new links and likes, keeping only the top-10 recent entries.

    :param links: List of link URLs
    :param likes: List of corresponding like counts
    """
    # Load existing data if available
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []

    # Today's date
    today = datetime.today().strftime(DATE_FORMAT)

    # Add new data
    for link, like in zip(links, likes):
        data.append({"link": link, "likes": like, "date": today})

    # Remove old entries (more than a week old)
    week_ago = datetime.today() - timedelta(days=7)
    data = [entry for entry in data if datetime.strptime(entry["date"], DATE_FORMAT) >= week_ago]

    # Sort by likes (highest first) and keep top 10
    data = sorted(data, key=lambda x: x["likes"], reverse=True)[:10]
    
    n_tops = data[:return_n_tops]
    data = data[return_n_tops:]

    # Save updated data
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    return n_tops

def pick_top():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []
    if data:
        top_1 = data[0]
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data[1:], f, indent=4, ensure_ascii=False)
            
        return top_1
    else:
        send_error_msg("Couldn't pick a top")
        return None

def load_pdf(ending, output_file="arxiv_paper.pdf"):
    base_url = "https://arxiv.org/pdf/"
    if "papers" in ending:
        ending = ending.replace("/papers/", "")
    url = os.path.join(base_url, ending)

    try:
        # Send a GET request to the URL
        response = requests.get(url)
        response.raise_for_status()  # Check for HTTP request errors

        # Write the content to a local file
        with open(output_file, "wb") as file:
            file.write(response.content)

        send_error_msg(f"PDF {url} downloaded successfully and saved as '{output_file}'")
        return url
    except Exception as e:
        send_error_msg(f"Failed to download the PDF: {e}")