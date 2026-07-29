import os
import subprocess
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest import mock

from sqlalchemy import delete, inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import CreateEnumType
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from packages.core.jstudy_core.auth_db import (
    create_application_tables,
    create_auth_engine,
    create_auth_tables,
)
from packages.core.jstudy_core.job_system import models as job_models
from packages.core.jstudy_core.job_system import repository as job_repository_module
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
from packages.core.jstudy_core.job_system.repository import (
    AdmissionResult,
    ArtifactInput,
    CreateJobCommand,
    JobRepository,
    JobSourceInput,
    OwnerActiveJobLimitExceededError,
    QueueCapacityExceededError,
    SectionInput,
    StaleWorkerError,
    TransitionEvent,
    resolve_job_path,
)
from packages.core.jstudy_core.job_system.states import JobState


class JobModelContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db_path = Path(self.tmp.name) / "jobs.db"
        self.engine = create_auth_engine(f"sqlite:///{db_path.as_posix()}")
        create_application_tables(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.tmp.cleanup()

    def make_job(self, job_id: str, **overrides) -> Job:
        values = {
            "id": job_id,
            "owner_user_id": "user-1",
            "service_mode": "course_outline",
            "scenario_id": "medicine",
            "parser_profile_id": "pymupdf",
            "max_attempts": 2,
        }
        values.update(overrides)
        return Job(**values)

    def test_application_tables_are_registered(self):
        tables = set(inspect(self.engine).get_table_names())
        self.assertTrue(
            {
                "users",
                "invite_codes",
                "invite_code_uses",
                "user_sessions",
                "jobs",
                "job_sources",
                "job_sections",
                "job_artifacts",
                "job_transitions",
            }.issubset(tables)
        )

    def test_create_auth_tables_alias_creates_application_tables(self):
        alias_db = Path(self.tmp.name) / "auth-alias.db"
        alias_engine = create_auth_engine(f"sqlite:///{alias_db.as_posix()}")
        self.addCleanup(alias_engine.dispose)

        create_auth_tables(alias_engine)

        tables = set(inspect(alias_engine).get_table_names())
        self.assertIn("users", tables)
        self.assertIn("jobs", tables)

    def test_owner_user_id_matches_auth_user_string_identity(self):
        self.assertIs(Job.model_fields["owner_user_id"].annotation, str)
        with Session(self.engine) as session:
            session.add(self.make_job("job-string-owner", owner_user_id="user-alpha"))
            session.commit()
            stored = session.get(Job, "job-string-owner")

        self.assertEqual(stored.owner_user_id, "user-alpha")

    def test_owner_idempotency_key_is_unique_only_within_owner(self):
        with Session(self.engine) as session:
            session.add(
                self.make_job(
                    "job-1",
                    idempotency_key="same-key",
                    request_fingerprint="fingerprint-1",
                )
            )
            session.add(
                self.make_job(
                    "job-2",
                    owner_user_id="user-2",
                    idempotency_key="same-key",
                    request_fingerprint="fingerprint-2",
                )
            )
            session.add(self.make_job("job-3"))
            session.add(self.make_job("job-4"))
            session.commit()

            session.add(
                self.make_job(
                    "job-5",
                    idempotency_key="same-key",
                    request_fingerprint="fingerprint-5",
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_section_identity_is_unique_per_job(self):
        with Session(self.engine) as session:
            session.add(self.make_job("job-1"))
            session.commit()
            session.add(
                JobSection(
                    job_id="job-1",
                    section_id="SEC001",
                    position=1,
                    title="Introduction",
                )
            )
            session.commit()

            session.add(
                JobSection(
                    job_id="job-1",
                    section_id="SEC001",
                    position=2,
                    title="Duplicate identity",
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_artifact_kind_is_controlled_and_round_trips(self):
        expected = {
            "chunks",
            "trace",
            "evidence",
            "evidence_links",
            "markdown",
            "quality",
            "package",
        }
        self.assertEqual(
            {kind.value for kind in job_models.ArtifactKind},
            expected,
        )
        self.assertIs(
            JobArtifact.model_fields["kind"].annotation,
            job_models.ArtifactKind,
        )

        with Session(self.engine) as session:
            session.add(self.make_job("job-1"))
            session.add(
                JobArtifact(
                    job_id="job-1",
                    kind=job_models.ArtifactKind.MARKDOWN,
                    relative_path="outputs/material.md",
                    mime_type="text/markdown",
                    byte_size=64,
                    sha256="b" * 64,
                )
            )
            session.commit()
            stored = session.exec(select(JobArtifact)).one()

        self.assertEqual(stored.kind, job_models.ArtifactKind.MARKDOWN)

        with self.assertRaises(ValueError):
            JobArtifact(
                job_id="job-1",
                kind="unknown",
                relative_path="outputs/unknown.bin",
                mime_type="application/octet-stream",
                byte_size=1,
                sha256="c" * 64,
            )

    def test_enum_values_are_persisted_as_canonical_lowercase(self):
        with Session(self.engine) as session:
            session.add(self.make_job("job-1"))
            session.add(
                JobArtifact(
                    job_id="job-1",
                    kind=job_models.ArtifactKind.MARKDOWN,
                    relative_path="outputs/material.md",
                    mime_type="text/markdown",
                    byte_size=64,
                    sha256="b" * 64,
                )
            )
            session.add(
                JobTransition(
                    job_id="job-1",
                    sequence=1,
                    from_state=JobState.QUEUED,
                    to_state=JobState.PARSING,
                    event="worker_claimed",
                    actor="worker:test",
                )
            )
            session.commit()

            job_state = session.exec(
                text("SELECT state FROM jobs WHERE id = 'job-1'")
            ).one()
            artifact_kind = session.exec(
                text("SELECT kind FROM job_artifacts WHERE job_id = 'job-1'")
            ).one()
            transition_states = session.exec(
                text(
                    "SELECT from_state, to_state "
                    "FROM job_transitions WHERE job_id = 'job-1'"
                )
            ).one()

        self.assertEqual(job_state, ("queued",))
        self.assertEqual(artifact_kind, ("markdown",))
        self.assertEqual(transition_states, ("queued", "parsing"))

    def test_sqlite_rejects_unknown_state_and_artifact_kind_values(self):
        with Session(self.engine) as session:
            session.add(self.make_job("job-1"))
            session.add(
                JobArtifact(
                    job_id="job-1",
                    kind=job_models.ArtifactKind.MARKDOWN,
                    relative_path="outputs/material.md",
                    mime_type="text/markdown",
                    byte_size=64,
                    sha256="b" * 64,
                )
            )
            session.add(
                JobTransition(
                    job_id="job-1",
                    sequence=1,
                    from_state=JobState.QUEUED,
                    to_state=JobState.PARSING,
                    event="worker_claimed",
                    actor="worker:test",
                )
            )
            session.commit()

            invalid_updates = (
                "UPDATE jobs SET state = 'bogus' WHERE id = 'job-1'",
                (
                    "UPDATE job_transitions SET from_state = 'bogus' "
                    "WHERE job_id = 'job-1'"
                ),
                (
                    "UPDATE job_transitions SET to_state = 'bogus' "
                    "WHERE job_id = 'job-1'"
                ),
                (
                    "UPDATE job_artifacts SET kind = 'bogus' "
                    "WHERE job_id = 'job-1'"
                ),
            )
            for statement in invalid_updates:
                with self.subTest(statement=statement):
                    with self.assertRaises(IntegrityError):
                        session.exec(text(statement))
                        session.commit()
                    session.rollback()

    def test_postgresql_enum_ddl_uses_canonical_lowercase_labels(self):
        expected_state_ddl = (
            "CREATE TYPE job_state AS ENUM "
            "('queued', 'parsing', 'retrieving', 'generating', "
            "'packaging', 'completed', 'failed', 'cancelled')"
        )
        state_columns = (
            Job.__table__.c.state,
            JobTransition.__table__.c.from_state,
            JobTransition.__table__.c.to_state,
        )
        for column in state_columns:
            with self.subTest(column=column.name):
                ddl = str(
                    CreateEnumType(column.type).compile(
                        dialect=postgresql.dialect()
                    )
                )
                self.assertEqual(ddl, expected_state_ddl)

        artifact_ddl = str(
            CreateEnumType(JobArtifact.__table__.c.kind.type).compile(
                dialect=postgresql.dialect()
            )
        )
        self.assertEqual(
            artifact_ddl,
            (
                "CREATE TYPE job_artifact_kind AS ENUM "
                "('chunks', 'trace', 'evidence', 'evidence_links', "
                "'markdown', 'quality', 'package')"
            ),
        )

    def test_source_identity_and_section_order_are_unique_per_job(self):
        with Session(self.engine) as session:
            session.add(self.make_job("job-1"))
            session.commit()

            session.add(
                JobSource(
                    job_id="job-1",
                    source_id="S001",
                    original_filename="lecture.pdf",
                    relative_path="inputs/S001.pdf",
                    mime_type="application/pdf",
                    byte_size=128,
                    sha256="a" * 64,
                )
            )
            session.add(
                JobSection(
                    job_id="job-1",
                    section_id="SEC001",
                    position=1,
                    title="Introduction",
                )
            )
            session.commit()

            session.add(
                JobSource(
                    job_id="job-1",
                    source_id="S001",
                    original_filename="duplicate.pdf",
                    relative_path="inputs/duplicate.pdf",
                    mime_type="application/pdf",
                    byte_size=256,
                    sha256="b" * 64,
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()
            session.rollback()

            session.add(
                JobSection(
                    job_id="job-1",
                    section_id="SEC002",
                    position=1,
                    title="Duplicate order",
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_deleting_job_cascades_to_all_job_owned_tables(self):
        with Session(self.engine) as session:
            session.add(self.make_job("job-1"))
            session.add(
                JobSource(
                    job_id="job-1",
                    source_id="S001",
                    original_filename="lecture.pdf",
                    relative_path="inputs/S001.pdf",
                    mime_type="application/pdf",
                    byte_size=128,
                    sha256="a" * 64,
                )
            )
            session.add(
                JobSection(
                    job_id="job-1",
                    section_id="SEC001",
                    position=1,
                    title="Introduction",
                )
            )
            session.add(
                JobArtifact(
                    job_id="job-1",
                    kind="markdown",
                    relative_path="outputs/material.md",
                    mime_type="text/markdown",
                    byte_size=64,
                    sha256="b" * 64,
                )
            )
            session.add(
                JobTransition(
                    job_id="job-1",
                    sequence=1,
                    from_state=JobState.QUEUED,
                    to_state=JobState.PARSING,
                    event="worker_claimed",
                    actor="worker:test",
                )
            )
            session.commit()

            session.exec(delete(Job).where(Job.id == "job-1"))
            session.commit()

            for model in (JobSource, JobSection, JobArtifact, JobTransition):
                with self.subTest(model=model.__name__):
                    self.assertEqual(session.exec(select(model)).all(), [])

    def test_utc_timestamps_survive_database_round_trip(self):
        before = utc_now() - timedelta(seconds=1)
        with Session(self.engine) as session:
            session.add(self.make_job("job-1"))
            session.commit()
            stored = session.exec(select(Job).where(Job.id == "job-1")).one()

        self.assertIsNotNone(stored.created_at.tzinfo)
        self.assertEqual(stored.created_at.utcoffset(), timedelta(0))
        self.assertGreater(stored.created_at, before)
        self.assertEqual(stored.state, JobState.QUEUED)
        self.assertEqual(stored.progress, 0)
        self.assertEqual(stored.attempt_count, 0)

    def test_relative_paths_are_normalized_and_unsafe_paths_are_rejected(self):
        self.assertEqual(
            normalize_relative_path(r"inputs\S001.pdf"),
            "inputs/S001.pdf",
        )

        for unsafe in (
            "",
            ".",
            "..",
            "../escape.pdf",
            "inputs/../../escape.pdf",
            "/absolute.pdf",
            r"C:\absolute.pdf",
            r"C:drive-relative.pdf",
            r"\\server\share\file.pdf",
            r"\\?\C:\device\file.pdf",
            r"\\.\C:\device\file.pdf",
            "inputs/file.pdf:stream",
            "CON",
            "nul.txt",
            "inputs/AUX.json",
            "inputs/COM1.log",
            "inputs/LPT9",
            "inputs/file.txt.",
            "inputs/file.txt ",
            "inputs/directory./file.pdf",
            "inputs/\x00file.pdf",
            "inputs/\x1ffile.pdf",
            "inputs/file<name.pdf",
            "inputs/file>name.pdf",
            'inputs/file"name.pdf',
            "inputs/file|name.pdf",
            "inputs/file?name.pdf",
            "inputs/file*name.pdf",
        ):
            with self.subTest(path=unsafe):
                with self.assertRaises(RelativePathError):
                    normalize_relative_path(unsafe)

        with self.assertRaises(RelativePathError):
            JobSource(
                job_id="job-1",
                source_id="S001",
                original_filename="lecture.pdf",
                relative_path="../escape.pdf",
                mime_type="application/pdf",
                byte_size=128,
                sha256="a" * 64,
            )
        with self.assertRaises(RelativePathError):
            JobArtifact(
                job_id="job-1",
                kind="markdown",
                relative_path="C:/escape.md",
                mime_type="text/markdown",
                byte_size=64,
                sha256="b" * 64,
            )

    def test_model_defaults_do_not_share_mutable_values(self):
        mutable_types = (dict, list, set)
        for model in (Job, JobSource, JobSection, JobArtifact, JobTransition):
            for name, field in model.model_fields.items():
                with self.subTest(model=model.__name__, field=name):
                    self.assertNotIsInstance(field.default, mutable_types)


class JobRepositoryContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "repository.db"
        self.jobs_root = Path(self.tmp.name) / "jobs"
        self.jobs_root.mkdir()
        self.engine = create_auth_engine(f"sqlite:///{self.db_path.as_posix()}")
        create_application_tables(self.engine)
        self.repository = JobRepository(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.tmp.cleanup()

    def command(
        self,
        job_id: str = "job-1",
        *,
        owner_user_id: str = "owner-1",
        max_attempts: int = 2,
        created_at=None,
    ) -> CreateJobCommand:
        return CreateJobCommand(
            id=job_id,
            owner_user_id=owner_user_id,
            service_mode="course_outline",
            scenario_id="medicine",
            parser_profile_id="pymupdf",
            max_attempts=max_attempts,
            created_at=created_at,
            sources=(
                JobSourceInput(
                    source_id="S002",
                    original_filename="lecture-2.pdf",
                    relative_path="inputs/S002.pdf",
                    mime_type="application/pdf",
                    byte_size=202,
                    sha256="2" * 64,
                ),
                JobSourceInput(
                    source_id="S001",
                    original_filename="lecture-1.pdf",
                    relative_path="inputs/S001.pdf",
                    mime_type="application/pdf",
                    byte_size=101,
                    sha256="1" * 64,
                ),
            ),
            sections=(
                SectionInput(
                    section_id="SEC002",
                    position=2,
                    title="Second",
                ),
                SectionInput(
                    section_id="SEC001",
                    position=1,
                    title="First",
                ),
            ),
        )

    def claim(self, worker_id: str = "worker-1"):
        claimed = self.repository.claim_next(worker_id, lease_seconds=60)
        self.assertIsNotNone(claimed)
        return claimed

    def test_create_and_reload_from_file_sqlite(self):
        created = self.repository.create_job(self.command())
        self.assertEqual(created.id, "job-1")
        self.assertEqual(created.state, JobState.QUEUED)

        restarted = JobRepository(
            create_auth_engine(f"sqlite:///{self.db_path.as_posix()}")
        )
        self.addCleanup(restarted.engine.dispose)
        reloaded = restarted.get("job-1")

        self.assertEqual(reloaded, created)

    def test_sources_are_listed_by_stable_source_id(self):
        self.repository.create_job(self.command())

        sources = self.repository.list_sources("job-1")

        self.assertEqual([source.source_id for source in sources], ["S001", "S002"])
        self.assertEqual(sources[0].relative_path, "inputs/S001.pdf")

    def test_owner_lookup_hides_unknown_and_foreign_jobs(self):
        self.repository.create_job(self.command())

        self.assertIsNotNone(self.repository.get_owned("job-1", "owner-1"))
        self.assertIsNone(self.repository.get_owned("job-1", "other-owner"))
        self.assertIsNone(self.repository.get_owned("missing", "owner-1"))

    def test_admission_counts_and_owner_idempotency_lookup(self):
        self.repository.create_job(
            replace(
                self.command("owner-queued"),
                owner_user_id="owner-1",
                idempotency_key="request-key",
                request_fingerprint="a" * 64,
            )
        )
        self.repository.create_job(
            replace(
                self.command("other-queued"),
                owner_user_id="owner-2",
            )
        )
        self.repository.create_job(
            replace(
                self.command("owner-terminal"),
                owner_user_id="owner-1",
            )
        )
        with Session(self.engine) as session:
            terminal = session.get(Job, "owner-terminal")
            terminal.state = JobState.COMPLETED
            terminal.finished_at = utc_now()
            session.add(terminal)
            session.commit()

        found = self.repository.find_by_owner_idempotency_key(
            "owner-1",
            "request-key",
        )

        self.assertIsNotNone(found)
        self.assertEqual(found.id, "owner-queued")
        self.assertIsNone(
            self.repository.find_by_owner_idempotency_key(
                "owner-2",
                "request-key",
            )
        )
        self.assertEqual(self.repository.count_queued(), 2)
        self.assertEqual(
            self.repository.count_active_for_owner("owner-1"),
            1,
        )

    def test_atomic_admission_enforces_queue_and_owner_limits(self):
        first = self.repository.admit_job(
            self.command("first"),
            queue_capacity=1,
            owner_active_job_limit=1,
        )

        self.assertIsInstance(first, AdmissionResult)
        self.assertTrue(first.created)
        with self.assertRaisesRegex(
            QueueCapacityExceededError,
            "queue_full",
        ):
            self.repository.admit_job(
                replace(self.command("queue-full"), owner_user_id="owner-2"),
                queue_capacity=1,
                owner_active_job_limit=1,
            )

        with Session(self.engine) as session:
            job = session.get(Job, "first")
            job.state = JobState.COMPLETED
            job.finished_at = utc_now()
            session.add(job)
            session.commit()
        self.repository.admit_job(
            self.command("owner-active"),
            queue_capacity=2,
            owner_active_job_limit=1,
        )
        with self.assertRaisesRegex(
            OwnerActiveJobLimitExceededError,
            "user_active_job_limit",
        ):
            self.repository.admit_job(
                self.command("owner-limit"),
                queue_capacity=2,
                owner_active_job_limit=1,
            )

    def test_atomic_admission_returns_owner_idempotent_job_before_limits(self):
        command = replace(
            self.command("idempotent"),
            idempotency_key="same-request",
            request_fingerprint="a" * 64,
        )
        created = self.repository.admit_job(
            command,
            queue_capacity=1,
            owner_active_job_limit=1,
        )
        repeated = self.repository.admit_job(
            replace(command, id="ignored"),
            queue_capacity=1,
            owner_active_job_limit=1,
        )

        self.assertTrue(created.created)
        self.assertFalse(repeated.created)
        self.assertEqual(repeated.job.id, created.job.id)

    def test_transition_appends_history(self):
        self.repository.create_job(self.command())
        self.claim("worker-1")

        updated = self.repository.transition(
            "job-1",
            JobState.RETRIEVING,
            TransitionEvent(
                event="retrieval_started",
                actor="worker",
                worker_id="worker-1",
            ),
        )

        self.assertEqual(updated.state, JobState.RETRIEVING)
        with Session(self.engine) as session:
            rows = session.exec(
                select(JobTransition)
                .where(JobTransition.job_id == "job-1")
                .order_by(JobTransition.sequence)
            ).all()
        self.assertEqual(
            [(row.from_state, row.to_state) for row in rows],
            [
                (None, JobState.QUEUED),
                (JobState.QUEUED, JobState.PARSING),
                (JobState.PARSING, JobState.RETRIEVING),
            ],
        )

    def test_invalid_transition_rolls_back_state_and_history(self):
        self.repository.create_job(self.command())

        with self.assertRaises(ValueError):
            self.repository.transition(
                "job-1",
                JobState.COMPLETED,
                TransitionEvent(event="invalid", actor="test"),
            )

        self.assertEqual(self.repository.get("job-1").state, JobState.QUEUED)
        with Session(self.engine) as session:
            rows = session.exec(
                select(JobTransition).where(JobTransition.job_id == "job-1")
            ).all()
        self.assertEqual(len(rows), 1)

    def test_identity_and_section_order_have_no_repository_update_api(self):
        self.repository.create_job(self.command())

        self.assertFalse(hasattr(self.repository, "update_job_identity"))
        self.assertFalse(hasattr(self.repository, "update_source_identity"))
        self.assertFalse(hasattr(self.repository, "update_section_order"))
        with Session(self.engine) as session:
            sections = session.exec(
                select(JobSection)
                .where(JobSection.job_id == "job-1")
                .order_by(JobSection.position)
            ).all()
        self.assertEqual(
            [(section.section_id, section.position) for section in sections],
            [("SEC001", 1), ("SEC002", 2)],
        )

    def test_two_repository_threads_cannot_double_claim(self):
        self.repository.create_job(self.command())
        repositories = (JobRepository(self.engine), JobRepository(self.engine))
        barrier = threading.Barrier(2)

        def claim(index):
            barrier.wait()
            return repositories[index].claim_next(
                f"worker-{index}",
                lease_seconds=60,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(claim, range(2)))

        claimed = [result for result in results if result is not None]
        self.assertEqual(len(claimed), 1)
        self.assertEqual(claimed[0].attempt_count, 1)

    def test_expired_lease_requeues_when_attempts_remain(self):
        self.repository.create_job(self.command(max_attempts=2))
        claimed = self.claim()
        now = claimed.lease_expires_at + timedelta(seconds=1)

        result = self.repository.requeue_expired_leases(now)

        self.assertEqual((result.requeued, result.failed), (1, 0))
        recovered = self.repository.get("job-1")
        self.assertEqual(recovered.state, JobState.QUEUED)
        self.assertIsNone(recovered.lease_owner)
        self.assertIsNone(recovered.lease_expires_at)

    def test_expired_lease_fails_when_attempts_are_exhausted(self):
        self.repository.create_job(self.command(max_attempts=1))
        claimed = self.claim()
        now = claimed.lease_expires_at + timedelta(seconds=1)

        result = self.repository.requeue_expired_leases(now)

        self.assertEqual((result.requeued, result.failed), (0, 1))
        failed = self.repository.get("job-1")
        self.assertEqual(failed.state, JobState.FAILED)
        self.assertEqual(failed.error_code, "worker_attempts_exhausted")
        self.assertIsNone(failed.lease_owner)

    def test_stale_recovery_cannot_overwrite_a_new_worker_claim(self):
        self.repository.create_job(self.command(max_attempts=3))
        first_claim = self.claim("worker-1")
        recovery_now = first_claim.lease_expires_at + timedelta(seconds=1)
        stale_repository = JobRepository(self.engine)
        stale_read = threading.Event()
        release_stale = threading.Event()
        original_require_transition = job_repository_module.require_transition

        def block_stale_recovery(current, target, *, allow_retry=False):
            if threading.current_thread().name.startswith("stale-recovery"):
                stale_read.set()
                self.assertTrue(release_stale.wait(timeout=5))
            return original_require_transition(
                current,
                target,
                allow_retry=allow_retry,
            )

        with mock.patch.object(
            job_repository_module,
            "require_transition",
            side_effect=block_stale_recovery,
        ):
            with ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="stale-recovery",
            ) as executor:
                stale_future = executor.submit(
                    stale_repository.requeue_expired_leases,
                    recovery_now,
                )
                self.assertTrue(stale_read.wait(timeout=5))

                recovered = self.repository.requeue_expired_leases(recovery_now)
                new_claim = self.repository.claim_next("worker-2", lease_seconds=120)
                self.assertEqual((recovered.requeued, recovered.failed), (1, 0))
                self.assertIsNotNone(new_claim)

                release_stale.set()
                stale_result = stale_future.result(timeout=5)

        self.assertEqual((stale_result.requeued, stale_result.failed), (0, 0))
        current = self.repository.get("job-1")
        self.assertEqual(current.state, JobState.PARSING)
        self.assertEqual(current.lease_owner, "worker-2")
        with Session(self.engine) as session:
            transitions = session.exec(
                select(JobTransition).where(JobTransition.job_id == "job-1")
            ).all()
        self.assertEqual(len(transitions), 4)

    def test_active_transition_requires_a_current_worker(self):
        self.repository.create_job(self.command())
        self.claim("worker-1")

        with self.assertRaises(StaleWorkerError):
            self.repository.transition(
                "job-1",
                JobState.RETRIEVING,
                TransitionEvent(event="missing_worker", actor="worker"),
            )

        self.assertEqual(self.repository.get("job-1").state, JobState.PARSING)
        with Session(self.engine) as session:
            transitions = session.exec(
                select(JobTransition).where(JobTransition.job_id == "job-1")
            ).all()
        self.assertEqual(len(transitions), 2)

    def test_queued_job_can_be_cancelled_without_a_worker(self):
        self.repository.create_job(self.command())

        cancelled = self.repository.transition(
            "job-1",
            JobState.CANCELLED,
            TransitionEvent(event="user_cancelled", actor="api"),
        )

        self.assertEqual(cancelled.state, JobState.CANCELLED)

    def test_concurrent_transition_uses_state_and_lease_cas(self):
        self.repository.create_job(self.command())
        self.claim("worker-1")
        stale_repository = JobRepository(self.engine)
        stale_read = threading.Event()
        release_stale = threading.Event()
        original_require_transition = job_repository_module.require_transition

        def block_stale_transition(current, target, *, allow_retry=False):
            if threading.current_thread().name.startswith("stale-transition"):
                stale_read.set()
                self.assertTrue(release_stale.wait(timeout=5))
            return original_require_transition(
                current,
                target,
                allow_retry=allow_retry,
            )

        with mock.patch.object(
            job_repository_module,
            "require_transition",
            side_effect=block_stale_transition,
        ):
            with ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="stale-transition",
            ) as executor:
                stale_future = executor.submit(
                    stale_repository.transition,
                    "job-1",
                    JobState.RETRIEVING,
                    TransitionEvent(
                        event="stale_retrieval",
                        actor="worker",
                        worker_id="worker-1",
                    ),
                )
                self.assertTrue(stale_read.wait(timeout=5))

                current = self.repository.transition(
                    "job-1",
                    JobState.RETRIEVING,
                    TransitionEvent(
                        event="retrieval_started",
                        actor="worker",
                        worker_id="worker-1",
                    ),
                )
                self.assertEqual(current.state, JobState.RETRIEVING)
                release_stale.set()
                with self.assertRaises(StaleWorkerError):
                    stale_future.result(timeout=5)

        self.assertEqual(self.repository.get("job-1").state, JobState.RETRIEVING)
        with Session(self.engine) as session:
            transitions = session.exec(
                select(JobTransition).where(JobTransition.job_id == "job-1")
            ).all()
        self.assertEqual(len(transitions), 3)

    def test_completion_clears_lease_metadata(self):
        self.repository.create_job(self.command())
        self.claim("worker-1")
        for target in (
            JobState.RETRIEVING,
            JobState.GENERATING,
            JobState.PACKAGING,
            JobState.COMPLETED,
        ):
            completed = self.repository.transition(
                "job-1",
                target,
                TransitionEvent(
                    event=f"enter_{target.value}",
                    actor="worker",
                    worker_id="worker-1",
                ),
            )

        self.assertEqual(completed.state, JobState.COMPLETED)
        self.assertIsNone(completed.lease_owner)
        self.assertIsNone(completed.lease_expires_at)

    def test_renew_lease_requires_current_worker(self):
        self.repository.create_job(self.command())
        claimed = self.claim("worker-1")

        self.assertFalse(
            self.repository.renew_lease("job-1", "worker-2", lease_seconds=120)
        )
        self.assertTrue(
            self.repository.renew_lease("job-1", "worker-1", lease_seconds=120)
        )
        renewed = self.repository.get("job-1")
        self.assertGreater(renewed.lease_expires_at, claimed.lease_expires_at)

    def test_stale_worker_cannot_transition_or_complete(self):
        self.repository.create_job(self.command())
        claimed = self.claim("worker-1")
        self.repository.requeue_expired_leases(
            claimed.lease_expires_at + timedelta(seconds=1)
        )
        self.claim("worker-2")

        with self.assertRaises(StaleWorkerError):
            self.repository.transition(
                "job-1",
                JobState.RETRIEVING,
                TransitionEvent(
                    event="stale_progress",
                    actor="worker",
                    worker_id="worker-1",
                ),
            )
        with self.assertRaises(StaleWorkerError):
            self.repository.transition(
                "job-1",
                JobState.COMPLETED,
                TransitionEvent(
                    event="stale_complete",
                    actor="worker",
                    worker_id="worker-1",
                ),
            )
        self.assertEqual(self.repository.get("job-1").lease_owner, "worker-2")

    def test_artifacts_survive_repository_restart(self):
        self.repository.create_job(self.command())
        self.claim("worker-1")
        for target in (
            JobState.RETRIEVING,
            JobState.GENERATING,
            JobState.PACKAGING,
        ):
            self.repository.transition(
                "job-1",
                target,
                TransitionEvent(
                    event=f"enter_{target.value}",
                    actor="worker",
                    worker_id="worker-1",
                ),
            )
        self.repository.record_artifacts(
            "job-1",
            "worker-1",
            [
                ArtifactInput(
                    kind=ArtifactKind.MARKDOWN,
                    relative_path="outputs/material.md",
                    mime_type="text/markdown",
                    byte_size=64,
                    sha256="a" * 64,
                )
            ],
        )

        restarted = JobRepository(
            create_auth_engine(f"sqlite:///{self.db_path.as_posix()}")
        )
        self.addCleanup(restarted.engine.dispose)
        artifacts = restarted.list_artifacts("job-1")

        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0].kind, ArtifactKind.MARKDOWN)
        self.assertEqual(artifacts[0].relative_path, "outputs/material.md")

    def test_complete_with_artifacts_replaces_prior_attempt_atomically(self):
        self.repository.create_job(self.command(max_attempts=2))
        self.claim("worker-1")
        for target in (
            JobState.RETRIEVING,
            JobState.GENERATING,
            JobState.PACKAGING,
        ):
            self.repository.transition(
                "job-1",
                target,
                TransitionEvent(
                    event=f"enter_{target.value}",
                    actor="worker",
                    worker_id="worker-1",
                ),
            )
        self.repository.record_artifacts(
            "job-1",
            "worker-1",
            [
                ArtifactInput(
                    kind=ArtifactKind.MARKDOWN,
                    relative_path="job-1/attempts/1/output/old.md",
                    mime_type="text/markdown",
                    byte_size=3,
                    sha256="a" * 64,
                )
            ],
        )

        completed = self.repository.complete_with_artifacts(
            "job-1",
            "worker-1",
            [
                ArtifactInput(
                    kind=ArtifactKind.MARKDOWN,
                    relative_path="job-1/attempts/1/output/result.md",
                    mime_type="text/markdown",
                    byte_size=6,
                    sha256="b" * 64,
                ),
                ArtifactInput(
                    kind=ArtifactKind.PACKAGE,
                    relative_path="job-1/attempts/1/output/result.json",
                    mime_type="application/json",
                    byte_size=8,
                    sha256="c" * 64,
                ),
            ],
        )

        self.assertEqual(completed.state, JobState.COMPLETED)
        self.assertEqual(
            {
                (artifact.kind, artifact.relative_path)
                for artifact in self.repository.list_artifacts("job-1")
            },
            {
                (
                    ArtifactKind.MARKDOWN,
                    "job-1/attempts/1/output/result.md",
                ),
                (
                    ArtifactKind.PACKAGE,
                    "job-1/attempts/1/output/result.json",
                ),
            },
        )

    def test_complete_with_artifacts_rolls_back_on_artifact_failure(self):
        self.repository.create_job(self.command())
        self.claim("worker-1")
        for target in (
            JobState.RETRIEVING,
            JobState.GENERATING,
            JobState.PACKAGING,
        ):
            self.repository.transition(
                "job-1",
                target,
                TransitionEvent(
                    event=f"enter_{target.value}",
                    actor="worker",
                    worker_id="worker-1",
                ),
            )

        with self.assertRaises(IntegrityError):
            self.repository.complete_with_artifacts(
                "job-1",
                "worker-1",
                [
                    ArtifactInput(
                        kind=ArtifactKind.MARKDOWN,
                        relative_path="job-1/attempts/1/output/result.md",
                        mime_type=None,
                        byte_size=None,
                        sha256=None,
                    )
                ],
            )

        job = self.repository.get("job-1")
        self.assertEqual(job.state, JobState.PACKAGING)
        self.assertEqual(job.lease_owner, "worker-1")
        self.assertEqual(self.repository.list_artifacts("job-1"), [])
        with Session(self.engine) as session:
            last_transition = session.exec(
                select(JobTransition)
                .where(JobTransition.job_id == "job-1")
                .order_by(JobTransition.sequence.desc())
            ).first()
        self.assertEqual(last_transition.to_state, JobState.PACKAGING)

    def test_stale_worker_cannot_record_artifacts(self):
        self.repository.create_job(self.command())
        self.claim("worker-1")
        for target in (
            JobState.RETRIEVING,
            JobState.GENERATING,
            JobState.PACKAGING,
        ):
            self.repository.transition(
                "job-1",
                target,
                TransitionEvent(
                    event=f"enter_{target.value}",
                    actor="worker",
                    worker_id="worker-1",
                ),
            )

        with self.assertRaises(StaleWorkerError):
            self.repository.record_artifacts(
                "job-1",
                "worker-2",
                [
                    ArtifactInput(
                        kind=ArtifactKind.MARKDOWN,
                        relative_path="outputs/stale.md",
                        mime_type="text/markdown",
                        byte_size=32,
                        sha256="b" * 64,
                    )
                ],
            )

        self.assertEqual(self.repository.list_artifacts("job-1"), [])

    def test_expired_worker_cannot_record_artifacts(self):
        self.repository.create_job(self.command())
        self.claim("worker-1")
        for target in (
            JobState.RETRIEVING,
            JobState.GENERATING,
            JobState.PACKAGING,
        ):
            self.repository.transition(
                "job-1",
                target,
                TransitionEvent(
                    event=f"enter_{target.value}",
                    actor="worker",
                    worker_id="worker-1",
                ),
            )
        with Session(self.engine) as session:
            job = session.get(Job, "job-1")
            job.lease_expires_at = utc_now() - timedelta(seconds=1)
            session.add(job)
            session.commit()

        with self.assertRaises(StaleWorkerError):
            self.repository.record_artifacts(
                "job-1",
                "worker-1",
                [
                    ArtifactInput(
                        kind=ArtifactKind.MARKDOWN,
                        relative_path="outputs/expired.md",
                        mime_type="text/markdown",
                        byte_size=32,
                        sha256="c" * 64,
                    )
                ],
            )

        self.assertEqual(self.repository.list_artifacts("job-1"), [])

    def test_artifacts_require_packaging_state(self):
        self.repository.create_job(self.command())
        self.claim("worker-1")

        with self.assertRaises(StaleWorkerError):
            self.repository.record_artifacts(
                "job-1",
                "worker-1",
                [
                    ArtifactInput(
                        kind=ArtifactKind.MARKDOWN,
                        relative_path="outputs/early.md",
                        mime_type="text/markdown",
                        byte_size=32,
                        sha256="d" * 64,
                    )
                ],
            )

        self.assertEqual(self.repository.list_artifacts("job-1"), [])

    def test_terminal_retention_selection_excludes_active_and_recent_jobs(self):
        old = utc_now() - timedelta(days=31)
        recent = utc_now() - timedelta(days=1)
        cutoff = utc_now() - timedelta(days=30)
        for job_id in (
            "old-completed",
            "recent-failed",
            "old-active",
            "old-lease-metadata",
        ):
            self.repository.create_job(self.command(job_id))

        with Session(self.engine) as session:
            completed = session.get(Job, "old-completed")
            completed.state = JobState.COMPLETED
            completed.finished_at = old
            failed = session.get(Job, "recent-failed")
            failed.state = JobState.FAILED
            failed.finished_at = recent
            active = session.get(Job, "old-active")
            active.state = JobState.PARSING
            active.finished_at = old
            lease_metadata = session.get(Job, "old-lease-metadata")
            lease_metadata.state = JobState.FAILED
            lease_metadata.finished_at = old
            lease_metadata.lease_expires_at = utc_now() + timedelta(minutes=5)
            session.add_all([completed, failed, active, lease_metadata])
            session.commit()

        selected = self.repository.list_terminal_before(cutoff)

        self.assertEqual([job.id for job in selected], ["old-completed"])

    def test_check_connection_returns_false_without_exposing_database_error(self):
        self.assertTrue(self.repository.check_connection())
        private_error = RuntimeError(
            r"postgresql://private-user:secret@db.internal/jstudy unavailable"
        )
        with mock.patch.object(self.engine, "connect", side_effect=private_error):
            self.assertFalse(self.repository.check_connection())

    def test_delete_terminal_cascades_only_terminal_unleased_job(self):
        for job_id in ("terminal", "active", "leased-terminal"):
            self.repository.create_job(self.command(job_id))

        with Session(self.engine) as session:
            terminal = session.get(Job, "terminal")
            terminal.state = JobState.COMPLETED
            terminal.finished_at = utc_now() - timedelta(days=2)
            active = session.get(Job, "active")
            active.state = JobState.PARSING
            leased = session.get(Job, "leased-terminal")
            leased.state = JobState.FAILED
            leased.finished_at = utc_now() - timedelta(days=2)
            leased.lease_owner = "worker-1"
            leased.lease_expires_at = utc_now() + timedelta(minutes=5)
            session.add_all([terminal, active, leased])
            session.commit()

        self.assertTrue(self.repository.delete_terminal("terminal"))
        self.assertFalse(self.repository.delete_terminal("active"))
        self.assertFalse(self.repository.delete_terminal("leased-terminal"))
        self.assertIsNone(self.repository.get("terminal"))
        self.assertEqual(self.repository.list_sources("terminal"), [])
        with Session(self.engine) as session:
            transitions = session.exec(
                select(JobTransition).where(JobTransition.job_id == "terminal")
            ).all()
        self.assertEqual(transitions, [])
        self.assertIsNotNone(self.repository.get("active"))
        self.assertIsNotNone(self.repository.get("leased-terminal"))

    def test_resolve_job_path_rejects_escape_and_existing_links(self):
        safe = resolve_job_path(self.jobs_root, "job-1/inputs/S001.pdf")
        self.assertEqual(safe, self.jobs_root / "job-1" / "inputs" / "S001.pdf")
        with self.assertRaises(RelativePathError):
            resolve_job_path(self.jobs_root, "../escape.pdf")

        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        link = self.jobs_root / "linked"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as symlink_error:
            if os.name != "nt":
                self.fail(f"could not create test symlink: {symlink_error}")
            completed = subprocess.run(
                ["cmd.exe", "/c", "mklink", "/J", str(link), str(outside)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )
        try:
            with self.assertRaises(RelativePathError):
                resolve_job_path(self.jobs_root, "linked/escape.pdf")
        finally:
            if link.is_symlink():
                link.unlink()
            elif link.exists():
                link.rmdir()


if __name__ == "__main__":
    unittest.main()
