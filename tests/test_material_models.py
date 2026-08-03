import copy
import unittest

from pydantic import ValidationError

from packages.core.jstudy_core.materials.models import (
    LegacyMaterialPackageV1,
    MaterialPackageV2,
)


def valid_package_payload() -> dict:
    return {
        "schema_version": "material-package.v2",
        "package_id": "job-123",
        "service_mode": "course_outline",
        "title": "课程学习资料",
        "subject": "medicine",
        "language": "zh-CN",
        "source_ids": ["S001"],
        "sections": [
            {
                "id": "section-001",
                "order": 1,
                "title": "绪论",
                "status": "generated",
                "quality": {
                    "evidence_status": "sufficient",
                    "evidence_count": 1,
                    "cited_evidence_count": 1,
                    "citation_coverage": 1.0,
                },
                "source_ids": ["S001"],
                "evidence_ids": ["E001"],
                "blocks": [
                    {
                        "id": "heading-001",
                        "type": "heading",
                        "level": 3,
                        "runs": [
                            {"type": "text", "text": "基础"},
                            {"type": "strong", "text": "重点"},
                            {"type": "emphasis", "text": "提示"},
                            {"type": "inline_code", "text": "code"},
                            {"type": "inline_formula", "latex": "x^2"},
                            {"type": "citation", "evidence_id": "E001"},
                        ],
                    },
                    {
                        "id": "paragraph-001",
                        "type": "paragraph",
                        "runs": [{"type": "text", "text": "正文"}],
                    },
                    {
                        "id": "list-001",
                        "type": "list",
                        "ordered": True,
                        "items": [
                            [{"type": "text", "text": "第一项"}],
                            [{"type": "strong", "text": "第二项"}],
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
                                [{"type": "text", "text": "A"}],
                                [{"type": "text", "text": "B"}],
                            ]
                        ],
                    },
                    {
                        "id": "callout-001",
                        "type": "callout",
                        "variant": "key_point",
                        "runs": [{"type": "text", "text": "关键点"}],
                    },
                    {
                        "id": "formula-001",
                        "type": "formula",
                        "latex": "a+b=c",
                    },
                ],
            }
        ],
        "rendering": {
            "default_theme": {
                "theme_id": "clinical-standard",
                "theme_version": "1.0.0",
            }
        },
    }


def valid_legacy_package_payload() -> dict:
    return {
        "type": "material_package",
        "service_mode": "single_courseware",
        "generation_mode": "study",
        "source_files": [
            {
                "source_id": "S001",
                "file_name": "lecture.pdf",
                "page_count": 1,
                "parser_backend": "pymupdf",
            }
        ],
        "sections": [
            {
                "id": "full-material",
                "title": "完整资料",
                "order": 1,
                "status": "generated",
                "quality": {"evidence_count": 1},
                "source_files": ["S001"],
                "evidence_ids": ["E001"],
                "artifact_urls": {"markdown": "result-output.md"},
            }
        ],
    }


