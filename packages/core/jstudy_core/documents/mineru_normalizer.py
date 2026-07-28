from __future__ import annotations

import io
import json
import re
import stat
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .models import (
    DocumentContractError,
    ParsedBlock,
    ParsedDocument,
    ParsedPage,
)


AUXILIARY_TYPES = {"header", "footer", "page_number", "aside_text", "page_footnote"}


class MinerUNormalizationError(DocumentContractError):
    """MinerU output cannot be safely normalized into contract version 1."""


@dataclass(frozen=True)
class MinerUNormalizerLimits:
    max_members: int = 2000
    max_uncompressed_bytes: int = 536870912
    max_compression_ratio: float = 100.0

    def __post_init__(self) -> None:
        if self.max_members < 1 or self.max_uncompressed_bytes < 1:
            raise MinerUNormalizationError("ZIP limits must be positive")
        if self.max_compression_ratio <= 0:
            raise MinerUNormalizationError("ZIP compression ratio limit must be positive")


def normalize_mineru_zip(
    *,
    zip_bytes: bytes,
    source_id: str,
    source_file: str,
    source_sha256: str,
    source_page_count: int,
    parser_version: str,
    parser_model: str,
    provider_trace_id: str,
    artifact_dir: Path,
    limits: MinerUNormalizerLimits = MinerUNormalizerLimits(),
) -> ParsedDocument:
    if source_page_count < 1:
        raise MinerUNormalizationError("source PDF page count must be positive")
    if artifact_dir.exists() and artifact_dir.is_symlink():
        raise MinerUNormalizationError("artifact directory cannot be a symlink")

    try:
        archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except (zipfile.BadZipFile, OSError) as exc:
        raise MinerUNormalizationError("MinerU artifact is not a valid ZIP") from exc

    with archive:
        members = _validate_members(archive, limits)
        content_members = [
            info
            for info in members
            if not info.is_dir()
            and PurePosixPath(_normalized_name(info.filename)).name.endswith("_content_list.json")
            and not PurePosixPath(_normalized_name(info.filename)).name.endswith("_content_list_v2.json")
        ]
        if len(content_members) != 1:
            raise MinerUNormalizationError("MinerU ZIP must contain exactly one content_list.json")
        try:
            raw_content = json.loads(archive.read(content_members[0]).decode("utf-8"))
        except (KeyError, UnicodeError, json.JSONDecodeError) as exc:
            raise MinerUNormalizationError("MinerU content list is malformed") from exc
        if not isinstance(raw_content, list) or not raw_content:
            raise MinerUNormalizationError("MinerU content list is empty or invalid")

        document = _normalize_content(
            raw_content=raw_content,
            member_names={_normalized_name(info.filename) for info in members if not info.is_dir()},
            source_id=source_id,
            source_file=source_file,
            source_sha256=source_sha256,
            source_page_count=source_page_count,
            parser_version=parser_version,
            parser_model=parser_model,
            provider_trace_id=provider_trace_id,
        )
        _write_private_artifacts(archive, members, zip_bytes, artifact_dir)
        return document


def _validate_members(
    archive: zipfile.ZipFile,
    limits: MinerUNormalizerLimits,
) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if len(members) > limits.max_members:
        raise MinerUNormalizationError("MinerU ZIP contains too many members")

    names: set[str] = set()
    total_uncompressed = 0
    for info in members:
        name = _normalized_name(info.filename)
        path = PurePosixPath(name)
        if (
            not name
            or name.startswith("/")
            or re.match(r"^[A-Za-z]:/", name)
            or path.is_absolute()
            or ".." in path.parts
        ):
            raise MinerUNormalizationError("MinerU ZIP contains an unsafe member path")
        if name in names:
            raise MinerUNormalizationError("MinerU ZIP contains duplicate member paths")
        names.add(name)
        unix_mode = info.external_attr >> 16
        if stat.S_ISLNK(unix_mode):
            raise MinerUNormalizationError("MinerU ZIP symlinks are not allowed")
        total_uncompressed += info.file_size
        if total_uncompressed > limits.max_uncompressed_bytes:
            raise MinerUNormalizationError("MinerU ZIP exceeds the uncompressed byte limit")
        if info.file_size:
            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > limits.max_compression_ratio:
                raise MinerUNormalizationError("MinerU ZIP exceeds the compression ratio limit")
    return members


