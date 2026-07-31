import copy
import unittest

from pydantic import ValidationError

from packages.core.jstudy_core.courseware import (
    CoursewareManifestV1,
    CoverageLedgerV1,
    LearningMapV1,
)


def manifest_payload():
    return {
        "schema_version": "courseware-manifest.v1",
        "manifest_id": "job-1",
        "job_id": "job-1",
        "service_mode": "course_outline",
        "outline": None,
        "sources": [
            {
                "source_id": "S001",
                "original_filename": "b.pdf",
                "sha256": "a" * 64,
                "display_title": "球菌",
                "display_order": 2,
                "primary_outline_section_id": None,
                "title_origin": "user",
                "order_origin": "user",
            },
            {
                "source_id": "S002",
                "original_filename": "a.pdf",
                "sha256": "b" * 64,
                "display_title": "绪论",
                "display_order": 1,
                "primary_outline_section_id": None,
                "title_origin": "auto",
                "order_origin": "auto",
            },
        ],
    }


def learning_map_payload():
    return {
        "schema_version": "learning-map.v1",
        "manifest_id": "job-1",
        "units": [
            {
                "id": "unit-001",
                "order": 1,
                "outline_section_id": None,
                "primary_source_id": "S002",
                "page_start": 1,
                "page_end": 2,
                "block_ids": ["S002-P001-B001", "S002-P002-B001"],
                "material_section_id": "unit-001",
            }
        ],
    }


def coverage_payload():
    return {
        "schema_version": "coverage-ledger.v1",
        "manifest_id": "job-1",
        "entries": [
            {
                "block_id": "S002-P001-B001",
                "source_id": "S002",
                "page_number": 1,
                "disposition": "used",
                "reason": "learning_unit",
                "learning_unit_id": "unit-001",
            }
        ],
        "metrics": {
            "usable_block_count": 1,
            "used_block_count": 1,
            "ignored_block_count": 0,
            "duplicate_block_count": 0,
            "unsupported_block_count": 0,
            "coverage_rate": 1.0,
            "ignored_reason_counts": {},
            "primary_backward_jump_count": 0,
            "large_jump_count": 0,
            "remote_reference_ratio": 0.0,
            "page_distance_p90": 0.0,
        },
    }


class CoursewareModelsTest(unittest.TestCase):
    def test_manifest_keeps_identity_separate_from_display_order(self):
        manifest = CoursewareManifestV1.model_validate(manifest_payload())

        self.assertEqual(
            [item.source_id for item in manifest.ordered_sources()],
            ["S002", "S001"],
        )
        self.assertEqual(manifest.sources[0].source_id, "S001")

    def test_manifest_rejects_duplicate_identity_order_and_invalid_fields(self):
        cases = []
        duplicate_id = manifest_payload()
        duplicate_id["sources"][1]["source_id"] = "S001"
        cases.append(duplicate_id)
        duplicate_order = manifest_payload()
        duplicate_order["sources"][1]["display_order"] = 2
        cases.append(duplicate_order)
        malformed_sha = manifest_payload()
        malformed_sha["sources"][0]["sha256"] = "bad"
        cases.append(malformed_sha)
        unsupported_origin = manifest_payload()
        unsupported_origin["sources"][0]["title_origin"] = "model"
        cases.append(unsupported_origin)

        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    CoursewareManifestV1.model_validate(payload)

    def test_learning_map_rejects_invalid_span_and_cross_source_block(self):
        invalid_span = learning_map_payload()
        invalid_span["units"][0]["page_start"] = 3
        cross_source = learning_map_payload()
        cross_source["units"][0]["block_ids"] = ["S001-P001-B001"]

        for payload in (invalid_span, cross_source):
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    LearningMapV1.model_validate(payload)

    def test_coverage_rejects_duplicate_block_disposition(self):
        payload = coverage_payload()
        payload["entries"].append(copy.deepcopy(payload["entries"][0]))

        with self.assertRaises(ValidationError):
            CoverageLedgerV1.model_validate(payload)

    def test_coverage_rejects_block_source_and_page_mismatch(self):
        for field, value in (
            ("source_id", "S999"),
            ("page_number", 99),
        ):
            payload = coverage_payload()
            payload["entries"][0][field] = value
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    CoverageLedgerV1.model_validate(payload)

    def test_coverage_rejects_ignored_reason_metric_mismatch(self):
        payload = coverage_payload()
        payload["entries"][0].update(
            {
                "disposition": "ignored",
                "reason": "cover_page",
                "learning_unit_id": None,
            }
        )
        payload["metrics"].update(
            {
                "used_block_count": 0,
                "ignored_block_count": 1,
                "coverage_rate": 0.0,
                "ignored_reason_counts": {"wrong_reason": 1},
            }
        )

        with self.assertRaises(ValidationError):
            CoverageLedgerV1.model_validate(payload)

    def test_strict_integer_and_boolean_coercion_is_rejected(self):
        manifest = manifest_payload()
        manifest["sources"][0]["display_order"] = "2"
        learning_map = learning_map_payload()
        learning_map["units"][0]["page_start"] = True
        coverage = coverage_payload()
        coverage["metrics"]["used_block_count"] = "1"

        for model, payload in (
            (CoursewareManifestV1, manifest),
            (LearningMapV1, learning_map),
            (CoverageLedgerV1, coverage),
        ):
            with self.subTest(model=model.__name__):
                with self.assertRaises(ValidationError):
                    model.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
