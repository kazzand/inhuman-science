import requests
import json
import os
import datetime

from core.pdf_utils.text_extraction_utils import get_clean_text
from parsing_utils import get_links_of_todays_papers, load_pdf
from core.telegram_utils import send_post, send_post_in_chat, send_error_msg
from core.openai_utils import generate_image, generate_post
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
        top_links = links[:n]

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

def build_post(paper_dict):
    """
    Build and send the post for a single paper, given
    a dictionary with 'pdf_filename' and 'pdf_link'.
    """
    pdf_filename = paper_dict["pdf_filename"]
    link_to_paper = paper_dict["pdf_link"]

    # 1. Extract text from the paper PDF
    try:
        text_of_paper = get_clean_text(os.path.join("data", pdf_filename))
    except Exception as e:
        send_error_msg(f"Failed to parse pdf {pdf_filename}: {e}")
        return None, None, None

    # 2. Generate the post text
    try:
        post_text = generate_post(text_of_paper)
    except Exception as e:
        send_error_msg(f"Failed to generate text of post: {e}")
        return None, None, None

    # 3. Generate an image (optional)
    try:
        image_url = generate_image(post_text)
    except Exception as e:
        send_error_msg(f"Failed to generate image: {e}")
        image_url = None  # fallback if image generation fails

    return image_url, post_text, link_to_paper

def send_post_to_chat(image_url, post_text, link_to_paper):
    # 4. Send the final post
    try:
        send_post(image_url, post_text, link_to_paper)
    except Exception as e:
        send_error_msg(f"Failed to send a post: {e}")


def send_one_paper(paper_info):
    """
    Builds and sends a post for a single paper.
    """
    print(f"Processing paper: {paper_info.get('link', 'N/A')}")
    image_url, post_text, link_to_paper = build_post(paper_info)
    if post_text and link_to_paper:  # Ensure we have content to send
        send_post_to_chat(image_url, post_text, link_to_paper)
        print(f"Successfully sent post for paper {paper_info.get('link', 'N/A')}")
    else:
        print(f"Skipping sending post for paper {paper_info.get('link', 'N/A')} due to missing content or link.")


def prepare_all_and_schedule_sending(scheduler, base_timezone, papers_to_prepare_at_once=5, send_interval_hours=3):
    """
    Prepares a batch of papers and schedules each one to be sent at intervals.
    The first paper is scheduled shortly after preparation, and subsequent
    papers are staggered by send_interval_hours.
    """
    print(f"Attempting to prepare {papers_to_prepare_at_once} papers.")
    prepared_papers = prepare_papers(papers_to_prepare_at_once)
    print(f"Prepared {len(prepared_papers)} papers. Scheduling them for sending.")

    if not prepared_papers:
        print("No papers prepared. Nothing to schedule for this run.")
        return

    current_time_in_zone = datetime.datetime.now(base_timezone)
    initial_delay_seconds = 60  # Start sending the first paper after 1 minute

    for i, paper_info in enumerate(prepared_papers):
        # Calculate the run time for this specific paper relative to the preparation time
        run_time = current_time_in_zone + datetime.timedelta(seconds=(initial_delay_seconds + i * send_interval_hours * 3600))
        
        # Create a unique job ID
        pdf_filename_part = paper_info.get('pdf_filename', f'unknown_paper_{i}')
        job_id = f"send_paper_{pdf_filename_part}_{int(run_time.timestamp())}"

        print(f"Scheduling paper job '{job_id}' (Link: {paper_info.get('link', 'N/A')}) to be sent at {run_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        try:
            scheduler.add_job(
                send_one_paper,
                'date',
                run_date=run_time,
                args=[paper_info],
                id=job_id,
                replace_existing=True, # In case of overlap, though timestamp in ID should prevent most
                timezone=base_timezone # Ensure job is scheduled with the correct timezone context
            )
        except Exception as e:
            send_error_msg(f"Failed to schedule job {job_id} for paper {paper_info.get('link', 'N/A')}: {e}")


def prepare_and_send_all(n=3):
    """
    Prepare n papers and then send each one.
    """
    papers = prepare_papers(n)
    print(f"Found {len(papers)} papers to post.")
    if not papers:
        print("No papers available; will try again next run.")
        return None

    for paper_info in papers:
        print(f"Preparing post for paper {build_post(paper_info)}")
        image_url, post_text, link_to_paper = build_post(paper_info)
        send_post_to_chat(image_url, post_text, link_to_paper)    


if __name__ == "__main__":
    # Configuration for the new scheduled posting
    PAPERS_TO_FETCH_DAILY = 3  # Number of papers to fetch and schedule daily (N)
    SEND_INTERVAL_HOURS = 1    # Interval in hours between sending each paper (M)
    SCHEDULER_TIMEZONE_STR = "Asia/Dubai"  # Timezone for scheduling
    PREPARATION_HOUR = 10       # Hour of the day to run the paper preparation and scheduling (e.g., 8 AM)
    PREPARATION_MINUTE = 0     # Minute of the hour

    # prepare_and_send_all(3) # Keep this if you want to run it manually sometimes, or comment out

    # Setup for scheduled preparation and subsequent individual postings
    scheduler_timezone = pytz.timezone(SCHEDULER_TIMEZONE_STR)
    scheduler = BackgroundScheduler(timezone=scheduler_timezone)

    print(f"Scheduler initialized with timezone: {SCHEDULER_TIMEZONE_STR}")
    print(f"Daily paper preparation and scheduling will run at {PREPARATION_HOUR:02d}:{PREPARATION_MINUTE:02d} {SCHEDULER_TIMEZONE_STR}.")
    print(f"It will attempt to fetch {PAPERS_TO_FETCH_DAILY} papers.")
    print(f"Posts for these papers will be scheduled every {SEND_INTERVAL_HOURS} hours after preparation.")

    # Schedule the main preparation task
    # This job runs once per day (or as configured) to gather papers and set up their individual sending times.
    scheduler.add_job(
        prepare_all_and_schedule_sending,
        CronTrigger(hour=PREPARATION_HOUR, minute=PREPARATION_MINUTE, timezone=scheduler_timezone),
        args=[scheduler, scheduler_timezone, PAPERS_TO_FETCH_DAILY, SEND_INTERVAL_HOURS],
        id="daily_paper_preparation_and_scheduling",
        replace_existing=True
    )

    scheduler.start()
    print("Scheduler is running... Press Ctrl+C to exit.")

    try:
        while True:
            time.sleep(2)  # Keep the main thread alive
    except (KeyboardInterrupt, SystemExit):
        print("Shutting down scheduler...")
        scheduler.shutdown()
        print("Scheduler stopped.")