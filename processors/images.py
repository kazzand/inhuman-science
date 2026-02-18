from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np
from PIL import Image

import config
from llm.client import chat_with_images

logger = logging.getLogger(__name__)

_PAGE_SELECT_PROMPT = """\
I'm showing you pages from a scientific paper (image 0 = page 0, image 1 = page 1, ...).

Pick the ONE page that contains the best visual FIGURE for a social media post \
about this paper. The figure should be a diagram, architecture overview, method \
pipeline, flowchart, chart, or visual illustration that explains the paper's core idea.

Rules:
- ONLY pick a page that has a prominent VISUAL element (not just text/equations).
- Prefer pages where the figure takes up a large portion of the page.
- Prefer pages 1-4 — they usually have the main method overview figure.
- If page 0 (title page) has a nice overview figure, that's fine too.

Respond ONLY with JSON: {"page_index": <0-based>, "reason": "<brief why>"}
If NO page has a good visual figure: {"page_index": -1, "reason": "no figure found"}
"""

PREVIEW_DPI = 120
CROP_DPI = 200
MAX_PAGES = 8

_FIG_CAPTION_RE = re.compile(
    r"^(Figure|Fig\.?)\s*\d+", re.IGNORECASE
)


def extract_best_figure(pdf_path: Path) -> Path | None:
    os.makedirs(config.IMG_DIR, exist_ok=True)

    page_idx = _pick_best_page(pdf_path)
    if page_idx < 0:
        page_idx = 1

    return _extract_figure_region(pdf_path, page_idx)


def _pick_best_page(pdf_path: Path) -> int:
    doc = fitz.open(str(pdf_path))
    n = min(len(doc), MAX_PAGES)
    temp_paths: list[Path] = []

    for i in range(n):
        pix = doc[i].get_pixmap(dpi=PREVIEW_DPI)
        p = Path(config.IMG_DIR) / f"_prev_{pdf_path.stem}_{i}.png"
        pix.save(str(p))
        temp_paths.append(p)
    doc.close()

    try:
        raw = chat_with_images(
            _PAGE_SELECT_PROMPT, temp_paths, temperature=0.1, max_tokens=128,
        )
        data = _parse_json(raw)
        if data:
            idx = int(data.get("page_index", -1))
            if 0 <= idx < n:
                logger.info("Page select: page %d for %s", idx, pdf_path.name)
                return idx
    except Exception:
        logger.exception("Page selection failed for %s", pdf_path.name)
    finally:
        for p in temp_paths:
            _safe_remove(p)

    return -1


def _extract_figure_region(pdf_path: Path, page_idx: int) -> Path | None:
    """Extract just the figure from a page using text block analysis."""
    doc = fitz.open(str(pdf_path))
    if page_idx >= len(doc):
        page_idx = min(1, len(doc) - 1)

    page = doc[page_idx]
    page_rect = page.rect

    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

    text_blocks = []
    for b in blocks:
        if b["type"] == 0:  # text block
            text = ""
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    text += span.get("text", "")
            text = text.strip()
            if text:
                text_blocks.append({
                    "bbox": fitz.Rect(b["bbox"]),
                    "text": text,
                })

    fig_region = _find_figure_region(text_blocks, page_rect)

    if fig_region is None:
        fig_region = _find_largest_gap(text_blocks, page_rect)

    if fig_region is None:
        doc.close()
        return _fallback_render(pdf_path, page_idx)

    pad_pts = 5
    clip = fitz.Rect(
        max(page_rect.x0, fig_region.x0 - pad_pts),
        max(page_rect.y0, fig_region.y0 - pad_pts),
        min(page_rect.x1, fig_region.x1 + pad_pts),
        min(page_rect.y1, fig_region.y1 + pad_pts),
    )

    scale = CROP_DPI / 72
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, clip=clip)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()

    img = _trim_white_margins(img, margin=8)

    out_path = Path(config.IMG_DIR) / f"figure_{pdf_path.stem}.png"
    img.save(str(out_path), "PNG", optimize=True)
    logger.info("Figure extracted: %s (%dx%d)", out_path, img.width, img.height)
    return out_path


def _is_body_paragraph(block: dict, page_width: float) -> bool:
    """A body paragraph is wide text (>50% page width) with >80 chars."""
    bw = block["bbox"].width
    return bw > page_width * 0.5 and len(block["text"]) > 80


