from __future__ import annotations

import stat
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import Engine, delete, func, text, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from packages.core.jstudy_core.job_system.models import (
    ArtifactKind,
    Job,
    JobArtifact,
    JobSection,
    JobSource,
    JobTransition,
    RelativePathError,
    normalize_relative_path,
    utc_now,
)
from packages.core.jstudy_core.job_system.states import (
    JobState,
    is_terminal,
    progress_for,
    require_transition,
)


class JobNotFoundError(LookupError):
    """A requested durable job does not exist."""


class StaleWorkerError(RuntimeError):
    """A worker no longer owns the job lease."""


class IdempotencyKeyCollisionError(RuntimeError):
    """A concurrent insert won an owner-scoped idempotency key."""


class QueueCapacityExceededError(RuntimeError):
    """The durable queued-job capacity is exhausted."""


class OwnerActiveJobLimitExceededError(RuntimeError):
    """The owner already has the maximum number of active jobs."""


ADMISSION_LOCK_KEY = 0x4A535406
ACTIVE_JOB_STATES = (
    JobState.QUEUED,
    JobState.PARSING,
    JobState.RETRIEVING,
    JobState.GENERATING,
    JobState.PACKAGING,
)


@dataclass(frozen=True)
class JobSourceInput:
    source_id: str
    original_filename: str
    relative_path: str
    mime_type: str
    byte_size: int
    sha256: str
    page_count: int | None = None


@dataclass(frozen=True)
class SectionInput:
    section_id: str
    position: int
    title: str
    status: str = "pending"
    quality_json: str = "{}"
    artifact_filename: str | None = None


@dataclass(frozen=True)
class CreateJobCommand:
    id: str
    owner_user_id: str
    service_mode: str
    scenario_id: str
    parser_profile_id: str
    generation_mode: str | None = None
    max_attempts: int = 2
    idempotency_key: str | None = None
    request_fingerprint: str | None = None
    outline_relative_path: str | None = None
    created_at: datetime | None = None
    sources: tuple[JobSourceInput, ...] = field(default_factory=tuple)
    sections: tuple[SectionInput, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TransitionEvent:
    event: str
    actor: str
    worker_id: str | None = None
    allow_retry: bool = False
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class ArtifactInput:
    kind: ArtifactKind
    relative_path: str
    mime_type: str
    byte_size: int
    sha256: str


@dataclass(frozen=True)
class JobSnapshot:
    id: str
    owner_user_id: str
    service_mode: str
    scenario_id: str
    parser_profile_id: str
    generation_mode: str | None
    state: JobState
    progress: int
    attempt_count: int
    max_attempts: int
    lease_owner: str | None
    lease_expires_at: datetime | None
    idempotency_key: str | None
    request_fingerprint: str | None
    outline_relative_path: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True)
class JobSourceSnapshot:
    source_id: str
    original_filename: str
    relative_path: str
    mime_type: str
    byte_size: int
    sha256: str
    page_count: int | None


@dataclass(frozen=True)
class ArtifactSnapshot:
    kind: ArtifactKind
    relative_path: str
    mime_type: str
    byte_size: int
    sha256: str


@dataclass(frozen=True)
class SectionSnapshot:
    section_id: str
    position: int
    title: str
    status: str
    quality_json: str
    artifact_filename: str | None


@dataclass(frozen=True)
class LeaseRecoveryResult:
    requeued: int = 0
    failed: int = 0


@dataclass(frozen=True)
class AdmissionResult:
    job: JobSnapshot
    created: bool


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def resolve_job_path(jobs_root: Path | str, relative_path: str) -> Path:
    normalized = normalize_relative_path(relative_path)
    root = Path(jobs_root)
    if not root.exists() or not root.is_dir() or _is_link_or_reparse(root):
        raise RelativePathError("jobs root must be an existing ordinary directory")

    resolved_root = root.resolve(strict=True)
    target = root.joinpath(*normalized.split("/"))
    try:
        target.relative_to(root)
        target.resolve(strict=False).relative_to(resolved_root)
    except ValueError as exc:
        raise RelativePathError("path escapes the jobs root") from exc

    current = root
    for part in normalized.split("/"):
        current = current / part
        if _is_link_or_reparse(current):
            raise RelativePathError("path crosses a symlink or reparse point")
    return target


