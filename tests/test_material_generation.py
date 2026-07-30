import copy
import unittest
from unittest.mock import patch

from packages.core.jstudy_core.materials.generation import (
    generate_material_section,
)
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
from packages.core.jstudy_core.providers import (
    ProviderJSONError,
    generate_json_object,
)


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

    def test_text_runs_are_not_treated_as_raw_html(self):
        payload = valid_package_payload()
        payload["sections"][0]["blocks"] = [
            {
                "id": "paragraph-unsafe",
                "type": "paragraph",
                "runs": [
                    {
                        "type": "text",
                        "text": "<script>alert('x')</script> & text",
                    }
                ],
            }
        ]
        package = MaterialPackageV2.model_validate(payload)

        markdown = render_compatibility_markdown(package)

        self.assertNotIn("<script>", markdown)
        self.assertIn(
            "&lt;script&gt;alert('x')&lt;/script&gt; &amp; text",
            markdown,
        )


def generated_section_payload() -> dict:
    return {
        "id": "section-001",
        "order": 1,
        "title": "绪论",
        "status": "generated",
        "quality": {
            "evidence_status": "failed",
            "evidence_count": 999,
            "cited_evidence_count": 999,
            "citation_coverage": 0.0,
        },
        "source_ids": ["S001"],
        "evidence_ids": ["E001"],
        "blocks": [
            {
                "id": "paragraph-001",
                "type": "paragraph",
                "runs": [
                    {"type": "text", "text": "事实"},
                    {"type": "citation", "evidence_id": "E001"},
                ],
            }
        ],
    }


class StructuredGenerationTest(unittest.TestCase):
    @patch("packages.core.jstudy_core.providers.siliconflow_post")
    def test_json_provider_requests_json_object_mode(self, post):
        post.return_value = {
            "choices": [{"message": {"content": '{"answer": "ok"}'}}]
        }

        result = generate_json_object(
            [{"role": "user", "content": "return json"}],
            api_key="test-key",
            model="test-model",
        )

        self.assertEqual(result, {"answer": "ok"})
        request_payload = post.call_args.args[1]
        self.assertEqual(
            request_payload["response_format"],
            {"type": "json_object"},
        )

    @patch(
        "packages.core.jstudy_core.materials.generation.providers.generate_json_object"
    )
    def test_valid_json_returns_typed_section_with_direct_quality(self, provider):
        provider.return_value = generated_section_payload()

        section = generate_material_section(
            section_id="section-001",
            order=1,
            title="绪论",
            soul="teaching rules",
            evidence=evidence_items()[:1],
            source_ids=["S001"],
            api_key="test-key",
            model="test-model",
        )

        self.assertEqual(section.id, "section-001")
        self.assertEqual(section.quality.evidence_status, "sufficient")
        self.assertEqual(section.quality.evidence_count, 1)
        self.assertEqual(section.quality.cited_evidence_count, 1)
        self.assertEqual(section.quality.citation_coverage, 1.0)
        provider.assert_called_once()

    @patch(
        "packages.core.jstudy_core.materials.generation.providers.generate_json_object"
    )
    def test_malformed_json_receives_exactly_one_repair_call(self, provider):
        provider.side_effect = [
            ProviderJSONError("invalid_json"),
            generated_section_payload(),
        ]

        section = generate_material_section(
            section_id="section-001",
            order=1,
            title="绪论",
            soul="teaching rules",
            evidence=evidence_items()[:1],
            source_ids=["S001"],
            api_key="test-key",
            model="test-model",
        )

        self.assertEqual(section.status, "generated")
        self.assertEqual(provider.call_count, 2)
        repair_messages = provider.call_args_list[1].args[0]
        self.assertIn("invalid_json", repair_messages[-1]["content"])

    @patch(
        "packages.core.jstudy_core.materials.generation.providers.generate_json_object"
    )
    def test_schema_invalid_result_is_repaired_with_safe_summary(self, provider):
        invalid = generated_section_payload()
        invalid["blocks"][0]["unexpected"] = "PRIVATE-MODEL-TEXT"
        provider.side_effect = [invalid, generated_section_payload()]

        section = generate_material_section(
            section_id="section-001",
            order=1,
            title="绪论",
            soul="teaching rules",
            evidence=evidence_items()[:1],
            source_ids=["S001"],
            api_key="credential-must-not-appear",
            model="test-model",
        )

        self.assertEqual(section.status, "generated")
        repair_messages = provider.call_args_list[1].args[0]
        repair_text = repair_messages[-1]["content"]
        self.assertIn("extra_forbidden", repair_text)
        self.assertNotIn("PRIVATE-MODEL-TEXT", repair_text)
        self.assertNotIn("credential-must-not-appear", repair_text)

    @patch(
        "packages.core.jstudy_core.materials.generation.providers.generate_json_object"
    )
    def test_second_invalid_result_returns_deterministic_failed_section(self, provider):
        provider.side_effect = [
            {"raw": "FIRST-PRIVATE-TEXT"},
            {"raw": "SECOND-PRIVATE-TEXT"},
        ]

        section = generate_material_section(
            section_id="section-001",
            order=1,
            title="绪论",
            soul="teaching rules",
            evidence=evidence_items()[:1],
            source_ids=["S001"],
            api_key="test-key",
            model="test-model",
        )

        self.assertEqual(provider.call_count, 2)
        self.assertEqual(section.status, "failed")
        self.assertEqual(section.blocks, [])
        dumped = str(section.model_dump())
        self.assertNotIn("FIRST-PRIVATE-TEXT", dumped)
        self.assertNotIn("SECOND-PRIVATE-TEXT", dumped)

    @patch(
        "packages.core.jstudy_core.materials.generation.providers.generate_json_object"
    )
    def test_provider_exceptions_propagate_for_worker_retry(self, provider):
        provider.side_effect = RuntimeError("provider unavailable")

        with self.assertRaisesRegex(RuntimeError, "provider unavailable"):
            generate_material_section(
                section_id="section-001",
                order=1,
                title="绪论",
                soul="teaching rules",
                evidence=evidence_items()[:1],
                source_ids=["S001"],
                api_key="test-key",
                model="test-model",
            )
        provider.assert_called_once()

    @patch(
        "packages.core.jstudy_core.materials.generation.providers.generate_json_object"
    )
    def test_no_evidence_returns_deterministic_weak_section_without_provider(self, provider):
        section = generate_material_section(
            section_id="section-001",
            order=1,
            title="绪论",
            soul="teaching rules",
            evidence=[],
            source_ids=[],
            api_key="test-key",
            model="test-model",
        )

        self.assertEqual(section.status, "weak_evidence")
        self.assertEqual(section.quality.evidence_status, "weak")
        self.assertEqual(section.blocks[0].type, "callout")
        provider.assert_not_called()


if __name__ == "__main__":
    unittest.main()