def _find_figure_region(
    text_blocks: list[dict], page_rect: fitz.Rect
) -> fitz.Rect | None:
    """Find figure region anchored by 'Figure N:' caption."""
    caption_blocks = []
    for i, b in enumerate(text_blocks):
        if _FIG_CAPTION_RE.match(b["text"]):
            caption_blocks.append((i, b))

    if not caption_blocks:
        return None

    pw = page_rect.width
    best_region = None
    best_area = 0

    for cap_idx, cap_block in caption_blocks:
        cap_end = cap_block["bbox"].y1
        for j in range(cap_idx + 1, len(text_blocks)):
            nb = text_blocks[j]
            if nb["bbox"].y0 - cap_end < 8 and not _FIG_CAPTION_RE.match(nb["text"]):
                cap_end = nb["bbox"].y1
            else:
                break

        fig_top = page_rect.y0
        for b in text_blocks:
            if b["bbox"].y1 <= cap_block["bbox"].y0 - 5:
                if _is_body_paragraph(b, pw):
                    fig_top = max(fig_top, b["bbox"].y1)

        region = fitz.Rect(page_rect.x0, fig_top, page_rect.x1, cap_end)
        area = region.width * region.height
        if area > best_area and region.height > 40:
            best_area = area
            best_region = region

    return best_region


def _find_largest_gap(
    text_blocks: list[dict], page_rect: fitz.Rect
) -> fitz.Rect | None:
    """Find the largest vertical gap between text blocks (likely a figure)."""
    if not text_blocks:
        return None

    sorted_blocks = sorted(text_blocks, key=lambda b: b["bbox"].y0)

    edges = [page_rect.y0]
    for b in sorted_blocks:
        edges.append(b["bbox"].y0)
        edges.append(b["bbox"].y1)
    edges.append(page_rect.y1)

    best_gap = None
    best_height = 50

    for i in range(1, len(edges), 2):
        gap_top = edges[i - 1] if i > 0 else page_rect.y0
        gap_bottom = edges[i]
        gap_top_actual = gap_top
        gap_bottom_actual = gap_bottom

        if i > 0:
            gap_top_actual = edges[i - 1]
        if i < len(edges):
            gap_bottom_actual = edges[i]

        h = gap_bottom_actual - gap_top_actual
        if h > best_height:
            best_height = h
            best_gap = fitz.Rect(page_rect.x0, gap_top_actual, page_rect.x1, gap_bottom_actual)

    sorted_y1 = sorted(b["bbox"].y1 for b in sorted_blocks)
    sorted_y0 = sorted(b["bbox"].y0 for b in sorted_blocks)

    for i in range(len(sorted_y1)):
        for j in range(len(sorted_y0)):
            if sorted_y0[j] > sorted_y1[i] + 30:
                gap_h = sorted_y0[j] - sorted_y1[i]
                if gap_h > best_height:
                    best_height = gap_h
                    best_gap = fitz.Rect(
                        page_rect.x0, sorted_y1[i],
                        page_rect.x1, sorted_y0[j],
                    )
                break

    return best_gap


def _fallback_render(pdf_path: Path, page_idx: int) -> Path | None:
    doc = fitz.open(str(pdf_path))
    if page_idx >= len(doc):
        page_idx = 0
    pix = doc[min(page_idx, len(doc) - 1)].get_pixmap(dpi=CROP_DPI)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()
    img = _trim_white_margins(img, margin=10)
    out_path = Path(config.IMG_DIR) / f"figure_{pdf_path.stem}.png"
    img.save(str(out_path), "PNG", optimize=True)
    return out_path


def _trim_white_margins(img: Image.Image, margin: int = 8) -> Image.Image:
    arr = np.array(img.convert("L"))
    non_white = arr < 248
    rows = non_white.any(axis=1)
    cols = non_white.any(axis=0)
    if not rows.any() or not cols.any():
        return img
    ri = rows.nonzero()[0]
    ci = cols.nonzero()[0]
    return img.crop((
        max(0, ci[0] - margin),
        max(0, ri[0] - margin),
        min(img.width, ci[-1] + margin),
        min(img.height, ri[-1] + margin),
    ))


def _parse_json(raw: str) -> dict | None:
    match = re.search(r"\{.*?\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def _safe_remove(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass
