import unittest
import json
import os
import subprocess
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def compose_service_names(compose_text: str) -> list[str]:
    services_match = re.search(
        r"(?ms)^services:\s*\n(?P<body>.*?)(?=^[^\s#][^:]*:\s*(?:\n|$)|\Z)",
        compose_text,
    )
    if services_match is None:
        return []
    return re.findall(r"(?m)^  ([a-z0-9][a-z0-9-]*):\s*$", services_match.group("body"))


def compose_service_block(compose_text: str, service_name: str) -> str:
    service_match = re.search(
        rf"(?ms)^  {re.escape(service_name)}:\s*\n"
        rf"(?P<body>.*?)(?=^  [a-z0-9][a-z0-9-]*:\s*$|\Z)",
        compose_text,
    )
    if service_match is None:
        return ""
    return service_match.group("body")


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

    def test_dockerfile_does_not_override_admin_managed_runtime_settings(self):
        dockerfile_text = (ROOT / "apps" / "api" / "Dockerfile").read_text(
            encoding="utf-8"
        )

        self.assertIn("JSTUDY_JOBS_DIR=/app/data/jobs", dockerfile_text)
        for name in (
            "JSTUDY_SOUL_PATH",
            "JSTUDY_MNEMONICS_PATH",
            "JSTUDY_MAX_PDF_BYTES",
            "JSTUDY_JOB_RETENTION_HOURS",
            "SILICONFLOW_API_KEY",
            "SILICONFLOW_CHAT_MODEL",
            "SILICONFLOW_EMBED_MODEL",
        ):
            self.assertNotIn(name, dockerfile_text)

    def test_compose_has_exact_api_worker_postgres_topology(self):
        compose_file = ROOT / "deploy" / "docker-compose" / "api.compose.yml"
        compose_text = compose_file.read_text(encoding="utf-8")

        self.assertEqual(
            set(compose_service_names(compose_text)),
            {"postgres", "jstudy-api", "jstudy-worker"},
        )
        self.assertEqual(compose_text.count("dockerfile: apps/api/Dockerfile"), 2)
        self.assertEqual(compose_text.count("image: jstudy-backend:pilot"), 2)
        self.assertIn("command: [\"python\", \"-m\", \"apps.worker.main\"]", compose_text)
        self.assertRegex(
            compose_text,
            r"(?ms)^  jstudy-worker:.*?depends_on:\s*\n"
            r"\s+postgres:\s*\n\s+condition: service_healthy",
        )
        worker_block = compose_service_block(compose_text, "jstudy-worker")
        self.assertNotIn("ports:", worker_block)

    def test_api_and_worker_share_database_jobs_and_runtime_environment(self):
        compose_file = ROOT / "deploy" / "docker-compose" / "api.compose.yml"
        compose_text = compose_file.read_text(encoding="utf-8")
        api_block = compose_service_block(compose_text, "jstudy-api")
        worker_block = compose_service_block(compose_text, "jstudy-worker")

        shared_entries = (
            "JSTUDY_DATABASE_URL:",
            "JSTUDY_JOBS_DIR: /app/data/jobs",
            "../../data/jobs:/app/data/jobs",
            "JSTUDY_SETTINGS_DIR: /app/data/settings",
        )
        for entry in shared_entries:
            self.assertIn(entry, api_block)
            self.assertIn(entry, worker_block)

        explicit_runtime_overrides = (
            "SILICONFLOW_API_KEY:",
            "SILICONFLOW_API_KEY_FILE:",
            "SILICONFLOW_CHAT_MODEL:",
            "SILICONFLOW_EMBED_MODEL:",
            "MINERU_API_BASE_URL:",
            "MINERU_API_TOKEN:",
            "MINERU_MODEL_VERSION:",
            "MINERU_LANGUAGE:",
            "JSTUDY_SOUL_PATH:",
            "JSTUDY_MNEMONICS_PATH:",
            "JSTUDY_MAX_PDF_BYTES:",
            "JSTUDY_JOB_RETENTION_HOURS:",
        )
        for entry in explicit_runtime_overrides:
            self.assertIn(entry, api_block)
            self.assertIn(entry, worker_block)

        self.assertIn(
            "SILICONFLOW_CHAT_MODEL: ${SILICONFLOW_CHAT_MODEL:-}",
            compose_text,
        )
        self.assertIn(
            "SILICONFLOW_EMBED_MODEL: ${SILICONFLOW_EMBED_MODEL:-}",
            compose_text,
        )

        self.assertIn("ports:", api_block)
        self.assertIn("/api/health", api_block)
        self.assertIn("condition: service_healthy", api_block)

    def test_compose_config_passes_explicit_provider_and_retention_overrides(self):
        env = {
            **os.environ,
            "SILICONFLOW_API_KEY": "probe-provider-key",
            "SILICONFLOW_CHAT_MODEL": "probe-chat-model",
            "SILICONFLOW_EMBED_MODEL": "probe-embed-model",
            "JSTUDY_MAX_PDF_BYTES": "123456",
            "JSTUDY_JOB_RETENTION_HOURS": "72",
        }
        completed = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(ROOT / "deploy" / "docker-compose" / "api.compose.yml"),
                "config",
                "--format",
                "json",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            completed.stdout + completed.stderr,
        )
        services = json.loads(completed.stdout)["services"]
        for service_name in ("jstudy-api", "jstudy-worker"):
            runtime = services[service_name]["environment"]
            self.assertEqual(
                runtime["SILICONFLOW_API_KEY"],
                "probe-provider-key",
            )
            self.assertEqual(
                runtime["SILICONFLOW_CHAT_MODEL"],
                "probe-chat-model",
            )
            self.assertEqual(
                runtime["SILICONFLOW_EMBED_MODEL"],
                "probe-embed-model",
            )
            self.assertEqual(runtime["JSTUDY_MAX_PDF_BYTES"], "123456")
            self.assertEqual(runtime["JSTUDY_JOB_RETENTION_HOURS"], "72")

    def test_compose_keeps_auth_environment_on_api(self):
        compose_file = ROOT / "deploy" / "docker-compose" / "api.compose.yml"
        compose_text = compose_file.read_text(encoding="utf-8")

        self.assertIn("JSTUDY_DATABASE_URL", compose_text)
        self.assertIn("JSTUDY_SESSION_SECRET", compose_text)

    def test_runbook_documents_durable_three_service_operations(self):
        runbook = (ROOT / "deploy" / "docker-compose" / "README.md").read_text(
            encoding="utf-8"
        )

        required_text = (
            "docker compose -f deploy/docker-compose/api.compose.yml up -d --build",
            "docker compose -f deploy/docker-compose/api.compose.yml logs -f",
            "docker compose -f deploy/docker-compose/api.compose.yml down",
            "postgres",
            "jstudy-api",
            "jstudy-worker",
            "worker 不暴露端口",
            "/api/health",
            "/api/readiness",
            "retention",
            "jobs.json",
            "create_all()",
            "versioned migrations",
        )
        for text in required_text:
            self.assertIn(text, runbook)

    def test_architecture_and_roadmap_describe_durable_worker_boundary(self):
        architecture = (ROOT / "docs" / "architecture" / "overview.md").read_text(
            encoding="utf-8"
        )
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

        for text in ("PostgreSQL", "jstudy-worker", "jobs.json", "versioned migrations"):
            self.assertIn(text, architecture)
            self.assertIn(text, roadmap)


if __name__ == "__main__":
    unittest.main()
