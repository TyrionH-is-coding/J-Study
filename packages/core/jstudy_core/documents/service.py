from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Callable

from .mineru_client import (
    MinerUInput,
    MinerUPrecisionClient,
    MinerUProtocolError,
)
from .mineru_normalizer import MinerUBatchBudget, normalize_mineru_zip
from .models import ParsedDocument
from .pdf_utility import (
    PdfValidationError,
    pdf_page_count,
    pdf_sha256,
    validate_pdf,
)


class DocumentServiceError(RuntimeError):
    code = "invalid_mineru_output"


class OutlineTextError(DocumentServiceError):
    code = "invalid_outline"


class SourceIdentityError(DocumentServiceError):
    code = "source_identity_mismatch"


@dataclass(frozen=True)
class DocumentSource:
    source_id: str
    pdf_path: Path
    sha256: str


class MinerUDocumentService:
    def __init__(
        self,
        client: MinerUPrecisionClient,
        *,
        parser_version: str,
        parser_model: str,
        normalizer: Callable[..., ParsedDocument] = normalize_mineru_zip,
    ) -> None:
        self.client = client
        self.parser_version = parser_version
        self.parser_model = parser_model
        self.normalizer = normalizer

    def parse(
        self,
        sources: list[DocumentSource],
        *,
        artifact_root: Path,
    ) -> list[ParsedDocument]:
        if not sources:
            raise DocumentServiceError("at least one document source is required")
        source_ids = [item.source_id for item in sources]
        if len(source_ids) != len(set(source_ids)):
            raise DocumentServiceError("document source ids must be unique")

        page_counts: dict[str, int] = {}
        for source in sources:
            try:
                validate_pdf(source.pdf_path)
                if pdf_sha256(source.pdf_path) != source.sha256:
                    raise SourceIdentityError(
                        "source PDF no longer matches its admission identity"
                    )
                page_counts[source.source_id] = pdf_page_count(source.pdf_path)
            except SourceIdentityError:
                raise
            except PdfValidationError as exc:
                raise DocumentServiceError("source PDF is invalid") from exc

        artifacts = self.client.extract(
            [
                MinerUInput(source_id=item.source_id, path=item.pdf_path)
                for item in sources
            ],
            download_root=artifact_root / "downloads",
        )
        try:
            artifact_by_source = {item.source_id: item for item in artifacts}
            if (
                len(artifact_by_source) != len(artifacts)
                or set(artifact_by_source) != set(source_ids)
            ):
                raise MinerUProtocolError(
                    "MinerU artifacts do not match requested sources"
                )

            documents: dict[str, ParsedDocument] = {}
            batch_budget = MinerUBatchBudget()
            for source in sources:
                artifact = artifact_by_source[source.source_id]
                documents[source.source_id] = self.normalizer(
                    zip_path=artifact.zip_path,
                    source_id=source.source_id,
                    source_file=source.pdf_path.name,
                    source_sha256=source.sha256,
                    source_page_count=page_counts[source.source_id],
                    parser_version=self.parser_version,
                    parser_model=self.parser_model,
                    provider_trace_id=artifact.provider_trace_id,
                    artifact_dir=artifact_root / source.source_id,
                    batch_budget=batch_budget,
                )
            return [documents[source_id] for source_id in source_ids]
        except Exception:
            shutil.rmtree(artifact_root, ignore_errors=True)
            raise
        finally:
            for artifact in artifacts:
                artifact.zip_path.unlink(missing_ok=True)

    def close(self) -> None:
        self.client.close()


def read_text_outline(path: Path, *, max_bytes: int) -> str:
    with path.open("rb") as handle:
        raw = handle.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise OutlineTextError("outline exceeds the configured read limit")
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise OutlineTextError("outline text must be valid UTF-8") from exc
