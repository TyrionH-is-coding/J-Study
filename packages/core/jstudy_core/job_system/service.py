from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol, Sequence
from uuid import uuid4

from packages.core.jstudy_core.documents.pdf_utility import (
    PdfValidationError,
    pdf_page_count,
    validate_pdf,
)
from packages.core.jstudy_core.job_system.repository import (
    CreateJobCommand,
    JobRepository,
    JobSnapshot,
    JobSourceInput,
    OwnerActiveJobLimitExceededError,
    QueueCapacityExceededError,
    resolve_job_path,
)
from packages.core.jstudy_core.settings import (
    RuntimeSettings,
    RuntimeSettingsProvider,
    load_runtime_settings_snapshot,
)


UPLOAD_CHUNK_BYTES = 64 * 1024
SUPPORTED_SERVICE_MODES = frozenset({"single_courseware", "course_outline"})
SUPPORTED_OUTLINE_SUFFIXES = frozenset({".md", ".txt", ".pdf"})
SUPPORTED_PDF_CONTENT_TYPES = frozenset(
    {"", "application/octet-stream", "application/pdf", "application/x-pdf"}
)
AdmissionErrorCode = Literal[
    "unsupported_service_mode",
    "invalid_outline",
    "outline_too_large",
    "too_many_pdfs",
    "pdf_too_large",
    "total_upload_too_large",
    "invalid_pdf",
    "queue_full",
    "user_active_job_limit",
    "idempotency_conflict",
]


class Upload(Protocol):
    filename: str | None
    content_type: str | None

    async def read(self, size: int = -1) -> bytes: ...


