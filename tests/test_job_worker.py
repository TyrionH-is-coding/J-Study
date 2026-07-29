from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest import mock

from sqlmodel import Session, select

from packages.core.jstudy_core.auth_db import (
    create_application_tables,
    create_auth_engine,
)
from packages.core.jstudy_core.job_system.models import (
    ArtifactKind,
    Job,
    JobTransition,
    utc_now,
)
from packages.core.jstudy_core.job_system.repository import (
    CreateJobCommand,
    JobRepository,
    JobSourceInput,
    StaleWorkerError,
)
from packages.core.jstudy_core.job_system.states import JobState
from packages.core.jstudy_core.job_system.worker import (
    JobWorker,
    PermanentJobError,
    RetryableJobError,
    _filter_runner_kwargs,
)
from packages.core.jstudy_core.settings import RuntimeSettings


class ObservedRepository(JobRepository):
    def __init__(self, engine):
        super().__init__(engine)
        self.lease_renewed = threading.Event()

    def renew_lease(self, job_id, worker_id, lease_seconds):
        renewed = super().renew_lease(job_id, worker_id, lease_seconds)
        if renewed:
            self.lease_renewed.set()
        return renewed


class LeaseLosingRepository(JobRepository):
    def __init__(self, engine):
        super().__init__(engine)
        self.renew_attempted = threading.Event()

    def renew_lease(self, job_id, worker_id, lease_seconds):
        self.renew_attempted.set()
        return False


class LeaseErrorRepository(JobRepository):
    def __init__(self, engine):
        super().__init__(engine)
        self.renew_attempted = threading.Event()

    def renew_lease(self, job_id, worker_id, lease_seconds):
        self.renew_attempted.set()
        raise RuntimeError("database unavailable")


class JobWorkerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.jobs_root = self.root / "jobs"
        self.jobs_root.mkdir()
        self.engine = create_auth_engine(
            f"sqlite:///{(self.root / 'jobs.db').as_posix()}"
        )
        self.addCleanup(self.engine.dispose)
        create_application_tables(self.engine)
        self.repository = JobRepository(self.engine)
        self.settings = RuntimeSettings(
            project_root=self.root,
            jobs_root=self.jobs_root,
            soul_path=self.root / "soul.md",
            mnemonics_path=self.root / "mnemonics.md",
            api_key_path=None,
            chat_model="chat",
            embed_model="embed",
            worker_poll_seconds=0,
            worker_lease_seconds=3,
            worker_max_attempts=2,
            parser_profiles_config={
                "default_profile_id": "fast",
                "profiles": [
                    {
                        "id": "fast",
                        "display_name": "Fast",
                        "backend": "pymupdf",
                        "tier": "fast",
                        "enabled": True,
                        "visible_to_users": True,
                        "requires_admin": False,
                    }
                ],
            },
        )
        self.settings.soul_path.write_text("soul", encoding="utf-8")
        self.settings.mnemonics_path.write_text("", encoding="utf-8")

    def create_job(
        self,
        *,
        job_id: str = "job-1",
        service_mode: str = "single_courseware",
        max_attempts: int = 2,
        scenario_id: str = "medicine-default",
        parser_profile_id: str = "fast",
    ):
        job_dir = self.jobs_root / job_id
        inputs = job_dir / "inputs"
        inputs.mkdir(parents=True)
        source = inputs / "S001.pdf"
        source.write_bytes(b"%PDF-1.4\nsource")
        outline_relative_path = None
        if service_mode == "course_outline":
            outline = inputs / "outline.md"
            outline.write_text("# Unit", encoding="utf-8")
            outline_relative_path = f"{job_id}/inputs/outline.md"
        return self.repository.create_job(
            CreateJobCommand(
                id=job_id,
                owner_user_id="owner-1",
                service_mode=service_mode,
                scenario_id=scenario_id,
                parser_profile_id=parser_profile_id,
                generation_mode="study",
                max_attempts=max_attempts,
                outline_relative_path=outline_relative_path,
                sources=(
                    JobSourceInput(
                        source_id="S001",
                        original_filename="lecture.pdf",
                        relative_path=f"{job_id}/inputs/S001.pdf",
                        mime_type="application/pdf",
                        byte_size=source.stat().st_size,
                        sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    ),
                ),
            )
        )

    def output_runner(self, calls, expected_mode):
        def runner(**kwargs):
            calls.append(kwargs)
            self.assertEqual(kwargs["service_mode"], expected_mode)
            callback = kwargs["progress_callback"]
            for state in (
                JobState.PARSING,
                JobState.RETRIEVING,
                JobState.GENERATING,
                JobState.PACKAGING,
            ):
                callback(state)
            output_dir = kwargs["output_dir"]
            output_dir.mkdir(parents=True, exist_ok=True)
            markdown = output_dir / "result-output.md"
            package = output_dir / "result-material-package.json"
            markdown.write_text("# Result\n", encoding="utf-8")
            sections = (
                [
                    {
                        "id": "section-001",
                        "title": "Unit One",
                        "order": 1,
                        "status": "generated",
                        "quality": {"evidence_count": 2},
                        "artifact_filenames": {"markdown": markdown.name},
                    },
                    {
                        "id": "section-002",
                        "title": "Unit Two",
                        "order": 2,
                        "status": "weak_evidence",
                        "quality": {"evidence_count": 0},
                        "artifact_filenames": {"markdown": markdown.name},
                    },
                ]
                if expected_mode == "course_outline"
                else [
                    {
                        "id": "full-material",
                        "title": "完整资料",
                        "order": 1,
                        "artifact_urls": {"markdown": markdown.name},
                    }
                ]
            )
            package.write_text(
                json.dumps(
                    {
                        "type": "material_package",
                        "service_mode": expected_mode,
                        "sections": sections,
                    }
                ),
                encoding="utf-8",
            )
            return {"markdown": markdown, "package": package}

        return runner

    def transitions(self, job_id="job-1"):
        with Session(self.engine) as session:
            return list(
                session.exec(
                    select(JobTransition)
                    .where(JobTransition.job_id == job_id)
                    .order_by(JobTransition.sequence)
                ).all()
            )

    def test_claims_single_courseware_completes_and_indexes_artifacts(self):
        self.create_job()
        calls = []
        worker = JobWorker(
            self.repository,
            self.settings,
            worker_id="worker-1",
            single_runner=self.output_runner(calls, "single_courseware"),
            outline_runner=lambda **kwargs: self.fail("wrong runner"),
        )

        self.assertTrue(worker.run_once())

        job = self.repository.get("job-1")
        self.assertEqual(job.state, JobState.COMPLETED)
        self.assertEqual(
            [event.to_state for event in self.transitions()],
            [
                JobState.QUEUED,
                JobState.PARSING,
                JobState.RETRIEVING,
                JobState.GENERATING,
                JobState.PACKAGING,
                JobState.COMPLETED,
            ],
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["pdf_path"], self.jobs_root / "job-1/inputs/S001.pdf")
        self.assertEqual(
            calls[0]["output_dir"],
            self.jobs_root / "job-1/attempts/1/output",
        )
        artifacts = self.repository.list_artifacts("job-1")
        artifacts_by_kind = {
            artifact.kind: artifact for artifact in artifacts
        }
        self.assertEqual(
            set(artifacts_by_kind),
            {ArtifactKind.MARKDOWN, ArtifactKind.PACKAGE},
        )
        self.assertTrue(all(artifact.byte_size > 0 for artifact in artifacts))
        self.assertTrue(all(len(artifact.sha256) == 64 for artifact in artifacts))
        self.assertEqual(
            artifacts_by_kind[ArtifactKind.MARKDOWN].relative_path,
            "job-1/attempts/1/output/result-output.md",
        )
        self.assertEqual(
            artifacts_by_kind[ArtifactKind.PACKAGE].relative_path,
            "job-1/attempts/1/output/result-material-package.json",
        )
        sections = self.repository.list_sections("job-1")
        self.assertEqual(
            [
                (
                    section.section_id,
                    section.position,
                    section.title,
                    section.status,
                    section.artifact_filename,
                )
                for section in sections
            ],
            [
                (
                    "full-material",
                    1,
                    "完整资料",
                    "generated",
                    "result-output.md",
                )
            ],
        )

    def test_course_outline_selects_outline_runner_and_preserves_sources(self):
        self.create_job(service_mode="course_outline")
        calls = []
        worker = JobWorker(
            self.repository,
            self.settings,
            worker_id="worker-1",
            single_runner=lambda **kwargs: self.fail("wrong runner"),
            outline_runner=self.output_runner(calls, "course_outline"),
        )

        self.assertTrue(worker.run_once())

        kwargs = calls[0]
        self.assertEqual(
            kwargs["outline_path"],
            self.jobs_root / "job-1/inputs/outline.md",
        )
        self.assertEqual(
            kwargs["pdf_paths"],
            [self.jobs_root / "job-1/inputs/S001.pdf"],
        )
        self.assertEqual(
            kwargs["source_files"],
            [
                {
                    "source_id": "S001",
                    "file_name": "lecture.pdf",
                }
            ],
        )
        sections = self.repository.list_sections("job-1")
        self.assertEqual(
            [
                (
                    section.section_id,
                    section.position,
                    section.status,
                    json.loads(section.quality_json),
                )
                for section in sections
            ],
            [
                ("section-001", 1, "generated", {"evidence_count": 2}),
                ("section-002", 2, "weak_evidence", {"evidence_count": 0}),
            ],
        )

    def test_embedding_cache_is_isolated_to_the_claimed_job_attempt(self):
        self.create_job(job_id="job-1")
        self.create_job(job_id="job-2")
        calls = []
        worker = JobWorker(
            self.repository,
            self.settings,
            worker_id="worker-1",
            single_runner=self.output_runner(calls, "single_courseware"),
        )

        self.assertTrue(worker.run_once())
        self.assertTrue(worker.run_once())

        cache_paths = [call["embedding_cache_path"] for call in calls]
        self.assertEqual(
            cache_paths,
            [
                self.jobs_root / "job-1/attempts/1/embedding-cache.json",
                self.jobs_root / "job-2/attempts/1/embedding-cache.json",
            ],
        )
        self.assertNotEqual(cache_paths[0], cache_paths[1])

    def test_each_claim_reloads_generation_settings_and_keeps_running_snapshot(self):
        self.create_job(job_id="job-1")
        self.create_job(
            job_id="job-2",
            scenario_id="new-scenario",
            parser_profile_id="new-parser",
        )
        new_soul = self.root / "new-soul.md"
        new_mnemonics = self.root / "new-mnemonics.md"
        new_soul.write_text("new soul", encoding="utf-8")
        new_mnemonics.write_text("new mnemonics", encoding="utf-8")
        updated = replace(
            self.settings,
            chat_model="chat-new",
            embed_model="embed-new",
            rag_config=replace(
                self.settings.rag_config,
                top_k_candidates=7,
            ),
            parser_profiles_config={
                "default_profile_id": "new-parser",
                "profiles": [
                    {
                        "id": "new-parser",
                        "display_name": "New parser",
                        "backend": "pymupdf",
                        "tier": "fast",
                        "enabled": True,
                        "visible_to_users": True,
                        "requires_admin": False,
                    }
                ],
            },
            content_pack_config={
                "active_pack_id": "new-pack",
                "default_scenario_id": "new-scenario",
                "packs": [
                    {
                        "id": "new-pack",
                        "enabled": True,
                        "mnemonics_path": new_mnemonics.name,
                    }
                ],
                "scenarios": [
                    {
                        "id": "new-scenario",
                        "enabled": True,
                        "content_pack_id": "new-pack",
                        "prompt_profile": "new-soul",
                    }
                ],
                "soul_profiles": [
                    {
                        "id": "new-soul",
                        "soul_path": new_soul.name,
                    }
                ],
            },
            default_scenario_id="medicine-default",
        )
        current = [self.settings]
        calls = []

        def runner(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                current[0] = updated
                self.assertEqual(kwargs["chat_model"], "chat")
                self.assertEqual(kwargs["embed_model"], "embed")
                self.assertEqual(kwargs["rag_config"].top_k_candidates, 14)
            callback = kwargs["progress_callback"]
            for state in (
                JobState.PARSING,
                JobState.RETRIEVING,
                JobState.GENERATING,
                JobState.PACKAGING,
            ):
                callback(state)
            output_dir = kwargs["output_dir"]
            output_dir.mkdir(parents=True, exist_ok=True)
            markdown = output_dir / "result-output.md"
            package = output_dir / "result-material-package.json"
            markdown.write_text("# Result\n", encoding="utf-8")
            package.write_text(
                json.dumps(
                    {
                        "type": "material_package",
                        "service_mode": kwargs["service_mode"],
                        "sections": [
                            {
                                "id": "full-material",
                                "title": "完整资料",
                                "order": 1,
                                "artifact_urls": {"markdown": markdown.name},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            return {"markdown": markdown, "package": package}

        worker = JobWorker(
            self.repository,
            self.settings,
            worker_id="worker-settings-test",
            single_runner=runner,
            settings_provider=lambda: current[0],
        )

        self.assertTrue(worker.run_once())
        self.assertTrue(worker.run_once())

        self.assertEqual(calls[1]["chat_model"], "chat-new")
        self.assertEqual(calls[1]["embed_model"], "embed-new")
        self.assertEqual(calls[1]["rag_config"].top_k_candidates, 7)
        self.assertEqual(calls[1]["parser_backend"], "pymupdf")
        self.assertEqual(
            calls[1]["routing_metadata"]["scenario"]["resolved_scenario_id"],
            "new-scenario",
        )
        self.assertEqual(calls[1]["soul_path"], new_soul)
        self.assertEqual(calls[1]["mnemonics_path"], new_mnemonics)

    def test_retryable_failure_requeues_then_exhausts_attempts(self):
        self.create_job(max_attempts=2)

        def failing_runner(**kwargs):
            raise RetryableJobError("provider_timeout", "Provider unavailable.")

        worker = JobWorker(
            self.repository,
            self.settings,
            worker_id="worker-1",
            single_runner=failing_runner,
        )

        self.assertTrue(worker.run_once())
        first = self.repository.get("job-1")
        self.assertEqual(first.state, JobState.QUEUED)
        self.assertIsNone(first.error_code)

        self.assertTrue(worker.run_once())
        second = self.repository.get("job-1")
        self.assertEqual(second.state, JobState.FAILED)
        self.assertEqual(second.error_code, "provider_timeout")
        self.assertEqual(second.error_message, "Provider unavailable.")

    def test_package_service_mode_mismatch_fails_without_sections(self):
        self.create_job(
            service_mode="course_outline",
            max_attempts=1,
        )

        def mismatched_runner(**kwargs):
            outputs = self.output_runner([], "course_outline")(**kwargs)
            package = json.loads(
                outputs["package"].read_text(encoding="utf-8")
            )
            package["service_mode"] = "single_courseware"
            outputs["package"].write_text(
                json.dumps(package),
                encoding="utf-8",
            )
            return outputs

        worker = JobWorker(
            self.repository,
            self.settings,
            worker_id="worker-package-validation",
            outline_runner=mismatched_runner,
        )

        self.assertTrue(worker.run_once())

        job = self.repository.get("job-1")
        self.assertEqual(job.state, JobState.FAILED)
        self.assertEqual(job.error_code, "invalid_job_output")
        self.assertEqual(self.repository.list_artifacts("job-1"), [])
        self.assertEqual(self.repository.list_sections("job-1"), [])

    def test_permanent_and_generic_failures_store_safe_errors(self):
        cases = (
            (
                "permanent",
                lambda **kwargs: (_ for _ in ()).throw(
                    PermanentJobError("invalid_job_input", "Job input is invalid.")
                ),
                "invalid_job_input",
                "Job input is invalid.",
            ),
            (
                "generic",
                lambda **kwargs: (_ for _ in ()).throw(
                    RuntimeError(r"D:\private\secret.pdf token=secret")
                ),
                "worker_error",
                "The job could not be processed.",
            ),
        )
        for job_id, runner, code, message in cases:
            with self.subTest(job_id=job_id):
                self.create_job(job_id=job_id, max_attempts=1)
                worker = JobWorker(
                    self.repository,
                    self.settings,
                    worker_id=f"worker-{job_id}",
                    single_runner=runner,
                )
                self.assertTrue(worker.run_once())
                job = self.repository.get(job_id)
                self.assertEqual(job.state, JobState.FAILED)
                self.assertEqual(job.error_code, code)
                self.assertEqual(job.error_message, message)
                self.assertNotIn("private", job.error_message)
                self.assertNotIn("secret", job.error_message)

    def test_heartbeat_renews_lease_while_runner_is_active(self):
        self.create_job()
        repository = ObservedRepository(self.engine)

        def long_runner(**kwargs):
            self.assertTrue(repository.lease_renewed.wait(timeout=3))
            return self.output_runner([], "single_courseware")(**kwargs)

        worker = JobWorker(
            repository,
            self.settings,
            worker_id="worker-1",
            single_runner=long_runner,
        )

        self.assertTrue(worker.run_once())
        self.assertEqual(repository.get("job-1").state, JobState.COMPLETED)

    def test_stale_worker_cannot_record_artifacts_or_complete(self):
        self.create_job()
        repository = LeaseLosingRepository(self.engine)

        def stale_runner(**kwargs):
            callback = kwargs["progress_callback"]
            for state in (
                JobState.PARSING,
                JobState.RETRIEVING,
                JobState.GENERATING,
                JobState.PACKAGING,
            ):
                callback(state)
            self.assertTrue(repository.renew_attempted.wait(timeout=3))
            output_dir = kwargs["output_dir"]
            output_dir.mkdir(parents=True, exist_ok=True)
            markdown = output_dir / "result-output.md"
            package = output_dir / "result-material-package.json"
            markdown.write_text("# stale\n", encoding="utf-8")
            package.write_text("{}", encoding="utf-8")
            return {"markdown": markdown, "package": package}

        worker = JobWorker(
            repository,
            self.settings,
            worker_id="worker-1",
            single_runner=stale_runner,
        )

        self.assertTrue(worker.run_once())

        job = repository.get("job-1")
        self.assertNotEqual(job.state, JobState.COMPLETED)
        self.assertEqual(repository.list_artifacts("job-1"), [])
        self.assertEqual(repository.list_sections("job-1"), [])
        first_attempt = (
            self.jobs_root / "job-1/attempts/1/output/result-output.md"
        )
        self.assertEqual(first_attempt.read_text(encoding="utf-8"), "# stale\n")

        with Session(self.engine) as session:
            stored = session.get(Job, "job-1")
            stored.lease_expires_at = utc_now() - timedelta(seconds=1)
            session.add(stored)
            session.commit()
        recovery = repository.requeue_expired_leases(utc_now())
        self.assertEqual(recovery.requeued, 1)

        next_worker = JobWorker(
            self.repository,
            self.settings,
            worker_id="worker-2",
            single_runner=self.output_runner([], "single_courseware"),
        )
        self.assertTrue(next_worker.run_once())

        second_attempt = (
            self.jobs_root / "job-1/attempts/2/output/result-output.md"
        )
        self.assertEqual(first_attempt.read_text(encoding="utf-8"), "# stale\n")
        self.assertEqual(second_attempt.read_text(encoding="utf-8"), "# Result\n")
        self.assertEqual(
            {
                artifact.relative_path
                for artifact in repository.list_artifacts("job-1")
            },
            {
                "job-1/attempts/2/output/result-output.md",
                "job-1/attempts/2/output/result-material-package.json",
            },
        )

    def test_stale_failure_transition_does_not_escape_run_once(self):
        self.create_job()

        class StaleFailureRepository(JobRepository):
            def transition(self, job_id, target, event):
                if event.event in {"worker_retry", "worker_failed"}:
                    raise StaleWorkerError("lease changed during failure")
                return super().transition(job_id, target, event)

        repository = StaleFailureRepository(self.engine)
        worker = JobWorker(
            repository,
            self.settings,
            worker_id="worker-1",
            single_runner=lambda **kwargs: (_ for _ in ()).throw(
                RuntimeError("runner failed")
            ),
        )

        self.assertTrue(worker.run_once())

    def test_positional_only_runner_kwargs_are_not_forwarded(self):
        def runner(output_dir, /, *, service_mode):
            return output_dir, service_mode

        filtered = _filter_runner_kwargs(
            runner,
            {
                "output_dir": Path("output"),
                "service_mode": "single_courseware",
                "ignored": True,
            },
        )

        self.assertEqual(filtered, {"service_mode": "single_courseware"})

    def test_heartbeat_error_marks_worker_stale(self):
        self.create_job()
        repository = LeaseErrorRepository(self.engine)

        def stale_runner(**kwargs):
            self.assertTrue(repository.renew_attempted.wait(timeout=3))
            return self.output_runner([], "single_courseware")(**kwargs)

        worker = JobWorker(
            repository,
            self.settings,
            worker_id="worker-1",
            single_runner=stale_runner,
        )

        self.assertTrue(worker.run_once())

        job = repository.get("job-1")
        self.assertNotEqual(job.state, JobState.COMPLETED)
        self.assertEqual(repository.list_artifacts("job-1"), [])

    def test_new_worker_instance_resumes_queued_job_and_empty_queue_returns_false(self):
        self.create_job()
        first = JobWorker(
            self.repository,
            self.settings,
            worker_id="worker-before-restart",
            single_runner=lambda **kwargs: self.fail("must not run"),
        )
        second = JobWorker(
            self.repository,
            self.settings,
            worker_id="worker-after-restart",
            single_runner=self.output_runner([], "single_courseware"),
        )

        self.assertTrue(second.run_once())
        self.assertFalse(first.run_once())
        self.assertEqual(self.repository.get("job-1").state, JobState.COMPLETED)

    def test_run_forever_stops_without_claiming_more_work(self):
        stop_event = threading.Event()
        stop_event.set()
        worker = JobWorker(
            self.repository,
            self.settings,
            worker_id="worker-1",
            single_runner=lambda **kwargs: self.fail("must not run"),
        )

        worker.run_forever(stop_event)

    def mark_old_terminal(self, job_id: str, state: JobState = JobState.COMPLETED):
        with Session(self.engine) as session:
            job = session.get(Job, job_id)
            job.state = state
            job.finished_at = utc_now() - timedelta(hours=2)
            job.lease_owner = None
            job.lease_expires_at = None
            session.add(job)
            session.commit()

    def retention_worker(self) -> JobWorker:
        return JobWorker(
            self.repository,
            replace(self.settings, job_retention_hours=1),
            worker_id="cleanup-worker",
            single_runner=lambda **kwargs: self.fail("must not run"),
        )

    def test_retention_cleanup_removes_files_then_cascades_database_job(self):
        self.create_job(job_id="old-terminal")
        self.mark_old_terminal("old-terminal")
        job_dir = self.jobs_root / "old-terminal"

        self.assertFalse(self.retention_worker().run_once())

        self.assertFalse(job_dir.exists())
        self.assertIsNone(self.repository.get("old-terminal"))

    def test_retention_cleanup_deletes_database_job_when_directory_is_missing(self):
        self.create_job(job_id="missing-files")
        self.mark_old_terminal("missing-files")
        shutil.rmtree(self.jobs_root / "missing-files")

        self.assertFalse(self.retention_worker().run_once())

        self.assertIsNone(self.repository.get("missing-files"))

    def test_retention_cleanup_is_bounded_to_ten_jobs_per_run(self):
        for index in range(11):
            job_id = f"old-{index:02d}"
            self.create_job(job_id=job_id)
            self.mark_old_terminal(job_id)

        self.assertFalse(self.retention_worker().run_once())

        remaining = [
            job_id
            for index in range(11)
            if self.repository.get(job_id := f"old-{index:02d}") is not None
        ]
        self.assertEqual(len(remaining), 1)

    def test_retention_cleanup_never_deletes_active_or_leased_job(self):
        self.create_job(job_id="active-job")
        with Session(self.engine) as session:
            job = session.get(Job, "active-job")
            job.state = JobState.PARSING
            job.finished_at = utc_now() - timedelta(hours=2)
            job.lease_owner = "other-worker"
            job.lease_expires_at = utc_now() + timedelta(minutes=5)
            session.add(job)
            session.commit()

        self.assertFalse(self.retention_worker().run_once())

        self.assertTrue((self.jobs_root / "active-job").is_dir())
        self.assertIsNotNone(self.repository.get("active-job"))

    def test_retention_cleanup_rejects_job_directory_link(self):
        self.create_job(job_id="linked-job")
        self.mark_old_terminal("linked-job")
        job_dir = self.jobs_root / "linked-job"
        shutil.rmtree(job_dir)
        outside = self.root / "outside"
        outside.mkdir()
        marker = outside / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        try:
            job_dir.symlink_to(outside, target_is_directory=True)
        except OSError as symlink_error:
            if os.name != "nt":
                self.fail(f"could not create test symlink: {symlink_error}")
            completed = subprocess.run(
                ["cmd.exe", "/c", "mklink", "/J", str(job_dir), str(outside)],
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
            self.assertFalse(self.retention_worker().run_once())
            self.assertTrue(marker.is_file())
            self.assertIsNotNone(self.repository.get("linked-job"))
        finally:
            if job_dir.is_symlink():
                job_dir.unlink()
            elif job_dir.exists():
                job_dir.rmdir()

    def test_retention_cleanup_keeps_database_row_after_file_error_for_retry(self):
        self.create_job(job_id="retry-job")
        self.mark_old_terminal("retry-job")
        self.create_job(job_id="queued-job")
        calls = []
        worker = JobWorker(
            self.repository,
            replace(self.settings, job_retention_hours=1),
            worker_id="cleanup-worker",
            single_runner=self.output_runner(calls, "single_courseware"),
        )

        with mock.patch(
            "packages.core.jstudy_core.job_system.worker.shutil.rmtree",
            side_effect=OSError(r"D:\private\jobs\retry-job access denied"),
        ):
            self.assertTrue(worker.run_once())

        self.assertIsNotNone(self.repository.get("retry-job"))
        self.assertTrue((self.jobs_root / "retry-job").is_dir())
        self.assertEqual(
            self.repository.get("queued-job").state,
            JobState.COMPLETED,
        )
        self.assertEqual(len(calls), 1)
        self.assertFalse(worker.run_once())
        self.assertIsNone(self.repository.get("retry-job"))


if __name__ == "__main__":
    unittest.main()
