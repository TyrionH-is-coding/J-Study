import tempfile
import unittest
from pathlib import Path

import fitz

from packages.core.jstudy_core.documents import ParsedDocument, ParsedPage
from packages.core.jstudy_core.documents.mineru_client import (
    MinerUArtifact,
    MinerUTimeoutError,
)
from packages.core.jstudy_core.documents.pdf_utility import pdf_sha256
from packages.core.jstudy_core.documents.service import (
    DocumentSource,
    MinerUDocumentService,
    SourceIdentityError,
    OutlineTextError,
    read_text_outline,
)


def make_pdf(path: Path, pages: int) -> None:
    document = fitz.open()
    for index in range(pages):
        page = document.new_page()
        page.insert_text((40, 80), f"Page {index + 1}")
    document.save(path)
    document.close()


class FakeClient:
    def __init__(self, artifacts=None, error=None):
        self.artifacts = artifacts or []
        self.error = error
        self.calls = []

    def extract(self, inputs, *, download_root):
        self.calls.append((inputs, download_root))
        if self.error is not None:
            raise self.error
        return self.artifacts


class DocumentServiceTest(unittest.TestCase):
    def test_batches_stable_ids_and_restores_requested_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.pdf"
            second = root / "second.pdf"
            make_pdf(first, 2)
            make_pdf(second, 1)
            sources = [
                DocumentSource("S002", second, pdf_sha256(second)),
                DocumentSource("S001", first, pdf_sha256(first)),
            ]
            client = FakeClient(
                [
                    MinerUArtifact(
                        "S001",
                        "first.pdf",
                        root / "S001.zip",
                        "trace-1",
                    ),
                    MinerUArtifact(
                        "S002",
                        "second.pdf",
                        root / "S002.zip",
                        "trace-2",
                    ),
                ]
            )
            (root / "S001.zip").write_bytes(b"one")
            (root / "S002.zip").write_bytes(b"two")
            normalizer_calls = []

            def normalizer(**kwargs):
                normalizer_calls.append(kwargs)
                return ParsedDocument(
                    contract_version="1",
                    source_id=kwargs["source_id"],
                    source_file=kwargs["source_file"],
                    source_sha256=kwargs["source_sha256"],
                    parser_name="mineru",
                    parser_version=kwargs["parser_version"],
                    parser_model=kwargs["parser_model"],
                    page_count=kwargs["source_page_count"],
                    pages=[
                        ParsedPage(index, "", "", [])
                        for index in range(
                            1,
                            kwargs["source_page_count"] + 1,
                        )
                    ],
                    warnings=[],
                    provider_trace_id=kwargs["provider_trace_id"],
                )

            service = MinerUDocumentService(
                client,
                parser_version="v4",
                parser_model="vlm",
                normalizer=normalizer,
            )
            documents = service.parse(
                sources,
                artifact_root=root / "artifacts",
            )

        self.assertEqual(len(client.calls), 1)
        self.assertEqual(
            [item.source_id for item in client.calls[0][0]],
            ["S002", "S001"],
        )
        self.assertEqual(
            client.calls[0][1].name,
            "downloads",
        )
        self.assertEqual(
            [item.source_id for item in documents],
            ["S002", "S001"],
        )
        by_source = {item["source_id"]: item for item in normalizer_calls}
        self.assertEqual(by_source["S001"]["source_page_count"], 2)
        self.assertEqual(by_source["S002"]["source_page_count"], 1)
        self.assertEqual(
            by_source["S001"]["artifact_dir"].name,
            "S001",
        )
        self.assertIn("zip_path", by_source["S001"])
        self.assertNotIn("zip_bytes", by_source["S001"])

    def test_timeout_error_remains_typed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "source.pdf"
            make_pdf(pdf, 1)
            service = MinerUDocumentService(
                FakeClient(error=MinerUTimeoutError("timeout")),
                parser_version="v4",
                parser_model="vlm",
            )
            with self.assertRaises(MinerUTimeoutError):
                service.parse(
                    [DocumentSource("S001", pdf, pdf_sha256(pdf))],
                    artifact_root=root / "artifacts",
                )

    def test_normalization_failure_cleans_all_downloaded_zip_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.pdf"
            second = root / "second.pdf"
            make_pdf(first, 1)
            make_pdf(second, 1)
            first_zip = root / "first.zip"
            second_zip = root / "second.zip"
            first_zip.write_bytes(b"first")
            second_zip.write_bytes(b"second")
            service = MinerUDocumentService(
                FakeClient(
                    [
                        MinerUArtifact(
                            "S001",
                            "first.pdf",
                            first_zip,
                            "trace-1",
                        ),
                        MinerUArtifact(
                            "S002",
                            "second.pdf",
                            second_zip,
                            "trace-2",
                        ),
                    ]
                ),
                parser_version="v4",
                parser_model="vlm",
                normalizer=lambda **_kwargs: (_ for _ in ()).throw(
                    ValueError("invalid archive")
                ),
            )

            with self.assertRaisesRegex(ValueError, "invalid archive"):
                service.parse(
                    [
                        DocumentSource("S001", first, pdf_sha256(first)),
                        DocumentSource("S002", second, pdf_sha256(second)),
                    ],
                    artifact_root=root / "artifacts",
                )

            self.assertFalse(first_zip.exists())
            self.assertFalse(second_zip.exists())

    def test_rejects_source_content_that_no_longer_matches_admission_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "source.pdf"
            make_pdf(pdf, 1)
            client = FakeClient()
            service = MinerUDocumentService(
                client,
                parser_version="v4",
                parser_model="vlm",
            )

            with self.assertRaises(SourceIdentityError):
                service.parse(
                    [DocumentSource("S001", pdf, "0" * 64)],
                    artifact_root=root / "artifacts",
                )

        self.assertEqual(client.calls, [])

    def test_text_outline_is_bounded_and_strict_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid = root / "outline.md"
            valid.write_text("# 第一章", encoding="utf-8")
            self.assertEqual(
                read_text_outline(valid, max_bytes=64),
                "# 第一章",
            )

            invalid = root / "invalid.txt"
            invalid.write_bytes(b"\xff\xfe")
            with self.assertRaises(OutlineTextError):
                read_text_outline(invalid, max_bytes=64)

            oversized = root / "large.md"
            oversized.write_bytes(b"x" * 65)
            with self.assertRaises(OutlineTextError):
                read_text_outline(oversized, max_bytes=64)


if __name__ == "__main__":
    unittest.main()