class AdmissionError(ValueError):
    def __init__(self, code: AdmissionErrorCode, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class JobAdmissionRequest:
    owner_user_id: str
    service_mode: str
    scenario_id: str
    parser_profile_id: str
    generation_mode: str | None
    outline: Upload | None
    pdfs: Sequence[Upload]
    idempotency_key: str | None = None
    content_metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class JobSubmissionResult:
    job: JobSnapshot
    created: bool


@dataclass(frozen=True)
class _StoredUpload:
    relative_path: str
    byte_size: int
    sha256: str
    page_count: int | None = None


class _TotalUploadCounter:
    def __init__(self, limit: int):
        self.limit = limit
        self.value = 0

    def add(self, byte_count: int) -> None:
        if self.value + byte_count > self.limit:
            raise AdmissionError(
                "total_upload_too_large",
                "Total upload size exceeds the configured limit.",
            )
        self.value += byte_count


class JobService:
    def __init__(
        self,
        repository: JobRepository,
        settings: RuntimeSettings,
        *,
        settings_provider: RuntimeSettingsProvider | None = None,
    ):
        self.repository = repository
        self.settings = settings
        self.settings_provider = settings_provider or (lambda: settings)

    async def submit(
        self,
        request: JobAdmissionRequest,
        *,
        settings_snapshot: RuntimeSettings | None = None,
    ) -> JobSubmissionResult:
        settings = load_runtime_settings_snapshot(
            self.settings,
            (
                (lambda: settings_snapshot)
                if settings_snapshot is not None
                else self.settings_provider
            ),
        )
        return await JobService(self.repository, settings)._submit_once(request)

    async def _submit_once(
        self,
        request: JobAdmissionRequest,
    ) -> JobSubmissionResult:
        self._validate_request_shape(request)
        job_id = uuid4().hex
        keep_directory = False
        try:
            job_dir = self._create_job_directory(job_id)
            total = _TotalUploadCounter(
                self.settings.max_total_upload_bytes
            )
            outline = await self._store_outline(
                request.outline,
                job_id,
                job_dir,
                total,
            )
            sources = await self._store_sources(
                request.pdfs,
                job_id,
                job_dir,
                total,
            )
            fingerprint = self._request_fingerprint(
                request,
                outline.sha256 if outline is not None else None,
                sources,
            )
            idempotency_key = (
                request.idempotency_key.strip()
                if request.idempotency_key
                else None
            )
            command = CreateJobCommand(
                id=job_id,
                owner_user_id=request.owner_user_id,
                service_mode=request.service_mode,
                scenario_id=request.scenario_id,
                parser_profile_id=request.parser_profile_id,
                generation_mode=request.generation_mode,
                max_attempts=self.settings.worker_max_attempts,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                outline_relative_path=(
                    outline.relative_path if outline is not None else None
                ),
                sources=tuple(
                    JobSourceInput(
                        source_id=f"S{index:03d}",
                        original_filename=self._safe_original_filename(
                            request.pdfs[index - 1].filename,
                            f"S{index:03d}.pdf",
                        ),
                        relative_path=source.relative_path,
                        mime_type="application/pdf",
                        byte_size=source.byte_size,
                        sha256=source.sha256,
                        page_count=source.page_count,
                    )
                    for index, source in enumerate(sources, start=1)
                ),
            )
            try:
                admitted = self.repository.admit_job(
                    command,
                    queue_capacity=self.settings.queue_capacity,
                    owner_active_job_limit=(
                        self.settings.user_active_job_limit
                    ),
                )
            except QueueCapacityExceededError as exc:
                raise AdmissionError(
                    "queue_full",
                    "The job queue is currently full.",
                ) from exc
            except OwnerActiveJobLimitExceededError as exc:
                raise AdmissionError(
                    "user_active_job_limit",
                    "The user already has the maximum number of active jobs.",
                ) from exc
            if not admitted.created:
                return self._resolve_idempotent(admitted.job, fingerprint)
            keep_directory = True
            return JobSubmissionResult(job=admitted.job, created=True)
        finally:
            if not keep_directory:
                self._cleanup_new_job_directory(job_id)

    def _validate_request_shape(self, request: JobAdmissionRequest) -> None:
        if request.service_mode not in SUPPORTED_SERVICE_MODES:
            raise AdmissionError(
                "unsupported_service_mode",
                "The requested service mode is not supported.",
            )

        pdf_count = len(request.pdfs)
        if pdf_count > self.settings.max_pdfs:
            raise AdmissionError(
                "too_many_pdfs",
                "The submission contains too many PDF files.",
            )
        if pdf_count < 1:
            raise AdmissionError(
                "invalid_pdf",
                "At least one valid PDF is required.",
            )

        if request.service_mode == "single_courseware":
            if pdf_count != 1:
                raise AdmissionError(
                    "invalid_pdf",
                    "Single courseware requires exactly one PDF.",
                )
            if request.outline is not None:
                suffix = Path(request.outline.filename or "").suffix.lower()
                if suffix not in SUPPORTED_OUTLINE_SUFFIXES:
                    raise AdmissionError(
                        "invalid_outline",
                        "The outline must be a .md, .txt, or .pdf file.",
                    )
            return

        if request.outline is None:
            raise AdmissionError(
                "invalid_outline",
                "Course outline mode requires an outline.",
            )
        suffix = Path(request.outline.filename or "").suffix.lower()
        if suffix not in SUPPORTED_OUTLINE_SUFFIXES:
            raise AdmissionError(
                "invalid_outline",
                "The outline must be a .md, .txt, or .pdf file.",
            )

    def _create_job_directory(self, job_id: str) -> Path:
        self.settings.jobs_root.mkdir(parents=True, exist_ok=True)
        job_dir = resolve_job_path(self.settings.jobs_root, job_id)
        job_dir.mkdir()
        (job_dir / "inputs").mkdir()
        return job_dir

    async def _store_outline(
        self,
        upload: Upload | None,
        job_id: str,
        job_dir: Path,
        total: _TotalUploadCounter,
    ) -> _StoredUpload | None:
        if upload is None:
            return None
        suffix = Path(upload.filename or "").suffix.lower()
        relative_path = f"{job_id}/inputs/outline{suffix}"
        stored = await self._stream_upload(
            upload,
            job_dir / "inputs" / f"outline{suffix}",
            relative_path,
            self.settings.max_outline_bytes,
            "outline_too_large",
            total,
        )
        if stored.byte_size == 0:
            raise AdmissionError(
                "invalid_outline",
                "The outline must not be empty.",
            )
        destination = job_dir / "inputs" / f"outline{suffix}"
        if suffix in {".md", ".txt"}:
            try:
                destination.read_bytes().decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise AdmissionError(
                    "invalid_outline",
                    "The outline text must be valid UTF-8.",
                ) from exc
        elif suffix == ".pdf":
            try:
                validate_pdf(destination)
            except PdfValidationError as exc:
                raise AdmissionError(
                    "invalid_outline",
                    "The outline PDF is invalid.",
                ) from exc
        return stored

    async def _store_sources(
        self,
        uploads: Sequence[Upload],
        job_id: str,
        job_dir: Path,
        total: _TotalUploadCounter,
    ) -> list[_StoredUpload]:
        stored_sources = []
        for index, upload in enumerate(uploads, start=1):
            content_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
            if content_type not in SUPPORTED_PDF_CONTENT_TYPES:
                raise AdmissionError(
                    "invalid_pdf",
                    "One of the uploaded files is not a PDF.",
                )
            source_id = f"S{index:03d}"
            destination = job_dir / "inputs" / f"{source_id}.pdf"
            stored = await self._stream_upload(
                upload,
                destination,
                f"{job_id}/inputs/{source_id}.pdf",
                self.settings.max_pdf_bytes,
                "pdf_too_large",
                total,
            )
            try:
                validate_pdf(destination)
            except PdfValidationError as exc:
                raise AdmissionError(
                    "invalid_pdf",
                    "One of the uploaded PDFs is invalid.",
                ) from exc
            stored_sources.append(
                _StoredUpload(
                    relative_path=stored.relative_path,
                    byte_size=stored.byte_size,
                    sha256=stored.sha256,
                    page_count=pdf_page_count(destination),
                )
            )
        return stored_sources

    async def _stream_upload(
        self,
        upload: Upload,
        destination: Path,
        relative_path: str,
        byte_limit: int,
        limit_code: str,
        total: _TotalUploadCounter,
    ) -> _StoredUpload:
        digest = hashlib.sha256()
        byte_size = 0
        with destination.open("xb") as output:
            while True:
                chunk = await upload.read(UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                if not isinstance(chunk, bytes):
                    raise TypeError("upload.read() must return bytes")
                if byte_size + len(chunk) > byte_limit:
                    raise AdmissionError(
                        limit_code,
                        "An uploaded file exceeds the configured limit.",
                    )
                total.add(len(chunk))
                output.write(chunk)
                digest.update(chunk)
                byte_size += len(chunk)
        return _StoredUpload(
            relative_path=relative_path,
            byte_size=byte_size,
            sha256=digest.hexdigest(),
        )

    @staticmethod
    def _request_fingerprint(
        request: JobAdmissionRequest,
        outline_sha256: str | None,
        sources: Sequence[_StoredUpload],
    ) -> str:
        payload = {
            "service_mode": request.service_mode,
            "scenario_id": request.scenario_id,
            "parser_profile_id": request.parser_profile_id,
            "generation_mode": request.generation_mode,
            "outline_sha256": outline_sha256,
            "sources": [
                {
                    "source_id": f"S{index:03d}",
                    "sha256": source.sha256,
                }
                for index, source in enumerate(sources, start=1)
            ],
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _resolve_idempotent(
        existing: JobSnapshot,
        fingerprint: str,
    ) -> JobSubmissionResult:
        if existing.request_fingerprint != fingerprint:
            raise AdmissionError(
                "idempotency_conflict",
                "The idempotency key was already used for another request.",
            )
        return JobSubmissionResult(job=existing, created=False)

    @staticmethod
    def _safe_original_filename(
        filename: str | None,
        fallback: str,
    ) -> str:
        value = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        value = value.replace("\x00", "").strip()
        return value or fallback

    def _cleanup_new_job_directory(self, job_id: str) -> None:
        try:
            job_dir = resolve_job_path(self.settings.jobs_root, job_id)
        except (OSError, ValueError):
            return
        if job_dir.exists() and job_dir.is_dir():
            try:
                shutil.rmtree(job_dir)
            except OSError:
                return