def _normalize_content(
    *,
    raw_content: list[Any],
    member_names: set[str],
    source_id: str,
    source_file: str,
    source_sha256: str,
    source_page_count: int,
    parser_version: str,
    parser_model: str,
    provider_trace_id: str,
) -> ParsedDocument:
    page_blocks: dict[int, list[ParsedBlock]] = {
        page_number: [] for page_number in range(1, source_page_count + 1)
    }
    excluded = Counter[str]()
    unsupported = Counter[str]()

    for value in raw_content:
        if not isinstance(value, dict):
            raise MinerUNormalizationError("MinerU content item must be an object")
        page_idx = value.get("page_idx")
        if not isinstance(page_idx, int) or isinstance(page_idx, bool):
            raise MinerUNormalizationError("MinerU page_idx must be an integer")
        page_number = page_idx + 1
        if page_number < 1 or page_number > source_page_count:
            raise MinerUNormalizationError("MinerU content references a page outside the source PDF")
        mineru_type = str(value.get("type") or "").strip().lower()
        if not mineru_type:
            raise MinerUNormalizationError("MinerU content item type is required")
        if mineru_type in AUXILIARY_TYPES:
            excluded[mineru_type] += 1
            continue

        normalized = _normalize_block_fields(value, mineru_type, member_names)
        if normalized is None:
            unsupported[mineru_type] += 1
            continue
        kind, text, markdown, asset_path, metadata = normalized
        block_number = len(page_blocks[page_number]) + 1
        try:
            block = ParsedBlock(
                block_id=f"{source_id}-P{page_number:03d}-B{block_number:03d}",
                kind=kind,
                text=text,
                markdown=markdown,
                bbox=_normalize_bbox(value.get("bbox")),
                asset_path=asset_path,
                metadata=metadata,
            )
        except DocumentContractError as exc:
            raise MinerUNormalizationError(str(exc)) from exc
        page_blocks[page_number].append(block)

    if not any(page_blocks.values()):
        raise MinerUNormalizationError("MinerU document contains no usable content blocks")

    pages = []
    for page_number in range(1, source_page_count + 1):
        blocks = page_blocks[page_number]
        pages.append(
            ParsedPage(
                page_number=page_number,
                text="\n\n".join(block.text for block in blocks if block.text.strip()),
                markdown="\n\n".join(block.markdown for block in blocks if block.markdown.strip()),
                blocks=blocks,
            )
        )

    warnings = []
    if excluded:
        detail = ", ".join(f"{name}={count}" for name, count in sorted(excluded.items()))
        warnings.append(f"Excluded auxiliary MinerU blocks from retrieval text: {detail}")
    if unsupported:
        detail = ", ".join(f"{name}={count}" for name, count in sorted(unsupported.items()))
        warnings.append(f"Skipped unsupported MinerU blocks: {detail}")

    try:
        return ParsedDocument(
            contract_version="1",
            source_id=source_id,
            source_file=source_file,
            source_sha256=source_sha256,
            parser_name="mineru",
            parser_version=parser_version,
            parser_model=parser_model,
            page_count=source_page_count,
            pages=pages,
            warnings=warnings,
            provider_trace_id=provider_trace_id,
        )
    except DocumentContractError as exc:
        raise MinerUNormalizationError(str(exc)) from exc


