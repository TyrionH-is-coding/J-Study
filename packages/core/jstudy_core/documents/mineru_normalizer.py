from __future__ import annotations

import io
import json
import shutil
import stat
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from .models import (
    DocumentContractError,
    ParsedBlock,
    ParsedDocument,
    ParsedPage,
)


AUXILIARY_TYPES = {"header", "footer", "page_number", "aside_text", "page_footnote"}
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class MinerUNormalizationError(DocumentContractError):
    """MinerU output cannot be safely normalized into contract version 1."""


@dataclass(frozen=True)
class MinerUNormalizerLimits:
    max_members: int = 2000
    max_uncompressed_bytes: int = 536870912
    max_content_list_bytes: int = 16777216
    max_compression_ratio: float = 100.0

    def __post_init__(self) -> None:
        if (
            self.max_members < 1
            or self.max_uncompressed_bytes < 1
            or self.max_content_list_bytes < 1
        ):
            raise MinerUNormalizationError("ZIP limits must be positive")
        if self.max_compression_ratio <= 0:
            raise MinerUNormalizationError("ZIP compression ratio limit must be positive")


@dataclass
class MinerUBatchBudget:
    max_uncompressed_bytes: int = 536870912
    max_private_bytes: int = 1073741824
    uncompressed_bytes: int = 0
    private_bytes: int = 0

    def __post_init__(self) -> None:
        if self.max_uncompressed_bytes < 1 or self.max_private_bytes < 1:
            raise MinerUNormalizationError("batch limits must be positive")

    def reserve(self, *, uncompressed_bytes: int, private_bytes: int) -> None:
        next_uncompressed = self.uncompressed_bytes + uncompressed_bytes
        if next_uncompressed > self.max_uncompressed_bytes:
            raise MinerUNormalizationError(
                "MinerU batch uncompressed byte limit exceeded"
            )
        next_private = self.private_bytes + private_bytes
        if next_private > self.max_private_bytes:
            raise MinerUNormalizationError(
                "MinerU batch private artifact byte limit exceeded"
            )
        self.uncompressed_bytes = next_uncompressed
        self.private_bytes = next_private


def normalize_mineru_zip(
    *,
    zip_bytes: bytes | None = None,
    zip_path: Path | None = None,
    source_id: str,
    source_file: str,
    source_sha256: str,
    source_page_count: int,
    parser_version: str,
    parser_model: str,
    provider_trace_id: str,
    artifact_dir: Path,
    limits: MinerUNormalizerLimits = MinerUNormalizerLimits(),
    batch_budget: MinerUBatchBudget | None = None,
) -> ParsedDocument:
    if source_page_count < 1:
        raise MinerUNormalizationError("source PDF page count must be positive")
    if artifact_dir.exists() and _is_link_or_reparse(artifact_dir):
        raise MinerUNormalizationError("artifact directory cannot be a symlink")

    if (zip_bytes is None) == (zip_path is None):
        raise MinerUNormalizationError("exactly one MinerU ZIP source is required")
    artifact_dir_existed = artifact_dir.exists()
    try:
        archive_size = (
            len(zip_bytes)
            if zip_bytes is not None
            else Path(zip_path).stat().st_size
        )
    except OSError as exc:
        raise MinerUNormalizationError(
            "MinerU artifact is not readable"
        ) from exc
    archive_source = io.BytesIO(zip_bytes) if zip_bytes is not None else zip_path
    try:
        archive = zipfile.ZipFile(archive_source)
    except (zipfile.BadZipFile, OSError) as exc:
        raise MinerUNormalizationError("MinerU artifact is not a valid ZIP") from exc

    try:
        with archive:
            members, total_uncompressed = _validate_members(archive, limits)
            budget = batch_budget or MinerUBatchBudget()
            budget.reserve(
                uncompressed_bytes=total_uncompressed,
                private_bytes=archive_size + total_uncompressed,
            )
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
                content_payload = _read_member_bounded(
                    archive,
                    content_members[0],
                    max_bytes=limits.max_content_list_bytes,
                )
                raw_content = json.loads(content_payload.decode("utf-8"))
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
            _write_private_artifacts(
                archive,
                members,
                artifact_dir=artifact_dir,
            )
        _retain_original_zip(
            zip_bytes=zip_bytes,
            zip_path=zip_path,
            artifact_dir=artifact_dir,
        )
        return document
    except Exception:
        if not artifact_dir_existed:
            shutil.rmtree(artifact_dir, ignore_errors=True)
        raise


def _validate_members(
    archive: zipfile.ZipFile,
    limits: MinerUNormalizerLimits,
) -> tuple[list[zipfile.ZipInfo], int]:
    members = archive.infolist()
    if len(members) > limits.max_members:
        raise MinerUNormalizationError("MinerU ZIP contains too many members")

    target_keys: set[str] = set()
    total_uncompressed = 0
    for info in members:
        name = _validate_member_path(info.filename)
        target_key = name.rstrip("/").casefold()
        if target_key in target_keys:
            raise MinerUNormalizationError("MinerU ZIP contains duplicate member paths")
        target_keys.add(target_key)

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
    return members, total_uncompressed


