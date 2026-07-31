import unittest
from types import SimpleNamespace

from packages.core.jstudy_core.courseware.planning import (
    build_courseware_manifest,
    plan_learning_map,
)
from packages.core.jstudy_core.documents import (
    ParsedBlock,
    ParsedDocument,
    ParsedPage,
)


def document(source_id, pages):
    return ParsedDocument(
        contract_version="1",
        source_id=source_id,
        source_file=f"{source_id}.pdf",
        source_sha256=("a" if source_id == "S001" else "b") * 64,
        parser_name="mineru",
        parser_version="v4",
        parser_model="vlm",
        page_count=len(pages),
        pages=[
            ParsedPage(
                page_number=index,
                text="\n".join(block.text for block in blocks),
                markdown="\n".join(block.markdown for block in blocks),
                blocks=blocks,
            )
            for index, blocks in enumerate(pages, start=1)
        ],
        warnings=[],
        provider_trace_id=f"trace-{source_id}",
    )


def block(source_id, page, number, text, kind="text"):
    return ParsedBlock(
        block_id=f"{source_id}-P{page:03d}-B{number:03d}",
        kind=kind,
        text=text,
        markdown=text,
    )


class CoursewarePlanningTest(unittest.TestCase):
    def sources(self):
        return [
            SimpleNamespace(
                source_id="S001",
                original_filename="late.pdf",
                sha256="a" * 64,
                display_title="Late",
                display_order=2,
                primary_outline_section_id=None,
                title_origin="upload",
                order_origin="upload",
            ),
            SimpleNamespace(
                source_id="S002",
                original_filename="early.pdf",
                sha256="b" * 64,
                display_title="Early",
                display_order=1,
                primary_outline_section_id=None,
                title_origin="upload",
                order_origin="upload",
            ),
        ]

    def test_manifest_preserves_display_order_and_bounds_outline_mapping(self):
        manifest = build_courseware_manifest(
            job_id="job-1",
            service_mode="course_outline",
            sources=self.sources(),
            outline_filename="outline.md",
            outline_sha256="c" * 64,
            outline_text="# First",
        )

        self.assertEqual(
            [source.source_id for source in manifest.ordered_sources()],
            ["S002", "S001"],
        )
        self.assertEqual(
            manifest.ordered_sources()[0].primary_outline_section_id,
            "section-001",
        )
        self.assertIsNone(
            manifest.ordered_sources()[1].primary_outline_section_id
        )

    def test_planner_is_continuous_ordered_and_covers_every_block_once(self):
        manifest = build_courseware_manifest(
            job_id="job-1",
            service_mode="course_outline",
            sources=self.sources(),
            outline_filename=None,
            outline_sha256=None,
            outline_text=None,
        )
        documents = [
            document(
                "S001",
                [
                    [block("S001", 1, 1, "Later source")],
                    [block("S001", 2, 1, "Repeated")],
                ],
            ),
            document(
                "S002",
                [
                    [block("S002", 1, 1, "Cover", "title")],
                    [
                        block("S002", 2, 1, "First heading", "title"),
                        block("S002", 2, 2, "A" * 12),
                    ],
                    [block("S002", 3, 1, "B" * 12)],
                    [
                        block("S002", 4, 1, "Second heading", "title"),
                        block("S002", 4, 2, "Repeated"),
                    ],
                    [block("S002", 5, 1, "", "unsupported")],
                ],
            ),
        ]

        learning_map, coverage = plan_learning_map(
            manifest,
            documents,
            character_budget=20,
        )

        self.assertEqual(
            [unit.primary_source_id for unit in learning_map.units],
            ["S002", "S002", "S002", "S001"],
        )
        self.assertEqual(
            [(unit.page_start, unit.page_end) for unit in learning_map.units],
            [(2, 2), (3, 3), (4, 4), (1, 1)],
        )
        self.assertTrue(
            all(unit.page_start <= unit.page_end for unit in learning_map.units)
        )
        all_blocks = [
            item.block_id
            for parsed in documents
            for page in parsed.pages
            for item in page.blocks
        ]
        self.assertEqual(
            sorted(entry.block_id for entry in coverage.entries),
            sorted(all_blocks),
        )
        self.assertEqual(
            len({entry.block_id for entry in coverage.entries}),
            len(all_blocks),
        )
        self.assertEqual(coverage.metrics.duplicate_block_count, 1)
        self.assertEqual(
            coverage.metrics.usable_block_count,
            (
                coverage.metrics.used_block_count
                + coverage.metrics.ignored_block_count
                + coverage.metrics.duplicate_block_count
                + coverage.metrics.unsupported_block_count
            ),
        )


if __name__ == "__main__":
    unittest.main()
