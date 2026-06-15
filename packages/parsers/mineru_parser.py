from __future__ import annotations

from pathlib import Path
from typing import Any


def extract_pdf_pages_with_mineru(
    pdf_path: Path,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    raise RuntimeError("MinerU parser is selected but no MinerU adapter is configured")
