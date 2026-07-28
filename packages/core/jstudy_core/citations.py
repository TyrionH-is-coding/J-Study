from __future__ import annotations

import re
from typing import Any

from packages.retrieval.hybrid import Chunk

PDF_GARBAGE_RE = re.compile(
    r"[\u05c0-\u05ff\u0600-\u06ff\u0700-\u074f\u0780-\u07bf"
    r"\u0900-\u097f\u0980-\u09ff\u0a00-\u0a7f\u0a80-\u0aff"
    r"\u0b00-\u0b7f\u0b80-\u0bff\u0c00-\u0c7f\u0c80-\u0cff"
    r"\u0d00-\u0dff\u0e00-\u0eff\u0f00-\u0fff\u1000-\u109f"
    r"\u10a0-\u10ff\u1200-\u137f\ue000-\uf8ff]"
)
PDF_ARTIFACT_LINE_RE = re.compile(r"^[+\-\\*/=·•■□○●\s]{5,}$", re.MULTILINE)


def clean_quote(text: str, max_length: int = 500) -> str:
    cleaned = PDF_GARBAGE_RE.sub("", text or "")
    cleaned = PDF_ARTIFACT_LINE_RE.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return (cleaned or "(non-text content)")[:max_length]


def build_evidence_items(chunks: list[Chunk], source_file: str) -> list[dict[str, Any]]:
    evidence = []
    for idx, chunk in enumerate(chunks, start=1):
        item = {
            "id": f"E{idx:03d}",
            "source_id": chunk.source_id,
            "source_file": chunk.source_file or source_file,
            "page": chunk.page,
            "chunk_id": chunk.id,
            "score": round(chunk.score, 4),
            "excerpt": clean_quote(chunk.text),
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
                        "source_id": item.get("source_id", ""),
                        "source_file": item.get("source_file", ""),
                        "page": item.get("page", ""),
                        "chunk_id": item.get("chunk_id", ""),
                        "quote": item.get("excerpt", ""),
                    },
                }
            )

    return links
