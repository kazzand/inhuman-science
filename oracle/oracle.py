from __future__ import annotations

import json
import logging
import re

import requests

import config
from llm.client import oracle_score, fact_check
from sources.base import ContentItem
from storage.state import save_oracle_decision

logger = logging.getLogger(__name__)

_SCORE_PROMPT = """\
You are an expert AI/ML content curator. Evaluate the following content for \
publication on a popular science channel about AI and machine learning.

Score from 1 to 10 based on:
- Novelty (is this a genuinely new idea or just incremental?)
- Practical impact (does this change how people build or use AI?)
- Author/org reputation (is this from a top lab or well-known researcher?)
- Community engagement (likes/upvotes if available)
- Accessibility (can a technical audience understand and appreciate this?)

Content type: {content_type}
Source: {source}
Title: {title}
Likes/engagement: {likes}
Authors/orgs: {authors}

Summary:
{summary}

Respond with ONLY valid JSON:
{{"score": <1-10>, "reason": "<1-2 sentence justification>", "publish": <true/false>}}

Use threshold: publish=true if score >= {threshold}.
"""

_FACT_CHECK_PROMPT = """\
You are a fact-checker for AI/ML news. Verify the following claim or announcement.

Source: {source}
Title: {title}
Content:
{content}

Additional context from the web:
{web_context}

Check:
1. Is this announcement real and from a legitimate source?
2. Are the claimed results or features accurate based on available information?
3. Is this not a duplicate or rehash of old news?

Respond with ONLY valid JSON:
{{"verified": <true/false>, "confidence": <0.0-1.0>, "issues": "<any concerns or empty string>"}}
"""


def evaluate_content(item: ContentItem) -> tuple[float, bool, str]:
    """Score content for interestingness. Returns (score, should_publish, reason)."""
    authors_str = ", ".join(item.authors) if item.authors else ""
    if item.organizations:
        authors_str += " (" + ", ".join(item.organizations) + ")"

    prompt = _SCORE_PROMPT.format(
        content_type=item.source_type,
        source=item.source_name,
        title=item.title,
        likes=item.likes if item.likes else "N/A",
        authors=authors_str or "Unknown",
        summary=item.summary[:2000] or item.title,
        threshold=config.ORACLE_MIN_SCORE,
    )

    try:
        raw = oracle_score(prompt)
        result = _parse_json(raw)
        if result is None:
            return 5.0, False, "Failed to parse oracle response"

        score = float(result.get("score", 5))
        publish = bool(result.get("publish", False))
        reason = result.get("reason", "")

        save_oracle_decision(
            item.content_id,
            item.source_type,
            score,
            "publish" if publish else "skip",
            reason,
        )

        logger.info(
            "Oracle: %s [%s] score=%.1f publish=%s reason=%s",
            item.title[:60], item.source_name, score, publish, reason,
        )
        return score, publish, reason

    except Exception:
        logger.exception("Oracle evaluation failed for %s", item.content_id)
        return 5.0, False, "Oracle error"


def verify_content(item: ContentItem) -> tuple[bool, float, str]:
    """Fact-check a blog post or tweet. Returns (verified, confidence, issues)."""
    web_context = _fetch_web_context(item.url) if item.url else ""

    prompt = _FACT_CHECK_PROMPT.format(
        source=item.source_name,
        title=item.title,
        content=item.summary[:3000],
        web_context=web_context[:5000],
    )

    try:
        raw = fact_check(prompt)
        result = _parse_json(raw)
        if result is None:
            return True, 0.5, "Could not parse fact-check response"

        verified = bool(result.get("verified", True))
        confidence = float(result.get("confidence", 0.5))
        issues = result.get("issues", "")

        logger.info(
            "Fact-check: %s verified=%s confidence=%.2f issues=%s",
            item.title[:60], verified, confidence, issues,
        )
        return verified, confidence, issues

    except Exception:
        logger.exception("Fact-check failed for %s", item.content_id)
        return True, 0.3, "Fact-check error"


def _fetch_web_context(url: str) -> str:
    """Fetch page content for fact-checking context."""
    try:
        resp = requests.get(
            url, timeout=15,
            headers={"User-Agent": "InhumanScience/1.0"},
        )
        resp.raise_for_status()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text[:5000]
    except Exception:
        logger.debug("Could not fetch web context from %s", url)
        return ""


def _parse_json(raw: str) -> dict | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None
