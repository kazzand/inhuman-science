from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import feedparser
import requests
from bs4 import BeautifulSoup

import config
from sources.base import ContentItem

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "InhumanScience/1.0"}


def fetch_blog_posts(max_age_days: int = 3) -> list[ContentItem]:
    """Fetch recent posts from all configured AI company blogs."""
    items: list[ContentItem] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    for source_name, feed_url in config.BLOG_FEEDS.items():
        try:
            posts = _parse_feed(source_name, feed_url, cutoff)
            items.extend(posts)
            logger.info("Fetched %d posts from %s", len(posts), source_name)
        except Exception:
            logger.exception("Failed to fetch blog feed %s", source_name)

    return items


def _parse_feed(
    source_name: str, feed_url: str, cutoff: datetime
) -> list[ContentItem]:
    feed = feedparser.parse(feed_url)
    items: list[ContentItem] = []

    for entry in feed.entries:
        published = _parse_date(entry)
        if published and published < cutoff:
            continue

        link = entry.get("link", "")
        title = entry.get("title", "")
        summary = entry.get("summary", "")

        if not summary:
            summary = entry.get("description", "")

        summary = BeautifulSoup(summary, "html.parser").get_text(strip=True)

        items.append(
            ContentItem(
                content_id=link,
                source_type="blog",
                source_name=source_name,
                title=title,
                summary=summary[:1000],
                url=link,
                published_at=published.isoformat() if published else "",
            )
        )

    return items


def fetch_full_blog_content(url: str) -> str:
    """Download and extract readable text from a blog post URL."""
    try:
        resp = requests.get(url, timeout=30, headers=_HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        article = soup.find("article") or soup.find("main") or soup.body
        if article is None:
            return ""
        text = article.get_text(separator="\n", strip=True)
        return text[:15000]
    except Exception:
        logger.exception("Failed to fetch blog content from %s", url)
        return ""


def _parse_date(entry: dict) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        tp = entry.get(field)
        if tp:
            try:
                from time import mktime
                return datetime.fromtimestamp(mktime(tp), tz=timezone.utc)
            except Exception:
                pass
    for field in ("published", "updated"):
        val = entry.get(field)
        if val:
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except Exception:
                pass
    return None
