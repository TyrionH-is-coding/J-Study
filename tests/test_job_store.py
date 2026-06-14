import tempfile
import unittest
from datetime import datetime, timedelta, timezone
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

    def test_job_store_prunes_finished_jobs_older_than_cutoff_and_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = JobStore(store_path=root / "jobs.json")
            now = datetime.now(timezone.utc)

            old_dir = root / "old-job"
            old_dir.joinpath("input").mkdir(parents=True)
            old_dir.joinpath("output").mkdir()
            old_dir.joinpath("output", "result.md").write_text("old", encoding="utf-8")
            store.create(
                job_id="old-job",
                pdf_path=old_dir / "input" / "lecture.pdf",
                output_dir=old_dir / "output",
            )
            store.mark_completed("old-job", outputs={}, quality={"status": "pass"})
            store.require("old-job").updated_at = (now - timedelta(hours=2)).isoformat()

            fresh_dir = root / "fresh-job"
            fresh_dir.joinpath("output").mkdir(parents=True)
            store.create(
                job_id="fresh-job",
                pdf_path=fresh_dir / "input" / "lecture.pdf",
                output_dir=fresh_dir / "output",
            )
            store.mark_completed("fresh-job", outputs={}, quality={"status": "pass"})

            running_dir = root / "running-job"
            running_dir.joinpath("output").mkdir(parents=True)
            store.create(
                job_id="running-job",
                pdf_path=running_dir / "input" / "lecture.pdf",
                output_dir=running_dir / "output",
            )
            store.mark_running("running-job")
            store.require("running-job").updated_at = (now - timedelta(hours=2)).isoformat()

            pruned = store.cleanup_finished_older_than(now - timedelta(hours=1), delete_files=True)
            restored = JobStore(store_path=root / "jobs.json")

            self.assertEqual(pruned, ["old-job"])
            self.assertFalse(old_dir.exists())
            self.assertIsNone(restored.get("old-job"))
            self.assertIsNotNone(restored.get("fresh-job"))
            self.assertIsNotNone(restored.get("running-job"))


if __name__ == "__main__":
    unittest.main()
