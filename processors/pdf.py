from __future__ import annotations

import logging
import os
import re
import textwrap
from pathlib import Path

import requests

import config

logger = logging.getLogger(__name__)


def ensure_dirs() -> None:
    os.makedirs(config.PDF_DIR, exist_ok=True)
    os.makedirs(config.IMG_DIR, exist_ok=True)


def download_pdf(paper_id: str, pdf_url: str) -> Path:
    """Download a PDF from arXiv and return the local path."""
    ensure_dirs()
    safe_name = re.sub(r"[^\w.-]", "_", paper_id)
    path = Path(config.PDF_DIR) / f"{safe_name}.pdf"

    if path.exists():
        logger.info("PDF already cached: %s", path)
        return path

    logger.info("Downloading PDF: %s", pdf_url)
    resp = requests.get(pdf_url, timeout=60, stream=True)
    resp.raise_for_status()

    with open(path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    logger.info("PDF saved: %s", path)
    return path


def extract_text(pdf_path: Path) -> str:
    """Extract clean text from a PDF (Introduction through References)."""
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    raw_parts: list[str] = []
    for page in doc:
        raw_parts.append(page.get_text())
    doc.close()

    raw_text = "\n".join(raw_parts)
    text = _cut_body(raw_text)
    text = _clean_text(text)
    return text


def _cut_body(raw: str) -> str:
    """Keep text between Introduction and References."""
    intro_markers = ["Introduction", "INTRODUCTION", "1 Introduction", "1. Introduction"]
    ref_markers = ["References", "REFERENCES", "Bibliography"]

    start = 0
    for marker in intro_markers:
        idx = raw.find(marker)
        if idx != -1:
            start = idx
            break

    end = len(raw)
    for marker in ref_markers:
        idx = raw.rfind(marker)
        if idx != -1 and idx > start:
            end = idx
            break

    return raw[start:end]


def _clean_text(text: str, width: int = 120) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\[[^\]]{0,30}\]", "", text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"/gid(?:\s*\d)+", "", text)

    paragraphs = re.split(r"\n\s*\n+", text)
    cleaned: list[str] = []
    for para in paragraphs:
        para = para.strip()
        if not para or len(para) < 20:
            continue
        lines = para.split("\n")
        merged: list[str] = []
        for line in lines:
            line = line.strip()
            if not merged:
                merged.append(line)
            elif re.search(r"[.!?;:]\s*$", merged[-1]):
                merged.append(line)
            else:
                merged[-1] += " " + line
        full = " ".join(merged)
        full = re.sub(r"\s+", " ", full).strip()
        wrapped = textwrap.fill(full, width=width)
        cleaned.append(wrapped)

    return "\n\n".join(cleaned)
