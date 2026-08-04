from __future__ import annotations

import hashlib
import inspect
import json
import mimetypes
import shutil
import threading
import httpx
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

from packages.core.jstudy_core.job_system.models import ArtifactKind, utc_now
from packages.core.jstudy_core.job_system.repository import (
    ArtifactInput,
    JobRepository,
    JobSnapshot,
    RelativePathError,
    SectionInput,
    StaleWorkerError,
    TransitionEvent,
    resolve_job_path,
)
from packages.core.jstudy_core.job_system.states import JobState
from packages.core.jstudy_core.pipeline import (
    run_course_outline,
    run_multi_courseware,
    run_mvp,
)
from packages.core.jstudy_core.courseware import (
    CoursewareManifestV1,
    CoverageLedgerV1,
    LearningMapV1,
    build_courseware_manifest,
    plan_learning_map,
    validate_courseware_coordination,
    validate_manifest_snapshot,
)
from packages.core.jstudy_core.documents import (
    DocumentServiceError,
    DocumentSource,
    MinerUDocumentService,
    read_text_outline,
)
from packages.core.jstudy_core.documents.mineru_client import (
    MinerUPermanentProviderError,
    MinerUPrecisionClient,
    MinerUProtocolError,
    MinerUProviderError,
    MinerURetryableProviderError,
    MinerUTimeoutError,
)
from packages.core.jstudy_core.documents.mineru_normalizer import (
    MinerUNormalizationError,
)
from packages.core.jstudy_core.materials.models import (
    LegacyMaterialPackageV1,
    MaterialPackageV2,
)
from packages.core.jstudy_core.materials.validation import (
    MATERIAL_PACKAGE_MAX_BYTES,
    MaterialValidationError,
    read_material_package_payload,
    validate_material_package,
    validate_material_package_coordination,
)
from packages.core.jstudy_core.scenario_router import resolve_scenario
from packages.core.jstudy_core.settings import (
    RuntimeSettings,
    RuntimeSettingsProvider,
    load_runtime_settings_snapshot,
)
from packages.core.jstudy_core.storage import write_json


Runner = Callable[..., Mapping[str, Path]]
MAINTENANCE_BATCH_SIZE = 10
ARTIFACT_HASH_CHUNK_BYTES = 64 * 1024
REQUIRED_PUBLIC_ARTIFACT_KINDS = frozenset(
    {
        ArtifactKind.MARKDOWN,
        ArtifactKind.EVIDENCE,
        ArtifactKind.EVIDENCE_LINKS,
        ArtifactKind.QUALITY,
        ArtifactKind.TRACE,
        ArtifactKind.PACKAGE,
        ArtifactKind.MANIFEST,
        ArtifactKind.LEARNING_MAP,
        ArtifactKind.COVERAGE,
    }
)


def _hash_artifact_stream(
    handle: BinaryIO,
    *,
    max_bytes: int | None = None,
) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_size = 0
    while chunk := handle.read(ARTIFACT_HASH_CHUNK_BYTES):
        byte_size += len(chunk)
        if max_bytes is not None and byte_size > max_bytes:
            raise MaterialValidationError(
                "package_too_large",
                "material package exceeds the migration read limit",
            )
        digest.update(chunk)
    return digest.hexdigest(), byte_size


class JobExecutionError(RuntimeError):
    def __init__(self, code: str, public_message: str):
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message


class RetryableJobError(JobExecutionError):
    """A safe, typed failure that may be retried."""


class PermanentJobError(JobExecutionError):
    """A safe, typed failure that must terminate the job."""


class _LeaseHeartbeat:
    def __init__(
        self,
        repository: JobRepository,
        job_id: str,
        worker_id: str,
        lease_seconds: int,
    ):
        self.repository = repository
        self.job_id = job_id
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.stale = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name=f"jstudy-lease-{job_id}",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join()

    def _run(self) -> None:
        interval = max(0.05, self.lease_seconds / 3)
        while not self._stop.wait(interval):
            try:
                renewed = self.repository.renew_lease(
                    self.job_id,
                    self.worker_id,
                    self.lease_seconds,
                )
            except Exception:
                self.stale.set()
                return
            if not renewed:
                self.stale.set()
                return


