from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import fitz

from packages.core.jstudy_core.documents.pdf_utility import validate_pdf


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_pdf_pages(pdf_path: Path) -> list[dict[str, Any]]:
    validate_pdf(pdf_path)
    pages: list[dict[str, Any]] = []
    with fitz.open(str(pdf_path)) as doc:
        for page_index, page in enumerate(doc, start=1):
            text = _normalize_text(page.get_text("text"))
            if text:
                pages.append({"page": page_index, "text": text})
    return pages
