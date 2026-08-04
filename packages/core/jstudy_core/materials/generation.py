from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from packages.core.jstudy_core import providers

from .models import (
    MaterialBlock,
    MaterialPackageV2,
    MaterialSection,
    SectionQuality,
)
from .validation import (
    MaterialValidationError,
    citation_ids_for_section,
    validate_material_package,
)


class _GeneratedSectionContent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: list[MaterialBlock] = Field(min_length=1, max_length=120)


def _messages(
    *,
    soul: str,
    section_id: str,
    order: int,
    title: str,
    evidence: Sequence[Mapping[str, Any]],
    source_ids: Sequence[str],
    validation_summary: str | None = None,
) -> list[dict[str, str]]:
    allowed_evidence_ids = [
        str(item["id"]) for item in evidence if item.get("id") is not None
    ]
    prompt_evidence = [
        {
            "id": str(item.get("id") or ""),
            "source_id": str(item.get("source_id") or ""),
            "source_file": str(item.get("source_file") or ""),
            "page": item.get("page"),
            "chunk_id": str(item.get("chunk_id") or ""),
            "content": str(
                item.get("content")
                or item.get("excerpt")
                or ""
            ),
        }
        for item in evidence
    ]
    first_evidence_id = allowed_evidence_ids[0]
    example = {
        "blocks": [
            {
                "id": "heading-001",
                "type": "heading",
                "level": 3,
                "runs": [{"type": "text", "text": "知识标题"}],
            },
            {
                "id": "paragraph-001",
                "type": "paragraph",
                "runs": [
                    {"type": "text", "text": "有证据支持的知识陈述。"},
                    {
                        "type": "citation",
                        "evidence_id": first_evidence_id,
                    },
                ],
            },
            {
                "id": "list-001",
                "type": "list",
                "ordered": False,
                "items": [
                    [
                        {"type": "text", "text": "列表知识点"},
                        {
                            "type": "citation",
                            "evidence_id": first_evidence_id,
                        },
                    ]
                ],
            },
            {
                "id": "callout-001",
                "type": "callout",
                "variant": "key_point",
                "runs": [
                    {"type": "text", "text": "需要记忆的结论。"},
                    {
                        "type": "citation",
                        "evidence_id": first_evidence_id,
                    },
                ],
            },
            {
                "id": "table-001",
                "type": "table",
                "headers": [
                    [{"type": "text", "text": "项目"}],
                    [{"type": "text", "text": "结论"}],
                ],
                "rows": [
                    [
                        [{"type": "text", "text": "示例"}],
                        [
                            {"type": "text", "text": "有依据的内容"},
                            {
                                "type": "citation",
                                "evidence_id": first_evidence_id,
                            },
                        ],
                    ]
                ],
            },
        ]
    }
    format_instruction = (
        "Return exactly one JSON object with only the key blocks. "
        "Server metadata is added by the application; do not output "
        "id/order/title/status/quality/source_ids/evidence_ids at the top level. "
        "Prefer 4 to 12 concise learning blocks. Every block needs a unique id. "
        "Use runs for all prose. Cite each evidence-backed claim immediately with "
        "a citation run and only an allowed evidence_id. "
        "Preserve every source table row and workflow step unless it is an exact "
        "duplicate; do not silently omit entries. "
        "Do not fully repeat the same workflow or fact as prose, a list, and a table. "
        "Choose the single clearest learning representation unless a second form "
        "adds new information. "
        "Every source-derived table must include at least one citation run in a "
        "relevant cell. "
        "Do not include visual label prefixes such as 注意、重点、警告 in callout "
        "runs because the renderer adds them. "
        "Allowed block shapes: "
        "heading={id,type:'heading',level:3|4,runs}; "
        "paragraph={id,type:'paragraph',runs}; "
        "list={id,type:'list',ordered:boolean,items:[runs]}; "
        "table={id,type:'table',headers:[runs],rows:[[runs]]}; "
        "callout={id,type:'callout',variant:'key_point'|'note'|'warning',runs}; "
        "formula={id,type:'formula',latex}. "
        "Allowed run shapes: "
        "{type:'text'|'strong'|'emphasis'|'inline_code',text}; "
        "{type:'inline_formula',latex}; "
        "{type:'citation',evidence_id}. "
        "Do not return Markdown, HTML, CSS, URLs, scripts, comments, or wrapper text.\n"
        f"Example JSON: {json.dumps(example, ensure_ascii=False)}"
    )
    prompt = (
        f"Section title: {title}\n"
        f"Allowed source ids: {json.dumps(list(source_ids), ensure_ascii=False)}\n"
        f"Allowed evidence ids: {json.dumps(allowed_evidence_ids, ensure_ascii=False)}\n"
        f"Evidence: {json.dumps(prompt_evidence, ensure_ascii=False)}"
    )
    if validation_summary:
        prompt += (
            "\nThe previous result was invalid. Generate a new complete object. "
            f"Safe validation summary: {validation_summary}"
        )
    return [
        {
            "role": "system",
            "content": f"{soul}\n\nMandatory output format:\n{format_instruction}",
        },
        {"role": "user", "content": prompt},
    ]