class JobWorker:
    def __init__(
        self,
        repository: JobRepository,
        settings: RuntimeSettings,
        *,
        worker_id: str | None = None,
        single_runner: Runner = run_mvp,
        outline_runner: Runner = run_course_outline,
        multi_runner: Runner = run_multi_courseware,
        settings_provider: RuntimeSettingsProvider | None = None,
        document_service: Any | None = None,
    ):
        self.repository = repository
        self.settings = settings
        self.settings_provider = settings_provider or (lambda: settings)
        self.worker_id = worker_id or f"worker-{uuid4().hex}"
        self.single_runner = single_runner
        self.outline_runner = outline_runner
        self.multi_runner = multi_runner
        self.document_service = document_service

    def run_once(self) -> bool:
        settings = load_runtime_settings_snapshot(
            self.settings,
            self.settings_provider,
        )
        scoped_worker = JobWorker(
            self.repository,
            settings,
            worker_id=self.worker_id,
            single_runner=self.single_runner,
            outline_runner=self.outline_runner,
            multi_runner=self.multi_runner,
            document_service=self.document_service,
        )
        return scoped_worker._run_once_with_snapshot()

    def _run_once_with_snapshot(self) -> bool:
        now = utc_now()
        self.repository.requeue_expired_leases(now)
        self._cleanup_terminal_jobs(now)
        job = self.repository.claim_next(
            self.worker_id,
            self.settings.worker_lease_seconds,
        )
        if job is None:
            return False

        heartbeat = _LeaseHeartbeat(
            self.repository,
            job.id,
            self.worker_id,
            self.settings.worker_lease_seconds,
        )
        heartbeat.start()
        try:
            runner, kwargs, sequence_outputs, expected_sequence = self._runner_call(
                job,
                heartbeat,
            )
            outputs = {
                **runner(**_filter_runner_kwargs(runner, kwargs)),
                **sequence_outputs,
            }
            self._require_current_lease(heartbeat)
            self._validate_sequence_outputs(
                job,
                outputs,
                expected_sequence=expected_sequence,
            )
            artifacts = self._build_artifacts(job, outputs)
            artifact_kinds = {artifact.kind for artifact in artifacts}
            if not REQUIRED_PUBLIC_ARTIFACT_KINDS.issubset(artifact_kinds):
                raise PermanentJobError(
                    "invalid_job_output",
                    "Required job artifacts are missing.",
                )
            markdown_filenames = {
                Path(artifact.relative_path).name
                for artifact in artifacts
                if artifact.kind is ArtifactKind.MARKDOWN
            }
            sections = self._build_sections(
                job,
                outputs,
                markdown_filenames,
                expected_sequence=expected_sequence,
            )
            self.repository.complete_with_artifacts(
                job.id,
                self.worker_id,
                artifacts,
                sections,
            )
        except StaleWorkerError:
            pass
        except Exception as exc:
            if not heartbeat.stale.is_set():
                self._handle_failure(job.id, exc)
        finally:
            heartbeat.stop()
        return True

    def _cleanup_terminal_jobs(self, now: datetime) -> None:
        if self.settings.job_retention_hours <= 0:
            return
        cutoff = now - timedelta(hours=self.settings.job_retention_hours)
        try:
            jobs = self.repository.list_terminal_before(
                cutoff,
                limit=MAINTENANCE_BATCH_SIZE,
            )
        except Exception:
            return

        for job in jobs:
            try:
                job_dir = self._retention_job_dir(job.id)
                if job_dir.exists():
                    shutil.rmtree(job_dir)
                self.repository.delete_terminal(job.id)
            except (OSError, RelativePathError):
                continue
            except Exception:
                continue

    def _retention_job_dir(self, job_id: str) -> Path:
        jobs_root = Path(self.settings.jobs_root)
        target = resolve_job_path(jobs_root, job_id)
        if target != jobs_root / job_id or target.parent != jobs_root:
            raise RelativePathError("retention path must be the direct job directory")
        if target.exists() and not target.is_dir():
            raise RelativePathError("retention target must be a directory")
        return target

    def run_forever(
        self,
        stop_event: threading.Event | None = None,
    ) -> None:
        stop = stop_event or threading.Event()
        while not stop.is_set():
            if not self.run_once():
                settings = load_runtime_settings_snapshot(
                    self.settings,
                    self.settings_provider,
                )
                stop.wait(settings.worker_poll_seconds)

    def _runner_call(
        self,
        job: JobSnapshot,
        heartbeat: _LeaseHeartbeat,
    ) -> tuple[
        Runner,
        dict[str, Any],
        dict[str, Path],
        tuple[CoursewareManifestV1, LearningMapV1, CoverageLedgerV1],
    ]:
        sources = self.repository.list_sources(job.id)
        if not sources:
            raise PermanentJobError(
                "invalid_job_input",
                "The job has no source PDF.",
            )
        try:
            pdf_paths = [
                resolve_job_path(
                    self.settings.jobs_root,
                    source.relative_path,
                )
                for source in sources
            ]
            outline_path = (
                resolve_job_path(
                    self.settings.jobs_root,
                    job.outline_relative_path,
                )
                if job.outline_relative_path
                else None
            )
            output_dir = resolve_job_path(
                self.settings.jobs_root,
                f"{job.id}/attempts/{job.attempt_count}/output",
            )
        except Exception as exc:
            raise PermanentJobError(
                "invalid_job_input",
                "The job input path is invalid.",
            ) from exc

        if job.service_mode == "course_outline":
            if outline_path is None:
                raise PermanentJobError(
                    "invalid_job_input",
                    "The course outline is missing.",
                )
            runner = self.outline_runner
        elif job.service_mode == "single_courseware":
            runner = self.single_runner
        elif job.service_mode == "multi_courseware":
            runner = self.multi_runner
        else:
            raise PermanentJobError(
                "unsupported_service_mode",
                "The job service mode is unsupported.",
            )

        if outline_path is not None:
            self._verify_outline_snapshot(job, outline_path)
        soul_path, mnemonics_path, scenario_metadata = self._content_routing(job)

        def progress_callback(state: JobState) -> None:
            self._require_current_lease(heartbeat)
            current = self.repository.get(job.id)
            if current is None:
                raise StaleWorkerError("job no longer exists")
            if current.state is state:
                return
            self.repository.transition(
                job.id,
                state,
                TransitionEvent(
                    event=f"pipeline_{state.value}",
                    actor="worker",
                    worker_id=self.worker_id,
                ),
            )

        progress_callback(JobState.PARSING)
        document_sources = [
            DocumentSource(
                source_id=source.source_id,
                pdf_path=pdf_path,
                sha256=source.sha256,
            )
            for source, pdf_path in zip(sources, pdf_paths, strict=True)
        ]
        outline_text = None
        outline_sha256 = None
        outline_filename = None
        parse_sources = list(document_sources)
        if outline_path is not None:
            outline_filename = job.outline_original_filename
            outline_sha256 = job.outline_sha256
            if outline_path.suffix.lower() == ".pdf":
                parse_sources.append(
                    DocumentSource(
                        source_id="__outline__",
                        pdf_path=outline_path,
                        sha256=outline_sha256,
                    )
                )
            else:
                outline_text = read_text_outline(
                    outline_path,
                    max_bytes=self.settings.max_outline_bytes,
                )

        owns_service = self.document_service is None
        service = self.document_service or self._create_document_service()
        try:
            parsed = service.parse(
                parse_sources,
                artifact_root=output_dir.parent / "mineru",
            )
        except MinerUTimeoutError as exc:
            raise RetryableJobError(
                "mineru_timeout",
                "MinerU parsing timed out.",
            ) from exc
        except MinerURetryableProviderError as exc:
            raise RetryableJobError(
                "mineru_provider_error",
                "MinerU parsing is temporarily unavailable.",
            ) from exc
        except (
            MinerUPermanentProviderError,
            MinerUProviderError,
        ) as exc:
            raise PermanentJobError(
                getattr(exc, "code", "mineru_provider_rejected"),
                "MinerU rejected the parsing request.",
            ) from exc
        except (
            DocumentServiceError,
            MinerUProtocolError,
            MinerUNormalizationError,
            ValueError,
        ) as exc:
            raise PermanentJobError(
                getattr(exc, "code", "invalid_mineru_output"),
                "MinerU output is invalid.",
            ) from exc
        finally:
            if owns_service:
                service.close()

        parsed_by_id = {item.source_id: item for item in parsed}
        if "__outline__" in parsed_by_id:
            outline_document = parsed_by_id.pop("__outline__")
            outline_text = "\n".join(
                page.text for page in outline_document.pages if page.text
            )
        parsed_documents = [
            parsed_by_id[source.source_id] for source in sources
        ]
        manifest = build_courseware_manifest(
            job_id=job.id,
            service_mode=job.service_mode,
            sources=sources,
            outline_filename=outline_filename,
            outline_sha256=outline_sha256,
            outline_text=outline_text,
        )
        learning_map, coverage_ledger = plan_learning_map(
            manifest,
            parsed_documents,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        sequence_outputs = {
            "manifest": output_dir / "result-courseware-manifest.json",
            "learning_map": output_dir / "result-learning-map.json",
            "coverage": output_dir / "result-coverage-ledger.json",
        }
        write_json(
            sequence_outputs["manifest"],
            manifest.model_dump(mode="json"),
        )
        write_json(
            sequence_outputs["learning_map"],
            learning_map.model_dump(mode="json"),
        )
        write_json(
            sequence_outputs["coverage"],
            coverage_ledger.model_dump(mode="json"),
        )

        kwargs = {
            "pdf_path": pdf_paths[0],
            "pdf_paths": pdf_paths,
            "outline_path": outline_path,
            "soul_path": soul_path,
            "mnemonics_path": mnemonics_path,
            "api_key_path": self.settings.api_key_path,
            "output_dir": output_dir,
            "chat_model": self.settings.chat_model,
            "embed_model": self.settings.embed_model,
            "output_prefix": "result",
            "package_id": job.id,
            "rag_config": self.settings.rag_config,
            "embedding_cache_path": output_dir.parent / "embedding-cache.json",
            "api_key": self.settings.effective_api_key() or None,
            "chat_base_url": self.settings.chat_base_url,
            "embed_base_url": self.settings.embed_base_url,
            "parser_backend": "mineru",
            "routing_metadata": {
                "scenario": scenario_metadata,
                "parser_profile": {
                    "requested_parser_profile_id": job.parser_profile_id,
                    "resolved_parser_profile_id": "mineru",
                    "backend": "mineru",
                },
            },
            "parser_config": self.settings.parser_config,
            "generation_mode": job.generation_mode or "",
            "service_mode": job.service_mode,
            "source_files": [
                {
                    "source_id": source.source_id,
                    "file_name": source.original_filename,
                }
                for source in sources
            ],
            "progress_callback": progress_callback,
            "parsed_documents": parsed_documents,
            "courseware_manifest": manifest,
            "learning_map": learning_map,
            "coverage_ledger": coverage_ledger,
            "generation_max_concurrency": (
                self.settings.generation_max_concurrency
            ),
        }
        return (
            runner,
            kwargs,
            sequence_outputs,
            (
                manifest.model_copy(deep=True),
                learning_map.model_copy(deep=True),
                coverage_ledger.model_copy(deep=True),
            ),
        )

    def _verify_outline_snapshot(
        self,
        job: JobSnapshot,
        outline_path: Path,
    ) -> None:
        if (
            not job.outline_original_filename
            or not job.outline_sha256
            or job.outline_byte_size is None
            or not job.outline_mime_type
        ):
            raise PermanentJobError(
                "outline_identity_mismatch",
                "The course outline identity is invalid.",
            )
        try:
            if (
                not outline_path.is_file()
                or outline_path.stat().st_size != job.outline_byte_size
                or job.outline_byte_size > self.settings.max_outline_bytes
            ):
                raise ValueError("outline size mismatch")
            digest = hashlib.sha256()
            total = 0
            with outline_path.open("rb") as handle:
                while True:
                    chunk = handle.read(64 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > self.settings.max_outline_bytes:
                        raise ValueError("outline exceeds read limit")
                    digest.update(chunk)
            if digest.hexdigest() != job.outline_sha256:
                raise ValueError("outline hash mismatch")
        except (OSError, ValueError) as exc:
            raise PermanentJobError(
                "outline_identity_mismatch",
                "The course outline no longer matches its admission identity.",
            ) from exc

    def _validate_sequence_outputs(
        self,
        job: JobSnapshot,
        outputs: Mapping[str, Path],
        *,
        expected_sequence: tuple[
            CoursewareManifestV1,
            LearningMapV1,
            CoverageLedgerV1,
        ],
    ) -> None:
        paths = {
            key: outputs.get(key)
            for key in ("manifest", "learning_map", "coverage")
        }
        if any(path is None for path in paths.values()):
            raise PermanentJobError(
                "invalid_job_output",
                "A courseware synchronization artifact is missing.",
            )
        try:
            manifest = CoursewareManifestV1.model_validate_json(
                Path(paths["manifest"]).read_bytes()
            )
            learning_map = LearningMapV1.model_validate_json(
                Path(paths["learning_map"]).read_bytes()
            )
            coverage = CoverageLedgerV1.model_validate_json(
                Path(paths["coverage"]).read_bytes()
            )
            expected_manifest, expected_map, expected_coverage = expected_sequence
            if (
                manifest != expected_manifest
                or learning_map != expected_map
                or coverage != expected_coverage
            ):
                raise ValueError(
                    "courseware synchronization artifacts were mutated"
                )
            validate_manifest_snapshot(
                manifest,
                job=job,
                sources=self.repository.list_sources(job.id),
                expected_manifest=expected_manifest,
            )
            validate_courseware_coordination(
                manifest,
                learning_map,
                coverage,
            )
        except (OSError, UnicodeError, ValueError) as exc:
            raise PermanentJobError(
                "invalid_job_output",
                "The courseware synchronization artifacts are invalid.",
            ) from exc

    def _create_document_service(self) -> MinerUDocumentService:
        if not self.settings.mineru_api_token.strip():
            raise PermanentJobError(
                "mineru_not_configured",
                "MinerU is not configured.",
            )
        client = MinerUPrecisionClient(
            token=self.settings.mineru_api_token,
            config=self.settings.mineru_config,
            client=httpx.Client(),
        )
        return MinerUDocumentService(
            client,
            parser_version="v4",
            parser_model=self.settings.mineru_config.model_version,
        )


    def _content_routing(
        self,
        job: JobSnapshot,
    ) -> tuple[Path, Path, dict[str, Any]]:
        config = self.settings.content_pack_config
        if not config.get("scenarios"):
            return (
                self.settings.soul_path,
                self.settings.mnemonics_path,
                {
                    "requested_scenario_id": job.scenario_id,
                    "resolved_scenario_id": job.scenario_id,
                },
            )
        try:
            resolution = resolve_scenario(config, job.scenario_id)
            soul_path = self.settings.soul_path
            if resolution.scenario_id != self.settings.default_scenario_id:
                configured_soul = resolution.soul_profile.get("soul_path")
                if configured_soul:
                    soul_path = self.settings.project_root / str(
                        configured_soul
                    )
            configured_mnemonics = resolution.content_pack.get(
                "mnemonics_path"
            )
            mnemonics_path = (
                self.settings.project_root / str(configured_mnemonics)
                if configured_mnemonics
                else self.settings.mnemonics_path
            )
        except Exception as exc:
            raise PermanentJobError(
                "invalid_scenario",
                "The job scenario is unavailable.",
            ) from exc
        return soul_path, mnemonics_path, resolution.trace_metadata()

    def _build_artifacts(
        self,
        job: JobSnapshot,
        outputs: Mapping[str, Path],
    ) -> list[ArtifactInput]:
        artifacts = []
        output_root = resolve_job_path(
            self.settings.jobs_root,
            f"{job.id}/attempts/{job.attempt_count}/output",
        )
        for name, value in outputs.items():
            try:
                kind = ArtifactKind(name)
            except ValueError:
                continue
            path = Path(value)
            try:
                relative_to_output = path.resolve(strict=True).relative_to(
                    output_root.resolve(strict=True)
                )
                relative_path = (
                    Path(job.id)
                    / "attempts"
                    / str(job.attempt_count)
                    / "output"
                    / relative_to_output
                ).as_posix()
                verified_path = resolve_job_path(
                    self.settings.jobs_root,
                    relative_path,
                )
            except (FileNotFoundError, ValueError) as exc:
                raise PermanentJobError(
                    "invalid_job_output",
                    "A job artifact path is invalid.",
                ) from exc
            if not verified_path.is_file():
                raise PermanentJobError(
                    "invalid_job_output",
                    "A job artifact is invalid.",
                )
            try:
                with verified_path.open("rb") as handle:
                    sha256, byte_size = _hash_artifact_stream(
                        handle,
                        max_bytes=(
                            MATERIAL_PACKAGE_MAX_BYTES
                            if kind is ArtifactKind.PACKAGE
                            else None
                        ),
                    )
            except MaterialValidationError as exc:
                raise PermanentJobError(
                    "invalid_job_output",
                    "The material package is invalid.",
                ) from exc
            artifacts.append(
                ArtifactInput(
                    kind=kind,
                    relative_path=relative_path,
                    mime_type=(
                        mimetypes.guess_type(verified_path.name)[0]
                        or "application/octet-stream"
                    ),
                    byte_size=byte_size,
                    sha256=sha256,
                )
            )
        return artifacts

    def _build_sections(
        self,
        job: JobSnapshot,
        outputs: Mapping[str, Path],
        markdown_filenames: set[str],
        *,
        expected_sequence: tuple[
            CoursewareManifestV1,
            LearningMapV1,
            CoverageLedgerV1,
        ],
    ) -> list[SectionInput]:
        package_path = outputs.get("package")
        if package_path is None:
            raise PermanentJobError(
                "invalid_job_output",
                "The material package is missing.",
            )
        try:
            package = read_material_package_payload(package_path)
            if package.get("schema_version") == "material-package.v2":
                return self._build_v2_sections(
                    job,
                    outputs,
                    package,
                    markdown_filenames,
                    expected_sequence=expected_sequence,
                )
            if "schema_version" in package:
                raise ValueError("unknown material package schema")
            return self._build_legacy_sections(
                job,
                package,
                markdown_filenames,
            )
        except (
            AttributeError,
            KeyError,
            OSError,
            UnicodeError,
            ValueError,
            TypeError,
        ) as exc:
            raise PermanentJobError(
                "invalid_job_output",
                "The material package is invalid.",
            ) from exc

    def _build_v2_sections(
        self,
        job: JobSnapshot,
        outputs: Mapping[str, Path],
        payload: dict[str, Any],
        markdown_filenames: set[str],
        *,
        expected_sequence: tuple[
            CoursewareManifestV1,
            LearningMapV1,
            CoverageLedgerV1,
        ],
    ) -> list[SectionInput]:
        package = MaterialPackageV2.model_validate(payload)
        if len(markdown_filenames) != 1:
            raise ValueError("v2 package requires one compatibility Markdown")
        evidence_path = outputs.get("evidence")
        if evidence_path is None:
            raise ValueError("package evidence is missing")
        evidence = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
        if not isinstance(evidence, list):
            raise ValueError("package evidence must be a list")
        allowed_source_ids = [
            source.source_id
            for source in self.repository.list_sources(job.id)
        ]
        validate_material_package(
            package,
            evidence,
            allowed_source_ids,
            expected_package_id=job.id,
            expected_service_mode=job.service_mode,
        )
        validate_material_package_coordination(
            package,
            expected_sequence[0],
            expected_sequence[1],
        )
        if all(section.status == "failed" for section in package.sections):
            raise ValueError("all material sections failed")
        markdown_filename = next(iter(markdown_filenames))
        return [
            SectionInput(
                section_id=section.id,
                position=section.order,
                title=section.title,
                status=section.status,
                quality_json=json.dumps(
                    section.quality.model_dump(mode="json"),
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                artifact_filename=markdown_filename,
            )
            for section in sorted(
                package.sections,
                key=lambda item: item.order,
            )
        ]

    def _build_legacy_sections(
        self,
        job: JobSnapshot,
        package: dict[str, Any],
        markdown_filenames: set[str],
    ) -> list[SectionInput]:
        # Legacy v1 remains readable during the Package v2 migration.
        try:
            legacy_package = LegacyMaterialPackageV1.model_validate(package)
            raw_sections = legacy_package.sections
            if legacy_package.service_mode != job.service_mode:
                raise ValueError("package service mode does not match job")

            sections = []
            section_ids: set[str] = set()
            positions: set[int] = set()
            for raw in raw_sections:
                section_id = raw.id.strip()
                title = raw.title.strip()
                position = raw.order
                status = raw.status.strip()
                quality = raw.quality
                artifacts = (
                    raw.artifact_filenames
                    or raw.artifact_urls
                )
                if (
                    not section_id
                    or not title
                    or not status
                    or artifacts is None
                ):
                    raise ValueError("package section contract is invalid")
                if section_id in section_ids or position in positions:
                    raise ValueError("package section identity is duplicated")
                section_ids.add(section_id)
                positions.add(position)
                artifact_filename = str(
                    artifacts.markdown
                ).strip()
                if (
                    not artifact_filename
                    or "/" in artifact_filename
                    or "\\" in artifact_filename
                    or Path(artifact_filename).name != artifact_filename
                    or artifact_filename not in markdown_filenames
                ):
                    raise ValueError("section artifact filename is invalid")
                sections.append(
                    SectionInput(
                        section_id=section_id,
                        position=position,
                        title=title,
                        status=status,
                        quality_json=json.dumps(
                            quality,
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        artifact_filename=artifact_filename,
                    )
                )
            return sections
        except (
            AttributeError,
            KeyError,
            OSError,
            UnicodeError,
            ValueError,
            TypeError,
        ) as exc:
            raise ValueError("legacy material package is invalid") from exc

    def _handle_failure(self, job_id: str, exc: Exception) -> None:
        current = self.repository.get(job_id)
        if current is None or current.state not in {
            JobState.PARSING,
            JobState.RETRIEVING,
            JobState.GENERATING,
            JobState.PACKAGING,
        }:
            return

        if isinstance(exc, JobExecutionError):
            code = exc.code
            message = exc.public_message
            retryable = isinstance(exc, RetryableJobError)
        else:
            code = "worker_error"
            message = "The job could not be processed."
            retryable = True

        should_retry = retryable and current.attempt_count < current.max_attempts
        try:
            self.repository.transition(
                job_id,
                JobState.QUEUED if should_retry else JobState.FAILED,
                TransitionEvent(
                    event="worker_retry" if should_retry else "worker_failed",
                    actor="worker",
                    worker_id=self.worker_id,
                    allow_retry=should_retry,
                    error_code=None if should_retry else code,
                    error_message=None if should_retry else message,
                ),
            )
        except StaleWorkerError:
            return

    @staticmethod
    def _require_current_lease(heartbeat: _LeaseHeartbeat) -> None:
        if heartbeat.stale.is_set():
            raise StaleWorkerError("worker lease is stale")


def _filter_runner_kwargs(
    runner: Runner,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    signature = inspect.signature(runner)
    positional_only = {
        name
        for name, parameter in signature.parameters.items()
        if parameter.kind is inspect.Parameter.POSITIONAL_ONLY
    }
    if any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    ):
        return {
            name: value
            for name, value in kwargs.items()
            if name not in positional_only
        }
    return {
        name: value
        for name, value in kwargs.items()
        if name in signature.parameters
        and signature.parameters[name].kind
        in {
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        }
    }
