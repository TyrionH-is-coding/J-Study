from __future__ import annotations

import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from packages.core.jstudy_core.documents.mineru_normalizer import (
    MinerUBatchBudget,
    MinerUNormalizationError,
    MinerUNormalizerLimits,
    normalize_mineru_zip,
)


class MinerUNormalizerTest(unittest.TestCase):
    def make_zip(
        self,
        content: object | None,
        *,
        members: dict[str, bytes] | None = None,
        content_name: str = "lecture_content_list.json",
        compression: int = zipfile.ZIP_DEFLATED,
    ) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=compression) as archive:
            if content is not None:
                archive.writestr(content_name, json.dumps(content, ensure_ascii=False))
            archive.writestr("full.md", "# Full output")
            for name, value in (members or {}).items():
                archive.writestr(name, value)
        return buffer.getvalue()

    def normalize(
        self,
        root: Path,
        zip_bytes: bytes,
        *,
        page_count: int = 2,
        limits: MinerUNormalizerLimits = MinerUNormalizerLimits(),
        batch_budget: MinerUBatchBudget | None = None,
    ):
        return normalize_mineru_zip(
            zip_bytes=zip_bytes,
            source_id="S001",
            source_file="lecture.pdf",
            source_sha256="a" * 64,
            source_page_count=page_count,
            parser_version="v4",
            parser_model="vlm",
            provider_trace_id="trace-1",
            artifact_dir=root / "artifacts",
            limits=limits,
            batch_budget=batch_budget,
        )

    def mixed_content(self) -> list[dict[str, object]]:
        return [
            {"type": "text", "text": "Introduction", "text_level": 1, "bbox": [10, 10, 90, 30], "page_idx": 0},
            {"type": "header", "text": "Journal header", "bbox": [0, 0, 100, 5], "page_idx": 0},
            {"type": "text", "text": "Body text", "bbox": [10, 40, 90, 60], "page_idx": 0},
            {"type": "table", "table_body": "| A | B |\n|---|---|\n| 1 | 2 |", "bbox": [10, 70, 90, 120], "page_idx": 0},
            {"type": "equation", "text": "$$E=mc^2$$", "bbox": [10, 130, 90, 150], "page_idx": 0},
            {"type": "list", "list_items": ["First", "Second"], "bbox": [10, 10, 90, 40], "page_idx": 1},
            {"type": "image", "img_path": "images/figure.png", "image_caption": ["Figure 1"], "bbox": [10, 50, 90, 100], "page_idx": 1},
            {"type": "code", "code_body": "print('ok')", "bbox": [10, 110, 90, 150], "page_idx": 1},
        ]

    def test_normalizes_mixed_two_page_content_in_reading_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zip_bytes = self.make_zip(self.mixed_content(), members={"images/figure.png": b"png"})

            document = self.normalize(root, zip_bytes)

            self.assertEqual(document.contract_version, "1")
            self.assertEqual([page.page_number for page in document.pages], [1, 2])
            self.assertEqual([block.kind for block in document.pages[0].blocks], ["title", "text", "table", "formula"])
            self.assertEqual([block.kind for block in document.pages[1].blocks], ["list", "image", "code"])
            self.assertEqual(document.pages[0].blocks[0].block_id, "S001-P001-B001")
            self.assertEqual(document.pages[1].blocks[0].block_id, "S001-P002-B001")
            self.assertNotIn("Journal header", document.pages[0].text)
            self.assertTrue(any("header=1" in warning for warning in document.warnings))
            self.assertTrue((root / "artifacts" / "mineru-original.zip").is_file())
            self.assertEqual((root / "artifacts" / "full.md").read_text(encoding="utf-8"), "# Full output")

    def test_converts_zero_based_page_index_exactly_once(self):
        content = [{"type": "text", "text": "Only page", "page_idx": 0}]
        with tempfile.TemporaryDirectory() as tmp:
            document = self.normalize(Path(tmp), self.make_zip(content), page_count=1)

        self.assertEqual(document.pages[0].page_number, 1)

    def test_preserves_empty_source_pages(self):
        content = [
            {"type": "text", "text": "Page one", "page_idx": 0},
            {"type": "text", "text": "Page three", "page_idx": 2},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            document = self.normalize(Path(tmp), self.make_zip(content), page_count=3)

        self.assertEqual(document.pages[1].text, "")
        self.assertEqual(document.pages[1].blocks, [])

    def test_preserves_table_formula_and_image_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            document = self.normalize(
                Path(tmp),
                self.make_zip(self.mixed_content(), members={"images/figure.png": b"png"}),
            )

        table = document.pages[0].blocks[2]
        formula = document.pages[0].blocks[3]
        image = document.pages[1].blocks[1]
        self.assertIn("| A | B |", table.markdown)
        self.assertEqual(formula.markdown, "$$E=mc^2$$")
        self.assertEqual(image.asset_path, "mineru/images/figure.png")

    def test_deterministic_block_ids(self):
        zip_bytes = self.make_zip(self.mixed_content(), members={"images/figure.png": b"png"})
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            document_a = self.normalize(Path(first), zip_bytes)
            document_b = self.normalize(Path(second), zip_bytes)

        ids_a = [block.block_id for page in document_a.pages for block in page.blocks]
        ids_b = [block.block_id for page in document_b.pages for block in page.blocks]
        self.assertEqual(ids_a, ids_b)

    def test_rejects_malformed_or_out_of_range_content(self):
        cases = {
            "malformed-json": self.make_zip(None, members={"lecture_content_list.json": b"{"}),
            "out-of-range": self.make_zip([{"type": "text", "text": "bad", "page_idx": 2}]),
        }
        for name, zip_bytes in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(MinerUNormalizationError):
                    self.normalize(Path(tmp), zip_bytes, page_count=2)

    def test_rejects_missing_or_multiple_content_lists(self):
        multiple = self.make_zip(
            [],
            members={"other_content_list.json": b"[]"},
        )
        for name, zip_bytes in (("missing", self.make_zip(None)), ("multiple", multiple)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(MinerUNormalizationError):
                    self.normalize(Path(tmp), zip_bytes)

    def test_rejects_traversal_and_absolute_zip_paths(self):
        for member_name in ("../escape.txt", "/absolute.txt", "C:/windows.txt"):
            with self.subTest(member_name=member_name), tempfile.TemporaryDirectory() as tmp:
                zip_bytes = self.make_zip([], members={member_name: b"bad"})
                with self.assertRaises(MinerUNormalizationError):
                    self.normalize(Path(tmp), zip_bytes)

    def test_rejects_windows_drive_ads_unc_and_device_paths(self):
        content = [{"type": "text", "text": "safe", "page_idx": 0}]
        unsafe_names = (
            "C:escape.txt",
            "safe.txt:stream",
            "\\\\server\\share\\escape.txt",
            "\\\\?\\C:\\escape.txt",
            "\\\\.\\C:\\escape.txt",
        )
        for member_name in unsafe_names:
            with self.subTest(member_name=member_name), tempfile.TemporaryDirectory() as tmp:
                zip_bytes = self.make_zip(content, members={member_name: b"bad"})
                with self.assertRaises(MinerUNormalizationError):
                    self.normalize(Path(tmp), zip_bytes, page_count=1)

    def test_rejects_case_insensitive_duplicate_targets(self):
        content = [{"type": "text", "text": "safe", "page_idx": 0}]
        zip_bytes = self.make_zip(
            content,
            members={"Images/Figure.png": b"first", "images/figure.png": b"second"},
        )
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(MinerUNormalizationError):
            self.normalize(Path(tmp), zip_bytes, page_count=1)

    def test_rejects_preexisting_symlink_traversal(self):
        content = [{"type": "text", "text": "safe", "page_idx": 0}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside"
            outside.mkdir()
            extraction_root = root / "artifacts" / "mineru"
            extraction_root.mkdir(parents=True)
            try:
                os.symlink(outside, extraction_root / "images", target_is_directory=True)
            except OSError as exc:
                if os.name != "nt":
                    self.skipTest(f"directory symlink unavailable: {exc}")
                junction = subprocess.run(
                    [
                        "cmd.exe",
                        "/c",
                        "mklink",
                        "/J",
                        str(extraction_root / "images"),
                        str(outside),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(
                    junction.returncode,
                    0,
                    junction.stdout + junction.stderr,
                )

            zip_bytes = self.make_zip(content, members={"images/escape.txt": b"bad"})
            with self.assertRaises(MinerUNormalizationError):
                self.normalize(root, zip_bytes, page_count=1)
            self.assertFalse((outside / "escape.txt").exists())

    def test_extracts_normal_archive_inside_job_root(self):
        content = [{"type": "text", "text": "safe", "page_idx": 0}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zip_bytes = self.make_zip(content, members={"images/figure.png": b"png"})

            document = self.normalize(root, zip_bytes, page_count=1)

            self.assertEqual(document.pages[0].text, "safe")
            self.assertEqual(
                (root / "artifacts" / "mineru" / "images" / "figure.png").read_bytes(),
                b"png",
            )

    def test_rejects_zip_symlink(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("lecture_content_list.json", "[]")
            link = zipfile.ZipInfo("images/link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, "target")

        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(MinerUNormalizationError):
            self.normalize(Path(tmp), buffer.getvalue())

    def test_rejects_decompression_and_member_count_limits(self):
        ratio_zip = self.make_zip([], members={"large.txt": b"0" * 10000})
        count_zip = self.make_zip([], members={"a.txt": b"a", "b.txt": b"b"})
        cases = (
            (ratio_zip, MinerUNormalizerLimits(max_members=10, max_uncompressed_bytes=20000, max_compression_ratio=2.0)),
            (count_zip, MinerUNormalizerLimits(max_members=2, max_uncompressed_bytes=20000, max_compression_ratio=100.0)),
        )
        for zip_bytes, limits in cases:
            with tempfile.TemporaryDirectory() as tmp, self.assertRaises(MinerUNormalizationError):
                self.normalize(Path(tmp), zip_bytes, limits=limits)

    def test_batch_budget_rejects_aggregate_uncompressed_bytes(self):
        content = [{"type": "text", "text": "safe", "page_idx": 0}]
        zip_bytes = self.make_zip(
            content,
            members={"payload.txt": b"x" * 64},
            compression=zipfile.ZIP_STORED,
        )
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            archive_size = sum(info.file_size for info in archive.infolist())
        budget = MinerUBatchBudget(
            max_uncompressed_bytes=archive_size * 2 - 1,
            max_private_bytes=10_000,
        )
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            self.normalize(Path(first), zip_bytes, page_count=1, batch_budget=budget)
            with self.assertRaisesRegex(
                MinerUNormalizationError,
                "batch uncompressed",
            ):
                self.normalize(
                    Path(second),
                    zip_bytes,
                    page_count=1,
                    batch_budget=budget,
                )
            self.assertFalse((Path(second) / "artifacts").exists())

    def test_private_budget_counts_retained_original_zip_bytes(self):
        content = [{"type": "text", "text": "safe", "page_idx": 0}]
        zip_bytes = self.make_zip(
            content,
            compression=zipfile.ZIP_STORED,
        )
        budget = MinerUBatchBudget(
            max_uncompressed_bytes=10_000,
            max_private_bytes=len(zip_bytes) - 1,
        )
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(
            MinerUNormalizationError,
            "private artifact",
        ):
            self.normalize(
                Path(tmp),
                zip_bytes,
                page_count=1,
                batch_budget=budget,
            )

    def test_content_list_has_a_dedicated_bounded_read_limit(self):
        content = [{"type": "text", "text": "safe", "page_idx": 0}]
        limits = MinerUNormalizerLimits(
            max_uncompressed_bytes=10_000,
            max_content_list_bytes=8,
        )
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(
            MinerUNormalizationError,
            "content list exceeds",
        ):
            self.normalize(
                Path(tmp),
                self.make_zip(content, compression=zipfile.ZIP_STORED),
                page_count=1,
                limits=limits,
            )

    def test_normal_members_are_streamed_without_zipfile_read(self):
        content = [{"type": "text", "text": "safe", "page_idx": 0}]
        zip_bytes = self.make_zip(
            content,
            members={"payload.bin": b"streamed"},
            compression=zipfile.ZIP_STORED,
        )
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            zipfile.ZipFile,
            "read",
            side_effect=AssertionError("whole-member read is forbidden"),
        ):
            document = self.normalize(Path(tmp), zip_bytes, page_count=1)

        self.assertEqual(document.pages[0].text, "safe")

    def test_zip_path_is_moved_into_private_artifacts_without_duplicate(self):
        content = [{"type": "text", "text": "safe", "page_idx": 0}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zip_path = root / "download.zip"
            zip_path.write_bytes(
                self.make_zip(content, compression=zipfile.ZIP_STORED)
            )
            normalize_mineru_zip(
                zip_path=zip_path,
                source_id="S001",
                source_file="lecture.pdf",
                source_sha256="a" * 64,
                source_page_count=1,
                parser_version="v4",
                parser_model="vlm",
                provider_trace_id="trace-1",
                artifact_dir=root / "artifacts",
            )

            self.assertFalse(zip_path.exists())
            self.assertTrue(
                (root / "artifacts" / "mineru-original.zip").is_file()
            )

    def test_rejects_empty_content_list_as_typed_normalization_error(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(MinerUNormalizationError):
            self.normalize(Path(tmp), self.make_zip([]))
if __name__ == "__main__":
    unittest.main()