def _job_snapshot(job: Job) -> JobSnapshot:
    return JobSnapshot(
        id=job.id,
        owner_user_id=job.owner_user_id,
        service_mode=job.service_mode,
        scenario_id=job.scenario_id,
        parser_profile_id=job.parser_profile_id,
        generation_mode=job.generation_mode,
        state=job.state,
        progress=job.progress,
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
        lease_owner=job.lease_owner,
        lease_expires_at=job.lease_expires_at,
        idempotency_key=job.idempotency_key,
        request_fingerprint=job.request_fingerprint,
        outline_relative_path=job.outline_relative_path,
        error_code=job.error_code,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


class JobRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def check_connection(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def create_job(self, command: CreateJobCommand) -> JobSnapshot:
        with Session(self.engine, expire_on_commit=False) as session:
            job = self._add_job(session, command)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                if (
                    command.idempotency_key is not None
                    and self.find_by_owner_idempotency_key(
                        command.owner_user_id,
                        command.idempotency_key,
                    )
                    is not None
                ):
                    raise IdempotencyKeyCollisionError(
                        command.idempotency_key
                    ) from exc
                raise
            session.refresh(job)
            return _job_snapshot(job)

    def admit_job(
        self,
        command: CreateJobCommand,
        *,
        queue_capacity: int,
        owner_active_job_limit: int,
    ) -> AdmissionResult:
        with self.engine.connect() as connection:
            if self.engine.dialect.name == "sqlite":
                connection.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                connection.begin()
                if self.engine.dialect.name == "postgresql":
                    connection.execute(
                        text(
                            "SELECT pg_advisory_xact_lock(:lock_key)"
                        ),
                        {"lock_key": ADMISSION_LOCK_KEY},
                    )

            try:
                with Session(
                    bind=connection,
                    expire_on_commit=False,
                ) as session:
                    if command.idempotency_key is not None:
                        existing = session.exec(
                            select(Job).where(
                                Job.owner_user_id == command.owner_user_id,
                                Job.idempotency_key
                                == command.idempotency_key,
                            )
                        ).first()
                        if existing is not None:
                            result = AdmissionResult(
                                job=_job_snapshot(existing),
                                created=False,
                            )
                            connection.commit()
                            return result

                    queued = int(
                        session.exec(
                            select(func.count()).select_from(Job).where(
                                Job.state == JobState.QUEUED
                            )
                        ).one()
                    )
                    if queued >= queue_capacity:
                        raise QueueCapacityExceededError("queue_full")

                    owner_active = int(
                        session.exec(
                            select(func.count()).select_from(Job).where(
                                Job.owner_user_id == command.owner_user_id,
                                Job.state.in_(ACTIVE_JOB_STATES),
                            )
                        ).one()
                    )
                    if owner_active >= owner_active_job_limit:
                        raise OwnerActiveJobLimitExceededError(
                            "user_active_job_limit"
                        )

                    job = self._add_job(session, command)
                    session.flush()
                    result = AdmissionResult(
                        job=_job_snapshot(job),
                        created=True,
                    )
                    connection.commit()
                    return result
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _add_job(
        session: Session,
        command: CreateJobCommand,
    ) -> Job:
        created_at = _as_utc(command.created_at or utc_now())
        job = Job(
            id=command.id,
            owner_user_id=command.owner_user_id,
            service_mode=command.service_mode,
            scenario_id=command.scenario_id,
            parser_profile_id=command.parser_profile_id,
            generation_mode=command.generation_mode,
            max_attempts=command.max_attempts,
            idempotency_key=command.idempotency_key,
            request_fingerprint=command.request_fingerprint,
            outline_relative_path=command.outline_relative_path,
            created_at=created_at,
            updated_at=created_at,
        )
        session.add(job)
        for source in command.sources:
            session.add(
                JobSource(
                    job_id=job.id,
                    source_id=source.source_id,
                    original_filename=source.original_filename,
                    relative_path=source.relative_path,
                    mime_type=source.mime_type,
                    byte_size=source.byte_size,
                    sha256=source.sha256,
                    page_count=source.page_count,
                )
            )
        for section in command.sections:
            session.add(
                JobSection(
                    job_id=job.id,
                    section_id=section.section_id,
                    position=section.position,
                    title=section.title,
                    status=section.status,
                    quality_json=section.quality_json,
                    artifact_filename=section.artifact_filename,
                )
            )
        session.add(
            JobTransition(
                job_id=job.id,
                sequence=1,
                from_state=None,
                to_state=JobState.QUEUED,
                event="job_created",
                actor="api",
                created_at=created_at,
            )
        )
        return job

    def get(self, job_id: str) -> JobSnapshot | None:
        with Session(self.engine) as session:
            job = session.get(Job, job_id)
            return _job_snapshot(job) if job is not None else None

    def get_owned(self, job_id: str, owner_user_id: str) -> JobSnapshot | None:
        with Session(self.engine) as session:
            job = session.exec(
                select(Job).where(
                    Job.id == job_id,
                    Job.owner_user_id == owner_user_id,
                )
            ).first()
            return _job_snapshot(job) if job is not None else None

    def find_by_owner_idempotency_key(
        self,
        owner_user_id: str,
        idempotency_key: str,
    ) -> JobSnapshot | None:
        with Session(self.engine) as session:
            job = session.exec(
                select(Job).where(
                    Job.owner_user_id == owner_user_id,
                    Job.idempotency_key == idempotency_key,
                )
            ).first()
            return _job_snapshot(job) if job is not None else None

    def count_queued(self) -> int:
        with Session(self.engine) as session:
            return int(
                session.exec(
                    select(func.count()).select_from(Job).where(
                        Job.state == JobState.QUEUED
                    )
                ).one()
            )

    def count_active_for_owner(self, owner_user_id: str) -> int:
        with Session(self.engine) as session:
            return int(
                session.exec(
                    select(func.count()).select_from(Job).where(
                        Job.owner_user_id == owner_user_id,
                        Job.state.in_(ACTIVE_JOB_STATES),
                    )
                ).one()
            )

    def list_sources(self, job_id: str) -> list[JobSourceSnapshot]:
        with Session(self.engine) as session:
            sources = session.exec(
                select(JobSource)
                .where(JobSource.job_id == job_id)
                .order_by(JobSource.source_id)
            ).all()
            return [
                JobSourceSnapshot(
                    source_id=source.source_id,
                    original_filename=source.original_filename,
                    relative_path=source.relative_path,
                    mime_type=source.mime_type,
                    byte_size=source.byte_size,
                    sha256=source.sha256,
                    page_count=source.page_count,
                )
                for source in sources
            ]

    def transition(
        self,
        job_id: str,
        target: JobState,
        event: TransitionEvent,
    ) -> JobSnapshot:
        now = utc_now()
        with Session(self.engine, expire_on_commit=False) as session:
            job = session.get(Job, job_id)
            if job is None:
                raise JobNotFoundError(job_id)
            previous = job.state
            active_states = (
                JobState.PARSING,
                JobState.RETRIEVING,
                JobState.GENERATING,
                JobState.PACKAGING,
            )
            if previous in active_states:
                self._require_worker(job, event.worker_id, now)
            require_transition(
                previous,
                target,
                allow_retry=event.allow_retry,
            )

            conditions = [Job.id == job_id, Job.state == previous]
            if previous in active_states:
                conditions.extend(
                    (
                        Job.lease_owner == event.worker_id,
                        Job.lease_expires_at.is_not(None),
                        Job.lease_expires_at > now,
                    )
                )

            values = {
                "state": target,
                "progress": progress_for(target),
                "updated_at": now,
                "error_code": event.error_code,
                "error_message": event.error_message,
            }
            if target is JobState.PARSING:
                values["started_at"] = func.coalesce(Job.started_at, now)
            if is_terminal(target):
                values["finished_at"] = now
                values["lease_owner"] = None
                values["lease_expires_at"] = None
            elif target is JobState.QUEUED:
                values["lease_owner"] = None
                values["lease_expires_at"] = None

            result = session.exec(
                update(Job)
                .where(*conditions)
                .values(**values)
            )
            if result.rowcount != 1:
                session.rollback()
                raise StaleWorkerError(
                    f"job {job_id!r} changed or its worker lease expired"
                )

            session.expire_all()
            job = session.get(Job, job_id)
            self._append_transition(
                session,
                job,
                previous,
                target,
                event,
                now,
            )
            session.commit()
            session.refresh(job)
            return _job_snapshot(job)

    def claim_next(
        self,
        worker_id: str,
        lease_seconds: int,
    ) -> JobSnapshot | None:
        require_transition(JobState.QUEUED, JobState.PARSING)
        now = utc_now()
        lease_expires_at = now + timedelta(seconds=lease_seconds)
        with Session(self.engine, expire_on_commit=False) as session:
            candidate_ids = session.exec(
                select(Job.id)
                .where(
                    Job.state == JobState.QUEUED,
                    Job.lease_owner.is_(None),
                )
                .order_by(Job.created_at, Job.id)
            ).all()
            for job_id in candidate_ids:
                result = session.exec(
                    update(Job)
                    .where(
                        Job.id == job_id,
                        Job.state == JobState.QUEUED,
                        Job.lease_owner.is_(None),
                    )
                    .values(
                        state=JobState.PARSING,
                        progress=progress_for(JobState.PARSING),
                        attempt_count=Job.attempt_count + 1,
                        lease_owner=worker_id,
                        lease_expires_at=lease_expires_at,
                        started_at=func.coalesce(Job.started_at, now),
                        updated_at=now,
                    )
                )
                if result.rowcount != 1:
                    session.rollback()
                    continue
                job = session.get(Job, job_id)
                self._append_transition(
                    session,
                    job,
                    JobState.QUEUED,
                    JobState.PARSING,
                    TransitionEvent(
                        event="worker_claimed",
                        actor="worker",
                        worker_id=worker_id,
                    ),
                    now,
                )
                session.commit()
                session.refresh(job)
                return _job_snapshot(job)
            return None

    def renew_lease(
        self,
        job_id: str,
        worker_id: str,
        lease_seconds: int,
    ) -> bool:
        now = utc_now()
        active_states = (
            JobState.PARSING,
            JobState.RETRIEVING,
            JobState.GENERATING,
            JobState.PACKAGING,
        )
        with Session(self.engine) as session:
            result = session.exec(
                update(Job)
                .where(
                    Job.id == job_id,
                    Job.state.in_(active_states),
                    Job.lease_owner == worker_id,
                    Job.lease_expires_at.is_not(None),
                    Job.lease_expires_at > now,
                )
                .values(
                    lease_expires_at=now + timedelta(seconds=lease_seconds),
                    updated_at=now,
                )
            )
            session.commit()
            return result.rowcount == 1

    def requeue_expired_leases(self, now: datetime) -> LeaseRecoveryResult:
        now = _as_utc(now)
        requeued = 0
        failed = 0
        active_states = (
            JobState.PARSING,
            JobState.RETRIEVING,
            JobState.GENERATING,
            JobState.PACKAGING,
        )
        with Session(self.engine) as session:
            jobs = session.exec(
                select(Job)
                .where(
                    Job.state.in_(active_states),
                    Job.lease_expires_at.is_not(None),
                    Job.lease_expires_at <= now,
                )
                .order_by(Job.lease_expires_at, Job.id)
            ).all()
            candidates = [
                (
                    job.id,
                    job.state,
                    job.lease_owner,
                    job.lease_expires_at,
                    job.attempt_count,
                    job.max_attempts,
                )
                for job in jobs
            ]
            for (
                job_id,
                previous,
                lease_owner,
                lease_expires_at,
                attempt_count,
                max_attempts,
            ) in candidates:
                exhausted = attempt_count >= max_attempts
                target = JobState.FAILED if exhausted else JobState.QUEUED
                require_transition(
                    previous,
                    target,
                    allow_retry=not exhausted,
                )
                conditions = [
                    Job.id == job_id,
                    Job.state == previous,
                    Job.lease_expires_at == lease_expires_at,
                    Job.lease_expires_at.is_not(None),
                    Job.lease_expires_at <= now,
                ]
                if lease_owner is None:
                    conditions.append(Job.lease_owner.is_(None))
                else:
                    conditions.append(Job.lease_owner == lease_owner)

                values = {
                    "state": target,
                    "progress": progress_for(target),
                    "updated_at": now,
                    "lease_owner": None,
                    "lease_expires_at": None,
                }
                if exhausted:
                    values["error_code"] = "worker_attempts_exhausted"
                    values["error_message"] = "worker attempts exhausted"
                    values["finished_at"] = now
                else:
                    values["error_code"] = None
                    values["error_message"] = None

                result = session.exec(
                    update(Job)
                    .where(*conditions)
                    .values(**values)
                )
                if result.rowcount != 1:
                    session.rollback()
                    continue

                session.expire_all()
                job = session.get(Job, job_id)
                self._append_transition(
                    session,
                    job,
                    previous,
                    target,
                    TransitionEvent(
                        event=(
                            "worker_attempts_exhausted"
                            if exhausted
                            else "worker_lease_expired"
                        ),
                        actor="repository",
                        allow_retry=not exhausted,
                        error_code=values["error_code"],
                    ),
                    now,
                )
                session.commit()
                if exhausted:
                    failed += 1
                else:
                    requeued += 1
        return LeaseRecoveryResult(requeued=requeued, failed=failed)

    def record_artifacts(
        self,
        job_id: str,
        worker_id: str,
        artifacts: list[ArtifactInput],
    ) -> None:
        now = utc_now()
        with Session(self.engine) as session:
            result = session.exec(
                update(Job)
                .where(
                    Job.id == job_id,
                    Job.state == JobState.PACKAGING,
                    Job.lease_owner == worker_id,
                    Job.lease_expires_at.is_not(None),
                    Job.lease_expires_at > now,
                )
                .values(updated_at=now)
            )
            if result.rowcount != 1:
                session.rollback()
                if session.get(Job, job_id) is None:
                    raise JobNotFoundError(job_id)
                raise StaleWorkerError(
                    f"worker {worker_id!r} cannot record artifacts for job {job_id!r}"
                )
            for artifact in artifacts:
                session.add(
                    JobArtifact(
                        job_id=job_id,
                        kind=artifact.kind,
                        relative_path=artifact.relative_path,
                        mime_type=artifact.mime_type,
                        byte_size=artifact.byte_size,
                        sha256=artifact.sha256,
                    )
                )
            session.commit()

    def complete_with_artifacts(
        self,
        job_id: str,
        worker_id: str,
        artifacts: list[ArtifactInput],
        sections: Sequence[SectionInput] = (),
    ) -> JobSnapshot:
        now = utc_now()
        event = TransitionEvent(
            event="worker_completed",
            actor="worker",
            worker_id=worker_id,
        )
        require_transition(JobState.PACKAGING, JobState.COMPLETED)
        with Session(self.engine, expire_on_commit=False) as session:
            result = session.exec(
                update(Job)
                .where(
                    Job.id == job_id,
                    Job.state == JobState.PACKAGING,
                    Job.lease_owner == worker_id,
                    Job.lease_expires_at.is_not(None),
                    Job.lease_expires_at > now,
                )
                .values(
                    state=JobState.COMPLETED,
                    progress=progress_for(JobState.COMPLETED),
                    updated_at=now,
                    finished_at=now,
                    lease_owner=None,
                    lease_expires_at=None,
                    error_code=None,
                    error_message=None,
                )
            )
            if result.rowcount != 1:
                session.rollback()
                if session.get(Job, job_id) is None:
                    raise JobNotFoundError(job_id)
                raise StaleWorkerError(
                    f"worker {worker_id!r} cannot complete job {job_id!r}"
                )

            session.exec(
                delete(JobArtifact).where(JobArtifact.job_id == job_id)
            )
            for artifact in artifacts:
                session.add(
                    JobArtifact(
                        job_id=job_id,
                        kind=artifact.kind,
                        relative_path=artifact.relative_path,
                        mime_type=artifact.mime_type,
                        byte_size=artifact.byte_size,
                        sha256=artifact.sha256,
                    )
                )

            session.exec(
                delete(JobSection).where(JobSection.job_id == job_id)
            )
            for section in sections:
                session.add(
                    JobSection(
                        job_id=job_id,
                        section_id=section.section_id,
                        position=section.position,
                        title=section.title,
                        status=section.status,
                        quality_json=section.quality_json,
                        artifact_filename=section.artifact_filename,
                        updated_at=now,
                    )
                )

            session.expire_all()
            job = session.get(Job, job_id)
            self._append_transition(
                session,
                job,
                JobState.PACKAGING,
                JobState.COMPLETED,
                event,
                now,
            )
            session.commit()
            session.refresh(job)
            return _job_snapshot(job)

    def list_sections(self, job_id: str) -> list[SectionSnapshot]:
        with Session(self.engine) as session:
            sections = session.exec(
                select(JobSection)
                .where(JobSection.job_id == job_id)
                .order_by(JobSection.position)
            ).all()
            return [
                SectionSnapshot(
                    section_id=section.section_id,
                    position=section.position,
                    title=section.title,
                    status=section.status,
                    quality_json=section.quality_json,
                    artifact_filename=section.artifact_filename,
                )
                for section in sections
            ]

    def list_artifacts(self, job_id: str) -> list[ArtifactSnapshot]:
        with Session(self.engine) as session:
            artifacts = session.exec(
                select(JobArtifact)
                .where(JobArtifact.job_id == job_id)
                .order_by(JobArtifact.created_at, JobArtifact.id)
            ).all()
            return [
                ArtifactSnapshot(
                    kind=artifact.kind,
                    relative_path=artifact.relative_path,
                    mime_type=artifact.mime_type,
                    byte_size=artifact.byte_size,
                    sha256=artifact.sha256,
                )
                for artifact in artifacts
            ]

    def list_terminal_before(
        self,
        cutoff: datetime,
        *,
        limit: int | None = None,
    ) -> list[JobSnapshot]:
        cutoff = _as_utc(cutoff)
        with Session(self.engine) as session:
            statement = (
                select(Job)
                .where(
                    Job.state.in_(
                        (
                            JobState.COMPLETED,
                            JobState.FAILED,
                            JobState.CANCELLED,
                        )
                    ),
                    Job.finished_at.is_not(None),
                    Job.finished_at < cutoff,
                    Job.lease_owner.is_(None),
                    Job.lease_expires_at.is_(None),
                )
                .order_by(Job.finished_at, Job.id)
            )
            if limit is not None:
                statement = statement.limit(limit)
            jobs = session.exec(statement).all()
            return [_job_snapshot(job) for job in jobs]

    def delete_terminal(self, job_id: str) -> bool:
        with Session(self.engine) as session:
            result = session.exec(
                delete(Job).where(
                    Job.id == job_id,
                    Job.state.in_(
                        (
                            JobState.COMPLETED,
                            JobState.FAILED,
                            JobState.CANCELLED,
                        )
                    ),
                    Job.lease_owner.is_(None),
                    Job.lease_expires_at.is_(None),
                )
            )
            session.commit()
            return result.rowcount == 1

    @staticmethod
    def _require_worker(
        job: Job,
        worker_id: str | None,
        now: datetime,
    ) -> None:
        if worker_id is None:
            raise StaleWorkerError(
                f"an active transition for job {job.id!r} requires a worker"
            )
        if (
            job.lease_owner != worker_id
            or job.lease_expires_at is None
            or job.lease_expires_at <= now
        ):
            raise StaleWorkerError(
                f"worker {worker_id!r} does not own job {job.id!r}"
            )

    @staticmethod
    def _append_transition(
        session: Session,
        job: Job,
        previous: JobState | None,
        target: JobState,
        event: TransitionEvent,
        created_at: datetime,
    ) -> None:
        last_sequence = session.exec(
            select(func.max(JobTransition.sequence)).where(
                JobTransition.job_id == job.id
            )
        ).one()
        session.add(
            JobTransition(
                job_id=job.id,
                sequence=(last_sequence or 0) + 1,
                from_state=previous,
                to_state=target,
                event=event.event,
                actor=event.actor,
                error_code=event.error_code,
                created_at=created_at,
            )
        )
