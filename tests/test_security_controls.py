import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.api.jstudy_api.app import create_app  # noqa: E402
from packages.core.jstudy_core.auth_db import create_application_tables, create_auth_engine  # noqa: E402
from packages.core.jstudy_core.documents import (  # noqa: E402
    ParsedBlock,
    ParsedDocument,
    ParsedPage,
)
from packages.core.jstudy_core.job_system import (  # noqa: E402
    JobRepository,
    JobService,
    JobState,
)
from packages.core.jstudy_core.job_system.worker import JobWorker  # noqa: E402
from packages.core.jstudy_core.settings import RuntimeSettings  # noqa: E402


class FakeDocumentService:
    def parse(self, sources, *, artifact_root):
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
                                block_id=f"{source.source_id}-P001-B001",
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


class BackendSecurityControlsTest(unittest.TestCase):
    def make_pdf_bytes(self) -> bytes:
        doc = fitz.open()
        page = doc.new_page(width=240, height=320)
        page.insert_text((40, 80), "Security test")
        return doc.tobytes()

    def ready_settings(self, root: Path, cookie_secure: bool = False) -> RuntimeSettings:
        soul_path = root / "config" / "soul.md"
        mnemonics_path = root / "config" / "mnemonics.md"
        api_key_path = root / "secrets" / "api-key.txt"
        soul_path.parent.mkdir(parents=True, exist_ok=True)
        api_key_path.parent.mkdir(parents=True, exist_ok=True)
        soul_path.write_text("soul", encoding="utf-8")
        mnemonics_path.write_text("mnemonics", encoding="utf-8")
        api_key_path.write_text("key", encoding="utf-8")
        return RuntimeSettings(
            project_root=root,
            jobs_root=root / "jobs",
            soul_path=soul_path,
            mnemonics_path=mnemonics_path,
            api_key_path=api_key_path,
            chat_model="chat-model",
            embed_model="embed-model",
            cookie_secure=cookie_secure,
        )

    def register_user(
        self,
        client: TestClient,
        email: str = "student@example.com",
        password: str = "password123",
        invite_code: str = "MED-PILOT",
    ) -> dict:
        with patch.dict(os.environ, {"JSTUDY_ADMIN_TOKEN": "secret"}, clear=False):
            created = client.post(
                "/api/admin/invite-codes?admin_token=secret",
                json={"code": invite_code, "label": "Security test invite"},
            )
        self.assertEqual(created.status_code, 200)
        response = client.post(
            "/api/auth/register",
            json={"email": email, "password": password, "invite_code": invite_code},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def create_invite(self, client: TestClient, invite_code: str = "MED-PILOT") -> None:
        with patch.dict(os.environ, {"JSTUDY_ADMIN_TOKEN": "secret"}, clear=False):
            created = client.post(
                "/api/admin/invite-codes?admin_token=secret",
                json={"code": invite_code, "label": "Security test invite"},
            )
        self.assertEqual(created.status_code, 200)

    def fake_runner(self, **kwargs):
        output_dir = kwargs["output_dir"]
        output_prefix = kwargs["output_prefix"]
        output_dir.mkdir(parents=True, exist_ok=True)
        markdown = output_dir / f"{output_prefix}-output.md"
        evidence = output_dir / f"{output_prefix}-evidence.json"
        evidence_links = output_dir / f"{output_prefix}-evidence_links.json"
        quality = output_dir / f"{output_prefix}-quality.json"
        trace = output_dir / f"{output_prefix}-retrieval_trace.json"
        package = output_dir / f"{output_prefix}-package.json"
        markdown.write_text("Fact\n", encoding="utf-8")
        evidence.write_text("[]", encoding="utf-8")
        evidence_links.write_text("[]", encoding="utf-8")
        quality.write_text(json.dumps({"status": "pass"}), encoding="utf-8")
        trace.write_text("{}", encoding="utf-8")
        package.write_text(
            json.dumps(
                {
                    "type": "material_package",
                    "service_mode": "single_courseware",
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
        return {
            "markdown": markdown,
            "evidence": evidence,
            "evidence_links": evidence_links,
            "quality": quality,
            "trace": trace,
            "package": package,
        }

    def test_durable_repository_hides_unknown_and_foreign_jobs_identically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            database_url = settings.database_url or (
                f"sqlite:///{(settings.jobs_root / 'jstudy.db').as_posix()}"
            )
            engine = create_auth_engine(database_url)
            create_application_tables(engine)
            repository = JobRepository(engine)
            service = JobService(repository, settings)
            first_client = TestClient(
                create_app(
                    settings=settings,
                    job_repository=repository,
                    job_service=service,
                )
            )
            self.register_user(first_client, email="owner@example.com", invite_code="OWNER")
            generated = first_client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )
            job_id = generated.json()["job_id"]

            second_client = TestClient(
                create_app(
                    settings=settings,
                    job_repository=repository,
                    job_service=service,
                )
            )
            self.register_user(second_client, email="other@example.com", invite_code="OTHER")

            foreign = second_client.get(f"/api/jobs/{job_id}")
            unknown = second_client.get("/api/jobs/does-not-exist")

        self.assertEqual(generated.status_code, 200)
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(foreign.json(), unknown.json())

    def test_authentication_requires_valid_session_and_sets_hardened_cookie(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root, cookie_secure=True)
            client = TestClient(create_app(settings=settings))

            missing = client.get("/api/auth/me")
            self.create_invite(client)
            registered = client.post(
                "/api/auth/register",
                json={"email": "student@example.com", "password": "password123", "invite_code": "MED-PILOT"},
            )
            cookie = registered.headers["set-cookie"]

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(registered.json()["email"], "student@example.com")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=lax", cookie)
        self.assertIn("Secure", cookie)

    def test_public_readiness_payloads_do_not_expose_server_paths_or_provider_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_provider_error = (
                f"provider failed while reading {root / 'secrets' / 'provider-token.txt'}"
            )
            settings = RuntimeSettings(
                project_root=root,
                jobs_root=root / "private-jobs",
                soul_path=root / "private-config" / "missing-soul.md",
                mnemonics_path=root / "private-config" / "missing-mnemonics.md",
                api_key_path=root / "private-secrets" / "missing-api-key.txt",
                api_key="test-key",
                chat_model="chat-model",
                embed_model="embed-model",
            )

            def failing_probe(*_args):
                raise RuntimeError(private_provider_error)

            client = TestClient(
                create_app(settings=settings, provider_probe=failing_probe)
            )
            readiness = client.get("/api/readiness?probe_provider=true")
            self.register_user(client)
            generate = client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )

        self.assertEqual(readiness.status_code, 200)
        self.assertEqual(generate.status_code, 503)
        for payload in (readiness.json(), generate.json()):
            serialized = json.dumps(payload)
            self.assertNotIn(str(root), serialized)
            self.assertNotIn(root.name, serialized)
            self.assertNotIn(private_provider_error, serialized)
            self.assertNotIn("provider-token.txt", serialized)
            self.assertNotIn("private-jobs", serialized)
            self.assertNotIn("missing-soul.md", serialized)
            self.assertNotIn("missing-mnemonics.md", serialized)
            self.assertNotIn("missing-api-key.txt", serialized)

    def test_public_trace_redacts_server_paths_recursively(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)
            generated = client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )
            job_id = generated.json()["job_id"]

            def trace_runner(**kwargs):
                for state in (
                    JobState.PARSING,
                    JobState.RETRIEVING,
                    JobState.GENERATING,
                    JobState.PACKAGING,
                ):
                    kwargs["progress_callback"](state)
                outputs = self.fake_runner(**kwargs)
                private_cache = root / "private-cache" / "embeddings.json"
                outputs["trace"].write_text(
                    json.dumps(
                        {
                            "pdf": str(kwargs["pdf_path"]),
                            "pdfs": [str(path) for path in kwargs["pdf_paths"]],
                            "embedding_cache": str(private_cache),
                            "nested": {
                                "provider_path": str(root / "secrets" / "token.txt"),
                                "strategy": "hybrid retrieval",
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                return outputs

            worker = JobWorker(
                client.app.state.job_repository,
                settings,
                worker_id="worker-security-test",
                single_runner=trace_runner,
                document_service=FakeDocumentService(),
            )
            self.assertTrue(worker.run_once())
            response = client.get(f"/api/jobs/{job_id}/trace")

        self.assertEqual(response.status_code, 200)
        serialized = json.dumps(response.json())
        self.assertNotIn(str(root), serialized)
        self.assertNotIn("private-cache", serialized)
        self.assertNotIn("token.txt", serialized)
        self.assertEqual(response.json()["nested"]["strategy"], "hybrid retrieval")

    def test_permission_control_blocks_logged_in_non_admin_from_admin_invites(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)

            with patch.dict(os.environ, {"JSTUDY_ADMIN_TOKEN": "secret"}, clear=False):
                response = client.post(
                    "/api/admin/invite-codes",
                    json={"code": "NOPE", "label": "should be blocked"},
                )

        self.assertEqual(response.status_code, 401)

    def test_input_validation_rejects_bad_auth_fields_and_sanitizes_upload_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))

            with patch.dict(os.environ, {"JSTUDY_ADMIN_TOKEN": "secret"}, clear=False):
                client.post("/api/admin/invite-codes?admin_token=secret", json={"code": "MED-PILOT"})
            bad_email = client.post(
                "/api/auth/register",
                json={"email": "not-an-email", "password": "password123", "invite_code": "MED-PILOT"},
            )
            short_password = client.post(
                "/api/auth/register",
                json={"email": "student@example.com", "password": "short", "invite_code": "MED-PILOT"},
            )
            self.register_user(client, email="safe@example.com", invite_code="SAFE")
            generated = client.post(
                "/api/generate",
                files={"pdf": ("../../evil.pdf", self.make_pdf_bytes(), "application/pdf")},
            )
            source = client.app.state.job_repository.list_sources(
                generated.json()["job_id"]
            )[0]

        self.assertEqual(bad_email.status_code, 400)
        self.assertEqual(short_password.status_code, 400)
        self.assertEqual(generated.status_code, 200)
        self.assertEqual(source.original_filename, "evil.pdf")
        self.assertFalse(Path(source.relative_path).is_absolute())
        self.assertNotIn("..", Path(source.relative_path).parts)

    def test_data_ownership_blocks_other_users_from_all_job_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            first_client = TestClient(create_app(settings=settings))
            first_user = self.register_user(first_client, email="one@example.com", invite_code="ONE")
            generated = first_client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )
            job_id = generated.json()["job_id"]

            second_client = TestClient(create_app(settings=settings))
            self.register_user(second_client, email="two@example.com", invite_code="TWO")
            blocked = [
                second_client.get(f"/api/jobs/{job_id}"),
                second_client.get(f"/api/jobs/{job_id}/output"),
                second_client.get(f"/api/jobs/{job_id}/evidence"),
                second_client.get(f"/api/jobs/{job_id}/evidence-links"),
                second_client.get(f"/api/jobs/{job_id}/trace"),
                second_client.get(f"/api/jobs/{job_id}/package"),
                second_client.get(f"/api/jobs/{job_id}/manifest"),
                second_client.get(f"/api/jobs/{job_id}/learning-map"),
                second_client.get(f"/api/jobs/{job_id}/coverage"),
                second_client.get(f"/api/jobs/{job_id}/export"),
                second_client.get(f"/api/jobs/{job_id}/pdf"),
                second_client.get(f"/api/jobs/{job_id}/pdf-info"),
                second_client.get(f"/api/jobs/{job_id}/pdf-page/1.png"),
                second_client.get(f"/api/jobs/{job_id}/pdfs"),
                second_client.get(f"/api/jobs/{job_id}/pdfs/S001/pdf"),
                second_client.get(f"/api/jobs/{job_id}/pdfs/S001/pdf-info"),
                second_client.get(f"/api/jobs/{job_id}/pdfs/S001/pdf-page/1.png"),
            ]
            record = first_client.app.state.job_repository.get(job_id)

        self.assertEqual(generated.status_code, 200)
        self.assertEqual(record.owner_user_id, first_user["id"])
        self.assertEqual([response.status_code for response in blocked], [404] * len(blocked))

    def test_sql_injection_payloads_do_not_bypass_login_or_invite_matching(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))
            self.register_user(client, email="victim@example.com", password="password123")
            client.post("/api/auth/logout")

            injected_login = client.post(
                "/api/auth/login",
                json={"email": "victim@example.com' OR '1'='1", "password": "wrong-password"},
            )
            injected_invite = client.post(
                "/api/auth/register",
                json={
                    "email": "attacker@example.com",
                    "password": "password123",
                    "invite_code": "MED-PILOT' OR '1'='1",
                },
            )

        self.assertEqual(injected_login.status_code, 401)
        self.assertNotIn("set-cookie", injected_login.headers)
        self.assertEqual(injected_invite.status_code, 400)


if __name__ == "__main__":
    unittest.main()
