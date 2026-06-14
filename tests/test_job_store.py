import tempfile
import unittest
from pathlib import Path

from packages.core.jstudy_core.jobs import JobStore


class JobStoreTest(unittest.TestCase):
    def test_job_store_tracks_generation_lifecycle(self):
        store = JobStore()

        record = store.create(
            job_id="job-1",
            pdf_path=Path("input/lecture.pdf"),
            output_dir=Path("output"),
            outline_path=Path("input/outline.md"),
        )

        self.assertEqual(record.status, "queued")
        self.assertEqual(record.outputs, {})
        self.assertEqual(record.quality, {})
        self.assertEqual(record.error, "")

        store.mark_running("job-1")
        self.assertEqual(store.require("job-1").status, "running")

        store.mark_completed(
            "job-1",
            outputs={"markdown": Path("output/result.md")},
            quality={"status": "pass"},
        )

        completed = store.require("job-1")
        self.assertEqual(completed.status, "completed")
        self.assertEqual(completed.outputs["markdown"], Path("output/result.md"))
        self.assertEqual(completed.quality["status"], "pass")
        self.assertEqual(completed.error, "")

    def test_job_store_marks_failed_jobs_with_error(self):
        store = JobStore()
        store.create(
            job_id="job-2",
            pdf_path=Path("input/lecture.pdf"),
            output_dir=Path("output"),
        )

        store.mark_failed("job-2", "provider timeout")

        failed = store.require("job-2")
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.error, "provider timeout")

    def test_job_store_persists_completed_jobs_when_store_path_is_provided(self):
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "jobs.json"
            store = JobStore(store_path=store_path)
            store.create(
                job_id="job-3",
                pdf_path=Path("input/lecture.pdf"),
                output_dir=Path("output"),
                outline_path=Path("input/outline.md"),
            )
            store.mark_running("job-3")
            store.mark_completed(
                "job-3",
                outputs={"markdown": Path("output/result.md")},
                quality={"status": "pass"},
            )

            restored = JobStore(store_path=store_path).require("job-3")

        self.assertEqual(restored.status, "completed")
        self.assertEqual(restored.pdf_path, Path("input/lecture.pdf"))
        self.assertEqual(restored.output_dir, Path("output"))
        self.assertEqual(restored.outline_path, Path("input/outline.md"))
        self.assertEqual(restored.outputs["markdown"], Path("output/result.md"))
        self.assertEqual(restored.quality["status"], "pass")
        self.assertEqual(restored.error, "")

    def test_job_store_marks_interrupted_jobs_failed_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "jobs.json"
            store = JobStore(store_path=store_path)
            store.create(
                job_id="job-4",
                pdf_path=Path("input/lecture.pdf"),
                output_dir=Path("output"),
            )
            store.mark_running("job-4")

            restored = JobStore(store_path=store_path).require("job-4")

        self.assertEqual(restored.status, "failed")
        self.assertIn("interrupted by server restart", restored.error)


if __name__ == "__main__":
    unittest.main()
