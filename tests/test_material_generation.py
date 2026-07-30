import copy
import unittest

from packages.core.jstudy_core.materials.compatibility import (
    render_compatibility_markdown,
)
from packages.core.jstudy_core.materials.models import MaterialPackageV2
from packages.core.jstudy_core.materials.validation import (
    MaterialValidationError,
    audit_material_package,
    validate_material_package,
)
from tests.test_material_models import valid_package_payload


def evidence_items() -> list[dict]:
    return [
        {
            "id": "E001",
            "source_id": "S001",
            "source_file": "lecture.pdf",
            "page": 2,
            "chunk_id": "S001-P002-C001",
            "excerpt": "Evidence one",
        },
        {
            "id": "E002",
            "source_id": "S001",
            "source_file": "lecture.pdf",
            "page": 3,
            "chunk_id": "S001-P003-C001",
            "excerpt": "Evidence two",
        },
    ]


class MaterialValidationTest(unittest.TestCase):
    def assert_validation_code(
        self,
        payload: dict,
        expected_code: str,
        *,
        evidence: list[dict] | None = None,
        allowed_source_ids: set[str] | None = None,
    ) -> None:
        package = MaterialPackageV2.model_validate(payload)
        with self.assertRaises(MaterialValidationError) as caught:
            validate_material_package(
                package,
                evidence if evidence is not None else evidence_items(),
                allowed_source_ids
                if allowed_source_ids is not None
                else {"S001"},
            )
        self.assertEqual(caught.exception.code, expected_code)

    def test_rejects_unknown_package_and_section_sources(self):
        package_unknown = valid_package_payload()
        package_unknown["source_ids"] = ["S999"]
        package_unknown["sections"][0]["source_ids"] = ["S999"]
        self.assert_validation_code(package_unknown, "unknown_source_id")

        section_undeclared = valid_package_payload()
        section_undeclared["sections"][0]["source_ids"] = ["S002"]
        self.assert_validation_code(
            section_undeclared,
            "unknown_source_id",
            allowed_source_ids={"S001", "S002"},
        )

    def test_rejects_unknown_and_undeclared_evidence(self):
        unknown = valid_package_payload()
        unknown["sections"][0]["evidence_ids"] = ["E999"]
        unknown["sections"][0]["blocks"][0]["runs"][-1]["evidence_id"] = "E999"
        self.assert_validation_code(unknown, "unknown_evidence_id")

        undeclared = valid_package_payload()
        undeclared["sections"][0]["evidence_ids"] = []
        self.assert_validation_code(undeclared, "undeclared_section_evidence")

    def test_validating_same_payload_preserves_section_identity_and_order(self):
        payload = valid_package_payload()
        second = copy.deepcopy(payload["sections"][0])
        second["id"] = "section-002"
        second["order"] = 2
        second["blocks"] = [
            {
                "id": "paragraph-002",
                "type": "paragraph",
                "runs": [{"type": "text", "text": "第二节"}],
            }
        ]
        payload["sections"].append(second)
        package = MaterialPackageV2.model_validate(payload)

        first = validate_material_package(package, evidence_items(), {"S001"})
        second_result = validate_material_package(package, evidence_items(), {"S001"})

        self.assertEqual(
            [(item.id, item.order) for item in first.sections],
            [("section-001", 1), ("section-002", 2)],
        )
        self.assertEqual(first.model_dump(), second_result.model_dump())

    def test_audit_uses_typed_citations_and_warns_about_unused_evidence(self):
        package = MaterialPackageV2.model_validate(valid_package_payload())
        report = audit_material_package(package, evidence_items())

        self.assertEqual(report["status"], "pass")
        self.assertEqual(
            report["metrics"],
            {
                "section_count": 1,
                "generated_section_count": 1,
                "evidence_count": 2,
                "referenced_evidence_count": 1,
                "citation_coverage": 0.5,
            },
        )
        self.assertEqual(
            report["issues"],
            [{"code": "unused_evidence", "evidence_ids": ["E002"]}],
        )

    def test_audit_reports_weak_and_failed_sections(self):
        payload = valid_package_payload()
        payload["sections"][0]["status"] = "weak_evidence"
        package = MaterialPackageV2.model_validate(payload)
        report = audit_material_package(package, evidence_items()[:1])

        self.assertEqual(report["status"], "warning")
        self.assertEqual(
            report["issues"],
            [{"code": "weak_evidence_section", "section_id": "section-001"}],
        )


class CompatibilityMarkdownTest(unittest.TestCase):
    def test_renders_all_blocks_and_runs_deterministically(self):
        package = MaterialPackageV2.model_validate(valid_package_payload())

        markdown = render_compatibility_markdown(package)

        self.assertEqual(
            markdown,
            """# 课程学习资料

## 绪论

### 基础**重点***提示*`code`$x^2$<!-- evidence: E001 -->

正文

1. 第一项
2. **第二项**

| 项目 | 结论 |
| --- | --- |
| A | B |

> **关键点：** 关键点

$$
a+b=c
$$
""",
        )

    def test_section_order_is_stable(self):
        payload = valid_package_payload()
        second = copy.deepcopy(payload["sections"][0])
        second["id"] = "section-002"
        second["order"] = 2
        second["title"] = "第二章"
        second["blocks"] = [
            {
                "id": "paragraph-002",
                "type": "paragraph",
                "runs": [{"type": "text", "text": "后生成"}],
            }
        ]
        payload["sections"] = [second, payload["sections"][0]]
        package = MaterialPackageV2.model_validate(payload)

        markdown = render_compatibility_markdown(package)

        self.assertLess(markdown.index("## 绪论"), markdown.index("## 第二章"))


if __name__ == "__main__":
    unittest.main()
