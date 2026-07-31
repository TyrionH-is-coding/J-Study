from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import re
from typing import Any

from packages.core.jstudy_core.documents import ParsedBlock, ParsedDocument

from .models import (
    CoursewareManifestV1,
    CoverageEntry,
    CoverageLedgerV1,
    CoverageMetrics,
    LearningMapV1,
    LearningUnit,
    ManifestOutline,
    ManifestSource,
    OutlineSection,
)


SUPPORTED_BLOCK_KINDS = {
    "title",
    "text",
    "list",
    "table",
    "formula",
    "image",
    "code",
}


def _outline_sections(value: str) -> list[OutlineSection]:
    sections = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        heading = re.match(r"^(?:#{1,6})\s+(.+)$", line)
        numbered = re.match(r"^(?:\d+[.)]|[A-Za-z][.)])\s+(.+)$", line)
        match = heading or numbered
        if match is None:
            continue
        order = len(sections) + 1
        sections.append(
            OutlineSection(
                id=f"section-{order:03d}",
                order=order,
                title=match.group(1).strip()[:500],
            )
        )
        if len(sections) >= 500:
            break
    return sections


def build_courseware_manifest(
    *,
    job_id: str,
    service_mode: str,
    sources: Sequence[Any],
    outline_filename: str | None,
    outline_sha256: str | None,
    outline_text: str | None,
) -> CoursewareManifestV1:
    outline = None
    outline_sections = (
        _outline_sections(outline_text) if outline_text is not None else []
    )
    if outline_filename is not None and outline_sha256 is not None:
        outline = ManifestOutline(
            original_filename=outline_filename,
            sha256=outline_sha256,
            sections=outline_sections,
        )

    ordered = sorted(sources, key=lambda item: item.display_order)
    manifest_sources = []
    for index, source in enumerate(ordered):
        explicit = source.primary_outline_section_id
        mapped = (
            explicit
            if explicit is not None
            else (
                outline_sections[index].id
                if index < len(outline_sections)
                else None
            )
        )
        manifest_sources.append(
            ManifestSource(
                source_id=source.source_id,
                original_filename=source.original_filename,
                sha256=source.sha256,
                display_title=source.display_title,
                display_order=source.display_order,
                primary_outline_section_id=mapped,
                title_origin=source.title_origin,
                order_origin=source.order_origin,
            )
        )
    return CoursewareManifestV1(
        schema_version="courseware-manifest.v1",
        manifest_id=job_id,
        job_id=job_id,
        service_mode=service_mode,
        outline=outline,
        sources=manifest_sources,
    )


def _is_cover_page(page_number: int, blocks: list[ParsedBlock]) -> bool:
    return (
        page_number == 1
        and bool(blocks)
        and all(block.kind == "title" for block in blocks)
    )


def _block_text(block: ParsedBlock) -> str:
    return (block.text or block.markdown).strip()


def plan_learning_map(
    manifest: CoursewareManifestV1,
    documents: Sequence[ParsedDocument],
    *,
    character_budget: int = 8000,
) -> tuple[LearningMapV1, CoverageLedgerV1]:
    if character_budget < 1:
        raise ValueError("character budget must be positive")
    documents_by_id = {item.source_id: item for item in documents}
    if set(documents_by_id) != {
        item.source_id for item in manifest.sources
    }:
        raise ValueError("parsed documents do not match the manifest")

    entries: list[CoverageEntry] = []
    units: list[LearningUnit] = []
    seen_text: set[str] = set()

    for source in manifest.ordered_sources():
        document = documents_by_id[source.source_id]
        usable_pages: list[tuple[int, list[ParsedBlock], int, bool]] = []
        for page in document.pages:
            page_used = []
            page_characters = 0
            has_heading = False
            cover_page = _is_cover_page(page.page_number, page.blocks)
            for block in page.blocks:
                text = _block_text(block)
                normalized = " ".join(text.casefold().split())
                if block.kind not in SUPPORTED_BLOCK_KINDS or not text:
                    disposition = "unsupported"
                    reason = "unsupported_or_empty"
                    unit_id = None
                elif cover_page:
                    disposition = "ignored"
                    reason = "cover_page"
                    unit_id = None
                elif normalized in seen_text:
                    disposition = "duplicate"
                    reason = "duplicate_text"
                    unit_id = None
                else:
                    disposition = "used"
                    reason = "learning_unit"
                    unit_id = "pending"
                    seen_text.add(normalized)
                    page_used.append(block)
                    page_characters += len(text)
                    has_heading = has_heading or block.kind == "title"
                entries.append(
                    CoverageEntry(
                        block_id=block.block_id,
                        source_id=source.source_id,
                        page_number=page.page_number,
                        disposition=disposition,
                        reason=reason,
                        learning_unit_id=unit_id,
                    )
                )
            if page_used:
                usable_pages.append(
                    (
                        page.page_number,
                        page_used,
                        page_characters,
                        has_heading,
                    )
                )

        pending: list[tuple[int, list[ParsedBlock], int, bool]] = []
        pending_characters = 0

        def flush() -> None:
            nonlocal pending, pending_characters
            if not pending:
                return
            order = len(units) + 1
            unit_id = f"unit-{order:03d}"
            block_ids = [
                block.block_id
                for _, page_blocks, _, _ in pending
                for block in page_blocks
            ]
            units.append(
                LearningUnit(
                    id=unit_id,
                    order=order,
                    outline_section_id=source.primary_outline_section_id,
                    primary_source_id=source.source_id,
                    page_start=pending[0][0],
                    page_end=pending[-1][0],
                    block_ids=block_ids,
                    material_section_id=unit_id,
                )
            )
            used_ids = set(block_ids)
            for index, entry in enumerate(entries):
                if entry.block_id in used_ids:
                    entries[index] = entry.model_copy(
                        update={"learning_unit_id": unit_id}
                    )
            pending = []
            pending_characters = 0

        for page_data in usable_pages:
            _, _, page_characters, has_heading = page_data
            if pending and (
                has_heading
                or pending_characters + page_characters > character_budget
            ):
                flush()
            pending.append(page_data)
            pending_characters += page_characters
        flush()

    if not units:
        raise ValueError("parsed documents contain no usable learning blocks")

    disposition_counts = Counter(item.disposition for item in entries)
    ignored_reasons = Counter(
        item.reason for item in entries if item.disposition == "ignored"
    )
    total = len(entries)
    used = disposition_counts["used"]
    ledger = CoverageLedgerV1(
        schema_version="coverage-ledger.v1",
        manifest_id=manifest.manifest_id,
        entries=entries,
        metrics=CoverageMetrics(
            usable_block_count=total,
            used_block_count=used,
            ignored_block_count=disposition_counts["ignored"],
            duplicate_block_count=disposition_counts["duplicate"],
            unsupported_block_count=disposition_counts["unsupported"],
            coverage_rate=used / total if total else 0.0,
            ignored_reason_counts=dict(ignored_reasons),
            primary_backward_jump_count=0,
            large_jump_count=0,
            remote_reference_ratio=0.0,
            page_distance_p90=0.0,
        ),
    )
    learning_map = LearningMapV1(
        schema_version="learning-map.v1",
        manifest_id=manifest.manifest_id,
        units=units,
    )
    return learning_map, ledger


