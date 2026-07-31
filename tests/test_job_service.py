from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
import threading
import unittest
from unittest import mock
from dataclasses import replace
from pathlib import Path

import fitz

from packages.core.jstudy_core.auth_db import (
    create_application_tables,
    create_auth_engine,
)
from packages.core.jstudy_core.job_system.repository import JobRepository
from packages.core.jstudy_core.job_system.service import (
    AdmissionError,
    JobAdmissionRequest,
    JobService,
)
from packages.core.jstudy_core.settings import RuntimeSettings


class AsyncUpload:
    def __init__(
        self,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ):
        self.filename = filename
        self.content_type = content_type
        self._content = content
        self._position = 0
        self.read_sizes: list[int] = []

    async def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        if size < 0:
            size = len(self._content) - self._position
        start = self._position
        self._position = min(len(self._content), self._position + size)
        return self._content[start : self._position]


def make_pdf(text: str = "source") -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    content = document.tobytes()
    document.close()
    return content


class BarrierRepository(JobRepository):
    def __init__(self, engine, barrier: threading.Barrier):
        super().__init__(engine)
        self.barrier = barrier

    def admit_job(self, command, **limits):
        self.barrier.wait(timeout=5)
        return super().admit_job(command, **limits)


class JobServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.jobs_root = self.root / "jobs"
        self.jobs_root.mkdir()
        self.db_path = self.root / "jobs.db"
        self.engine = create_auth_engine(f"sqlite:///{self.db_path.as_posix()}")
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
        )

    def request(
        self,
        *,
        owner: str = "owner-1",
        service_mode: str = "course_outline",
        outline: AsyncUpload | None = None,
        pdfs: tuple[AsyncUpload, ...] | None = None,
        idempotency_key: str | None = None,
    ) -> JobAdmissionRequest:
        return JobAdmissionRequest(
            owner_user_id=owner,
            service_mode=service_mode,
            scenario_id="medicine-default",
            parser_profile_id="fast",
            generation_mode="study",
            outline=outline
            if outline is not None
            else AsyncUpload("outline.md", b"# Course outline"),
            pdfs=pdfs
            if pdfs is not None
            else (AsyncUpload("lecture.pdf", make_pdf()),),
            idempotency_key=idempotency_key,
            content_metadata={"content_pack_id": "medicine-default"},
        )

    def submit(
        self,
        request: JobAdmissionRequest,
        *,
        settings: RuntimeSettings | None = None,
        repository: JobRepository | None = None,
    ):
        service = JobService(
            repository or self.repository,
            settings or self.settings,
        )
        return asyncio.run(service.submit(request))

    def assert_error(
        self,
        code: str,
        request: JobAdmissionRequest,
        *,
        settings: RuntimeSettings | None = None,
    ) -> AdmissionError:
        with self.assertRaises(AdmissionError) as caught:
            self.submit(request, settings=settings)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def assert_jobs_root_empty(self):
        self.assertEqual(list(self.jobs_root.iterdir()), [])

    def test_rejects_unsupported_service_mode(self):
        self.assert_error(
            "unsupported_service_mode",
            self.request(service_mode="batch_courseware"),
        )
        self.assert_jobs_root_empty()

    def test_course_outline_requires_supported_nonempty_outline(self):
        cases = (
            self.request(outline=None, pdfs=(AsyncUpload("source.pdf", make_pdf()),)),
            self.request(outline=AsyncUpload("outline.docx", b"outline")),
            self.request(outline=AsyncUpload("outline.txt", b"")),
        )
        cases = (
            replace(cases[0], outline=None),
            cases[1],
            cases[2],
        )
        for request in cases:
            with self.subTest(filename=getattr(request.outline, "filename", None)):
                self.assert_error("invalid_outline", request)
                self.assert_jobs_root_empty()

    def test_single_courseware_requires_one_pdf_and_accepts_optional_outline(self):
        accepted = replace(
            self.request(service_mode="single_courseware"),
            outline=None,
        )
        result = self.submit(accepted)
        self.assertTrue(result.created)

        with_outline = self.submit(
            self.request(
                service_mode="single_courseware",
                outline=AsyncUpload("notes.md", b"# Notes"),
            )
        )
        self.assertTrue(with_outline.created)
        self.assertIsNotNone(with_outline.job.outline_relative_path)

        rejected = replace(
            self.request(service_mode="single_courseware"),
            outline=None,
            pdfs=(),
        )
        self.assert_error("invalid_pdf", rejected)

    def test_outline_size_is_limited_while_streaming_and_cleans_up(self):
        settings = replace(self.settings, max_outline_bytes=8)
        upload = AsyncUpload("outline.md", b"012345678")
        self.assert_error(
            "outline_too_large",
            self.request(outline=upload),
            settings=settings,
        )
        self.assertTrue(all(size > 0 for size in upload.read_sizes))
        self.assert_jobs_root_empty()

    def test_large_outline_is_read_in_bounded_chunks(self):
        upload = AsyncUpload("outline.txt", b"x" * (150 * 1024))

        result = self.submit(self.request(outline=upload))

        self.assertTrue(result.created)
        self.assertGreaterEqual(len(upload.read_sizes), 3)
        self.assertEqual(set(upload.read_sizes), {64 * 1024})

    def test_text_outline_requires_valid_utf8_and_cleans_up(self):
        for suffix in (".md", ".txt"):
            with self.subTest(suffix=suffix):
                self.assert_error(
                    "invalid_outline",
                    self.request(
                        outline=AsyncUpload(
                            f"outline{suffix}",
                            b"\xff\xfe\xfd",
                        )
                    ),
                )
                self.assertEqual(self.repository.count_queued(), 0)
                self.assert_jobs_root_empty()

    def test_pdf_outline_uses_shared_pdf_validation(self):
        valid = self.submit(
            self.request(
                outline=AsyncUpload("outline.pdf", make_pdf("outline")),
            )
        )
        self.assertEqual(
            valid.job.outline_relative_path,
            f"{valid.job.id}/inputs/outline.pdf",
        )

        self.assert_error(
            "invalid_outline",
            self.request(
                outline=AsyncUpload("outline.pdf", b"%PDF-broken"),
            ),
        )
        self.assertEqual(len(list(self.jobs_root.iterdir())), 1)

    def test_pdf_count_is_limited(self):
        settings = replace(self.settings, max_pdfs=1)
        self.assert_error(
            "too_many_pdfs",
            self.request(
                pdfs=(
                    AsyncUpload("one.pdf", make_pdf("one")),
                    AsyncUpload("two.pdf", make_pdf("two")),
                )
            ),
            settings=settings,
        )
        self.assert_jobs_root_empty()

    def test_each_submission_uses_latest_settings_without_switching_storage(self):
        current = [replace(self.settings, max_pdfs=2)]
        service = JobService(
            self.repository,
            current[0],
            settings_provider=lambda: current[0],
        )
        accepted = asyncio.run(
            service.submit(
                self.request(
                    owner="owner-1",
                    pdfs=(
                        AsyncUpload("one.pdf", make_pdf("one")),
                        AsyncUpload("two.pdf", make_pdf("two")),
                    ),
                )
            )
        )
        self.assertTrue(accepted.created)

        current[0] = replace(current[0], max_pdfs=1)
        with self.assertRaises(AdmissionError) as caught:
            asyncio.run(
                service.submit(
                    self.request(
                        owner="owner-2",
                        pdfs=(
                            AsyncUpload("one.pdf", make_pdf("one")),
                            AsyncUpload("two.pdf", make_pdf("two")),
                        ),
                    )
                )
            )
        self.assertEqual(caught.exception.code, "too_many_pdfs")
        self.assertEqual(self.repository.count_queued(), 1)

        current[0] = replace(
            current[0],
            jobs_root=self.root / "other-jobs",
        )
        with self.assertRaises(RuntimeError):
            asyncio.run(service.submit(self.request(owner="owner-3")))
        self.assertFalse((self.root / "other-jobs").exists())

    def test_each_pdf_size_is_limited_while_streaming_and_cleans_up(self):
        pdf = make_pdf()
        settings = replace(self.settings, max_pdf_bytes=len(pdf) - 1)
        upload = AsyncUpload("source.pdf", pdf)
        self.assert_error(
            "pdf_too_large",
            self.request(pdfs=(upload,)),
            settings=settings,
        )
        self.assertTrue(all(size > 0 for size in upload.read_sizes))
        self.assert_jobs_root_empty()

    def test_total_upload_size_is_limited_and_cleans_up(self):
        pdf = make_pdf()
        outline = b"outline"
        settings = replace(
            self.settings,
            max_pdf_bytes=len(pdf) + 10,
            max_total_upload_bytes=len(pdf) + len(outline) - 1,
        )
        self.assert_error(
            "total_upload_too_large",
            self.request(outline=AsyncUpload("outline.txt", outline)),
            settings=settings,
        )
        self.assert_jobs_root_empty()

    def test_pdf_magic_and_shared_validation_are_required(self):
        for content in (b"not a pdf", b"%PDF-broken"):
            with self.subTest(content=content):
                self.assert_error(
                    "invalid_pdf",
                    self.request(pdfs=(AsyncUpload("source.pdf", content),)),
                )
                self.assert_jobs_root_empty()

    def test_pdf_rejects_explicit_non_pdf_mime_even_with_valid_magic(self):
        self.assert_error(
            "invalid_pdf",
            self.request(
                pdfs=(
                    AsyncUpload(
                        "source.pdf",
                        make_pdf(),
                        "text/plain",
                    ),
                ),
            ),
        )
        self.assert_jobs_root_empty()

    def test_queue_capacity_is_enforced_after_upload_cleanup(self):
        self.submit(self.request())
        existing_dirs = {path.name for path in self.jobs_root.iterdir()}
        settings = replace(self.settings, queue_capacity=1)

        self.assert_error("queue_full", self.request(), settings=settings)

        self.assertEqual(
            {path.name for path in self.jobs_root.iterdir()},
            existing_dirs,
        )

    def test_per_user_active_job_limit_does_not_count_other_owners(self):
        self.submit(self.request(owner="owner-1"))
        settings = replace(self.settings, user_active_job_limit=1)
        self.assert_error(
            "user_active_job_limit",
            self.request(owner="owner-1"),
            settings=settings,
        )

        other = self.submit(
            self.request(owner="owner-2"),
            settings=settings,
        )
        self.assertTrue(other.created)

    def test_concurrent_submissions_cannot_overbook_queue_capacity(self):
        barrier = threading.Barrier(2)
        repository = BarrierRepository(self.engine, barrier)
        settings = replace(
            self.settings,
            queue_capacity=1,
            user_active_job_limit=2,
        )
        results = []
        errors = []

        def submit_one():
            try:
                results.append(
                    self.submit(
                        self.request(),
                        settings=settings,
                        repository=repository,
                    )
                )
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=submit_one) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertEqual(len(results), 1)
        self.assertEqual(
            [error.code for error in errors if isinstance(error, AdmissionError)],
            ["queue_full"],
        )
        self.assertEqual(self.repository.count_queued(), 1)
        self.assertEqual(len(list(self.jobs_root.iterdir())), 1)

    def test_concurrent_submissions_cannot_overbook_owner_active_limit(self):
        barrier = threading.Barrier(2)
        repository = BarrierRepository(self.engine, barrier)
        settings = replace(
            self.settings,
            queue_capacity=2,
            user_active_job_limit=1,
        )
        results = []
        errors = []

        def submit_one():
            try:
                results.append(
                    self.submit(
                        self.request(),
                        settings=settings,
                        repository=repository,
                    )
                )
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=submit_one) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertEqual(len(results), 1)
        self.assertEqual(
            [error.code for error in errors if isinstance(error, AdmissionError)],
            ["user_active_job_limit"],
        )
        self.assertEqual(
            self.repository.count_active_for_owner("owner-1"),
            1,
        )
        self.assertEqual(len(list(self.jobs_root.iterdir())), 1)

    def test_cleanup_failure_does_not_mask_typed_admission_error(self):
        private_path = self.jobs_root / "private-job-path"
        with mock.patch(
            "packages.core.jstudy_core.job_system.service.shutil.rmtree",
            side_effect=PermissionError(str(private_path)),
        ):
            error = self.assert_error(
                "invalid_pdf",
                self.request(
                    pdfs=(AsyncUpload("broken.pdf", b"%PDF-broken"),),
                ),
            )

        self.assertNotIn(str(private_path), str(error))

    def test_partial_directory_creation_is_cleaned_up(self):
        original_mkdir = Path.mkdir

        def fail_inputs(path, *args, **kwargs):
            if path.name == "inputs":
                raise PermissionError("inputs unavailable")
            return original_mkdir(path, *args, **kwargs)

        with mock.patch.object(Path, "mkdir", new=fail_inputs):
            with self.assertRaises(PermissionError):
                self.submit(self.request())

        self.assert_jobs_root_empty()

    def test_persists_stable_sources_hashes_and_relative_paths_across_restart(self):
        first_pdf = make_pdf("first")
        second_pdf = make_pdf("second")
        outline = b"# Stable outline"
        result = self.submit(
            self.request(
                outline=AsyncUpload("course.md", outline, "text/markdown"),
                pdfs=(
                    AsyncUpload("first handout.pdf", first_pdf),
                    AsyncUpload("second.pdf", second_pdf),
                ),
            )
        )

        restarted = JobRepository(
            create_auth_engine(f"sqlite:///{self.db_path.as_posix()}")
        )
        self.addCleanup(restarted.engine.dispose)
        snapshot = restarted.get(result.job.id)
        sources = restarted.list_sources(result.job.id)

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.outline_relative_path, f"{result.job.id}/inputs/outline.md")
        self.assertEqual(snapshot.outline_original_filename, "course.md")
        self.assertEqual(
            snapshot.outline_sha256,
            hashlib.sha256(outline).hexdigest(),
        )
        self.assertEqual(snapshot.outline_byte_size, len(outline))
        self.assertEqual(snapshot.outline_mime_type, "text/markdown")
        self.assertEqual([source.source_id for source in sources], ["S001", "S002"])
        self.assertEqual(
            [source.original_filename for source in sources],
            ["first handout.pdf", "second.pdf"],
        )
        self.assertEqual(
            [source.display_title for source in sources],
            ["first handout", "second"],
        )
        self.assertEqual([source.display_order for source in sources], [1, 2])
        self.assertEqual(
            [source.title_origin for source in sources],
            ["upload", "upload"],
        )
        self.assertEqual(
            [source.order_origin for source in sources],
            ["upload", "upload"],
        )
        self.assertEqual(
            [source.primary_outline_section_id for source in sources],
            [None, None],
        )
        self.assertEqual(
            [source.sha256 for source in sources],
            [
                hashlib.sha256(first_pdf).hexdigest(),
                hashlib.sha256(second_pdf).hexdigest(),
            ],
        )
        self.assertEqual(
            [source.relative_path for source in sources],
            [
                f"{result.job.id}/inputs/S001.pdf",
                f"{result.job.id}/inputs/S002.pdf",
            ],
        )
        self.assertTrue(
            (self.jobs_root / result.job.id / "inputs" / "outline.md").is_file()
        )
        expected_fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "service_mode": "course_outline",
                    "scenario_id": "medicine-default",
                    "parser_profile_id": "fast",
                    "generation_mode": "study",
                    "outline_sha256": hashlib.sha256(outline).hexdigest(),
                    "sources": [
                        {
                            "source_id": "S001",
                            "sha256": hashlib.sha256(first_pdf).hexdigest(),
                        },
                        {
                            "source_id": "S002",
                            "sha256": hashlib.sha256(second_pdf).hexdigest(),
                        },
                    ],
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(snapshot.request_fingerprint, expected_fingerprint)

    def test_idempotency_is_owner_scoped_and_fingerprint_sensitive(self):
        key = "request-123"
        original_pdf = make_pdf("original")
        first = self.submit(
            self.request(
                idempotency_key=key,
                pdfs=(AsyncUpload("lecture.pdf", original_pdf),),
            )
        )
        repeated = self.submit(
            self.request(
                idempotency_key=key,
                pdfs=(AsyncUpload("lecture.pdf", original_pdf),),
            )
        )
        other_owner = self.submit(
            self.request(
                owner="owner-2",
                idempotency_key=key,
                pdfs=(AsyncUpload("lecture.pdf", original_pdf),),
            )
        )

        self.assertTrue(first.created)
        self.assertFalse(repeated.created)
        self.assertEqual(repeated.job.id, first.job.id)
        self.assertNotEqual(other_owner.job.id, first.job.id)

        self.assert_error(
            "idempotency_conflict",
            self.request(
                idempotency_key=key,
                pdfs=(AsyncUpload("changed.pdf", make_pdf("changed")),),
            ),
        )
        self.assertEqual(len(list(self.jobs_root.iterdir())), 2)

    def test_concurrent_idempotent_insert_returns_one_authoritative_job(self):
        barrier = threading.Barrier(2)
        repository = BarrierRepository(self.engine, barrier)
        original_pdf = make_pdf("concurrent")
        results = []
        errors = []

        def submit_one():
            try:
                results.append(
                    self.submit(
                        self.request(
                            idempotency_key="concurrent-key",
                            pdfs=(
                                AsyncUpload("lecture.pdf", original_pdf),
                            ),
                        ),
                        repository=repository,
                    )
                )
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=submit_one) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(errors)
        self.assertEqual(len(results), 2)
        self.assertEqual({result.job.id for result in results}, {results[0].job.id})
        self.assertEqual(sum(result.created for result in results), 1)
        self.assertEqual(len(list(self.jobs_root.iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
