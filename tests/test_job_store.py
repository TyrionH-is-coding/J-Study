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


if __name__ == "__main__":
    unittest.main()
