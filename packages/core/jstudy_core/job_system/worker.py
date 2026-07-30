from __future__ import annotations

import hashlib
import inspect
import json
import mimetypes
import shutil
import threading
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
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
from packages.core.jstudy_core.parser_profile_router import resolve_parser_profile
from packages.core.jstudy_core.pipeline import run_course_outline, run_mvp
from packages.core.jstudy_core.materials.models import MaterialPackageV2
from packages.core.jstudy_core.materials.validation import (
    validate_material_package,
)
from packages.core.jstudy_core.scenario_router import resolve_scenario
from packages.core.jstudy_core.settings import (
    RuntimeSettings,
    RuntimeSettingsProvider,
    load_runtime_settings_snapshot,
)


Runner = Callable[..., Mapping[str, Path]]
MAINTENANCE_BATCH_SIZE = 10
REQUIRED_PUBLIC_ARTIFACT_KINDS = frozenset(
    {
        ArtifactKind.MARKDOWN,
        ArtifactKind.EVIDENCE,
        ArtifactKind.EVIDENCE_LINKS,
        ArtifactKind.QUALITY,
        ArtifactKind.TRACE,
        ArtifactKind.PACKAGE,
    }
)


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
        settings_provider: RuntimeSettingsProvider | None = None,
    ):
        self.repository = repository
        self.settings = settings
        self.settings_provider = settings_provider or (lambda: settings)
        self.worker_id = worker_id or f"worker-{uuid4().hex}"
        self.single_runner = single_runner
        self.outline_runner = outline_runner

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
            runner, kwargs = self._runner_call(job, heartbeat)
            outputs = runner(**_filter_runner_kwargs(runner, kwargs))
            self._require_current_lease(heartbeat)
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
    ) -> tuple[Runner, dict[str, Any]]:
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
        else:
            raise PermanentJobError(
                "unsupported_service_mode",
                "The job service mode is unsupported.",
            )

        parser_backend, parser_metadata = self._parser_routing(job)
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
            "parser_backend": parser_backend,
            "routing_metadata": {
                "scenario": scenario_metadata,
                "parser_profile": parser_metadata,
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
        }
        return runner, kwargs

    def _parser_routing(
        self,
        job: JobSnapshot,
    ) -> tuple[str, dict[str, Any]]:
        config = self.settings.parser_profiles_config
        if not config.get("profiles"):
            return "pymupdf", {
                "requested_parser_profile_id": job.parser_profile_id,
                "resolved_parser_profile_id": job.parser_profile_id,
                "backend": "pymupdf",
            }
        try:
            resolution = resolve_parser_profile(
                config,
                job.parser_profile_id,
                is_admin=True,
                parser_config=self.settings.parser_config,
            )
        except Exception as exc:
            raise PermanentJobError(
                "invalid_parser_profile",
                "The parser profile is unavailable.",
            ) from exc
        return resolution.backend, resolution.trace_metadata()

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
            digest = hashlib.sha256()
            byte_size = 0
            with verified_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(64 * 1024), b""):
                    digest.update(chunk)
                    byte_size += len(chunk)
            artifacts.append(
                ArtifactInput(
                    kind=kind,
                    relative_path=relative_path,
                    mime_type=(
                        mimetypes.guess_type(verified_path.name)[0]
                        or "application/octet-stream"
                    ),
                    byte_size=byte_size,
                    sha256=digest.hexdigest(),
                )
            )
        return artifacts

    def _build_sections(
        self,
        job: JobSnapshot,
        outputs: Mapping[str, Path],
        markdown_filenames: set[str],
    ) -> list[SectionInput]:
        package_path = outputs.get("package")
        if package_path is None:
            raise PermanentJobError(
                "invalid_job_output",
                "The material package is missing.",
            )
        try:
            package = json.loads(Path(package_path).read_text(encoding="utf-8"))
            if package.get("schema_version") == "material-package.v2":
                return self._build_v2_sections(
                    job,
                    outputs,
                    package,
                    markdown_filenames,
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
    ) -> list[SectionInput]:
        package = MaterialPackageV2.model_validate(payload)
        if package.package_id != job.id:
            raise ValueError("package id does not match job")
        if package.service_mode != job.service_mode:
            raise ValueError("package service mode does not match job")
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
        )
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
            raw_sections = package["sections"]
            if package.get("type") != "material_package":
                raise ValueError("unexpected package type")
            if package.get("service_mode") != job.service_mode:
                raise ValueError("package service mode does not match job")
            if not isinstance(raw_sections, list) or not raw_sections:
                raise ValueError("package sections are missing")

            sections = []
            section_ids: set[str] = set()
            positions: set[int] = set()
            for raw in raw_sections:
                if not isinstance(raw, dict):
                    raise ValueError("package section must be an object")
                section_id = str(raw.get("id") or "").strip()
                title = str(raw.get("title") or "").strip()
                position = raw.get("order")
                status = str(raw.get("status") or "generated").strip()
                quality = raw.get("quality") or {}
                artifacts = (
                    raw.get("artifact_filenames")
                    or raw.get("artifact_urls")
                    or {}
                )
                if (
                    not section_id
                    or not title
                    or isinstance(position, bool)
                    or not isinstance(position, int)
                    or position < 1
                    or not status
                    or not isinstance(quality, dict)
                    or not isinstance(artifacts, dict)
                ):
                    raise ValueError("package section contract is invalid")
                if section_id in section_ids or position in positions:
                    raise ValueError("package section identity is duplicated")
                section_ids.add(section_id)
                positions.add(position)
                artifact_filename = str(
                    artifacts.get("markdown") or ""
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
