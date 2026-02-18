from __future__ import annotations

import logging
import re

import requests
from bs4 import BeautifulSoup

import config
from sources.base import ContentItem

logger = logging.getLogger(__name__)


def fetch_trending_papers(max_papers: int = 20) -> list[ContentItem]:
    """Scrape AlphaRxiv Hot + Likes pages and return deduplicated papers."""
    seen_ids: set[str] = set()
    items: list[ContentItem] = []

    for url in (config.ALPHAXIV_HOT_URL, config.ALPHAXIV_LIKES_URL):
        try:
            papers = _parse_page(url)
            for p in papers:
                if p.content_id not in seen_ids:
                    seen_ids.add(p.content_id)
                    items.append(p)
        except Exception:
            logger.exception("Failed to parse AlphaRxiv page %s", url)

    items.sort(key=lambda p: p.likes, reverse=True)
    return items[:max_papers]


def _parse_page(url: str) -> list[ContentItem]:
    resp = requests.get(url, timeout=30, headers={"User-Agent": "InhumanScience/1.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    items: list[ContentItem] = []

    for link_tag in soup.find_all("a", href=re.compile(r"/abs/")):
        href = link_tag.get("href", "")
        paper_id = href.replace("/abs/", "").strip("/")
        if not paper_id:
            continue

        title = ""
        title_el = link_tag.find(["h2", "h3", "span", "p"])
        if title_el:
            title = title_el.get_text(strip=True)
        if not title:
            title = link_tag.get_text(strip=True)[:200]

        card = link_tag.find_parent(["div", "article", "li"])

        likes = 0
        if card:
            likes_el = card.find(string=re.compile(r"^\d+$"))
            if likes_el:
                try:
                    likes = int(likes_el.strip())
                except ValueError:
                    pass

        summary = ""
        if card:
            p_tags = card.find_all("p")
            for p in p_tags:
                text = p.get_text(strip=True)
                if len(text) > 60:
                    summary = text
                    break

        categories: list[str] = []
        orgs: list[str] = []
        if card:
            for cat_link in card.find_all("a", href=re.compile(r"\?(?:categories|subcategories|customCategories)=")):
                categories.append(cat_link.get_text(strip=True).lstrip("#"))
            for org_link in card.find_all("a", href=re.compile(r"\?organizations=")):
                orgs.append(org_link.get_text(strip=True))

        authors: list[str] = []
        if card:
            for author_el in card.find_all("a", href=re.compile(r"\?authors=")):
                authors.append(author_el.get_text(strip=True))

        pdf_url = f"{config.ARXIV_PDF_BASE}{paper_id}"

        items.append(
            ContentItem(
                content_id=paper_id,
                source_type="paper",
                source_name="alphaxiv",
                title=title,
                summary=summary,
                url=f"https://arxiv.org/abs/{paper_id}",
                likes=likes,
                authors=authors,
                categories=categories,
                organizations=orgs,
                pdf_url=pdf_url,
            )
        )

    return items
