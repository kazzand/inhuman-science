from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

from openai import OpenAI

import config

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=config.OPENROUTER_API_KEY,
            base_url=config.OPENROUTER_BASE_URL,
        )
    return _client


def chat(
    messages: list[dict[str, Any]],
    model: str = config.LLMModels.POST_RU,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    client = _get_client()
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()


def chat_with_images(
    text_prompt: str,
    image_paths: list[str | Path],
    model: str = config.LLMModels.VISION,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> str:
    """Send text + multiple images to a vision model."""
    content: list[dict[str, Any]] = [{"type": "text", "text": text_prompt}]
    for img_path in image_paths:
        img_path = Path(img_path)
        suffix = img_path.suffix.lower().lstrip(".")
        media_type = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
            "gif": "image/gif",
        }.get(suffix, "image/png")
        b64 = base64.b64encode(img_path.read_bytes()).decode()
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{media_type};base64,{b64}"},
            }
        )

    messages = [{"role": "user", "content": content}]
    client = _get_client()
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()


def oracle_score(prompt: str) -> str:
    return chat(
        [{"role": "user", "content": prompt}],
        model=config.LLMModels.ORACLE,
        temperature=0.3,
        max_tokens=2048,
    )


def fact_check(prompt: str) -> str:
    return chat(
        [{"role": "user", "content": prompt}],
        model=config.LLMModels.FACT_CHECK,
        temperature=0.2,
        max_tokens=2048,
    )


def generate_post_ru(system_prompt: str, user_prompt: str) -> str:
    return chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=config.LLMModels.POST_RU,
        temperature=0.7,
        max_tokens=4096,
    )


def generate_post_en(system_prompt: str, user_prompt: str) -> str:
    return chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=config.LLMModels.POST_EN,
        temperature=0.7,
        max_tokens=2048,
    )
