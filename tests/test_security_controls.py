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
from packages.core.jstudy_core.jobs import JobStore  # noqa: E402
from packages.core.jstudy_core.settings import RuntimeSettings  # noqa: E402


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
        markdown.write_text("Fact\n", encoding="utf-8")
        evidence.write_text("[]", encoding="utf-8")
        evidence_links.write_text("[]", encoding="utf-8")
        quality.write_text(json.dumps({"status": "pass"}), encoding="utf-8")
        trace.write_text("{}", encoding="utf-8")
        return {
            "markdown": markdown,
            "evidence": evidence,
            "evidence_links": evidence_links,
            "quality": quality,
            "trace": trace,
        }

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
            job_store = JobStore()
            settings = self.ready_settings(root)
            client = TestClient(create_app(runner=self.fake_runner, job_store=job_store, settings=settings))

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
            job = job_store.require(generated.json()["job_id"])

        self.assertEqual(bad_email.status_code, 400)
        self.assertEqual(short_password.status_code, 400)
        self.assertEqual(generated.status_code, 200)
        self.assertEqual(job.pdf_path.name, "evil.pdf")
        self.assertTrue(job.pdf_path.is_relative_to(settings.jobs_root))

    def test_data_ownership_blocks_other_users_from_all_job_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job_store = JobStore()
            settings = self.ready_settings(root)
            first_client = TestClient(create_app(runner=self.fake_runner, job_store=job_store, settings=settings))
            first_user = self.register_user(first_client, email="one@example.com", invite_code="ONE")
            generated = first_client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )
            job_id = generated.json()["job_id"]

            second_client = TestClient(create_app(runner=self.fake_runner, job_store=job_store, settings=settings))
            self.register_user(second_client, email="two@example.com", invite_code="TWO")
            blocked = [
                second_client.get(f"/api/jobs/{job_id}"),
                second_client.get(f"/api/jobs/{job_id}/output"),
                second_client.get(f"/api/jobs/{job_id}/evidence"),
                second_client.get(f"/api/jobs/{job_id}/evidence-links"),
                second_client.get(f"/api/jobs/{job_id}/trace"),
                second_client.get(f"/api/jobs/{job_id}/package"),
                second_client.get(f"/api/jobs/{job_id}/export"),
                second_client.get(f"/api/jobs/{job_id}/pdf"),
                second_client.get(f"/api/jobs/{job_id}/pdf-info"),
                second_client.get(f"/api/jobs/{job_id}/pdf-page/1.png"),
                second_client.get(f"/api/jobs/{job_id}/pdfs"),
                second_client.get(f"/api/jobs/{job_id}/pdfs/S001/pdf"),
                second_client.get(f"/api/jobs/{job_id}/pdfs/S001/pdf-info"),
                second_client.get(f"/api/jobs/{job_id}/pdfs/S001/pdf-page/1.png"),
            ]
            record = job_store.require(job_id)

        self.assertEqual(generated.status_code, 200)
        self.assertEqual(record.metadata["owner_user_id"], first_user["id"])
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
