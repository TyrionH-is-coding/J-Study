from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from packages.core.jstudy_core import providers

from .models import (
    MaterialPackageV2,
    MaterialSection,
    SectionQuality,
)
from .validation import (
    MaterialValidationError,
    citation_ids_for_section,
    validate_material_package,
)


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
    format_contract = {
        "section_id": section_id,
        "order": order,
        "title": title,
        "allowed_source_ids": list(source_ids),
        "allowed_evidence_ids": [
            str(item["id"]) for item in evidence if item.get("id") is not None
        ],
        "block_types": [
            "heading",
            "paragraph",
            "list",
            "table",
            "callout",
            "formula",
        ],
        "inline_run_types": [
            "text",
            "strong",
            "emphasis",
            "inline_code",
            "inline_formula",
            "citation",
        ],
    }
    format_instruction = (
        "Return one JSON object matching the MaterialSection contract. "
        "Use the exact section identity and only the allowed source and evidence ids. "
        "Do not return Markdown, HTML, CSS, URLs, scripts, or wrapper text.\n"
        f"Contract: {json.dumps(format_contract, ensure_ascii=False)}"
    )
    prompt = f"Evidence: {json.dumps(list(evidence), ensure_ascii=False)}"
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
    section = MaterialSection.model_validate(payload)
    if (
        section.id != section_id
        or section.order != order
        or section.title != title
    ):
        raise MaterialValidationError(
            "invalid_section_identity",
            "generated section identity does not match the planned section",
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

    evidence_count = len(section.evidence_ids)
    cited_count = len(set(citation_ids_for_section(section)))
    coverage = cited_count / evidence_count if evidence_count else 0.0
    evidence_status = "sufficient" if cited_count else "weak"
    status = "generated" if cited_count else "weak_evidence"
    return section.model_copy(
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
