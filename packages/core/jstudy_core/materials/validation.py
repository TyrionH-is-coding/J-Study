from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .models import CitationRun, MaterialPackageV2


class MaterialValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _citation_ids(package: MaterialPackageV2) -> Iterable[tuple[str, str]]:
    for section in package.sections:
        for block in section.blocks:
            if block.type in {"heading", "paragraph", "callout"}:
                run_groups = [block.runs]
            elif block.type == "list":
                run_groups = block.items
            elif block.type == "table":
                run_groups = [*block.headers, *(cell for row in block.rows for cell in row)]
            else:
                run_groups = []
            for runs in run_groups:
                for run in runs:
                    if isinstance(run, CitationRun):
                        yield section.id, run.evidence_id


def validate_material_package(
    package: MaterialPackageV2,
    evidence: Iterable[Mapping[str, Any]],
    allowed_source_ids: Iterable[str],
) -> MaterialPackageV2:
    allowed_sources = set(allowed_source_ids)
    package_sources = set(package.source_ids)
    if not package_sources <= allowed_sources:
        raise MaterialValidationError(
            "unknown_source_id",
            "package references a source outside the current job",
        )

    evidence_by_id = {
        str(item["id"]): item
        for item in evidence
        if item.get("id") is not None
    }
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
