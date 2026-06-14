import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DeploymentFilesTest(unittest.TestCase):
    def test_backend_container_files_reference_health_and_data_volume(self):
        dockerfile = ROOT / "apps" / "api" / "Dockerfile"
        compose_file = ROOT / "deploy" / "docker-compose" / "api.compose.yml"
        runbook = ROOT / "deploy" / "docker-compose" / "README.md"
        gitignore = ROOT / ".gitignore"

        self.assertTrue(dockerfile.exists())
        self.assertTrue(compose_file.exists())
        self.assertTrue(runbook.exists())
        self.assertTrue(gitignore.exists())

        dockerfile_text = dockerfile.read_text(encoding="utf-8")
        compose_text = compose_file.read_text(encoding="utf-8")
        runbook_text = runbook.read_text(encoding="utf-8")
        gitignore_text = gitignore.read_text(encoding="utf-8")

        self.assertIn("apps.api.jstudy_api.app:app", dockerfile_text)
        self.assertIn("/api/health", dockerfile_text)
        self.assertIn("JSTUDY_JOBS_DIR", compose_text)
        self.assertIn("/app/data/jobs", compose_text)
        self.assertIn("/api/health", compose_text)
        self.assertIn("docker compose", runbook_text)
        self.assertIn("data/", gitignore_text)


if __name__ == "__main__":
    unittest.main()
