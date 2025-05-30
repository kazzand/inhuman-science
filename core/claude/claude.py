import os
import time
from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")

def text_query_claude(system_prompt, 
                      input_text, 
                      model="claude-v1"):
    
    client = Anthropic(api_key=CLAUDE_API_KEY)
    output = client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=512,
        messages=[
            {"role": "user", "content": system_prompt},
            {"role": "user", "content": input_text}
        ]
    )
    return output.content[0].text