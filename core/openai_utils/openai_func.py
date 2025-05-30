from openai import OpenAI
from core.telegram_utils import send_error_msg
from core.openai_utils.constants import OpenAIConstants
from core.claude import text_query_claude
from core.claude.constants import ClaudeConstants


import textwrap
import time
import os
import requests

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ERROR_CHAT_ID = os.getenv("ERROR_CHAT_ID")
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

client = OpenAI(api_key=OPENAI_API_KEY)

def text_query_llm(system_prompt, user_prompt, model="o1-preview", max_symbols = 800, max_retries=5):
    try:
        if model == "o1-preview":
            msg =[
                {"role": "user", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        else:
            msg=[  
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=msg,
        )
        output_obj = completion.choices[0].message.content.strip()
        return output_obj
    except Exception as e:
        send_error_msg(f"Error in text_query_llm: {e}")
        raise  # Re-raise the exception after the last attempt

def generate_post(text_of_paper):
    post_text = text_query_llm(
        OpenAIConstants.GENERATE_POST_SYSTEM_PROMPT,
        "Text of paper: " + text_of_paper
    )
    print(f"Length of post: {len(post_text)}")
    attempts = 0
    if len(post_text) > 995:
        while attempts < 3 and len(post_text) > 995:
            post_text = text_query_claude(
                ClaudeConstants.CUTTING_POST_SYSTEM_PROMPT,
                "Text of post: " + post_text
            )
            attempts += 1
        print(f"Length of post after cutting: {len(post_text)}")
    if not len(post_text) or len(post_text) > 995:
        send_error_msg(f"Unable to generate post or it's too long")
        return None
    else:
        return post_text

def generate_image(post):
    response = client.images.generate(
      model="dall-e-3",
      prompt=f"{post}",
      n=1,
      size="1792x1024"
    )
    return response.data[0].url