from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ContentItem:
    """Universal container for any content source."""

    content_id: str
    source_type: Literal["paper", "blog", "tweet"]
    source_name: str  # e.g. "alphaxiv", "openai_blog", "twitter:sama"
    title: str
    summary: str = ""
    url: str = ""
    likes: int = 0
    authors: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    organizations: list[str] = field(default_factory=list)
    pdf_url: str = ""
    full_text: str = ""
    published_at: str = ""
