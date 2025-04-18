import requests
import json
import os

from utils.text_extraction_utils import get_clean_text
from utils.parsing_utils import get_links_of_todays_papers, update_top_links, pick_top, load_pdf
from utils.service_utils import send_error_msg
from utils.openai_utils import generate_image, generate_post, send_post

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import time


first_paper, second_paper = None, None
first_paper_link, second_paper_link = None, None


def prepare_papers():
    global first_paper, second_paper
    global first_paper_link, second_paper_link 
    try:
        links, likes = get_links_of_todays_papers()
        if likes[0] > 10 and likes[1] > 10:
            first_paper = links[0]
            second_paper = links[1]
            links = links[2:]
            likes = likes[2:]
            _ = update_top_links(links, likes, return_n_tops=0)
            #TBD
        elif likes[0] > 10 and likes[1] < 10:
            first_paper = links[0]
            links = links[1:]
            likes = likes[1:]
            n_tops = update_top_links(links, likes, return_n_tops=1)
            if n_tops:
                second_paper = n_tops[0]['link']
            else:
                second_paper = pick_top()
        else:
            n_tops = update_top_links(links, likes, return_n_tops=2)
            if len(n_tops) == 2:
                first_paper = n_tops[0]['link']
                second_paper = n_tops[1]['link']
            elif len(n_tops) == 1:
                first_paper = n_tops[0]['link']
                second_paper = pick_top()
            else:
                first_paper = pick_top()
                second_paper = pick_top()
    except Exception as e:
        send_error_msg(f"Failed to prepare papers: {e}")
    #block of code to load pdf
    first_paper_link = load_pdf(first_paper, "first_paper.pdf")
    second_paper_link = load_pdf(second_paper, "second_paper.pdf")

def build_n_send_post(path_to_paper, link_to_paper):
    global first_paper, second_paper
    global first_paper_link, second_paper_link 
    try:
        text_of_paper = get_clean_text(path_to_paper)
    except Exception as e:
        send_error_msg(f"Failed to parse pdf: {e}")

    try:
        post = generate_post(text_of_paper)
    except Exception as e:
        send_error_msg(f"Failed to generate text of post: {e}")

    try:
        image_url = generate_image(post)
    except Exception as e:
        send_error_msg(f"Failed to generate image: {e}")

    try:
        send_post(image_url, post, link_to_paper)
    except Exception as e:
        send_error_msg(f"Failed to send a post: {e}")

def send_ten_papers():
    links, likes = get_links_of_todays_papers()
    for i, (link, like) in enumerate(zip(links[:10], likes[:10])):
        paper_link = load_pdf(link, f"paper_{i}.pdf")
        build_n_send_post(f"paper_{i}.pdf", paper_link)

if __name__ == "__main__":
    # Define the functions to be triggered
    def prepare_n_send_first_paper():
        prepare_papers()
        print(first_paper_link)
        build_n_send_post("first_paper.pdf", first_paper_link)

    def send_second_paper():
        print(second_paper_link)
        build_n_send_post("second_paper.pdf", second_paper_link)

    # Set the timezone
    timezone = pytz.timezone("Asia/Dubai")

    # Initialize the scheduler
    scheduler = BackgroundScheduler()

    # Schedule my_func1 at 12:00 CET daily
    scheduler.add_job(prepare_n_send_first_paper, CronTrigger(hour=12, minute=0, timezone=timezone))

    # Schedule my_func2 at 16:00 CET daily
    scheduler.add_job(send_second_paper, CronTrigger(hour=16, minute=0, timezone=timezone))

    scheduler.add_job(send_ten_papers, CronTrigger(hour=20, minute=30, timezone=timezone))

    # Start the scheduler
    scheduler.start()

    print("Scheduler is running... Press Ctrl+C to exit.")

    # Keep the script running
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("Scheduler stopped.")

            

        