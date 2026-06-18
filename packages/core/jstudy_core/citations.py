from __future__ import annotations

import re
from typing import Any

from packages.retrieval.hybrid import Chunk

# PDF extraction often produces garbage characters from incorrect font encoding.
# These Unicode ranges are NOT legitimate content for English/Chinese engineering PDFs
# and indicate corrupted text extraction:
#   0x05C0-0x05FF  Hebrew
#   0x0600-0x06FF  Arabic
#   0x0700-0x074F  Syriac
#   0x0780-0x07BF  Thaana
#   0x0900-0x097F  Devanagari
#   0x0980-0x09FF  Bengali
#   0x0A00-0x0A7F  Gurmukhi
#   0x0A80-0x0AFF  Gujarati
#   0x0B00-0x0B7F  Odia
#   0x0B80-0x0BFF  Tamil
#   0x0C00-0x0C7F  Telugu
#   0x0C80-0x0CFF  Kannada
#   0x0D00-0x0D7F  Malayalam
#   0x0D80-0x0DFF  Sinhala
#   0x0E00-0x0E7F  Thai
#   0x0E80-0x0EFF  Lao
#   0x0F00-0x0FFF  Tibetan
#   0x1000-0x109F  Myanmar
#   0x10A0-0x10FF  Georgian
#   0x1200-0x137F  Ethiopic
#   0xE000-0xF8FF  Private Use Area (PDF ligature artifacts)
PDF_GARBAGE_RE = re.compile(
    r'[\u05C0-\u05FF'     # Hebrew
    r'\u0600-\u06FF'      # Arabic
    r'\u0700-\u074F'      # Syriac
    r'\u0780-\u07BF'      # Thaana
    r'\u0900-\u097F'      # Devanagari
    r'\u0980-\u09FF'      # Bengali
    r'\u0A00-\u0A7F'      # Gurmukhi
    r'\u0A80-\u0AFF'      # Gujarati
    r'\u0B00-\u0B7F'      # Odia
    r'\u0B80-\u0BFF'      # Tamil
    r'\u0C00-\u0C7F'      # Telugu
    r'\u0C80-\u0CFF'      # Kannada
    r'\u0D00-\u0D7F'      # Malayalam
    r'\u0D80-\u0DFF'      # Sinhala
    r'\u0E00-\u0E7F'      # Thai
    r'\u0E80-\u0EFF'      # Lao
    r'\u0F00-\u0FFF'      # Tibetan
    r'\u1000-\u109F'      # Myanmar
    r'\u10A0-\u10FF'      # Georgian
    r'\u1200-\u137F'      # Ethiopic
    r'\u1700-\u171F'      # Tagalog
    r'\u1720-\u173F'      # Hanunoo
    r'\u1740-\u175F'      # Buhid
    r'\u1760-\u177F'      # Tagbanwa
    r'\u1780-\u17FF'      # Khmer
    r'\u1800-\u18AF'      # Mongolian
    r'\uE000-\uF8FF]',    # Private Use Area (PDF ligature artifacts)
    re.UNICODE,
)

# Lines that are mostly PDF artifact noise (e.g., "++++ + + + + + + R Q r")
# More than 50% non-alphanumeric garbage -> strip the line
PDF_ARTIFACT_LINE_RE = re.compile(r'^[+\-\\*/=·•■□○●\s]{5,}$', re.MULTILINE)


def clean_quote(text: str, max_length: int = 500) -> str:
    """Strip PDF-extraction garbage characters from evidence quote text."""
    if not text:
        return ""
    cleaned = PDF_GARBAGE_RE.sub("", text)
    # Remove plus-sign-only artifact lines
    cleaned = PDF_ARTIFACT_LINE_RE.sub("", cleaned)
    # Collapse whitespace
    cleaned = re.sub(r'\s{3,}', ' ', cleaned)
    cleaned = cleaned.strip()
    if not cleaned:
        return "(non-text content)"
    return cleaned[:max_length]


def build_evidence_items(chunks: list[Chunk], source_file: str = "") -> list[dict[str, Any]]:
    evidence = []
    for idx, chunk in enumerate(chunks, start=1):
        src = chunk.source_file or source_file or "unknown.pdf"
        item = {
            "id": f"E{idx:03d}",
            "source_file": src,
            "page": chunk.page,
            "chunk_id": chunk.id,
            "score": round(chunk.score, 4),
            "excerpt": clean_quote(chunk.text, max_length=500),
        }
        if chunk.query_id:
            item["query_id"] = chunk.query_id
        if chunk.query_title:
            item["query_title"] = chunk.query_title
        if chunk.retrieval_method:
            item["retrieval_method"] = chunk.retrieval_method
        evidence.append(item)
    return evidence


def build_evidence_links(markdown: str, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence_by_id = {str(item.get("id")): item for item in evidence if item.get("id")}
    occurrence_counts: dict[str, int] = {}
    links: list[dict[str, Any]] = []

    for comment_index, match in enumerate(
        re.finditer(r"<!--\s*evidence:\s*([^>]+?)\s*-->", markdown, re.IGNORECASE),
        start=1,
    ):
        for ref_id in re.findall(r"\bE\d{3}\b", match.group(1)):
            item = evidence_by_id.get(ref_id)
            if item is None:
                continue
            occurrence_counts[ref_id] = occurrence_counts.get(ref_id, 0) + 1
            links.append(
                {
                    "ref_id": ref_id,
                    "occurrence": occurrence_counts[ref_id],
                    "comment_index": comment_index,
                    "target": {
                        "source_file": item.get("source_file", ""),
                        "page": item.get("page", ""),
                        "chunk_id": item.get("chunk_id", ""),
                        "quote": item.get("excerpt", ""),
                    },
                }
            )

    return links
