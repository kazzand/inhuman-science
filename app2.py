import requests
import json
import os

from utils.text_extraction_utils import get_clean_text
from utils.parsing_utils import get_links_of_todays_papers, update_top_links, pick_top, load_pdf
from utils.service_utils import send_error_msg
from utils.openai_utils import generate_image, generate_post, send_post

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import pytz
import time


# Global list to store the selected papers and their PDF paths/links
SELECTED_PAPERS = []  # Each element could be a dict with fields like {"link": "...", "pdf_path": "...", "pdf_link": "..."}

def prepare_papers(n=2):
    """
    Fetch n papers (by logic of links & likes), load their PDFs,
    and store them in the global SELECTED_PAPERS list.
    """

    global SELECTED_PAPERS
    SELECTED_PAPERS = []  # Reset each time you prepare fresh papers

    try:
        links, likes = get_links_of_todays_papers()  # Suppose this returns (["/papers/XYZ", ...], [15, 12, 3, ...])

        # Filter out links with likes > 10 first
        top_links = []
        top_likes = []

        for link, like in zip(links, likes):
            if like > 10:
                top_links.append(link)
                top_likes.append(like)

        # If top_links has fewer than n, fill from pick_top() or pick_pop()
        # Adjust logic as needed:
        while len(top_links) < n:
            popped = pick_top()  # Suppose pick_pop() returns dict {"link": "/papers/...", "likes": X, "date": "..."}
            if not popped:
                # No more papers in your system, break out
                break
            top_links.append(popped["link"])

        # If you still have more than n in top_links, slice it
        top_links = top_links[:n]

        # Now load PDFs for these top_links
        for i, link in enumerate(top_links, start=1):
            pdf_filename = f"paper_{i}.pdf"
            pdf_link = load_pdf(link, pdf_filename)
            # Store info in SELECTED_PAPERS
            SELECTED_PAPERS.append({
                "link": link,
                "pdf_filename": pdf_filename,
                "pdf_link": pdf_link  # Possibly a local path or a direct URL
            })

    except Exception as e:
        send_error_msg(f"Failed to prepare {n} papers: {e}")

    return SELECTED_PAPERS
def build_n_send_post(paper_dict):
    """
    Build and send the post for a single paper, given
    a dictionary with 'pdf_filename' and 'pdf_link'.
    """
    pdf_filename = paper_dict["pdf_filename"]
    link_to_paper = paper_dict["pdf_link"]

    # 1. Extract text from the paper PDF
    try:
        text_of_paper = get_clean_text(pdf_filename)
    except Exception as e:
        send_error_msg(f"Failed to parse pdf {pdf_filename}: {e}")
        return

    # 2. Generate the post text
    try:
        post_text = generate_post(text_of_paper)
    except Exception as e:
        send_error_msg(f"Failed to generate text of post: {e}")
        return

    # 3. Generate an image (optional)
    try:
        image_url = generate_image(post_text)
    except Exception as e:
        send_error_msg(f"Failed to generate image: {e}")
        image_url = None  # fallback if image generation fails

    # 4. Send the final post
    try:
        send_post(image_url, post_text, link_to_paper)
    except Exception as e:
        send_error_msg(f"Failed to send a post: {e}")


def prepare_and_send_all(n=2):
    """
    Prepare n papers and then send each one.
    """
    papers = prepare_papers(n=n)
    print(f"Found {len(papers)} papers to post.")

    # If no papers, do nothing
    if not papers:
        print("No papers available; will try again next run.")
        return

    # Send each paper
    for paper_info in papers:
        build_n_send_post(paper_info)


if __name__ == "__main__":
    # Example: run every hour until no more papers
    timezone = pytz.timezone("Asia/Dubai")
    scheduler = BackgroundScheduler()

    # Using interval trigger (every hour)
    scheduler.add_job(
        lambda: prepare_and_send_all(n=5),  # or any integer n
        IntervalTrigger(hours=1, timezone=timezone)
    )

    scheduler.start()
    print("Scheduler is running... Press Ctrl+C to exit.")

    # Keep the script alive
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("Scheduler stopped.")