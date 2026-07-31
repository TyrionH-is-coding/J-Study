from __future__ import annotations

from collections.abc import Iterable, Mapping
import json
import math
from pathlib import Path
import re
from typing import Any

from .models import CitationRun, MaterialPackageV2, MaterialSection


class MaterialValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
MATERIAL_PACKAGE_MAX_BYTES = 2 * 1024 * 1024


def read_material_package_payload(path: str | Path) -> dict[str, Any]:
    with Path(path).open("rb") as handle:
        raw = handle.read(MATERIAL_PACKAGE_MAX_BYTES + 1)
    if len(raw) > MATERIAL_PACKAGE_MAX_BYTES:
        raise MaterialValidationError(
            "package_too_large",
            "material package exceeds the migration read limit",
        )
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("material package must be an object")
    return payload


def citation_ids_for_section(section: MaterialSection) -> Iterable[str]:
    for block in section.blocks:
        if block.type in {"heading", "paragraph", "callout"}:
            run_groups = [block.runs]
        elif block.type == "list":
            run_groups = block.items
        elif block.type == "table":
            run_groups = [
                *block.headers,
                *(cell for row in block.rows for cell in row),
            ]
        else:
            run_groups = []
        for runs in run_groups:
            for run in runs:
                if isinstance(run, CitationRun):
                    yield run.evidence_id


def _citation_ids(package: MaterialPackageV2) -> Iterable[tuple[str, str]]:
    for section in package.sections:
        for evidence_id in citation_ids_for_section(section):
            yield section.id, evidence_id


def validate_material_package(
    package: MaterialPackageV2,
    evidence: Iterable[Mapping[str, Any]],
    allowed_source_ids: Iterable[str],
    *,
    expected_package_id: str | None = None,
    expected_service_mode: str | None = None,
) -> MaterialPackageV2:
    if (
        expected_package_id is not None
        and package.package_id != expected_package_id
    ):
        raise MaterialValidationError(
            "package_id_mismatch",
            "package identity does not match the current job",
        )
    if (
        expected_service_mode is not None
        and package.service_mode != expected_service_mode
    ):
        raise MaterialValidationError(
            "service_mode_mismatch",
            "package service mode does not match the current job",
        )

    allowed_sources = set(allowed_source_ids)
    package_sources = set(package.source_ids)
    if not package_sources <= allowed_sources:
        raise MaterialValidationError(
            "unknown_source_id",
            "package references a source outside the current job",
        )

    evidence_by_id: dict[str, Mapping[str, Any]] = {}
    for item in evidence:
        if not isinstance(item, Mapping):
            raise MaterialValidationError(
                "invalid_evidence_id",
                "evidence item must be an object with a valid id",
            )
        evidence_id = item.get("id")
        if (
            not isinstance(evidence_id, str)
            or not SAFE_ID_RE.fullmatch(evidence_id)
        ):
            raise MaterialValidationError(
                "invalid_evidence_id",
                "evidence item id is invalid",
            )
        if evidence_id in evidence_by_id:
            raise MaterialValidationError(
                "duplicate_evidence_id",
                "evidence item ids must be unique",
            )
        source_id = item.get("source_id")
        if (
            not isinstance(source_id, str)
            or not SAFE_ID_RE.fullmatch(source_id)
        ):
            raise MaterialValidationError(
                "invalid_evidence_source_id",
                "evidence source identity is invalid",
            )
        if source_id not in allowed_sources:
            raise MaterialValidationError(
                "evidence_source_not_in_job",
                "evidence references a source outside the current job",
            )
        if source_id not in package_sources:
            raise MaterialValidationError(
                "evidence_source_not_in_package",
                "evidence references a source not declared by the package",
            )
        evidence_by_id[evidence_id] = item

    for section in package.sections:
        section_sources = set(section.source_ids)
        if not section_sources <= package_sources:
            raise MaterialValidationError(
                "unknown_source_id",
                "section references a source not declared by the package",
            )
        unknown_evidence = set(section.evidence_ids) - evidence_by_id.keys()
        if unknown_evidence:
            raise MaterialValidationError(
                "unknown_evidence_id",
                "section references evidence outside the current job",
            )
        for evidence_id in section.evidence_ids:
            evidence_source_id = str(evidence_by_id[evidence_id]["source_id"])
            if evidence_source_id not in section_sources:
                raise MaterialValidationError(
                    "evidence_source_not_in_section",
                    "section evidence references an undeclared section source",
                )

    section_evidence = {
        section.id: set(section.evidence_ids) for section in package.sections
    }
    for section_id, evidence_id in _citation_ids(package):
        if evidence_id not in evidence_by_id:
            raise MaterialValidationError(
                "unknown_evidence_id",
                "citation references evidence outside the current job",
            )
        if evidence_id not in section_evidence[section_id]:
            raise MaterialValidationError(
                "undeclared_section_evidence",
                "citation is not declared by its section",
            )

    for section in package.sections:
        citation_ids = set(citation_ids_for_section(section))
        evidence_count = len(section.evidence_ids)
        cited_evidence_count = len(citation_ids)
        citation_coverage = (
            cited_evidence_count / evidence_count if evidence_count else 0.0
        )
        if section.status == "failed":
            expected_status = "failed"
            expected_evidence_status = "failed"
            if cited_evidence_count:
                raise MaterialValidationError(
                    "section_status_mismatch",
                    "failed section cannot contain citations",
                )
        elif cited_evidence_count:
            expected_status = "generated"
            expected_evidence_status = "sufficient"
        else:
            expected_status = "weak_evidence"
            expected_evidence_status = "weak"
        if section.status != expected_status:
            raise MaterialValidationError(
                "section_status_mismatch",
                "section status does not match typed citation coverage",
            )
        quality = section.quality
        if (
            quality.evidence_count != evidence_count
            or quality.cited_evidence_count != cited_evidence_count
            or not math.isclose(
                quality.citation_coverage,
                citation_coverage,
                rel_tol=0.0,
                abs_tol=1e-9,
            )
            or quality.evidence_status != expected_evidence_status
        ):
            raise MaterialValidationError(
                "section_quality_mismatch",
                "section quality does not match typed evidence and citations",
            )
    return package


def audit_material_package(
    package: MaterialPackageV2,
    evidence: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    evidence_ids = {
        str(item["id"]) for item in evidence if item.get("id") is not None
    }
    referenced_ids = {evidence_id for _, evidence_id in _citation_ids(package)}
    known_references = referenced_ids & evidence_ids
    unused_evidence = sorted(evidence_ids - known_references)

    issues: list[dict[str, Any]] = []
    if unused_evidence:
        issues.append(
            {"code": "unused_evidence", "evidence_ids": unused_evidence}
        )
    for section in sorted(package.sections, key=lambda item: item.order):
        if section.status == "weak_evidence":
            issues.append(
                {"code": "weak_evidence_section", "section_id": section.id}
            )
        elif section.status == "failed":
            issues.append({"code": "failed_section", "section_id": section.id})

    if any(issue["code"] == "failed_section" for issue in issues):
        status = "fail"
    elif any(issue["code"] == "weak_evidence_section" for issue in issues):
        status = "warning"
    else:
        status = "pass"

    evidence_count = len(evidence_ids)
    return {
        "status": status,
        "metrics": {
            "section_count": len(package.sections),
            "generated_section_count": sum(
                section.status == "generated" for section in package.sections
            ),
            "evidence_count": evidence_count,
            "referenced_evidence_count": len(known_references),
            "citation_coverage": (
                len(known_references) / evidence_count if evidence_count else 0.0
            ),
        },
        "issues": issues,
    }
