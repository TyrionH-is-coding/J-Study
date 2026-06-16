import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import fitz
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.api.jstudy_api.app import ADMIN_SETTINGS_HTML, INDEX_HTML, create_app  # noqa: E402
from packages.core.jstudy_core.admin_settings import AdminSettingsService  # noqa: E402
from packages.core.jstudy_core.jobs import JobStore  # noqa: E402
from packages.core.jstudy_core.settings import RuntimeSettings  # noqa: E402


class WebMvpTest(unittest.TestCase):
    def make_pdf_bytes(self) -> bytes:
        doc = fitz.open()
        for page_no in (1, 2):
            page = doc.new_page(width=240, height=320)
            page.insert_text((40, 80), f"Page {page_no}")
        return doc.tobytes()

    def ready_settings(
        self,
        root: Path,
        max_pdf_bytes: int = 50 * 1024 * 1024,
        job_retention_hours: int = 0,
        invite_required: bool = True,
    ) -> RuntimeSettings:
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
            max_pdf_bytes=max_pdf_bytes,
            job_retention_hours=job_retention_hours,
            invite_required=invite_required,
        )

    def register_user(
        self,
        client: TestClient,
        email: str = "student@example.com",
        password: str = "password123",
        invite_code: str = "MED-PILOT",
    ) -> dict:
        with patch.dict(os.environ, {"JSTUDY_ADMIN_TOKEN": "secret"}, clear=False):
            client.post(
                "/api/admin/invite-codes?admin_token=secret",
                json={"code": invite_code, "label": "Test invite"},
            )
        response = client.post(
            "/api/auth/register",
            json={"email": email, "password": password, "invite_code": invite_code},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def login_user(
        self,
        client: TestClient,
        email: str = "student@example.com",
        password: str = "password123",
    ) -> dict:
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_index_html_contains_pdf_citation_panel(self):
        self.assertIn('id="evidenceList"', INDEX_HTML)
        self.assertIn('id="pdfPages"', INDEX_HTML)
        self.assertIn("function renderEvidencePanel", INDEX_HTML)
        self.assertIn("function renderPdfPages", INDEX_HTML)
        self.assertIn("function scrollPdfPageIntoView", INDEX_HTML)
        self.assertIn("function renderCodeBlock", INDEX_HTML)
        self.assertIn("function renderTableBlock", INDEX_HTML)
        self.assertIn("function renderInlineMarkdown", INDEX_HTML)
        self.assertIn("headingMatch = line.match", INDEX_HTML)
        self.assertIn("<strong>", INDEX_HTML)
        self.assertIn('line.startsWith("```")', INDEX_HTML)
        self.assertIn('data-ref="${link.ref_id}"', INDEX_HTML)
        self.assertIn('event.target.closest(".citation-item")', INDEX_HTML)
        self.assertIn("scrollPdfPageIntoView(page)", INDEX_HTML)
        self.assertIn("pdfPages.scrollTo", INDEX_HTML)
        self.assertNotIn('target.scrollIntoView({ block: "center"', INDEX_HTML)
        self.assertIn("min-height: 0;", INDEX_HTML)
        self.assertIn("overflow-y: auto;", INDEX_HTML)
        self.assertIn("overflow-x: hidden;", INDEX_HTML)
        self.assertIn("function showEvidenceLink(link, options = {})", INDEX_HTML)
        self.assertIn("if (options.scrollCitationList && active)", INDEX_HTML)
        self.assertIn("showEvidenceLink(link, { scrollCitationList: false })", INDEX_HTML)
        self.assertIn("showEvidenceLink(link, { scrollCitationList: true })", INDEX_HTML)
        self.assertNotIn("<iframe", INDEX_HTML)

    def test_index_html_loads_scenario_and_parser_profile_options(self):
        self.assertIn("/api/options", INDEX_HTML)
        self.assertIn('name="scenario_id"', INDEX_HTML)
        self.assertIn('name="parser_profile_id"', INDEX_HTML)

    def test_index_html_contains_auth_gate(self):
        self.assertIn("/api/auth/me", INDEX_HTML)
        self.assertIn("/api/auth/login", INDEX_HTML)
        self.assertIn("/api/auth/register", INDEX_HTML)
        self.assertIn('name="invite_code"', INDEX_HTML)
        self.assertNotIn('name="invite_code" type="text" autocomplete="off" required', INDEX_HTML)

    def test_health_endpoint_reports_api_status(self):
        client = TestClient(create_app())

        response = client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json(), {"status": "ok", "service": "jstudy-api"})

    def test_options_endpoint_returns_public_scenarios_and_parser_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = AdminSettingsService(root / "data" / "settings")
            service.load_all()
            settings = RuntimeSettings.from_env(root, jobs_root=root / "jobs")
            client = TestClient(create_app(settings=settings))

            response = client.get("/api/options")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["default_scenario_id"], "medicine-default")
        self.assertIn("medicine-default", {item["id"] for item in payload["scenarios"]})
        self.assertEqual([item["id"] for item in payload["parser_profiles"]], ["fast"])

    def test_admin_settings_page_is_served(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))

            response = client.get("/admin/settings")

        self.assertEqual(response.status_code, 200)
        self.assertIn("adminSettingsApp", response.text)
        self.assertIn("/api/admin/settings", response.text)

    def test_admin_settings_page_contains_parser_profile_controls(self):
        self.assertIn("defaultScenarioId", ADMIN_SETTINGS_HTML)
        self.assertIn("defaultParserProfileId", ADMIN_SETTINGS_HTML)
        self.assertIn("qualityVisibleToUsers", ADMIN_SETTINGS_HTML)
        self.assertIn("qualityEnabled", ADMIN_SETTINGS_HTML)

    def test_admin_settings_page_contains_invite_management(self):
        self.assertIn("/api/admin/invite-codes", ADMIN_SETTINGS_HTML)
        self.assertIn("inviteCodeInput", ADMIN_SETTINGS_HTML)
        self.assertIn("createInviteBtn", ADMIN_SETTINGS_HTML)

    def test_admin_settings_endpoint_requires_token_when_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))

            with patch.dict(os.environ, {"JSTUDY_ADMIN_TOKEN": "secret"}, clear=False):
                blocked = client.get("/api/admin/settings")
                allowed = client.get("/api/admin/settings?admin_token=secret")

        self.assertEqual(blocked.status_code, 401)
        self.assertEqual(allowed.status_code, 200)

    def test_auth_register_login_me_and_logout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))

            with patch.dict(os.environ, {"JSTUDY_ADMIN_TOKEN": "secret"}, clear=False):
                missing_invite = client.post(
                    "/api/auth/register",
                    json={"email": "student@example.com", "password": "password123", "invite_code": "MED-PILOT"},
                )
                created = client.post(
                    "/api/admin/invite-codes?admin_token=secret",
                    json={"code": "MED-PILOT", "label": "Medicine pilot"},
                )
                registered = client.post(
                    "/api/auth/register",
                    json={"email": "Student@Example.com", "password": "password123", "invite_code": "MED-PILOT"},
                )
                me_after_register = client.get("/api/auth/me")
                logged_out = client.post("/api/auth/logout")
                me_after_logout = client.get("/api/auth/me")
                logged_in = client.post(
                    "/api/auth/login",
                    json={"email": "student@example.com", "password": "password123"},
                )
                me_after_login = client.get("/api/auth/me")

        self.assertEqual(missing_invite.status_code, 400)
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["code"], "MED-PILOT")
        self.assertEqual(registered.status_code, 200)
        self.assertIn("jstudy_session=", registered.headers["set-cookie"])
        self.assertEqual(me_after_register.json()["email"], "student@example.com")
        self.assertFalse(me_after_register.json()["email_verified"])
        self.assertEqual(logged_out.status_code, 200)
        self.assertIn("jstudy_session=", logged_out.headers["set-cookie"])
        self.assertEqual(me_after_logout.status_code, 401)
        self.assertEqual(logged_in.status_code, 200)
        self.assertEqual(me_after_login.json()["email"], "student@example.com")

    def test_auth_register_allows_missing_invite_when_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root, invite_required=False)
            client = TestClient(create_app(settings=settings))

            registered = client.post(
                "/api/auth/register",
                json={"email": "student@example.com", "password": "password123"},
            )
            me_after_register = client.get("/api/auth/me")

        self.assertEqual(registered.status_code, 200)
        self.assertEqual(registered.json()["email"], "student@example.com")
        self.assertEqual(me_after_register.json()["email"], "student@example.com")

    def test_admin_invite_api_requires_token_and_shared_code_registers_multiple_users(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))

            with patch.dict(os.environ, {"JSTUDY_ADMIN_TOKEN": "secret"}, clear=False):
                blocked = client.get("/api/admin/invite-codes")
                created = client.post(
                    "/api/admin/invite-codes?admin_token=secret",
                    json={"code": "MED-PILOT", "label": "Medicine pilot"},
                )
                first = client.post(
                    "/api/auth/register",
                    json={"email": "one@example.com", "password": "password123", "invite_code": "MED-PILOT"},
                )
                client.post("/api/auth/logout")
                second = client.post(
                    "/api/auth/register",
                    json={"email": "two@example.com", "password": "password456", "invite_code": "MED-PILOT"},
                )
                invites = client.get("/api/admin/invite-codes?admin_token=secret")
                uses = client.get(f"/api/admin/invite-codes/{created.json()['id']}/uses?admin_token=secret")

        self.assertEqual(blocked.status_code, 401)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(invites.json()[0]["usage_count"], 2)
        self.assertEqual([item["email"] for item in uses.json()], ["one@example.com", "two@example.com"])

    def test_admin_settings_api_redacts_and_persists_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = AdminSettingsService(root / "data" / "settings")
            payload = service.load_all()
            payload["model_catalog"]["services"]["llm"]["profiles"][0]["api_key"] = "sk-secret"
            service.save_all(payload)
            settings = RuntimeSettings.from_env(root)
            client = TestClient(create_app(settings=settings))

            loaded = client.get("/api/admin/settings").json()
            loaded["runtime"]["rag"]["chunk_max_chars"] = 900
            loaded["content_pack"]["packs"][0]["name"] = "Medicine Pilot"
            saved = client.put("/api/admin/settings", json=loaded)
            restored = service.load_all()

        self.assertEqual(loaded["model_catalog"]["services"]["llm"]["profiles"][0]["api_key"], "")
        self.assertTrue(loaded["model_catalog"]["services"]["llm"]["profiles"][0]["api_key_set"])
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(restored["runtime"]["rag"]["chunk_max_chars"], 900)
        self.assertEqual(restored["content_pack"]["packs"][0]["name"], "Medicine Pilot")
        self.assertEqual(
            restored["model_catalog"]["services"]["llm"]["profiles"][0]["api_key"],
            "sk-secret",
        )

    def test_admin_settings_diagnostic_uses_provider_probe(self):
        calls = []

        def probe(api_key: str, chat_model: str, embed_model: str):
            calls.append((api_key, chat_model, embed_model))
            return {
                "name": "provider_connectivity",
                "status": "ok",
                "detail": "chat and embedding reachable",
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            soul = root / "soul.md"
            mnemonics = root / "mnemonics.md"
            soul.write_text("soul", encoding="utf-8")
            mnemonics.write_text("mnemonics", encoding="utf-8")
            service = AdminSettingsService(root / "data" / "settings")
            payload = service.load_all()
            payload["model_catalog"]["services"]["llm"]["profiles"][0]["api_key"] = "catalog-key"
            payload["model_catalog"]["services"]["llm"]["profiles"][0]["models"][0]["model"] = "chat-model"
            payload["model_catalog"]["services"]["embedding"]["profiles"][0]["models"][0]["model"] = "embed-model"
            service.save_all(payload)
            settings = RuntimeSettings.from_env(root)
            client = TestClient(create_app(settings=settings, provider_probe=probe))

            response = client.post("/api/admin/settings/test/llm")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(calls, [("catalog-key", "chat-model", "embed-model")])

    def test_readiness_endpoint_reports_degraded_runtime_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = RuntimeSettings(
                project_root=root,
                jobs_root=root / "jobs",
                soul_path=root / "missing-soul.md",
                mnemonics_path=root / "missing-mnemonics.md",
                api_key_path=root / "missing-api-key.txt",
                chat_model="chat-model",
                embed_model="embed-model",
            )
            client = TestClient(create_app(settings=settings))

            response = client.get("/api/readiness")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        body = response.json()
        self.assertEqual(body["service"], "jstudy-api")
        self.assertEqual(body["status"], "degraded")
        checks = {check["name"]: check for check in body["checks"]}
        self.assertEqual(checks["soul_path"]["status"], "error")
        self.assertEqual(checks["mnemonics_path"]["status"], "error")
        self.assertEqual(checks["api_key"]["status"], "error")

    def test_readiness_endpoint_runs_provider_probe_only_when_requested(self):
        calls = []

        def probe(api_key: str, chat_model: str, embed_model: str):
            calls.append((api_key, chat_model, embed_model))
            return {
                "name": "provider_connectivity",
                "status": "ok",
                "detail": "chat and embedding reachable",
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings, provider_probe=probe))

            plain = client.get("/api/readiness").json()
            probed = client.get("/api/readiness?probe_provider=true").json()

        self.assertEqual(calls, [("key", "chat-model", "embed-model")])
        self.assertNotIn("provider_connectivity", {check["name"] for check in plain["checks"]})
        checks = {check["name"]: check for check in probed["checks"]}
        self.assertEqual(checks["provider_connectivity"]["status"], "ok")

    def test_generate_rejects_unready_runtime_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job_store = JobStore()
            settings = RuntimeSettings(
                project_root=root,
                jobs_root=root / "jobs",
                soul_path=root / "missing-soul.md",
                mnemonics_path=root / "missing-mnemonics.md",
                api_key_path=root / "missing-api-key.txt",
                chat_model="chat-model",
                embed_model="embed-model",
            )
            client = TestClient(create_app(runner=lambda **kwargs: {}, job_store=job_store, settings=settings))
            self.register_user(client)

            response = client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )

        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertNotIn("job_id", body)
        self.assertEqual(body["detail"]["status"], "degraded")
        checks = {check["name"]: check for check in body["detail"]["checks"]}
        self.assertEqual(checks["soul_path"]["status"], "error")

    def test_generate_requires_authenticated_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(runner=lambda **kwargs: {}, settings=settings))

            response = client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )

        self.assertEqual(response.status_code, 401)

    def test_generate_job_exposes_output_and_evidence_contracts(self):
        captured = {}

        def fake_runner(
            pdf_path,
            soul_path,
            mnemonics_path,
            api_key_path,
            output_dir,
            chat_model,
            embed_model,
            output_prefix,
            rag_config,
            embedding_cache_path,
            outline_path,
        ):
            captured.update(
                {
                    "soul_path": soul_path,
                    "mnemonics_path": mnemonics_path,
                    "api_key_path": api_key_path,
                    "chat_model": chat_model,
                    "embed_model": embed_model,
                }
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            markdown = output_dir / f"{output_prefix}-output.md"
            evidence = output_dir / f"{output_prefix}-evidence.json"
            evidence_links = output_dir / f"{output_prefix}-evidence_links.json"
            quality = output_dir / f"{output_prefix}-quality.json"
            trace = output_dir / f"{output_prefix}-retrieval_trace.json"
            markdown.write_text("Fact <!-- evidence: E001 -->\n", encoding="utf-8")
            evidence.write_text(
                json.dumps(
                    [
                        {
                            "id": "E001",
                            "source_file": pdf_path.name,
                            "page": 2,
                            "chunk_id": "C001",
                            "excerpt": "Fact",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            evidence_links.write_text(
                json.dumps(
                    [
                        {
                            "ref_id": "E001",
                            "occurrence": 1,
                            "target": {"source_file": pdf_path.name, "page": 2, "quote": "Fact"},
                        }
                    ]
                ),
                encoding="utf-8",
            )
            quality.write_text(json.dumps({"status": "pass"}), encoding="utf-8")
            trace.write_text(
                json.dumps({"selected_chunks": [{"id": "C001"}], "query_traces": [{"query": {"id": "sample"}}]}),
                encoding="utf-8",
            )
            return {
                "markdown": markdown,
                "evidence": evidence,
                "evidence_links": evidence_links,
                "quality": quality,
                "trace": trace,
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job_store = JobStore()
            settings = self.ready_settings(root)
            client = TestClient(create_app(runner=fake_runner, job_store=job_store, settings=settings))
            self.register_user(client)
            response = client.post(
                "/api/generate",
                files={
                    "pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf"),
                    "outline": ("outline.md", b"# outline\n", "text/markdown"),
                },
            )

            self.assertEqual(response.status_code, 200)
            job_id = response.json()["job_id"]
            status_response = client.get(f"/api/jobs/{job_id}")
            status = status_response.json()
            output_response = client.get(f"/api/jobs/{job_id}/output")
            output = output_response.json()
            evidence_response = client.get(f"/api/jobs/{job_id}/evidence")
            evidence = evidence_response.json()
            trace_response = client.get(f"/api/jobs/{job_id}/trace")
            trace = trace_response.json()
            pdf_response = client.get(f"/api/jobs/{job_id}/pdf")
            pdf_info_response = client.get(f"/api/jobs/{job_id}/pdf-info")
            pdf_info = pdf_info_response.json()
            page_png = client.get(f"/api/jobs/{job_id}/pdf-page/2.png")
            record = job_store.require(job_id)

        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(status_response.headers["cache-control"], "no-store")
        self.assertEqual(output_response.headers["cache-control"], "private, max-age=0, must-revalidate")
        self.assertEqual(evidence_response.headers["cache-control"], "private, max-age=0, must-revalidate")
        self.assertEqual(trace_response.headers["cache-control"], "private, max-age=0, must-revalidate")
        self.assertEqual(pdf_response.headers["cache-control"], "private, max-age=0, must-revalidate")
        self.assertEqual(pdf_info_response.headers["cache-control"], "private, max-age=0, must-revalidate")
        self.assertEqual(page_png.headers["cache-control"], "private, max-age=0, must-revalidate")
        self.assertEqual(status["status"], "completed")
        self.assertEqual(record.status, "completed")
        self.assertEqual(record.pdf_path.name, "lecture.pdf")
        self.assertEqual(captured["soul_path"], settings.soul_path)
        self.assertEqual(captured["mnemonics_path"], settings.mnemonics_path)
        self.assertEqual(captured["api_key_path"], settings.api_key_path)
        self.assertEqual(captured["chat_model"], "chat-model")
        self.assertEqual(captured["embed_model"], "embed-model")
        self.assertEqual(status["quality"]["status"], "pass")
        self.assertIn("evidence_links_url", status)
        self.assertIn("trace_url", status)
        self.assertIn("Fact", output["markdown"])
        self.assertEqual(evidence["evidence"][0]["id"], "E001")
        self.assertEqual(evidence["evidence_links"][0]["target"]["page"], 2)
        self.assertEqual(trace["selected_chunks"][0]["id"], "C001")
        self.assertEqual(trace["query_traces"][0]["query"]["id"], "sample")
        self.assertEqual(pdf_info["page_count"], 2)
        self.assertEqual(page_png.headers["content-type"], "image/png")
        self.assertTrue(page_png.content.startswith(b"\x89PNG"))

    def test_generate_job_records_owner_and_blocks_other_users(self):
        def fake_runner(**kwargs):
            output_dir = kwargs["output_dir"]
            output_prefix = kwargs["output_prefix"]
            output_dir.mkdir(parents=True, exist_ok=True)
            markdown = output_dir / f"{output_prefix}-output.md"
            evidence = output_dir / f"{output_prefix}-evidence.json"
            evidence_links = output_dir / f"{output_prefix}-evidence_links.json"
            quality = output_dir / f"{output_prefix}-quality.json"
            markdown.write_text("Fact\n", encoding="utf-8")
            evidence.write_text("[]", encoding="utf-8")
            evidence_links.write_text("[]", encoding="utf-8")
            quality.write_text(json.dumps({"status": "pass"}), encoding="utf-8")
            return {
                "markdown": markdown,
                "evidence": evidence,
                "evidence_links": evidence_links,
                "quality": quality,
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job_store = JobStore()
            settings = self.ready_settings(root)
            first_client = TestClient(create_app(runner=fake_runner, job_store=job_store, settings=settings))
            first_user = self.register_user(first_client, email="one@example.com", invite_code="ONE")
            response = first_client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )
            job_id = response.json()["job_id"]
            record = job_store.require(job_id)

            second_client = TestClient(create_app(runner=fake_runner, job_store=job_store, settings=settings))
            self.register_user(second_client, email="two@example.com", invite_code="TWO")
            blocked = second_client.get(f"/api/jobs/{job_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(record.metadata["owner_user_id"], first_user["id"])
        self.assertEqual(blocked.status_code, 404)

    def test_generate_job_uses_admin_runtime_model_and_rag_settings(self):
        captured = {}

        def fake_runner(**kwargs):
            captured.update(kwargs)
            output_dir = kwargs["output_dir"]
            output_prefix = kwargs["output_prefix"]
            output_dir.mkdir(parents=True, exist_ok=True)
            markdown = output_dir / f"{output_prefix}-output.md"
            evidence = output_dir / f"{output_prefix}-evidence.json"
            evidence_links = output_dir / f"{output_prefix}-evidence_links.json"
            quality = output_dir / f"{output_prefix}-quality.json"
            markdown.write_text("Fact\n", encoding="utf-8")
            evidence.write_text("[]", encoding="utf-8")
            evidence_links.write_text("[]", encoding="utf-8")
            quality.write_text(json.dumps({"status": "pass"}), encoding="utf-8")
            return {
                "markdown": markdown,
                "evidence": evidence,
                "evidence_links": evidence_links,
                "quality": quality,
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            soul = root / "soul.md"
            mnemonics = root / "mnemonics.md"
            soul.write_text("soul", encoding="utf-8")
            mnemonics.write_text("mnemonics", encoding="utf-8")
            service = AdminSettingsService(root / "data" / "settings")
            payload = service.load_all()
            payload["model_catalog"]["services"]["llm"]["profiles"][0]["api_key"] = "catalog-key"
            payload["model_catalog"]["services"]["llm"]["profiles"][0]["base_url"] = "https://chat.example/v1"
            payload["model_catalog"]["services"]["llm"]["profiles"][0]["models"][0]["model"] = "catalog-chat"
            payload["model_catalog"]["services"]["embedding"]["profiles"][0]["base_url"] = "https://embed.example/v1"
            payload["model_catalog"]["services"]["embedding"]["profiles"][0]["models"][0]["model"] = "catalog-embed"
            payload["runtime"]["rag"]["chunk_max_chars"] = 888
            payload["runtime"]["rag"]["per_query_limit"] = 4
            service.save_all(payload)
            settings = RuntimeSettings.from_env(root)
            client = TestClient(create_app(runner=fake_runner, settings=settings))
            self.register_user(client)

            response = client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["api_key"], "catalog-key")
        self.assertEqual(captured["chat_base_url"], "https://chat.example/v1")
        self.assertEqual(captured["embed_base_url"], "https://embed.example/v1")
        self.assertEqual(captured["chat_model"], "catalog-chat")
        self.assertEqual(captured["embed_model"], "catalog-embed")
        self.assertEqual(captured["rag_config"].chunk_max_chars, 888)
        self.assertEqual(captured["rag_config"].per_query_limit, 4)

    def test_generate_uses_default_scenario_and_fast_parser_profile(self):
        captured = {}

        def fake_runner(**kwargs):
            captured.update(kwargs)
            output_dir = kwargs["output_dir"]
            output_prefix = kwargs["output_prefix"]
            output_dir.mkdir(parents=True, exist_ok=True)
            markdown = output_dir / f"{output_prefix}-output.md"
            evidence = output_dir / f"{output_prefix}-evidence.json"
            evidence_links = output_dir / f"{output_prefix}-evidence_links.json"
            quality = output_dir / f"{output_prefix}-quality.json"
            trace = output_dir / f"{output_prefix}-retrieval_trace.json"
            chunks = output_dir / f"{output_prefix}-chunks.json"
            markdown.write_text("Fact\n", encoding="utf-8")
            evidence.write_text("[]", encoding="utf-8")
            evidence_links.write_text("[]", encoding="utf-8")
            quality.write_text(json.dumps({"status": "pass"}), encoding="utf-8")
            trace.write_text("{}", encoding="utf-8")
            chunks.write_text("[]", encoding="utf-8")
            return {
                "markdown": markdown,
                "evidence": evidence,
                "evidence_links": evidence_links,
                "quality": quality,
                "trace": trace,
                "chunks": chunks,
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = AdminSettingsService(root / "data" / "settings")
            service.load_all()
            settings = RuntimeSettings.from_env(root, jobs_root=root / "jobs")
            settings.soul_path.write_text("soul", encoding="utf-8")
            settings.mnemonics_path.write_text("mnemonics", encoding="utf-8")
            settings.api_key_path.write_text("key", encoding="utf-8")
            client = TestClient(create_app(runner=fake_runner, settings=settings))
            self.register_user(client)

            response = client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["parser_backend"], "pymupdf")
        self.assertEqual(captured["routing_metadata"]["scenario"]["resolved_scenario_id"], "medicine-default")
        self.assertEqual(captured["routing_metadata"]["parser_profile"]["resolved_parser_profile_id"], "fast")

    def test_generate_uses_selected_scenario_soul_profile(self):
        captured = {}

        def fake_runner(**kwargs):
            captured.update(kwargs)
            output_dir = kwargs["output_dir"]
            output_prefix = kwargs["output_prefix"]
            output_dir.mkdir(parents=True, exist_ok=True)
            markdown = output_dir / f"{output_prefix}-output.md"
            evidence = output_dir / f"{output_prefix}-evidence.json"
            evidence_links = output_dir / f"{output_prefix}-evidence_links.json"
            quality = output_dir / f"{output_prefix}-quality.json"
            trace = output_dir / f"{output_prefix}-retrieval_trace.json"
            chunks = output_dir / f"{output_prefix}-chunks.json"
            markdown.write_text("Fact\n", encoding="utf-8")
            evidence.write_text("[]", encoding="utf-8")
            evidence_links.write_text("[]", encoding="utf-8")
            quality.write_text(json.dumps({"status": "pass"}), encoding="utf-8")
            trace.write_text("{}", encoding="utf-8")
            chunks.write_text("[]", encoding="utf-8")
            return {
                "markdown": markdown,
                "evidence": evidence,
                "evidence_links": evidence_links,
                "quality": quality,
                "trace": trace,
                "chunks": chunks,
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = AdminSettingsService(root / "data" / "settings")
            payload = service.load_all()
            general = next(item for item in payload["content_pack"]["scenarios"] if item["id"] == "general-default")
            general["enabled"] = True
            profile = next(
                item for item in payload["content_pack"]["soul_profiles"] if item["id"] == "general-blank"
            )
            profile["soul_path"] = "souls/general.md"
            service.save_all(payload)
            settings = RuntimeSettings.from_env(root, jobs_root=root / "jobs")
            settings.soul_path.write_text("medicine soul", encoding="utf-8")
            settings.mnemonics_path.write_text("mnemonics", encoding="utf-8")
            general_soul = root / "souls" / "general.md"
            general_soul.parent.mkdir(parents=True, exist_ok=True)
            general_soul.write_text("general soul", encoding="utf-8")
            settings.api_key_path.write_text("key", encoding="utf-8")
            client = TestClient(create_app(runner=fake_runner, settings=settings))
            self.register_user(client)

            response = client.post(
                "/api/generate",
                data={"scenario_id": "general-default"},
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["soul_path"], general_soul)
        self.assertEqual(captured["routing_metadata"]["scenario"]["resolved_scenario_id"], "general-default")
        self.assertEqual(captured["routing_metadata"]["scenario"]["soul_profile_id"], "general-blank")

    def test_generate_rejects_hidden_quality_parser_for_public_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = AdminSettingsService(root / "data" / "settings")
            payload = service.load_all()
            quality = next(item for item in payload["runtime"]["parser_profiles"]["profiles"] if item["id"] == "quality")
            quality["enabled"] = True
            service.save_all(payload)
            settings = RuntimeSettings.from_env(root, jobs_root=root / "jobs")
            settings.soul_path.write_text("soul", encoding="utf-8")
            settings.mnemonics_path.write_text("mnemonics", encoding="utf-8")
            settings.api_key_path.write_text("key", encoding="utf-8")
            client = TestClient(create_app(settings=settings))
            self.register_user(client)

            response = client.post(
                "/api/generate",
                data={"parser_profile_id": "quality"},
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )

        self.assertEqual(response.status_code, 403)

    def test_default_job_store_persists_completed_job_status_between_app_instances(self):
        def fake_runner(
            pdf_path,
            soul_path,
            mnemonics_path,
            api_key_path,
            output_dir,
            chat_model,
            embed_model,
            output_prefix,
            rag_config,
            embedding_cache_path,
            outline_path,
        ):
            output_dir.mkdir(parents=True, exist_ok=True)
            markdown = output_dir / f"{output_prefix}-output.md"
            evidence = output_dir / f"{output_prefix}-evidence.json"
            evidence_links = output_dir / f"{output_prefix}-evidence_links.json"
            quality = output_dir / f"{output_prefix}-quality.json"
            markdown.write_text("Fact\n", encoding="utf-8")
            evidence.write_text("[]", encoding="utf-8")
            evidence_links.write_text("[]", encoding="utf-8")
            quality.write_text(json.dumps({"status": "pass"}), encoding="utf-8")
            return {
                "markdown": markdown,
                "evidence": evidence,
                "evidence_links": evidence_links,
                "quality": quality,
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            first_client = TestClient(create_app(runner=fake_runner, settings=settings))
            self.register_user(first_client)
            response = first_client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )
            job_id = response.json()["job_id"]

            second_client = TestClient(create_app(runner=fake_runner, settings=settings))
            self.login_user(second_client)
            restored = second_client.get(f"/api/jobs/{job_id}").json()

        self.assertEqual(restored["status"], "completed")
        self.assertEqual(restored["quality"]["status"], "pass")

    def test_failed_job_status_includes_exception_type_and_message(self):
        def failing_runner(**kwargs):
            raise TimeoutError("provider timeout")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(runner=failing_runner, settings=settings))
            self.register_user(client)
            response = client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )
            job_id = response.json()["job_id"]

            status = client.get(f"/api/jobs/{job_id}").json()

        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["error"], "TimeoutError: provider timeout")

    def test_create_app_prunes_expired_finished_jobs_when_retention_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root, job_retention_hours=1)
            job_store = JobStore(store_path=settings.jobs_root / "jobs.json")
            old_dir = settings.jobs_root / "old-job"
            old_dir.joinpath("input").mkdir(parents=True)
            old_dir.joinpath("output").mkdir()
            old_dir.joinpath("output", "result.md").write_text("old", encoding="utf-8")
            job_store.create(
                job_id="old-job",
                pdf_path=old_dir / "input" / "lecture.pdf",
                output_dir=old_dir / "output",
            )
            job_store.mark_completed("old-job", outputs={}, quality={"status": "pass"})
            job_store.require("old-job").updated_at = (
                datetime.now(timezone.utc) - timedelta(hours=2)
            ).isoformat()

            create_app(runner=lambda **kwargs: {}, job_store=job_store, settings=settings)

            restored = JobStore(store_path=settings.jobs_root / "jobs.json")

            self.assertIsNone(job_store.get("old-job"))
            self.assertIsNone(restored.get("old-job"))
            self.assertFalse(old_dir.exists())

    def test_queued_job_result_endpoints_return_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job_store = JobStore()
            job_store.create(
                job_id="queued-job",
                pdf_path=root / "input" / "lecture.pdf",
                output_dir=root / "output",
                metadata={"owner_user_id": "user-1"},
            )
            client = TestClient(
                create_app(base_dir=root, runner=lambda **kwargs: {}, job_store=job_store),
                raise_server_exceptions=False,
            )
            user = self.register_user(client)
            job_store.require("queued-job").metadata["owner_user_id"] = user["id"]

            output = client.get("/api/jobs/queued-job/output")
            evidence = client.get("/api/jobs/queued-job/evidence")
            evidence_links = client.get("/api/jobs/queued-job/evidence-links")

        self.assertEqual(output.status_code, 404)
        self.assertEqual(evidence.status_code, 404)
        self.assertEqual(evidence_links.status_code, 404)

    def test_generate_rejects_non_pdf_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root, max_pdf_bytes=1024)
            client = TestClient(create_app(runner=lambda **kwargs: {}, settings=settings))
            self.register_user(client)

            response = client.post(
                "/api/generate",
                files={"pdf": ("notes.txt", b"not a pdf", "text/plain")},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("PDF", response.json()["detail"])

    def test_generate_rejects_pdf_above_configured_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root, max_pdf_bytes=5)
            client = TestClient(create_app(runner=lambda **kwargs: {}, settings=settings))
            self.register_user(client)

            response = client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", b"%PDF- too large", "application/pdf")},
            )

        self.assertEqual(response.status_code, 413)
        self.assertIn("too large", response.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
