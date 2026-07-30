from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TextRun(StrictModel):
    type: Literal["text"]
    text: str = Field(min_length=1, max_length=8000)


class StrongRun(StrictModel):
    type: Literal["strong"]
    text: str = Field(min_length=1, max_length=8000)


class EmphasisRun(StrictModel):
    type: Literal["emphasis"]
    text: str = Field(min_length=1, max_length=8000)


class InlineCodeRun(StrictModel):
    type: Literal["inline_code"]
    text: str = Field(min_length=1, max_length=8000)


class InlineFormulaRun(StrictModel):
    type: Literal["inline_formula"]
    latex: str = Field(min_length=1, max_length=8000)


class CitationRun(StrictModel):
    type: Literal["citation"]
    evidence_id: str = Field(min_length=1)


InlineRun = Annotated[
    TextRun
    | StrongRun
    | EmphasisRun
    | InlineCodeRun
    | InlineFormulaRun
    | CitationRun,
    Field(discriminator="type"),
]


class HeadingBlock(StrictModel):
    id: str = Field(min_length=1)
    type: Literal["heading"]
    level: Literal[3, 4]
    runs: list[InlineRun] = Field(min_length=1)


class ParagraphBlock(StrictModel):
    id: str = Field(min_length=1)
    type: Literal["paragraph"]
    runs: list[InlineRun] = Field(min_length=1)


class ListBlock(StrictModel):
    id: str = Field(min_length=1)
    type: Literal["list"]
    ordered: bool
    items: list[list[InlineRun]] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_items(self) -> "ListBlock":
        if any(not item for item in self.items):
            raise ValueError("list items must contain at least one inline run")
        return self


class TableBlock(StrictModel):
    id: str = Field(min_length=1)
    type: Literal["table"]
    headers: list[list[InlineRun]] = Field(min_length=1, max_length=12)
    rows: list[list[list[InlineRun]]] = Field(max_length=100)

    @model_validator(mode="after")
    def validate_cells(self) -> "TableBlock":
        column_count = len(self.headers)
        if any(not cell for cell in self.headers):
            raise ValueError("table headers must contain at least one inline run")
        for row in self.rows:
            if len(row) != column_count:
                raise ValueError("table rows must match the header column count")
            if any(not cell for cell in row):
                raise ValueError("table cells must contain at least one inline run")
        return self


class CalloutBlock(StrictModel):
    id: str = Field(min_length=1)
    type: Literal["callout"]
    variant: Literal["key_point", "note", "warning"]
    runs: list[InlineRun] = Field(min_length=1)


class FormulaBlock(StrictModel):
    id: str = Field(min_length=1)
    type: Literal["formula"]
    latex: str = Field(min_length=1, max_length=8000)


MaterialBlock = Annotated[
    HeadingBlock
    | ParagraphBlock
    | ListBlock
    | TableBlock
    | CalloutBlock
    | FormulaBlock,
    Field(discriminator="type"),
]


class SectionQuality(StrictModel):
    evidence_status: Literal["sufficient", "weak", "failed"]
    evidence_count: int = Field(ge=0)
    cited_evidence_count: int = Field(ge=0)
    citation_coverage: float = Field(ge=0, le=1)


class MaterialSection(StrictModel):
    id: str = Field(min_length=1)
    order: int = Field(ge=1)
    title: str = Field(min_length=1)
    status: Literal["generated", "weak_evidence", "failed"]
    quality: SectionQuality
    source_ids: list[str]
    evidence_ids: list[str]
    blocks: list[MaterialBlock] = Field(max_length=120)

    @model_validator(mode="after")
    def validate_section(self) -> "MaterialSection":
        block_ids = [block.id for block in self.blocks]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("block ids must be unique within a section")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("source ids must be unique within a section")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("evidence ids must be unique within a section")
        if self.status != "failed" and not self.blocks:
            raise ValueError("non-failed sections must contain at least one block")
        return self


class ThemeReference(StrictModel):
    theme_id: str = Field(min_length=1)
    theme_version: str = Field(min_length=1)


class RenderingPreferences(StrictModel):
    default_theme: ThemeReference


class MaterialPackageV2(StrictModel):
    schema_version: Literal["material-package.v2"]
    package_id: str = Field(min_length=1)
    service_mode: Literal["single_courseware", "course_outline"]
    title: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    language: str = Field(
        min_length=1,
        pattern=r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$",
    )
    source_ids: list[str] = Field(min_length=1)
    sections: list[MaterialSection] = Field(min_length=1)
    rendering: RenderingPreferences

    @model_validator(mode="after")
    def validate_package(self) -> "MaterialPackageV2":
        section_ids = [section.id for section in self.sections]
        section_orders = [section.order for section in self.sections]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("section ids must be unique")
        if len(section_orders) != len(set(section_orders)):
            raise ValueError("section orders must be unique")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("source ids must be unique")
        return self


class LegacySourceFile(StrictModel):
    source_id: str | None = None
    file_name: str
    page_count: int | None = None
    parser_backend: str | None = None


class LegacyArtifactReferences(StrictModel):
    markdown: str
    evidence: str | None = None
    evidence_links: str | None = None
    quality: str | None = None
    package: str | None = None


class LegacyMaterialSectionV1(StrictModel):
    id: str
    title: str
    order: int
    status: str = "generated"
    quality: dict[str, Any] = Field(default_factory=dict)
    source_files: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    artifact_filenames: LegacyArtifactReferences | None = None
    artifact_urls: LegacyArtifactReferences | None = None


class LegacyMaterialPackageV1(StrictModel):
    type: Literal["material_package"]
    service_mode: Literal["single_courseware", "course_outline"]
    generation_mode: str = ""
    source_files: list[LegacySourceFile] = Field(default_factory=list)
    sections: list[LegacyMaterialSectionV1] = Field(min_length=1)