def validate_courseware_coordination(
    manifest: CoursewareManifestV1,
    learning_map: LearningMapV1,
    coverage: CoverageLedgerV1,
    *,
    documents: Sequence[ParsedDocument] | None = None,
    source_page_counts: Mapping[str, int | None] | None = None,
) -> None:
    if (
        learning_map.manifest_id != manifest.manifest_id
        or coverage.manifest_id != manifest.manifest_id
    ):
        raise ValueError("sequence artifacts do not share one manifest")
    source_ids = {item.source_id for item in manifest.sources}
    source_rank = {
        item.source_id: index
        for index, item in enumerate(manifest.ordered_sources())
    }
    page_counts = dict(source_page_counts or {})
    if page_counts and (
        set(page_counts) != source_ids
        or any(
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 1
            for value in page_counts.values()
        )
    ):
        raise ValueError("source page counts do not match the manifest")
    documents_by_id: dict[str, ParsedDocument] = {}
    if documents is not None:
        documents_by_id = {item.source_id: item for item in documents}
        if (
            len(documents_by_id) != len(documents)
            or set(documents_by_id) != source_ids
        ):
            raise ValueError("parsed documents do not match the manifest")
        manifest_by_id = {
            item.source_id: item for item in manifest.sources
        }
        for source_id, document in documents_by_id.items():
            if (
                document.source_sha256
                != manifest_by_id[source_id].sha256
            ):
                raise ValueError(
                    "parsed document identity does not match the manifest"
                )
            if (
                source_id in page_counts
                and page_counts[source_id] != document.page_count
            ):
                raise ValueError(
                    "parsed document page count does not match source"
                )
            page_counts[source_id] = document.page_count
    outline_ids = (
        {item.id for item in manifest.outline.sections}
        if manifest.outline is not None
        else set()
    )
    ordered_units = learning_map.ordered_units()
    if [item.order for item in ordered_units] != list(
        range(1, len(ordered_units) + 1)
    ):
        raise ValueError("learning map order must be contiguous")
    previous_source_rank = -1
    last_page_by_source: dict[str, int] = {}
    for unit in ordered_units:
        if unit.primary_source_id not in source_ids:
            raise ValueError("learning unit source is not in the manifest")
        if (
            unit.outline_section_id is not None
            and unit.outline_section_id not in outline_ids
        ):
            raise ValueError("learning unit outline section is invalid")
        if (
            page_counts
            and unit.page_end > page_counts[unit.primary_source_id]
        ):
            raise ValueError(
                "learning unit page span exceeds its source"
            )
        current_source_rank = source_rank[unit.primary_source_id]
        if current_source_rank < previous_source_rank:
            raise ValueError("learning map order violates manifest order")
        previous_end = last_page_by_source.get(unit.primary_source_id, 0)
        if unit.page_start <= previous_end:
            raise ValueError("learning map order moves backward within source")
        previous_source_rank = current_source_rank
        last_page_by_source[unit.primary_source_id] = unit.page_end

    expected_used = {
        block_id: unit.id
        for unit in ordered_units
        for block_id in unit.block_ids
    }
    actual_used = {
        entry.block_id: entry.learning_unit_id
        for entry in coverage.entries
        if entry.disposition == "used"
    }
    if actual_used != expected_used:
        raise ValueError(
            "coverage used blocks do not match learning units"
        )
    if any(entry.source_id not in source_ids for entry in coverage.entries):
        raise ValueError("coverage source is not in the manifest")

    if documents is None:
        return
    document_blocks = {
        block.block_id
        for document in documents
        for page in document.pages
        for block in page.blocks
    }
    if {entry.block_id for entry in coverage.entries} != document_blocks:
        raise ValueError("coverage does not match parsed document blocks")
    mapped_blocks = [
        block_id
        for unit in ordered_units
        for block_id in unit.block_ids
    ]
    mapped_block_set = set(mapped_blocks)
    canonical_used_blocks = [
        block.block_id
        for source in manifest.ordered_sources()
        for document in [documents_by_id[source.source_id]]
        for page in document.pages
        for block in page.blocks
        if block.block_id in mapped_block_set
    ]
    if mapped_blocks != canonical_used_blocks:
        raise ValueError(
            "learning map block order does not match parsed documents"
        )