class MaterialModelsTest(unittest.TestCase):
    def test_v2_accepts_multi_courseware_without_broadening_legacy_v1(self):
        payload = valid_package_payload()
        payload["service_mode"] = "multi_courseware"
        payload["source_ids"] = ["S001", "S002"]
        payload["sections"][0]["source_ids"] = ["S001"]

        package = MaterialPackageV2.model_validate(payload)
        self.assertEqual(package.service_mode, "multi_courseware")

        legacy = valid_legacy_package_payload()
        legacy["service_mode"] = "multi_courseware"
        with self.assertRaises(ValidationError):
            LegacyMaterialPackageV1.model_validate(legacy)
    def test_valid_package_supports_all_initial_blocks_and_runs(self):
        package = MaterialPackageV2.model_validate(valid_package_payload())

        self.assertEqual(package.schema_version, "material-package.v2")
        self.assertEqual(
            [block.type for block in package.sections[0].blocks],
            ["heading", "paragraph", "list", "table", "callout", "formula"],
        )
        heading = package.sections[0].blocks[0]
        self.assertEqual(
            [run.type for run in heading.runs],
            [
                "text",
                "strong",
                "emphasis",
                "inline_code",
                "inline_formula",
                "citation",
            ],
        )

    def test_unknown_fields_block_and_run_types_are_rejected(self):
        for mutation in (
            lambda payload: payload.update({"raw_html": "<script>x</script>"}),
            lambda payload: payload["rendering"]["default_theme"].update(
                {"css": "body{}"}
            ),
            lambda payload: payload["sections"][0]["blocks"][0].update(
                {"html": "<b>x</b>"}
            ),
            lambda payload: payload["sections"][0]["blocks"][0].update(
                {"type": "iframe"}
            ),
            lambda payload: payload["sections"][0]["blocks"][0]["runs"][0].update(
                {"type": "url"}
            ),
        ):
            with self.subTest(mutation=mutation):
                payload = valid_package_payload()
                mutation(payload)
                with self.assertRaises(ValidationError):
                    MaterialPackageV2.model_validate(payload)

    def test_duplicate_section_identity_and_block_ids_are_rejected(self):
        duplicate_section_id = valid_package_payload()
        second = copy.deepcopy(duplicate_section_id["sections"][0])
        second["order"] = 2
        duplicate_section_id["sections"].append(second)

        duplicate_section_order = valid_package_payload()
        second = copy.deepcopy(duplicate_section_order["sections"][0])
        second["id"] = "section-002"
        duplicate_section_order["sections"].append(second)

        duplicate_block = valid_package_payload()
        duplicate_block["sections"][0]["blocks"].append(
            copy.deepcopy(duplicate_block["sections"][0]["blocks"][0])
        )

        for payload in (
            duplicate_section_id,
            duplicate_section_order,
            duplicate_block,
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    MaterialPackageV2.model_validate(payload)

    def test_heading_callout_and_size_limits_are_enforced(self):
        cases = []

        bad_language = valid_package_payload()
        bad_language["language"] = "not a language tag"
        cases.append(bad_language)

        bad_heading = valid_package_payload()
        bad_heading["sections"][0]["blocks"][0]["level"] = 2
        cases.append(bad_heading)

        bad_callout = valid_package_payload()
        bad_callout["sections"][0]["blocks"][4]["variant"] = "danger"
        cases.append(bad_callout)

        too_many_blocks = valid_package_payload()
        template = too_many_blocks["sections"][0]["blocks"][1]
        too_many_blocks["sections"][0]["blocks"] = [
            {**copy.deepcopy(template), "id": f"paragraph-{index:03d}"}
            for index in range(121)
        ]
        cases.append(too_many_blocks)

        long_run = valid_package_payload()
        long_run["sections"][0]["blocks"][1]["runs"][0]["text"] = "x" * 8001
        cases.append(long_run)

        wide_table = valid_package_payload()
        wide_table["sections"][0]["blocks"][3]["headers"] = [
            [{"type": "text", "text": str(index)}] for index in range(13)
        ]
        wide_table["sections"][0]["blocks"][3]["rows"] = []
        cases.append(wide_table)

        long_table = valid_package_payload()
        row = long_table["sections"][0]["blocks"][3]["rows"][0]
        long_table["sections"][0]["blocks"][3]["rows"] = [
            copy.deepcopy(row) for _ in range(101)
        ]
        cases.append(long_table)

        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    MaterialPackageV2.model_validate(payload)

    def test_only_failed_sections_may_have_no_blocks(self):
        for status in ("generated", "weak_evidence"):
            payload = valid_package_payload()
            payload["sections"][0]["status"] = status
            payload["sections"][0]["blocks"] = []
            with self.subTest(status=status):
                with self.assertRaises(ValidationError):
                    MaterialPackageV2.model_validate(payload)

        failed = valid_package_payload()
        failed["sections"][0]["status"] = "failed"
        failed["sections"][0]["quality"] = {
            "evidence_status": "failed",
            "evidence_count": 0,
            "cited_evidence_count": 0,
            "citation_coverage": 0.0,
        }
        failed["sections"][0]["blocks"] = []

        package = MaterialPackageV2.model_validate(failed)
        self.assertEqual(package.sections[0].status, "failed")

    def test_v2_models_reject_provider_json_type_coercion(self):
        cases = []

        bool_order = valid_package_payload()
        bool_order["sections"][0]["order"] = True
        cases.append(bool_order)

        numeric_string = valid_package_payload()
        numeric_string["sections"][0]["quality"]["evidence_count"] = "1"
        cases.append(numeric_string)

        string_boolean = valid_package_payload()
        string_boolean["sections"][0]["blocks"][2]["ordered"] = "true"
        cases.append(string_boolean)

        string_heading_level = valid_package_payload()
        string_heading_level["sections"][0]["blocks"][0]["level"] = "3"
        cases.append(string_heading_level)

        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    MaterialPackageV2.model_validate(payload)

    def test_legacy_v1_contract_enforces_migration_limits(self):
        too_many_sections = valid_legacy_package_payload()
        template = too_many_sections["sections"][0]
        too_many_sections["sections"] = [
            {
                **copy.deepcopy(template),
                "id": f"section-{index:03d}",
                "order": index,
            }
            for index in range(1, 122)
        ]

        long_title = valid_legacy_package_payload()
        long_title["sections"][0]["title"] = "x" * 501

        too_many_sources = valid_legacy_package_payload()
        too_many_sources["sections"][0]["source_files"] = [
            f"S{index:03d}" for index in range(1, 122)
        ]

        too_many_evidence = valid_legacy_package_payload()
        too_many_evidence["sections"][0]["evidence_ids"] = [
            f"E{index:04d}" for index in range(1001)
        ]

        oversized_quality = valid_legacy_package_payload()
        oversized_quality["sections"][0]["quality"] = {
            "note": "x" * (32 * 1024 + 1)
        }

        too_many_quality_keys = valid_legacy_package_payload()
        too_many_quality_keys["sections"][0]["quality"] = {
            f"key-{index}": index for index in range(65)
        }

        for payload in (
            too_many_sections,
            long_title,
            too_many_sources,
            too_many_evidence,
            oversized_quality,
            too_many_quality_keys,
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    LegacyMaterialPackageV1.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
