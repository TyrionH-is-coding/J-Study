from __future__ import annotations

import hashlib
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import fitz


class PdfValidationError(ValueError):
    """A file cannot be used as a valid source PDF."""


@dataclass(frozen=True)
class PdfPageMetadata:
    page_number: int
    width: float
    height: float


def _require_pdf_header(path: Path) -> None:
    try:
        with path.open("rb") as handle:
            header = handle.read(5)
    except OSError as exc:
        raise PdfValidationError(f"PDF cannot be read: {path.name}") from exc
    if header != b"%PDF-":
        raise PdfValidationError("file does not have a PDF header")


@contextmanager
def _open_pdf(path: Path) -> Iterator[fitz.Document]:
    _require_pdf_header(path)
    try:
        document = fitz.open(str(path))
        if document.needs_pass:
            raise PdfValidationError("encrypted PDF requires a password")
        if len(document) < 1:
            raise PdfValidationError("PDF contains no pages")
        yield document
    except PdfValidationError:
        raise
    except (fitz.FileDataError, RuntimeError, OSError, ValueError) as exc:
        raise PdfValidationError("PDF is corrupt or unreadable") from exc
    finally:
        if "document" in locals():
            document.close()


def validate_pdf(path: Path) -> None:
    with _open_pdf(path):
        return


def pdf_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PdfValidationError(f"PDF cannot be read: {path.name}") from exc
    return digest.hexdigest()


def pdf_page_count(path: Path) -> int:
    with _open_pdf(path) as document:
        return len(document)


def pdf_page_metadata(path: Path) -> list[PdfPageMetadata]:
    with _open_pdf(path) as document:
        return [
            PdfPageMetadata(
                page_number=index + 1,
                width=round(page.rect.width, 2),
                height=round(page.rect.height, 2),
            )
            for index, page in enumerate(document)
        ]


def render_pdf_page_png(path: Path, page_number: int) -> bytes:
    with _open_pdf(path) as document:
        if page_number < 1 or page_number > len(document):
            raise PdfValidationError("PDF page number is out of range")
        page = document.load_page(page_number - 1)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
        return pixmap.tobytes("png")
