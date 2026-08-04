import unittest
import json
import os
import subprocess
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
STAGING_ENV_NAMES = (
    "JSTUDY_IMAGE_NAME",
    "JSTUDY_API_CONTAINER_NAME",
    "JSTUDY_WORKER_CONTAINER_NAME",
    "JSTUDY_POSTGRES_CONTAINER_NAME",
    "JSTUDY_API_BIND_ADDRESS",
    "JSTUDY_API_PORT",
)


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


def resolved_compose(overrides: dict[str, str] | None = None) -> dict:
    environment = os.environ.copy()
    for name in STAGING_ENV_NAMES:
        environment.pop(name, None)
    environment.update(overrides or {})
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
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stdout + completed.stderr)
    return json.loads(completed.stdout)


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
        self.assertEqual(
            compose_text.count(
                "image: ${JSTUDY_IMAGE_NAME:-jstudy-backend:pilot}"
            ),
            2,
        )
        self.assertIn("command: [\"python\", \"-m\", \"apps.worker.main\"]", compose_text)
        self.assertRegex(
            compose_text,
            r"(?ms)^  jstudy-worker:.*?depends_on:\s*\n"
            r"\s+postgres:\s*\n\s+condition: service_healthy",
        )
        worker_block = compose_service_block(compose_text, "jstudy-worker")
        self.assertNotIn("ports:", worker_block)

    def test_compose_defaults_preserve_existing_container_contract(self):
        services = resolved_compose()["services"]

        self.assertEqual(
            set(services),
            {"postgres", "jstudy-api", "jstudy-worker"},
        )
        self.assertEqual(services["jstudy-api"]["image"], "jstudy-backend:pilot")
        self.assertEqual(services["jstudy-worker"]["image"], "jstudy-backend:pilot")
        self.assertEqual(services["jstudy-api"]["container_name"], "jstudy-api")
        self.assertEqual(
            services["jstudy-worker"]["container_name"],
            "jstudy-worker",
        )
        self.assertEqual(
            services["postgres"]["container_name"],
            "jstudy-postgres",
        )
        self.assertEqual(
            services["jstudy-api"]["ports"],
            [
                {
                    "mode": "ingress",
                    "target": 8765,
                    "published": "8765",
                    "protocol": "tcp",
                    "host_ip": "0.0.0.0",
                }
            ],
        )

    def test_compose_staging_values_isolate_image_containers_and_port(self):
        services = resolved_compose(
            {
                "JSTUDY_IMAGE_NAME": "jstudy-backend:staging-test",
                "JSTUDY_API_CONTAINER_NAME": "jstudy-staging-api",
                "JSTUDY_WORKER_CONTAINER_NAME": "jstudy-staging-worker",
                "JSTUDY_POSTGRES_CONTAINER_NAME": "jstudy-staging-postgres",
                "JSTUDY_API_BIND_ADDRESS": "127.0.0.1",
                "JSTUDY_API_PORT": "8766",
            }
        )["services"]

        self.assertEqual(
            set(services),
            {"postgres", "jstudy-api", "jstudy-worker"},
        )
        self.assertEqual(
            services["jstudy-api"]["image"],
            "jstudy-backend:staging-test",
        )
        self.assertEqual(
            services["jstudy-worker"]["image"],
            "jstudy-backend:staging-test",
        )
        self.assertEqual(
            services["jstudy-api"]["container_name"],
            "jstudy-staging-api",
        )
        self.assertEqual(
            services["jstudy-worker"]["container_name"],
            "jstudy-staging-worker",
        )
        self.assertEqual(
            services["postgres"]["container_name"],
            "jstudy-staging-postgres",
        )
        self.assertEqual(
            services["jstudy-api"]["ports"],
            [
                {
                    "mode": "ingress",
                    "target": 8765,
                    "published": "8766",
                    "protocol": "tcp",
                    "host_ip": "127.0.0.1",
                }
            ],
        )

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
            "MINERU_POLL_INTERVAL_SECONDS:",
            "MINERU_DEADLINE_SECONDS:",
            "MINERU_MAX_RESULT_BYTES:",
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

    def test_compose_config_preserves_nonempty_and_empty_runtime_overrides(self):
        cases = (
            {
                "SILICONFLOW_API_KEY": "probe-provider-key",
                "SILICONFLOW_API_KEY_FILE": "probe-provider-key-file",
                "SILICONFLOW_CHAT_MODEL": "probe-chat-model",
                "SILICONFLOW_EMBED_MODEL": "probe-embed-model",
                "MINERU_API_BASE_URL": "https://api.mineru.net",
                "MINERU_API_TOKEN": "probe-mineru-token",
                "MINERU_MODEL_VERSION": "pipeline",
                "MINERU_LANGUAGE": "en",
                "MINERU_POLL_INTERVAL_SECONDS": "3",
                "MINERU_DEADLINE_SECONDS": "600",
                "MINERU_MAX_RESULT_BYTES": "1048576",
                "JSTUDY_MAX_PDF_BYTES": "123456",
                "JSTUDY_JOB_RETENTION_HOURS": "72",
            },
            {
                "SILICONFLOW_API_KEY": "",
                "SILICONFLOW_API_KEY_FILE": "",
                "SILICONFLOW_CHAT_MODEL": "",
                "SILICONFLOW_EMBED_MODEL": "",
                "MINERU_API_BASE_URL": "",
                "MINERU_API_TOKEN": "",
                "MINERU_MODEL_VERSION": "",
                "MINERU_LANGUAGE": "",
                "MINERU_POLL_INTERVAL_SECONDS": "",
                "MINERU_DEADLINE_SECONDS": "",
                "MINERU_MAX_RESULT_BYTES": "",
                "JSTUDY_MAX_PDF_BYTES": "",
                "JSTUDY_JOB_RETENTION_HOURS": "",
            },
        )
        for expected in cases:
            with self.subTest(empty=not bool(expected["SILICONFLOW_API_KEY"])):
                completed = subprocess.run(
                    [
                        "docker",
                        "compose",
                        "-f",
                        str(
                            ROOT
                            / "deploy"
                            / "docker-compose"
                            / "api.compose.yml"
                        ),
                        "config",
                        "--format",
                        "json",
                    ],
                    cwd=ROOT,
                    env={**os.environ, **expected},
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
                    for name, value in expected.items():
                        self.assertEqual(runtime[name], value)

    def test_compose_keeps_auth_environment_on_api(self):
        compose_file = ROOT / "deploy" / "docker-compose" / "api.compose.yml"
        compose_text = compose_file.read_text(encoding="utf-8")

        self.assertIn("JSTUDY_DATABASE_URL", compose_text)
        self.assertIn("JSTUDY_SESSION_SECRET", compose_text)
        self.assertIn(
            "JSTUDY_INVITE_REQUIRED: ${JSTUDY_INVITE_REQUIRED:-true}",
            compose_text,
        )

    def test_worker_generation_concurrency_environment_contract(self):
        compose_text = (
            ROOT / "deploy" / "docker-compose" / "api.compose.yml"
        ).read_text(encoding="utf-8")
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
        worker_block = compose_service_block(compose_text, "jstudy-worker")

        self.assertIn(
            "JSTUDY_GENERATION_MAX_CONCURRENCY: "
            "${JSTUDY_GENERATION_MAX_CONCURRENCY:-4}",
            worker_block,
        )
        self.assertIn(
            "JSTUDY_GENERATION_MAX_CONCURRENCY=4",
            env_example,
        )

    def test_generation_concurrency_operations_are_documented(self):
        documents = [
            (ROOT / "README.md").read_text(encoding="utf-8"),
            (ROOT / "docs" / "architecture" / "overview.md").read_text(
                encoding="utf-8"
            ),
            (ROOT / "docs" / "deployment" / "server-runbook.md").read_text(
                encoding="utf-8"
            ),
            (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8"),
        ]
        for content in documents:
            self.assertIn("JSTUDY_GENERATION_MAX_CONCURRENCY", content)
            self.assertIn("1..4", content)
            self.assertIn("默认值 `4`", content)
            self.assertIn("串行回滚", content)
            self.assertIn("Worker 副本", content)
            self.assertIn("Supervisor", content)
            self.assertIn("25 秒", content)
            self.assertIn("35 秒", content)

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

        server_runbook = (
            ROOT / "docs" / "deployment" / "server-runbook.md"
        ).read_text(encoding="utf-8")
        for text in (
            "PostgreSQL + API + Worker",
            "jstudy-worker",
            "queued",
            "completed",
            "failed",
        ):
            self.assertIn(text, server_runbook)
        self.assertNotIn(
            "Redis, a worker, and object storage are not required",
            server_runbook,
        )

    def test_staging_environment_and_runbooks_cover_safe_operations(self):
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
        compose_readme = (
            ROOT / "deploy" / "docker-compose" / "README.md"
        ).read_text(encoding="utf-8")
        server_runbook = (
            ROOT / "docs" / "deployment" / "server-runbook.md"
        ).read_text(encoding="utf-8")

        for entry in (
            "JSTUDY_IMAGE_NAME=jstudy-backend:pilot",
            "JSTUDY_API_CONTAINER_NAME=jstudy-api",
            "JSTUDY_WORKER_CONTAINER_NAME=jstudy-worker",
            "JSTUDY_POSTGRES_CONTAINER_NAME=jstudy-postgres",
            "JSTUDY_API_BIND_ADDRESS=0.0.0.0",
            "JSTUDY_API_PORT=8765",
        ):
            self.assertIn(entry, env_example)

        staging_commands = (
            "docker compose -p jstudy-staging --env-file .env "
            "-f deploy/docker-compose/api.compose.yml up -d --build",
            "docker compose -p jstudy-staging --env-file .env "
            "-f deploy/docker-compose/api.compose.yml ps",
            "docker compose -p jstudy-staging --env-file .env "
            "-f deploy/docker-compose/api.compose.yml logs --tail 200 "
            "jstudy-api jstudy-worker",
        )
        for command in staging_commands:
            self.assertIn(command, compose_readme)
            self.assertIn(command, server_runbook)

        for text in (
            "/opt/jstudy-staging/app",
            "127.0.0.1:8766",
            "/api/health",
            "/api/readiness",
            "/api/readiness?probe_provider=true",
            "Secure Cookie",
            "Manifest",
            "Learning Map",
            "Coverage",
            "Package v2",
            "queued",
            "completed",
            "failed",
            "backup",
            "rollback",
            "down -v",
            "旧数据库目录",
            "旧 `jstudy`",
        ):
            self.assertIn(text, server_runbook)

        for text in (".env", "Token", "上传文件", "生成产物"):
            self.assertIn(text, compose_readme)
            self.assertIn(text, server_runbook)

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
