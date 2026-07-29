from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import PurePosixPath, PureWindowsPath
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SQLAlchemyEnum, UniqueConstraint
from sqlalchemy.orm import validates
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, SQLModel

from packages.core.jstudy_core.job_system.states import JobState


class RelativePathError(ValueError):
    """A persisted job path is not a safe relative path."""


class ArtifactKind(StrEnum):
    CHUNKS = "chunks"
    TRACE = "trace"
    EVIDENCE = "evidence"
    EVIDENCE_LINKS = "evidence_links"
    MARKDOWN = "markdown"
    QUALITY = "quality"
    PACKAGE = "package"


WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
WINDOWS_INVALID_PATH_CHARACTERS = frozenset('<>"|?*')


def enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_type]


JOB_STATE_SQL_TYPE = SQLAlchemyEnum(
    JobState,
    name="job_state",
    values_callable=enum_values,
    validate_strings=True,
    create_constraint=True,
)
ARTIFACT_KIND_SQL_TYPE = SQLAlchemyEnum(
    ArtifactKind,
    name="job_artifact_kind",
    values_callable=enum_values,
    validate_strings=True,
    create_constraint=True,
)


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(DateTime(timezone=True))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def new_id() -> str:
    return uuid4().hex


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_relative_path(value: str) -> str:
    raw = str(value).replace("\\", "/")
    windows_path = PureWindowsPath(raw)
    if (
        not raw.strip()
        or raw == "."
        or raw.startswith("/")
        or windows_path.drive
        or windows_path.root
    ):
        raise RelativePathError("path must be relative")

    raw_parts = raw.split("/")
    for part in raw_parts:
        if (
            part in {"", ".."}
            or ":" in part
            or any(
                ord(character) < 32
                or character in WINDOWS_INVALID_PATH_CHARACTERS
                for character in part
            )
            or part.endswith((" ", "."))
            or part.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES
        ):
            raise RelativePathError("path contains an unsafe component")

    normalized = PurePosixPath(raw)
    if not normalized.parts or any(part == ".." for part in normalized.parts):
        raise RelativePathError("path contains parent traversal")
    return "/".join(part for part in normalized.parts if part != ".")


class Job(SQLModel, table=True):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_jobs_owner_idempotency_key",
        ),
    )

    id: str = Field(default_factory=new_id, primary_key=True)
    owner_user_id: str = Field(index=True)
    service_mode: str
    scenario_id: str
    parser_profile_id: str
    generation_mode: str | None = None
    state: JobState = Field(
        default=JobState.QUEUED,
        sa_type=JOB_STATE_SQL_TYPE,
        index=True,
    )
    progress: int = 0
    attempt_count: int = 0
    max_attempts: int = 2
    lease_owner: str | None = Field(default=None, index=True)
    lease_expires_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    idempotency_key: str | None = None
    request_fingerprint: str | None = None
    outline_relative_path: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime)
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime)
    started_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    finished_at: datetime | None = Field(default=None, sa_type=UTCDateTime)

    @validates("outline_relative_path")
    def validate_outline_relative_path(self, key: str, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_relative_path(value)


class JobSource(SQLModel, table=True):
    __tablename__ = "job_sources"
    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "source_id",
            name="uq_job_sources_job_source_id",
        ),
    )

    id: str = Field(default_factory=new_id, primary_key=True)
    job_id: str = Field(foreign_key="jobs.id", ondelete="CASCADE", index=True)
    source_id: str
    original_filename: str
    relative_path: str
    mime_type: str
    byte_size: int
    sha256: str
    page_count: int | None = None
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime)

    @validates("relative_path")
    def validate_relative_path(self, key: str, value: str) -> str:
        return normalize_relative_path(value)


class JobSection(SQLModel, table=True):
    __tablename__ = "job_sections"
    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "section_id",
            name="uq_job_sections_job_section_id",
        ),
        UniqueConstraint(
            "job_id",
            "position",
            name="uq_job_sections_job_position",
        ),
    )

    id: str = Field(default_factory=new_id, primary_key=True)
    job_id: str = Field(foreign_key="jobs.id", ondelete="CASCADE", index=True)
    section_id: str
    position: int
    title: str
    status: str = "pending"
    quality_json: str = "{}"
    artifact_filename: str | None = None
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime)
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime)


class JobArtifact(SQLModel, table=True):
    __tablename__ = "job_artifacts"

    id: str = Field(default_factory=new_id, primary_key=True)
    job_id: str = Field(foreign_key="jobs.id", ondelete="CASCADE", index=True)
    kind: ArtifactKind = Field(sa_type=ARTIFACT_KIND_SQL_TYPE, index=True)
    relative_path: str
    mime_type: str
    byte_size: int
    sha256: str
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime)

    @validates("kind")
    def validate_kind(self, key: str, value: ArtifactKind | str) -> ArtifactKind:
        return ArtifactKind(value)

    @validates("relative_path")
    def validate_relative_path(self, key: str, value: str) -> str:
        return normalize_relative_path(value)


class JobTransition(SQLModel, table=True):
    __tablename__ = "job_transitions"
    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "sequence",
            name="uq_job_transitions_job_sequence",
        ),
    )

    id: str = Field(default_factory=new_id, primary_key=True)
    job_id: str = Field(foreign_key="jobs.id", ondelete="CASCADE", index=True)
    sequence: int
    from_state: JobState | None = Field(
        default=None,
        sa_type=JOB_STATE_SQL_TYPE,
    )
    to_state: JobState = Field(sa_type=JOB_STATE_SQL_TYPE)
    event: str
    actor: str
    error_code: str | None = None
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime)
