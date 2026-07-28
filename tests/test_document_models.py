from __future__ import annotations

import unittest

from packages.core.jstudy_core.documents.models import (
    DocumentContractError,
    ParsedBlock,
    ParsedDocument,
    ParsedPage,
)


def make_page(page_number: int, block_id: str | None = None) -> ParsedPage:
    text = f"page {page_number}"
    blocks = []
    if block_id:
        blocks.append(
            ParsedBlock(
                block_id=block_id,
                kind="text",
                text=text,
                markdown=text,
            )
        )
    return ParsedPage(
        page_number=page_number,
        text=text,
        markdown=text,
        blocks=blocks,
    )


def make_document(*, pages: list[ParsedPage], page_count: int | None = None) -> ParsedDocument:
    return ParsedDocument(
        contract_version="1",
        source_id="S001",
        source_file="lecture.pdf",
        source_sha256="a" * 64,
        parser_name="mineru",
        parser_version="v4",
        parser_model="vlm",
        page_count=page_count if page_count is not None else len(pages),
        pages=pages,
        warnings=[],
        provider_trace_id="batch-123",
    )


class DocumentModelsTest(unittest.TestCase):
    def test_accepts_one_based_pages_and_empty_source_page(self):
        document = make_document(
            pages=[
                make_page(1, "S001-P001-B001"),
                ParsedPage(page_number=2, text="", markdown="", blocks=[]),
            ]
        )

        self.assertEqual(document.contract_version, "1")
        self.assertEqual(document.pages[1].page_number, 2)
        self.assertEqual(document.pages[1].blocks, [])

    def test_rejects_zero_based_page_number(self):
        with self.assertRaises(DocumentContractError):
            make_page(0)

    def test_rejects_duplicate_or_out_of_order_page_numbers(self):
        with self.subTest("duplicate"):
            with self.assertRaises(DocumentContractError):
                make_document(pages=[make_page(1), make_page(1)], page_count=2)

        with self.subTest("out-of-order"):
            with self.assertRaises(DocumentContractError):
                make_document(pages=[make_page(2), make_page(1)], page_count=2)

    def test_rejects_page_count_that_does_not_cover_source_pages(self):
        with self.assertRaises(DocumentContractError):
            make_document(pages=[make_page(1)], page_count=2)

    def test_rejects_empty_document_with_typed_error(self):
        with self.assertRaises(DocumentContractError):
            make_document(pages=[], page_count=0)

    def test_rejects_duplicate_block_ids(self):
        with self.assertRaises(DocumentContractError):
            make_document(
                pages=[
                    make_page(1, "S001-P001-B001"),
                    make_page(2, "S001-P001-B001"),
                ]
            )

    def test_rejects_missing_jstudy_source_identity(self):
        with self.assertRaises(DocumentContractError):
            ParsedDocument(
                contract_version="1",
                source_id=" ",
                source_file="lecture.pdf",
                source_sha256="a" * 64,
                parser_name="mineru",
                parser_version="v4",
                parser_model="vlm",
                page_count=1,
                pages=[make_page(1)],
                warnings=[],
                provider_trace_id="batch-123",
            )

    def test_rejects_non_v1_contract(self):
        with self.assertRaises(DocumentContractError):
            ParsedDocument(
                contract_version="2",
                source_id="S001",
                source_file="lecture.pdf",
                source_sha256="a" * 64,
                parser_name="mineru",
                parser_version="v4",
                parser_model="vlm",
                page_count=1,
                pages=[make_page(1)],
                warnings=[],
                provider_trace_id="batch-123",
            )

    def test_bbox_requires_four_finite_ordered_coordinates(self):
        invalid_bboxes = [
            (0.0, 0.0, 1.0),
            (0.0, 0.0, float("inf"), 1.0),
            (2.0, 0.0, 1.0, 1.0),
            (0.0, 2.0, 1.0, 1.0),
        ]

        for bbox in invalid_bboxes:
            with self.subTest(bbox=bbox):
                with self.assertRaises(DocumentContractError):
                    ParsedBlock(
                        block_id="S001-P001-B001",
                        kind="text",
                        text="body",
                        markdown="body",
                        bbox=bbox,
                    )


if __name__ == "__main__":
    unittest.main()