def _validation_summary(exc: Exception) -> str:
    if isinstance(exc, providers.ProviderJSONError):
        return str(exc)
    if isinstance(exc, MaterialValidationError):
        return exc.code
    if isinstance(exc, ValidationError):
        summaries = []
        for item in exc.errors(include_url=False, include_context=False)[:8]:
            location = ".".join(str(part) for part in item["loc"])
            summaries.append(f"{location}:{item['type']}")
        return ";".join(summaries)
    return "invalid_material_section"


def _validate_generated_section(
    payload: dict[str, Any],
    *,
    section_id: str,
    order: int,
    title: str,
    evidence: Sequence[Mapping[str, Any]],
    source_ids: Sequence[str],
) -> MaterialSection:
    generated = _GeneratedSectionContent.model_validate(
        {"blocks": payload.get("blocks")}
    )
    evidence_ids = [
        str(item["id"]) for item in evidence if item.get("id") is not None
    ]
    section = MaterialSection(
        id=section_id,
        order=order,
        title=title,
        status="generated",
        quality=SectionQuality(
            evidence_status="weak",
            evidence_count=len(evidence_ids),
            cited_evidence_count=0,
            citation_coverage=0.0,
        ),
        source_ids=list(source_ids),
        evidence_ids=evidence_ids,
        blocks=generated.blocks,
    )
    evidence_count = len(section.evidence_ids)
    cited_count = len(set(citation_ids_for_section(section)))
    coverage = cited_count / evidence_count if evidence_count else 0.0
    evidence_status = "sufficient" if cited_count else "weak"
    status = "generated" if cited_count else "weak_evidence"
    section = section.model_copy(
        update={
            "status": status,
            "quality": SectionQuality(
                evidence_status=evidence_status,
                evidence_count=evidence_count,
                cited_evidence_count=cited_count,
                citation_coverage=coverage,
            ),
        }
    )
    package = MaterialPackageV2(
        schema_version="material-package.v2",
        package_id="validation",
        service_mode="course_outline",
        title="validation",
        subject="validation",
        language="zh-CN",
        source_ids=list(source_ids),
        sections=[section],
        rendering={
            "default_theme": {
                "theme_id": "clinical-standard",
                "theme_version": "1.0.0",
            }
        },
    )
    validate_material_package(package, evidence, source_ids)
    return section


def _failed_section(
    *,
    section_id: str,
    order: int,
    title: str,
    evidence: Sequence[Mapping[str, Any]],
    source_ids: Sequence[str],
) -> MaterialSection:
    return MaterialSection(
        id=section_id,
        order=order,
        title=title,
        status="failed",
        quality=SectionQuality(
            evidence_status="failed",
            evidence_count=len(evidence),
            cited_evidence_count=0,
            citation_coverage=0.0,
        ),
        source_ids=list(source_ids),
        evidence_ids=[
            str(item["id"]) for item in evidence if item.get("id") is not None
        ],
        blocks=[],
    )


def _weak_evidence_section(
    *,
    section_id: str,
    order: int,
    title: str,
) -> MaterialSection:
    return MaterialSection(
        id=section_id,
        order=order,
        title=title,
        status="weak_evidence",
        quality=SectionQuality(
            evidence_status="weak",
            evidence_count=0,
            cited_evidence_count=0,
            citation_coverage=0.0,
        ),
        source_ids=[],
        evidence_ids=[],
        blocks=[
            {
                "id": f"{section_id}-note-001",
                "type": "callout",
                "variant": "note",
                "runs": [
                    {
                        "type": "text",
                        "text": "当前上传资料不足以支持本节内容。",
                    }
                ],
            }
        ],
    )


def generate_material_section(
    *,
    section_id: str,
    order: int,
    title: str,
    soul: str,
    evidence: Sequence[Mapping[str, Any]],
    source_ids: Sequence[str],
    api_key: str,
    model: str,
    base_url: str = providers.SILICONFLOW_BASE_URL,
) -> MaterialSection:
    if not evidence:
        return _weak_evidence_section(
            section_id=section_id,
            order=order,
            title=title,
        )

    validation_summary: str | None = None
    for attempt in range(2):
        messages = _messages(
            soul=soul,
            section_id=section_id,
            order=order,
            title=title,
            evidence=evidence,
            source_ids=source_ids,
            validation_summary=validation_summary,
        )
        try:
            payload = providers.generate_json_object(
                messages,
                api_key=api_key,
                model=model,
                base_url=base_url,
            )
            return _validate_generated_section(
                payload,
                section_id=section_id,
                order=order,
                title=title,
                evidence=evidence,
                source_ids=source_ids,
            )
        except (
            providers.ProviderJSONError,
            MaterialValidationError,
            ValidationError,
        ) as exc:
            validation_summary = _validation_summary(exc)
            if attempt == 1:
                break

    return _failed_section(
        section_id=section_id,
        order=order,
        title=title,
        evidence=evidence,
        source_ids=source_ids,
    )
