from __future__ import annotations

from collections import Counter
import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SHA256_PATTERN = r"^[0-9a-f]{64}$"
BLOCK_ID_PATTERN = re.compile(
    r"^(?P<source_id>[A-Za-z0-9_.-]+)-P(?P<page>\d+)-B\d+$"
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class OutlineSection(StrictModel):
    id: str = Field(min_length=1, max_length=128)
    order: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=500)


class ManifestOutline(StrictModel):
    original_filename: str = Field(min_length=1, max_length=255)
    sha256: str = Field(pattern=SHA256_PATTERN)
    sections: list[OutlineSection] = Field(max_length=500)

    @model_validator(mode="after")
    def validate_sections(self) -> "ManifestOutline":
        ids = [item.id for item in self.sections]
        orders = [item.order for item in self.sections]
        if len(ids) != len(set(ids)) or len(orders) != len(set(orders)):
            raise ValueError("outline section identity and order must be unique")
        return self


class ManifestSource(StrictModel):
    source_id: str = Field(min_length=1, max_length=128)
    original_filename: str = Field(min_length=1, max_length=255)
    sha256: str = Field(pattern=SHA256_PATTERN)
    display_title: str = Field(min_length=1, max_length=500)
    display_order: int = Field(ge=1)
    primary_outline_section_id: str | None = Field(
        default=None,
        max_length=128,
    )
    title_origin: Literal["upload", "auto", "user"]
    order_origin: Literal["upload", "auto", "user"]