def _normalize_block_fields(
    value: dict[str, Any],
    mineru_type: str,
    member_names: set[str],
) -> tuple[str, str, str, str | None, dict[str, Any]] | None:
    metadata = {"mineru_type": mineru_type}
    sub_type = str(value.get("sub_type") or "").strip()
    if sub_type:
        metadata["sub_type"] = sub_type

    if mineru_type in {"text", "title"}:
        text = str(value.get("text") or value.get("content") or "").strip()
        if not text:
            return None
        level_value = value.get("text_level", 1 if mineru_type == "title" else 0)
        level = level_value if isinstance(level_value, int) and not isinstance(level_value, bool) else 0
        if level > 0:
            metadata["text_level"] = level
            return "title", text, f"{'#' * min(level, 6)} {text}", None, metadata
        return "text", text, text, None, metadata

    if mineru_type == "list":
        items = value.get("list_items")
        if not isinstance(items, list):
            items = []
        normalized_items = [str(item).strip() for item in items if str(item).strip()]
        if not normalized_items:
            return None
        return (
            "list",
            "\n".join(normalized_items),
            "\n".join(f"- {item}" for item in normalized_items),
            None,
            metadata,
        )

    if mineru_type in {"table", "chart"}:
        body = str(value.get("table_body") or value.get("content") or "").strip()
        captions = _string_list(value.get("table_caption") or value.get("chart_caption"))
        text = "\n".join([*captions, body] if body else captions).strip()
        if not text:
            return None
        return "table", text, text, _asset_path(value, member_names), metadata

    if mineru_type == "equation":
        formula = str(value.get("text") or value.get("content") or "").strip()
        if not formula:
            return None
        return "formula", formula, formula, _asset_path(value, member_names), metadata

    if mineru_type == "image":
        captions = _string_list(value.get("image_caption"))
        footnotes = _string_list(value.get("image_footnote"))
        text = "\n".join([*captions, *footnotes]).strip()
        asset_path = _asset_path(value, member_names)
        if not text and not asset_path:
            return None
        alt = captions[0] if captions else "image"
        markdown = f"![{alt}]({asset_path})" if asset_path else text
        if text and markdown != text:
            markdown = f"{markdown}\n\n{text}"
        return "image", text, markdown, asset_path, metadata

    if mineru_type == "code":
        code = str(value.get("code_body") or value.get("content") or "").strip()
        if not code:
            return None
        return "code", code, f"```\n{code}\n```", None, metadata

    return None


def _asset_path(value: dict[str, Any], member_names: set[str]) -> str | None:
    raw = str(value.get("img_path") or "").strip()
    if not raw:
        return None
    name = _normalized_name(raw)
    path = PurePosixPath(name)
    if name.startswith("/") or re.match(r"^[A-Za-z]:/", name) or ".." in path.parts:
        raise MinerUNormalizationError("MinerU asset path is unsafe")
    if name not in member_names:
        raise MinerUNormalizationError("MinerU content references a missing asset")
    return f"mineru/{name}"


def _normalize_bbox(value: Any) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise MinerUNormalizationError("MinerU bbox must contain four coordinates")
    try:
        return tuple(float(item) for item in value)  # type: ignore[return-value]
    except (TypeError, ValueError) as exc:
        raise MinerUNormalizationError("MinerU bbox coordinates must be numeric") from exc


def _write_private_artifacts(
    archive: zipfile.ZipFile,
    members: list[zipfile.ZipInfo],
    zip_bytes: bytes,
    artifact_dir: Path,
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    extraction_root = artifact_dir / "mineru"
    extraction_root.mkdir(parents=True, exist_ok=True)
    for info in members:
        parts = PurePosixPath(_normalized_name(info.filename)).parts
        target = extraction_root.joinpath(*parts)
        if info.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read(info))
    (artifact_dir / "mineru-original.zip").write_bytes(zip_bytes)
    full_markdown = [
        info for info in members if not info.is_dir() and PurePosixPath(_normalized_name(info.filename)).name == "full.md"
    ]
    if len(full_markdown) == 1:
        (artifact_dir / "full.md").write_bytes(archive.read(full_markdown[0]))


def _normalized_name(value: str) -> str:
    return value.replace("\\", "/")


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