def _validate_member_path(value: str) -> str:
    name = _normalized_name(value)
    candidate = name.rstrip("/")
    if not candidate or name.startswith("/"):
        raise MinerUNormalizationError("MinerU ZIP contains an unsafe member path")

    parts = candidate.split("/")
    windows_path = PureWindowsPath(candidate)
    if windows_path.drive or windows_path.root or any(part in {"", ".", ".."} for part in parts):
        raise MinerUNormalizationError("MinerU ZIP contains an unsafe member path")

    for part in parts:
        device_name = part.split(".", 1)[0].upper()
        if (
            ":" in part
            or part.endswith((" ", "."))
            or device_name in WINDOWS_RESERVED_NAMES
        ):
            raise MinerUNormalizationError("MinerU ZIP contains an unsafe Windows member path")
    return name


def _is_link_or_reparse(path: Path) -> bool:
    try:
        details = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(details, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(details.st_mode) or bool(attributes & reparse_flag)


def _assert_safe_target(root: Path, target: Path) -> None:
    root_resolved = root.resolve(strict=True)
    try:
        target.relative_to(root)
        target.resolve(strict=False).relative_to(root_resolved)
    except ValueError as exc:
        raise MinerUNormalizationError("MinerU ZIP target escapes the extraction root") from exc

    current = root
    for part in target.relative_to(root).parts:
        current = current / part
        if _is_link_or_reparse(current):
            raise MinerUNormalizationError("MinerU ZIP target crosses a symlink or reparse point")


def _safe_mkdir(root: Path, target: Path) -> None:
    _assert_safe_target(root, target)
    target.mkdir(parents=True, exist_ok=True)
    _assert_safe_target(root, target)


def _safe_write_stream(
    root: Path,
    target: Path,
    source: Any,
    *,
    max_bytes: int,
) -> None:
    _safe_mkdir(root, target.parent)
    _assert_safe_target(root, target)
    written = 0
    try:
        with target.open("xb") as handle:
            while True:
                chunk = source.read(64 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise MinerUNormalizationError(
                        "MinerU ZIP member exceeds its declared size"
                    )
                handle.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise


def _read_member_bounded(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    *,
    max_bytes: int,
) -> bytes:
    if info.file_size > max_bytes:
        raise MinerUNormalizationError(
            "MinerU content list exceeds the byte limit"
        )
    with archive.open(info) as source:
        payload = source.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise MinerUNormalizationError(
            "MinerU content list exceeds the byte limit"
        )
    return payload


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
    try:
        name = _validate_member_path(raw)
    except MinerUNormalizationError as exc:
        raise MinerUNormalizationError("MinerU asset path is unsafe") from exc
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
    *,
    artifact_dir: Path,
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    if _is_link_or_reparse(artifact_dir):
        raise MinerUNormalizationError("artifact directory cannot be a symlink or reparse point")

    extraction_root = artifact_dir / "mineru"
    if _is_link_or_reparse(extraction_root):
        raise MinerUNormalizationError("extraction root cannot be a symlink or reparse point")
    extraction_root.mkdir(parents=True, exist_ok=True)

    for info in members:
        parts = PurePosixPath(_validate_member_path(info.filename)).parts
        target = extraction_root.joinpath(*parts)
        if info.is_dir():
            _safe_mkdir(extraction_root, target)
            continue
        with archive.open(info) as source:
            _safe_write_stream(
                extraction_root,
                target,
                source,
                max_bytes=info.file_size,
            )

    full_markdown = [
        info
        for info in members
        if not info.is_dir()
        and PurePosixPath(_normalized_name(info.filename)).name == "full.md"
    ]
    if len(full_markdown) == 1:
        source_path = extraction_root.joinpath(
            *PurePosixPath(
                _validate_member_path(full_markdown[0].filename)
            ).parts
        )
        target_path = artifact_dir / "full.md"
        _assert_safe_target(artifact_dir, target_path)
        source_path.replace(target_path)


def _retain_original_zip(
    *,
    zip_bytes: bytes | None,
    zip_path: Path | None,
    artifact_dir: Path,
) -> None:
    original_zip = artifact_dir / "mineru-original.zip"
    _assert_safe_target(artifact_dir, original_zip)
    if zip_path is not None:
        Path(zip_path).replace(original_zip)
        return
    with io.BytesIO(zip_bytes or b"") as source:
        _safe_write_stream(
            artifact_dir,
            original_zip,
            source,
            max_bytes=len(zip_bytes or b""),
        )


def _normalized_name(value: str) -> str:
    return value.replace("\\", "/")


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
