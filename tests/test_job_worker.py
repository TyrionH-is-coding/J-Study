from __future__ import annotations

import hashlib
import io
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
from packages.core.jstudy_core.documents import (
    ParsedBlock,
    ParsedDocument,
    ParsedPage,
)
from packages.core.jstudy_core.documents.mineru_client import (
    MinerUPermanentProviderError,
    MinerURetryableProviderError,
)
from packages.core.jstudy_core.admin_settings import AdminSettingsService
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
    ARTIFACT_HASH_CHUNK_BYTES,
    JobWorker,
    PermanentJobError,
    RetryableJobError,
    _hash_artifact_stream,
    _filter_runner_kwargs,
)
from packages.core.jstudy_core.materials.validation import (
    MATERIAL_PACKAGE_MAX_BYTES,
    MaterialValidationError,
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


class FakeDocumentService:
    def __init__(self):
        self.calls = []

    def parse(self, sources, *, artifact_root):
        self.calls.append((sources, artifact_root))
        return [
            ParsedDocument(
                contract_version="1",
                source_id=source.source_id,
                source_file=source.pdf_path.name,
                source_sha256=source.sha256,
                parser_name="mineru",
                parser_version="v4",
                parser_model="vlm",
                page_count=1,
                pages=[
                    ParsedPage(
                        page_number=1,
                        text="Courseware fact",
                        markdown="Courseware fact",
                        blocks=[
                            ParsedBlock(
                                block_id=(
                                    f"{source.source_id}-P001-B001"
                                ),
                                kind="text",
                                text="Courseware fact",
                                markdown="Courseware fact",
                            )
                        ],
                    )
                ],
                warnings=[],
                provider_trace_id="mock-trace",
            )
            for source in sources
        ]


class FailingDocumentService:
    def __init__(self, error):
        self.error = error

    def parse(self, sources, *, artifact_root):
        raise self.error


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
        self.default_document_service = FakeDocumentService()
        service_patch = mock.patch.object(
            JobWorker,
            "_create_document_service",
            return_value=self.default_document_service,
        )
        service_patch.start()
        self.addCleanup(service_patch.stop)

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

    def test_package_hash_stops_after_one_probe_chunk(self):
        stream = io.BytesIO(
            b"x"
            * (
                MATERIAL_PACKAGE_MAX_BYTES
                + ARTIFACT_HASH_CHUNK_BYTES * 3
            )
        )

        with self.assertRaises(MaterialValidationError) as context:
            _hash_artifact_stream(
                stream,
                max_bytes=MATERIAL_PACKAGE_MAX_BYTES,
            )

        self.assertEqual(context.exception.code, "package_too_large")
        self.assertLessEqual(
            stream.tell(),
            MATERIAL_PACKAGE_MAX_BYTES + ARTIFACT_HASH_CHUNK_BYTES,
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
            evidence = output_dir / "result-evidence.json"
            evidence_links = output_dir / "result-evidence_links.json"
            quality = output_dir / "result-quality.json"
            trace = output_dir / "result-retrieval_trace.json"
            package = output_dir / "result-material-package.json"
            markdown.write_text("# Result\n", encoding="utf-8")
            evidence.write_text("[]", encoding="utf-8")
            evidence_links.write_text("[]", encoding="utf-8")
            quality.write_text('{"status": "pass"}', encoding="utf-8")
            trace.write_text("{}", encoding="utf-8")
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
            return {
                "markdown": markdown,
                "evidence": evidence,
                "evidence_links": evidence_links,
                "quality": quality,
                "trace": trace,
                "package": package,
            }

        return runner

    def v2_output_runner(self, calls, expected_mode):
        legacy_runner = self.output_runner(calls, expected_mode)

        def runner(**kwargs):
            outputs = legacy_runner(**kwargs)
            evidence = [
                {
                    "id": "E001",
                    "source_id": "S001",
                    "source_file": "lecture.pdf",
                    "page": 1,
                    "chunk_id": "S001-C001",
                    "excerpt": "Fact",
                }
            ]
            outputs["evidence"].write_text(
                json.dumps(evidence),
                encoding="utf-8",
            )
            sections = [
                {
                    "id": (
                        "full-material"
                        if expected_mode == "single_courseware"
                        else "section-001"
                    ),
                    "order": 1,
                    "title": (
                        "完整资料"
                        if expected_mode == "single_courseware"
                        else "Unit One"
                    ),
                    "status": "generated",
                    "quality": {
                        "evidence_status": "sufficient",
                        "evidence_count": 1,
                        "cited_evidence_count": 1,
                        "citation_coverage": 1.0,
                    },
                    "source_ids": ["S001"],
                    "evidence_ids": ["E001"],
                    "blocks": [
                        {
                            "id": "paragraph-001",
                            "type": "paragraph",
                            "runs": [
                                {"type": "text", "text": "Fact "},
                                {
                                    "type": "citation",
                                    "evidence_id": "E001",
                                },
                            ],
                        }
                    ],
                }
            ]
            outputs["package"].write_text(
                json.dumps(
                    {
                        "schema_version": "material-package.v2",
                        "package_id": kwargs["package_id"],
                        "service_mode": expected_mode,
                        "title": "学习资料",
                        "subject": "medicine",
                        "language": "zh-CN",
                        "source_ids": ["S001"],
                        "sections": sections,
                        "rendering": {
                            "default_theme": {
                                "theme_id": "clinical-standard",
                                "theme_version": "1.0.0",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            return outputs

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
            },
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

    def test_worker_parses_once_and_persists_sequence_artifacts(self):
        self.create_job()
        document_service = FakeDocumentService()
        calls = []
        runner = self.v2_output_runner(calls, "single_courseware")
        worker = JobWorker(
            self.repository,
            self.settings,
            worker_id="worker-sequence",
            single_runner=runner,
            document_service=document_service,
        )

        self.assertTrue(worker.run_once())

        self.assertEqual(len(document_service.calls), 1)
        self.assertEqual(
            [item.source_id for item in document_service.calls[0][0]],
            ["S001"],
        )
        self.assertEqual(
            [item.source_id for item in calls[0]["parsed_documents"]],
            ["S001"],
        )
        self.assertEqual(
            calls[0]["courseware_manifest"].schema_version,
            "courseware-manifest.v1",
        )
        self.assertEqual(
            calls[0]["learning_map"].schema_version,
            "learning-map.v1",
        )
        self.assertEqual(
            calls[0]["coverage_ledger"].schema_version,
            "coverage-ledger.v1",
        )
        artifact_kinds = {
            artifact.kind
            for artifact in self.repository.list_artifacts("job-1")
        }
        self.assertTrue(
            {
                ArtifactKind.MANIFEST,
                ArtifactKind.LEARNING_MAP,
                ArtifactKind.COVERAGE,
            }
            <= artifact_kinds
        )

    def test_mineru_provider_errors_have_permanent_and_retryable_job_semantics(self):
        self.create_job(job_id="permanent", max_attempts=2)
        permanent = JobWorker(
            self.repository,
            self.settings,
            worker_id="worker-permanent",
            document_service=FailingDocumentService(
                MinerUPermanentProviderError("rejected")
            ),
        )
        self.assertTrue(permanent.run_once())
        permanent_job = self.repository.get("permanent")
        self.assertEqual(permanent_job.state, JobState.FAILED)
        self.assertEqual(
            permanent_job.error_code,
            "mineru_provider_rejected",
        )

        self.create_job(job_id="retryable", max_attempts=2)
        retryable = JobWorker(
            self.repository,
            self.settings,
            worker_id="worker-retryable",
            document_service=FailingDocumentService(
                MinerURetryableProviderError("unavailable")
            ),
        )
        self.assertTrue(retryable.run_once())
        retryable_job = self.repository.get("retryable")
        self.assertEqual(retryable_job.state, JobState.QUEUED)
        self.assertEqual(retryable_job.attempt_count, 1)

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
        self.assertEqual(calls[1]["parser_backend"], "mineru")
        self.assertEqual(
            calls[1]["routing_metadata"]["scenario"]["resolved_scenario_id"],
            "new-scenario",
        )
        self.assertEqual(calls[1]["soul_path"], new_soul)
        self.assertEqual(calls[1]["mnemonics_path"], new_mnemonics)

    def test_runner_credential_matches_readiness_priority(self):
        admin_key_file = self.root / "admin-key.txt"
        env_key_file = self.root / "env-key.txt"
        admin_key_file.write_text("admin-file-value", encoding="utf-8")
        env_key_file.write_text("env-file-value", encoding="utf-8")
        settings = replace(
            self.settings,
            api_key="admin-inline-value",
            api_key_path=admin_key_file,
        )
        cases = (
            (
                "environment inline",
                {
                    "SILICONFLOW_API_KEY": "env-inline-value",
                    "SILICONFLOW_API_KEY_FILE": str(env_key_file),
                },
                "env-inline-value",
            ),
            (
                "environment file",
                {
                    "SILICONFLOW_API_KEY": "",
                    "SILICONFLOW_API_KEY_FILE": str(env_key_file),
                },
                "env-file-value",
            ),
            (
                "admin fallback",
                {
                    "SILICONFLOW_API_KEY": "",
                    "SILICONFLOW_API_KEY_FILE": "",
                },
                "admin-inline-value",
            ),
        )

        for index, (label, environment, expected) in enumerate(cases, start=1):
            with self.subTest(label=label):
                job_id = f"credential-job-{index}"
                self.create_job(job_id=job_id)
                readiness_keys = []
                calls = []

                def probe(api_key, chat_model, embed_model):
                    readiness_keys.append(api_key)
                    return {
                        "name": "provider_connectivity",
                        "status": "ok",
                        "detail": "reachable",
                    }

                with mock.patch.dict(os.environ, environment, clear=True):
                    settings.readiness(
                        probe_provider=True,
                        provider_probe=probe,
                    )
                    worker = JobWorker(
                        self.repository,
                        settings,
                        worker_id=f"credential-worker-{index}",
                        single_runner=self.output_runner(
                            calls,
                            "single_courseware",
                        ),
                    )
                    self.assertTrue(worker.run_once())

                self.assertEqual(readiness_keys, [expected])
                self.assertEqual(calls[0]["api_key"], expected)

    def test_worker_routes_mineru_with_merged_environment_parser_config(self):
        service = AdminSettingsService(self.root / "data" / "settings")
        payload = service.load_all()
        quality = next(
            profile
            for profile in payload["runtime"]["parser_profiles"]["profiles"]
            if profile["id"] == "quality"
        )
        quality["enabled"] = True
        payload["runtime"]["parser"]["mineru"]["api_token"] = "admin-token"
        service.save_all(payload)
        self.create_job(
            job_id="mineru-job",
            parser_profile_id="quality",
        )
        calls = []

        with mock.patch.dict(
            os.environ,
            {
                "MINERU_API_BASE_URL": "https://api.mineru.net",
                "MINERU_API_TOKEN": "env-token",
                "MINERU_MODEL_VERSION": "pipeline",
                "MINERU_LANGUAGE": "en",
            },
            clear=True,
        ):
            settings = RuntimeSettings.from_env(
                self.root,
                jobs_root=self.jobs_root,
            )
            worker = JobWorker(
                self.repository,
                settings,
                worker_id="mineru-worker",
                single_runner=self.output_runner(
                    calls,
                    "single_courseware",
                ),
            )
            self.assertTrue(worker.run_once())

        self.assertEqual(calls[0]["parser_backend"], "mineru")
        mineru = calls[0]["parser_config"]["mineru"]
        self.assertEqual(mineru["api_base_url"], "https://api.mineru.net")
        self.assertEqual(mineru["api_token"], "env-token")
        self.assertEqual(mineru["model_version"], "pipeline")
        self.assertEqual(mineru["language"], "en")

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

    def test_v2_package_completes_atomically_and_uses_job_package_id(self):
        self.create_job()
        calls = []
        worker = JobWorker(
            self.repository,
            self.settings,
            worker_id="worker-v2",
            single_runner=self.v2_output_runner(
                calls,
                "single_courseware",
            ),
        )

        self.assertTrue(worker.run_once())

        job = self.repository.get("job-1")
        sections = self.repository.list_sections("job-1")
        self.assertEqual(job.state, JobState.COMPLETED)
        self.assertEqual(calls[0]["package_id"], "job-1")
        self.assertEqual(len(self.repository.list_artifacts("job-1")), 9)
        self.assertEqual(
            [
                (
                    section.section_id,
                    section.position,
                    section.status,
                    json.loads(section.quality_json),
                    section.artifact_filename,
                )
                for section in sections
            ],
            [
                (
                    "full-material",
                    1,
                    "generated",
                    {
                        "citation_coverage": 1.0,
                        "cited_evidence_count": 1,
                        "evidence_count": 1,
                        "evidence_status": "sufficient",
                    },
                    "result-output.md",
                )
            ],
        )

    def test_invalid_v2_packages_fail_without_artifacts_or_sections(self):
        cases = {
            "wrong-package-id": lambda package, evidence: package.update(
                {"package_id": "another-job"}
            ),
            "wrong-service-mode": lambda package, evidence: package.update(
                {"service_mode": "course_outline"}
            ),
            "unknown-source": lambda package, evidence: package.update(
                {"source_ids": ["S999"]}
            ),
            "unknown-evidence": lambda package, evidence: package["sections"][0].update(
                {"evidence_ids": ["E999"]}
            ),
            "duplicate-section": lambda package, evidence: package["sections"].append(
                dict(package["sections"][0])
            ),
            "malformed": lambda package, evidence: package.update(
                {"unexpected": "field"}
            ),
            "evidence-source-outside-job": lambda package, evidence: evidence[
                0
            ].update({"source_id": "S999"}),
            "duplicate-evidence": lambda package, evidence: evidence.append(
                dict(evidence[0])
            ),
            "quality-mismatch": lambda package, evidence: package["sections"][
                0
            ]["quality"].update({"evidence_count": 999}),
        }
        for index, (name, mutate) in enumerate(cases.items(), start=1):
            with self.subTest(name=name):
                job_id = f"invalid-v2-{index}"
                self.create_job(job_id=job_id, max_attempts=1)

                def invalid_runner(
                    _mutate=mutate,
                    _mode="single_courseware",
                    **kwargs,
                ):
                    outputs = self.v2_output_runner([], _mode)(**kwargs)
                    package = json.loads(
                        outputs["package"].read_text(encoding="utf-8")
                    )
                    evidence = json.loads(
                        outputs["evidence"].read_text(encoding="utf-8")
                    )
                    _mutate(package, evidence)
                    outputs["package"].write_text(
                        json.dumps(package),
                        encoding="utf-8",
                    )
                    outputs["evidence"].write_text(
                        json.dumps(evidence),
                        encoding="utf-8",
                    )
                    return outputs

                worker = JobWorker(
                    self.repository,
                    self.settings,
                    worker_id=f"worker-{job_id}",
                    single_runner=invalid_runner,
                )
                self.assertTrue(worker.run_once())

                job = self.repository.get(job_id)
                self.assertEqual(job.state, JobState.FAILED)
                self.assertEqual(job.error_code, "invalid_job_output")
                self.assertEqual(
                    self.repository.list_artifacts(job_id),
                    [],
                )
                self.assertEqual(self.repository.list_sections(job_id), [])

    def test_legacy_package_limits_fail_without_artifacts_or_sections(self):
        def too_many_sections(package_path):
            package = json.loads(package_path.read_text(encoding="utf-8"))
            template = package["sections"][0]
            package["sections"] = [
                {
                    **template,
                    "id": f"section-{index:03d}",
                    "order": index,
                }
                for index in range(1, 122)
            ]
            package_path.write_text(json.dumps(package), encoding="utf-8")

        def oversized_title(package_path):
            package = json.loads(package_path.read_text(encoding="utf-8"))
            package["sections"][0]["title"] = "x" * 501
            package_path.write_text(json.dumps(package), encoding="utf-8")

        def oversized_bytes(package_path):
            package_path.write_bytes(b" " * (2 * 1024 * 1024 + 1))

        for index, (name, mutate) in enumerate(
            (
                ("too-many-sections", too_many_sections),
                ("oversized-title", oversized_title),
                ("oversized-bytes", oversized_bytes),
            ),
            start=1,
        ):
            with self.subTest(name=name):
                job_id = f"invalid-legacy-{index}"
                self.create_job(job_id=job_id, max_attempts=1)

                def invalid_runner(_mutate=mutate, **kwargs):
                    outputs = self.output_runner(
                        [],
                        "single_courseware",
                    )(**kwargs)
                    _mutate(outputs["package"])
                    return outputs

                worker = JobWorker(
                    self.repository,
                    self.settings,
                    worker_id=f"worker-{job_id}",
                    single_runner=invalid_runner,
                )
                self.assertTrue(worker.run_once())

                job = self.repository.get(job_id)
                self.assertEqual(job.state, JobState.FAILED)
                self.assertEqual(job.error_code, "invalid_job_output")
                self.assertEqual(self.repository.list_artifacts(job_id), [])
                self.assertEqual(self.repository.list_sections(job_id), [])

    def test_deep_package_json_is_permanent_without_retry(self):
        self.create_job(max_attempts=2)

        def deep_package(**kwargs):
            outputs = self.output_runner(
                [],
                "single_courseware",
            )(**kwargs)
            outputs["package"].write_text(
                '{"nested":' * 1100 + "null" + "}" * 1100,
                encoding="utf-8",
            )
            return outputs

        worker = JobWorker(
            self.repository,
            self.settings,
            worker_id="worker-deep-package",
            single_runner=deep_package,
        )
        self.assertTrue(worker.run_once())

        job = self.repository.get("job-1")
        self.assertEqual(job.state, JobState.FAILED)
        self.assertEqual(job.attempt_count, 1)
        self.assertEqual(job.error_code, "invalid_job_output")
        self.assertEqual(self.repository.list_artifacts("job-1"), [])
        self.assertEqual(self.repository.list_sections("job-1"), [])

    def test_missing_markdown_artifact_fails_without_completion(self):
        self.create_job(max_attempts=1)

        def missing_markdown(**kwargs):
            outputs = self.output_runner([], "single_courseware")(**kwargs)
            outputs.pop("markdown")
            return outputs

        worker = JobWorker(
            self.repository,
            self.settings,
            worker_id="worker-missing-markdown",
            single_runner=missing_markdown,
        )

        self.assertTrue(worker.run_once())

        job = self.repository.get("job-1")
        self.assertEqual(job.state, JobState.FAILED)
        self.assertEqual(job.error_code, "invalid_job_output")
        self.assertEqual(self.repository.list_artifacts("job-1"), [])
        self.assertEqual(self.repository.list_sections("job-1"), [])

    def test_wrong_section_markdown_filename_fails_without_completion(self):
        self.create_job(max_attempts=1)

        def wrong_filename(**kwargs):
            outputs = self.output_runner([], "single_courseware")(**kwargs)
            package = json.loads(
                outputs["package"].read_text(encoding="utf-8")
            )
            package["sections"][0]["artifact_urls"]["markdown"] = "missing.md"
            outputs["package"].write_text(
                json.dumps(package),
                encoding="utf-8",
            )
            return outputs

        worker = JobWorker(
            self.repository,
            self.settings,
            worker_id="worker-wrong-markdown",
            single_runner=wrong_filename,
        )

        self.assertTrue(worker.run_once())

        job = self.repository.get("job-1")
        self.assertEqual(job.state, JobState.FAILED)
        self.assertEqual(job.error_code, "invalid_job_output")
        self.assertEqual(self.repository.list_artifacts("job-1"), [])
        self.assertEqual(self.repository.list_sections("job-1"), [])

    def test_missing_public_artifact_fails_without_completion(self):
        self.create_job(max_attempts=1)

        def missing_trace(**kwargs):
            outputs = self.output_runner([], "single_courseware")(**kwargs)
            outputs.pop("trace")
            return outputs

        worker = JobWorker(
            self.repository,
            self.settings,
            worker_id="worker-missing-trace",
            single_runner=missing_trace,
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
                "job-1/attempts/2/output/result-evidence.json",
                "job-1/attempts/2/output/result-evidence_links.json",
                "job-1/attempts/2/output/result-quality.json",
                "job-1/attempts/2/output/result-retrieval_trace.json",
                "job-1/attempts/2/output/result-material-package.json",
                "job-1/attempts/2/output/result-courseware-manifest.json",
                "job-1/attempts/2/output/result-learning-map.json",
                "job-1/attempts/2/output/result-coverage-ledger.json",
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