class CoursewareManifestV1(StrictModel):
    schema_version: Literal["courseware-manifest.v1"]
    manifest_id: str = Field(min_length=1, max_length=128)
    job_id: str = Field(min_length=1, max_length=128)
    service_mode: Literal["single_courseware", "course_outline"]
    outline: ManifestOutline | None
    sources: list[ManifestSource] = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_manifest(self) -> "CoursewareManifestV1":
        source_ids = [item.source_id for item in self.sources]
        display_orders = [item.display_order for item in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("manifest source ids must be unique")
        if len(display_orders) != len(set(display_orders)):
            raise ValueError("manifest display orders must be unique")
        outline_ids = (
            {item.id for item in self.outline.sections}
            if self.outline is not None
            else set()
        )
        if any(
            source.primary_outline_section_id is not None
            and source.primary_outline_section_id not in outline_ids
            for source in self.sources
        ):
            raise ValueError("manifest source references an unknown outline section")
        return self

    def ordered_sources(self) -> list[ManifestSource]:
        return sorted(self.sources, key=lambda item: item.display_order)


class LearningUnit(StrictModel):
    id: str = Field(min_length=1, max_length=128)
    order: int = Field(ge=1)
    outline_section_id: str | None = Field(default=None, max_length=128)
    primary_source_id: str = Field(min_length=1, max_length=128)
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    block_ids: list[str] = Field(min_length=1, max_length=5000)
    material_section_id: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_unit(self) -> "LearningUnit":
        if self.page_start > self.page_end:
            raise ValueError("learning unit page range is invalid")
        if len(self.block_ids) != len(set(self.block_ids)):
            raise ValueError("learning unit block ids must be unique")
        for block_id in self.block_ids:
            match = BLOCK_ID_PATTERN.fullmatch(block_id)
            if match is None:
                raise ValueError("learning unit block identity is invalid")
            if match.group("source_id") != self.primary_source_id:
                raise ValueError("learning unit block belongs to another source")
            page = int(match.group("page"))
            if not self.page_start <= page <= self.page_end:
                raise ValueError("learning unit block is outside its page range")
        return self


class LearningMapV1(StrictModel):
    schema_version: Literal["learning-map.v1"]
    manifest_id: str = Field(min_length=1, max_length=128)
    units: list[LearningUnit] = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_units(self) -> "LearningMapV1":
        ids = [item.id for item in self.units]
        orders = [item.order for item in self.units]
        section_ids = [item.material_section_id for item in self.units]
        block_ids = [block for item in self.units for block in item.block_ids]
        if len(ids) != len(set(ids)) or len(orders) != len(set(orders)):
            raise ValueError("learning unit identity and order must be unique")
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("material section ids must be unique")
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("a block cannot belong to multiple learning units")
        return self

    def ordered_units(self) -> list[LearningUnit]:
        return sorted(self.units, key=lambda item: item.order)


class CoverageEntry(StrictModel):
    block_id: str = Field(min_length=1, max_length=256)
    source_id: str = Field(min_length=1, max_length=128)
    page_number: int = Field(ge=1)
    disposition: Literal["used", "ignored", "duplicate", "unsupported"]
    reason: str = Field(min_length=1, max_length=128)
    learning_unit_id: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def validate_entry(self) -> "CoverageEntry":
        match = BLOCK_ID_PATTERN.fullmatch(self.block_id)
        if match is None:
            raise ValueError("coverage block identity is invalid")
        if match.group("source_id") != self.source_id:
            raise ValueError("coverage block source identity is invalid")
        if int(match.group("page")) != self.page_number:
            raise ValueError("coverage block page identity is invalid")
        if self.disposition == "used" and self.learning_unit_id is None:
            raise ValueError("used blocks require a learning unit")
        if self.disposition != "used" and self.learning_unit_id is not None:
            raise ValueError("non-used blocks cannot reference a learning unit")
        return self


class CoverageMetrics(StrictModel):
    usable_block_count: int = Field(ge=0)
    used_block_count: int = Field(ge=0)
    ignored_block_count: int = Field(ge=0)
    duplicate_block_count: int = Field(ge=0)
    unsupported_block_count: int = Field(ge=0)
    coverage_rate: float = Field(ge=0, le=1)
    ignored_reason_counts: dict[str, int]
    primary_backward_jump_count: int = Field(ge=0)
    large_jump_count: int = Field(ge=0)
    remote_reference_ratio: float = Field(ge=0, le=1)
    page_distance_p90: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> "CoverageMetrics":
        total = (
            self.used_block_count
            + self.ignored_block_count
            + self.duplicate_block_count
            + self.unsupported_block_count
        )
        if self.usable_block_count != total:
            raise ValueError("coverage disposition counts must cover all blocks")
        expected_rate = (
            self.used_block_count / self.usable_block_count
            if self.usable_block_count
            else 0.0
        )
        if not math.isclose(
            self.coverage_rate,
            expected_rate,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError("coverage rate does not match disposition counts")
        if any(value < 0 for value in self.ignored_reason_counts.values()):
            raise ValueError("ignored reason counts cannot be negative")
        return self


class CoverageLedgerV1(StrictModel):
    schema_version: Literal["coverage-ledger.v1"]
    manifest_id: str = Field(min_length=1, max_length=128)
    entries: list[CoverageEntry] = Field(max_length=100000)
    metrics: CoverageMetrics

    @model_validator(mode="after")
    def validate_entries(self) -> "CoverageLedgerV1":
        block_ids = [item.block_id for item in self.entries]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("coverage block ids must be unique")
        counts = {
            disposition: sum(
                item.disposition == disposition for item in self.entries
            )
            for disposition in (
                "used",
                "ignored",
                "duplicate",
                "unsupported",
            )
        }
        if (
            self.metrics.usable_block_count != len(self.entries)
            or self.metrics.used_block_count != counts["used"]
            or self.metrics.ignored_block_count != counts["ignored"]
            or self.metrics.duplicate_block_count != counts["duplicate"]
            or self.metrics.unsupported_block_count != counts["unsupported"]
        ):
            raise ValueError("coverage metrics do not match ledger entries")
        ignored_reasons = Counter(
            item.reason
            for item in self.entries
            if item.disposition == "ignored"
        )
        if self.metrics.ignored_reason_counts != dict(ignored_reasons):
            raise ValueError(
                "ignored reason metrics do not match ledger entries"
            )
        return self
