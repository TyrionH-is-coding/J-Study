from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


class DocumentContractError(ValueError):
    """A normalized document violates the J-Study document contract."""


def _required(value: str, name: str) -> None:
    if not value.strip():
        raise DocumentContractError(f"{name} is required")


@dataclass(frozen=True)
class ParsedBlock:
    block_id: str
    kind: str
    text: str = ""
    markdown: str = ""
    bbox: tuple[float, float, float, float] | None = None
    asset_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _required(self.block_id, "block_id")
        _required(self.kind, "kind")
        if self.bbox is None:
            return
        if len(self.bbox) != 4 or not all(math.isfinite(value) for value in self.bbox):
            raise DocumentContractError("bbox must contain four finite coordinates")
        x0, y0, x1, y1 = self.bbox
        if x0 > x1 or y0 > y1:
            raise DocumentContractError("bbox coordinates must be ordered")


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text: str
    markdown: str
    blocks: list[ParsedBlock]

    def __post_init__(self) -> None:
        if self.page_number < 1:
            raise DocumentContractError("page_number must be one-based and positive")


@dataclass(frozen=True)
class ParsedDocument:
    contract_version: str
    source_id: str
    source_file: str
    source_sha256: str
    parser_name: str
    parser_version: str
    parser_model: str
    page_count: int
    pages: list[ParsedPage]
    warnings: list[str]
    provider_trace_id: str

    def __post_init__(self) -> None:
        if self.contract_version != "1":
            raise DocumentContractError("unsupported document contract version")
        _required(self.source_id, "source_id")
        _required(self.source_file, "source_file")
        _required(self.source_sha256, "source_sha256")
        _required(self.parser_name, "parser_name")
        _required(self.parser_version, "parser_version")
        _required(self.parser_model, "parser_model")
        if self.page_count < 1 or not self.pages:
            raise DocumentContractError("document must contain at least one source page")

        page_numbers = [page.page_number for page in self.pages]
        if page_numbers != list(range(1, self.page_count + 1)):
            raise DocumentContractError(
                "pages must cover the source page count in ascending one-based order"
            )

        block_ids = [block.block_id for page in self.pages for block in page.blocks]
        if len(block_ids) != len(set(block_ids)):
            raise DocumentContractError("block ids must be unique within the document")
