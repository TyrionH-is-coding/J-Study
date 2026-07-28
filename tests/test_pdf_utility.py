from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import fitz

from packages.core.jstudy_core.documents.pdf_utility import (
    PdfValidationError,
    pdf_page_count,
    pdf_page_metadata,
    pdf_sha256,
    render_pdf_page_png,
    validate_pdf,
)


class PdfUtilityTest(unittest.TestCase):
    def make_pdf(self, path: Path, page_count: int = 2) -> None:
        document = fitz.open()
        for index in range(page_count):
            page = document.new_page(width=320, height=480)
            page.insert_text((40, 60), f"page {index + 1}")
        document.save(path)
        document.close()

    def test_rejects_non_pdf_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "not-pdf.bin"
            path.write_bytes(b"not a pdf")

            with self.assertRaises(PdfValidationError):
                validate_pdf(path)

    def test_rejects_corrupt_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "corrupt.pdf"
            path.write_bytes(b"%PDF-1.7\ncorrupt")

            with self.assertRaises(PdfValidationError):
                validate_pdf(path)

    def test_returns_deterministic_sha256_and_page_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lecture.pdf"
            self.make_pdf(path)

            self.assertEqual(pdf_sha256(path), hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(pdf_page_count(path), 2)

    def test_returns_one_based_page_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lecture.pdf"
            self.make_pdf(path)

            metadata = pdf_page_metadata(path)

            self.assertEqual([item.page_number for item in metadata], [1, 2])
            self.assertEqual(metadata[0].width, 320.0)
            self.assertEqual(metadata[0].height, 480.0)

    def test_rejects_page_zero_and_out_of_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lecture.pdf"
            self.make_pdf(path)

            for page_number in (0, 3):
                with self.subTest(page_number=page_number):
                    with self.assertRaises(PdfValidationError):
                        render_pdf_page_png(path, page_number)

    def test_renders_valid_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lecture.pdf"
            self.make_pdf(path)

            png = render_pdf_page_png(path, 1)

            self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))


if __name__ == "__main__":
    unittest.main()
