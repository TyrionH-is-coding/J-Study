from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from packages.core.jstudy_core.documents.models import ParsedDocument


class MinerUAdapterConfigurationError(RuntimeError):
    """The legacy MinerU adapter has no explicitly configured document parser."""


DocumentParser = Callable[[Path, dict[str, Any]], ParsedDocument]


def extract_pdf_pages_with_mineru(
    pdf_path: Path,
    config: dict[str, Any] | None = None,
    *,
    document_parser: DocumentParser | None = None,
) -> list[dict[str, Any]]:
    if document_parser is None:
        raise MinerUAdapterConfigurationError(
            "MinerU requires an explicitly supplied document parser"
        )

    document = document_parser(pdf_path, config or {})
    if not isinstance(document, ParsedDocument):
        raise MinerUAdapterConfigurationError(
            "MinerU document parser must return ParsedDocument"
        )

    return [
        {"page": page.page_number, "text": page.text}
        for page in document.pages
        if page.text.strip()
    ]
