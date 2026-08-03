import copy
import json
import inspect
import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import fitz
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.api.jstudy_api.app import ADMIN_SETTINGS_HTML, INDEX_HTML, create_app  # noqa: E402
from packages.core.jstudy_core.admin_settings import AdminSettingsService  # noqa: E402
from packages.core.jstudy_core.auth_db import create_application_tables, create_auth_engine  # noqa: E402
from packages.core.jstudy_core.documents import (  # noqa: E402
    ParsedBlock,
    ParsedDocument,
    ParsedPage,
)
from packages.core.jstudy_core.job_system import (  # noqa: E402
    ArtifactKind,
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


class WebMvpTest(unittest.TestCase):
    def make_pdf_bytes(self) -> bytes:
        doc = fitz.open()
        for page_no in (1, 2):
            page = doc.new_page(width=240, height=320)
            page.insert_text((40, 80), f"Page {page_no}")
        return doc.tobytes()

    def v2_runner(self, **kwargs):
        output_dir = kwargs["output_dir"]
        output_prefix = kwargs["output_prefix"]
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "markdown": output_dir / f"{output_prefix}-output.md",
            "evidence": output_dir / f"{output_prefix}-evidence.json",
            "evidence_links": output_dir
            / f"{output_prefix}-evidence_links.json",
            "quality": output_dir / f"{output_prefix}-quality.json",
            "trace": output_dir / f"{output_prefix}-retrieval_trace.json",
            "package": output_dir / f"{output_prefix}-package.json",
        }
        paths["markdown"].write_text(
            "# 学习资料\n\n## 完整资料\n\nFact <!-- evidence: E001 -->\n",
            encoding="utf-8",
        )
        evidence = [
            {
                "id": "E001",
                "source_id": "S001",
                "source_file": "lecture.pdf",
                "page": 1,
                "chunk_id": "S001-C001",
                "excerpt": "Fact",
            }
        ]
        paths["evidence"].write_text(json.dumps(evidence), encoding="utf-8")
        paths["evidence_links"].write_text("[]", encoding="utf-8")
        paths["quality"].write_text('{"status":"pass"}', encoding="utf-8")
        paths["trace"].write_text("{}", encoding="utf-8")
        paths["package"].write_text(
            json.dumps(
                {
                    "schema_version": "material-package.v2",
                    "package_id": kwargs["package_id"],
                    "service_mode": "single_courseware",
                    "title": "学习资料",
                    "subject": "medicine",
                    "language": "zh-CN",
                    "source_ids": ["S001"],
                    "sections": [
                        {
                            "id": "full-material",
                            "order": 1,
                            "title": "完整资料",
                            "status": "generated",
                            "quality": {
                                "evidence_status": "sufficient",
                                "evidence_count": 1,
                                "cited_evidence_count": 1,
                                "citation_coverage": 1.0,
                            },
                            "source_ids": ["S001"],
                            "evidence_ids": ["E001"],
                            "blocks": [
                                {
                                    "id": "paragraph-001",
                                    "type": "paragraph",
                                    "runs": [
                                        {"type": "text", "text": "Fact "},
                                        {
                                            "type": "citation",
                                            "evidence_id": "E001",
                                        },
                                    ],
                                }
                            ],
                        }
                    ],
                    "rendering": {
                        "default_theme": {
                            "theme_id": "clinical-standard",
                            "theme_version": "1.0.0",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        return paths

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
            mineru_api_token="test-mineru-token",
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

    def durable_dependencies(
        self,
        settings: RuntimeSettings,
    ) -> tuple[JobRepository, JobService]:
        database_url = settings.database_url or (
            f"sqlite:///{(settings.jobs_root / 'jstudy.db').as_posix()}"
        )
        engine = create_auth_engine(database_url)
        create_application_tables(engine)
        repository = JobRepository(engine)
        return repository, JobService(repository, settings)

    def run_next_job(
        self,
        client: TestClient,
        settings: RuntimeSettings,
        runner,
    ) -> None:
        def staged_runner(**kwargs):
            callback = kwargs["progress_callback"]
            callback(JobState.RETRIEVING)
            callback(JobState.GENERATING)
            callback(JobState.PACKAGING)
            signature = inspect.signature(runner)
            if any(
                parameter.kind is inspect.Parameter.VAR_KEYWORD
                for parameter in signature.parameters.values()
            ):
                forwarded = kwargs
            else:
                forwarded = {
                    name: value
                    for name, value in kwargs.items()
                    if name in signature.parameters
                    and signature.parameters[name].kind
                    in {
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect.Parameter.KEYWORD_ONLY,
                    }
                }
            return runner(**forwarded)

        worker = JobWorker(
            client.app.state.job_repository,
            settings,
            single_runner=staged_runner,
            outline_runner=staged_runner,
            document_service=FakeDocumentService(),
        )
        self.assertTrue(worker.run_once())

    def test_generate_is_durable_queued_and_never_calls_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            repository, service = self.durable_dependencies(settings)
            with patch(
                "packages.core.jstudy_core.pipeline.run_mvp",
                side_effect=AssertionError("API must not call the runner"),
            ) as runner:
                first_client = TestClient(
                    create_app(
                        settings=settings,
                        job_repository=repository,
                        job_service=service,
                    )
                )
                self.register_user(first_client)
                generated = first_client.post(
                    "/api/generate",
                    files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
                    headers={"Idempotency-Key": "durable-one"},
                )
                runner.assert_not_called()
            job_id = generated.json()["job_id"]
            first_status = first_client.get(f"/api/jobs/{job_id}").json()

            restarted_repository, restarted_service = self.durable_dependencies(settings)
            second_client = TestClient(
                create_app(
                    settings=settings,
                    job_repository=restarted_repository,
                    job_service=restarted_service,
                )
            )
            self.login_user(second_client)
            restarted_status = second_client.get(f"/api/jobs/{job_id}").json()

        self.assertEqual(generated.status_code, 200)
        self.assertEqual(first_status["status"], "queued")
        self.assertEqual(first_status["state"], "queued")
        self.assertEqual(first_status["progress"], 0)
        self.assertEqual(restarted_status["job_id"], job_id)
        self.assertEqual(restarted_status["status"], "queued")

    def test_generate_reloads_submission_limits_and_routing_without_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            current = [settings]
            provider_calls = []

            def settings_provider():
                provider_calls.append(current[0])
                return current[0]

            repository, service = self.durable_dependencies(settings)
            client = TestClient(
                create_app(
                    settings=settings,
                    job_repository=repository,
                    job_service=service,
                    settings_provider=settings_provider,
                )
            )
            self.register_user(client)
            updated_soul = root / "config" / "updated-soul.md"
            updated_soul.write_text("updated soul", encoding="utf-8")
            current[0] = replace(
                settings,
                default_scenario_id="updated-scenario",
                content_pack_config={
                    "active_pack_id": "updated-pack",
                    "default_scenario_id": "updated-scenario",
                    "packs": [
                        {
                            "id": "updated-pack",
                            "enabled": True,
                            "soul_path": "config/updated-soul.md",
                        }
                    ],
                    "scenarios": [
                        {
                            "id": "updated-scenario",
                            "enabled": True,
                            "content_pack_id": "updated-pack",
                            "prompt_profile": "updated-profile",
                        }
                    ],
                    "soul_profiles": [
                        {
                            "id": "updated-profile",
                            "soul_path": "config/updated-soul.md",
                        }
                    ],
                },
            )
            pdf = self.make_pdf_bytes()
            generated = client.post(
                "/api/generate",
                data={
                    "scenario_id": "updated-scenario",
                    "parser_profile_id": "fast",
                },
                files={"pdf": ("lecture.pdf", pdf, "application/pdf")},
            )
            job = client.app.state.job_repository.get(
                generated.json()["job_id"]
            )

            current[0] = replace(
                current[0],
                max_pdf_bytes=len(pdf) - 1,
            )
            rejected = client.post(
                "/api/generate",
                data={
                    "scenario_id": "updated-scenario",
                    "parser_profile_id": "fast",
                },
                files={"pdf": ("lecture.pdf", pdf, "application/pdf")},
            )

        self.assertEqual(generated.status_code, 200)
        self.assertEqual(job.scenario_id, "updated-scenario")
        self.assertEqual(job.parser_profile_id, "fast")
        self.assertEqual(rejected.status_code, 413, rejected.json())
        self.assertEqual(rejected.json()["detail"]["code"], "pdf_too_large")
        self.assertEqual(len(provider_calls), 2)

    def test_generate_idempotency_is_owner_scoped_and_conflict_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)
            pdf_bytes = self.make_pdf_bytes()

            first = client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", pdf_bytes, "application/pdf")},
                headers={"Idempotency-Key": "same-request"},
            )
            replay = client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", pdf_bytes, "application/pdf")},
                headers={"Idempotency-Key": "same-request"},
            )
            conflict = client.post(
                "/api/generate",
                data={"mode": "different-metadata"},
                files={"pdf": ("lecture.pdf", pdf_bytes, "application/pdf")},
                headers={"Idempotency-Key": "same-request"},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(first.json()["job_id"], replay.json()["job_id"])
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(
            conflict.json()["detail"]["code"],
            "idempotency_conflict",
        )

    def test_index_html_contains_pdf_citation_panel(self):
        self.assertIn('id="evidenceList"', INDEX_HTML)
        self.assertIn('id="pdfPages"', INDEX_HTML)
        self.assertIn("function renderEvidencePanel", INDEX_HTML)
        self.assertIn("function renderPdfPages", INDEX_HTML)
        self.assertIn("function scrollPdfPageIntoView", INDEX_HTML)
        self.assertIn("function renderCodeBlock", INDEX_HTML)
        self.assertIn("function renderTableBlock", INDEX_HTML)
        self.assertIn("function renderInlineMarkdown", INDEX_HTML)
        self.assertIn("function renderMath", INDEX_HTML)
        self.assertIn("renderMath", INDEX_HTML)
        self.assertIn("katex", INDEX_HTML)
        self.assertIn("headingMatch = line.match", INDEX_HTML)
        self.assertIn("<strong>", INDEX_HTML)
        self.assertIn('line.startsWith("```")', INDEX_HTML)
        self.assertIn('id="downloadLink"', INDEX_HTML)
        self.assertIn('class="quality-badge', INDEX_HTML)
        self.assertIn("job.export_url", INDEX_HTML)
        self.assertIn("jobId", INDEX_HTML)
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

    def test_options_endpoint_returns_public_scenarios_without_parser_profiles(self):
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
        self.assertEqual(payload["default_service_mode"], "single_courseware")
        self.assertEqual(
            [
                (item["id"], item["enabled"])
                for item in payload["service_modes"]
            ],
            [
                ("single_courseware", True),
                ("course_outline", True),
                ("multi_courseware", True),
            ],
        )
        self.assertNotIn("default_parser_profile_id", payload)
        self.assertNotIn("parser_profiles", payload)

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
            (root / "soul.md").write_text("soul", encoding="utf-8")
            (root / "mnemonics.md").write_text("mnemonics", encoding="utf-8")
            service = AdminSettingsService(root / "data" / "settings")
            payload = service.load_all()
            payload["model_catalog"]["services"]["llm"]["profiles"][0]["api_key"] = "sk-secret"
            payload["runtime"]["parser"]["mineru"]["api_token"] = "mineru-key"
            service.save_all(payload)
            settings = RuntimeSettings.from_env(root)
            client = TestClient(create_app(settings=settings))

            loaded = client.get("/api/admin/settings").json()
            loaded["runtime"]["rag"]["chunk_max_chars"] = 900
            loaded["runtime"]["jobs"]["max_pdf_bytes"] = 64
            loaded["content_pack"]["packs"][0]["name"] = "Medicine Pilot"
            saved = client.put("/api/admin/settings", json=loaded)
            self.register_user(client)
            rejected = client.post(
                "/api/generate",
                files={
                    "pdf": (
                        "lecture.pdf",
                        self.make_pdf_bytes(),
                        "application/pdf",
                    )
                },
            )
            restored = service.load_all()

        self.assertEqual(loaded["model_catalog"]["services"]["llm"]["profiles"][0]["api_key"], "")
        self.assertTrue(loaded["model_catalog"]["services"]["llm"]["profiles"][0]["api_key_set"])
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(rejected.status_code, 413, rejected.json())
        self.assertEqual(rejected.json()["detail"]["code"], "pdf_too_large")
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
        serialized = json.dumps(body)
        for private_value in (
            root,
            settings.jobs_root,
            settings.soul_path,
            settings.mnemonics_path,
            settings.api_key_path,
        ):
            self.assertNotIn(str(private_value), serialized)
        self.assertNotIn(root.name, serialized)
        self.assertNotIn("missing-soul.md", serialized)
        self.assertNotIn("missing-mnemonics.md", serialized)
        self.assertNotIn("missing-api-key.txt", serialized)

    def test_readiness_endpoint_runs_provider_probe_only_when_requested(self):
        calls = []
        private_error = r"D:\private\provider-token.txt connection refused"

        def probe(api_key: str, chat_model: str, embed_model: str):
            calls.append((api_key, chat_model, embed_model))
            raise RuntimeError(private_error)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings, provider_probe=probe))

            plain = client.get("/api/readiness").json()
            probed = client.get("/api/readiness?probe_provider=true").json()

        self.assertEqual(calls, [("key", "chat-model", "embed-model")])
        self.assertNotIn("provider_connectivity", {check["name"] for check in plain["checks"]})
        checks = {check["name"]: check for check in probed["checks"]}
        self.assertEqual(checks["provider_connectivity"]["status"], "error")
        self.assertNotIn(private_error, json.dumps(probed))
        self.assertNotIn("provider-token.txt", json.dumps(probed))

    def test_database_unavailable_degrades_readiness_and_blocks_admission(self):
        private_error = (
            r"postgresql://private-user:secret@db.internal/jstudy "
            r"D:\private\jobs"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)
            repository = client.app.state.job_repository
            with patch.object(repository, "check_connection", return_value=False):
                health = client.get("/api/health")
                readiness = client.get("/api/readiness")
                generated = client.post(
                    "/api/generate",
                    files={
                        "pdf": (
                            "lecture.pdf",
                            self.make_pdf_bytes(),
                            "application/pdf",
                        )
                    },
                )

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        self.assertEqual(readiness.status_code, 200)
        self.assertEqual(readiness.json()["status"], "degraded")
        checks = {item["name"]: item for item in readiness.json()["checks"]}
        self.assertEqual(
            checks["database"],
            {
                "name": "database",
                "status": "error",
                "detail": "database unavailable",
            },
        )
        self.assertEqual(generated.status_code, 503)
        self.assertEqual(
            {
                item["name"]: item
                for item in generated.json()["detail"]["checks"]
            }["database"]["detail"],
            "database unavailable",
        )
        serialized = json.dumps(
            [readiness.json(), generated.json()],
            ensure_ascii=False,
        )
        self.assertNotIn(private_error, serialized)
        self.assertNotIn("private-user", serialized)
        self.assertNotIn("secret", serialized)
        self.assertNotIn("db.internal", serialized)
        self.assertNotIn(r"D:\private\jobs", serialized)

    def test_missing_mineru_degrades_readiness_and_blocks_admission_without_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = replace(self.ready_settings(root), mineru_api_token="")
            client = TestClient(create_app(settings=settings))
            self.register_user(client)

            readiness = client.get("/api/readiness")
            generated = client.post(
                "/api/generate",
                files={
                    "pdf": (
                        "lecture.pdf",
                        self.make_pdf_bytes(),
                        "application/pdf",
                    )
                },
            )

            repository = client.app.state.job_repository
            self.assertEqual(repository.count_queued(), 0)
            self.assertFalse(
                any(
                    path.is_dir() and path.name != "settings"
                    for path in settings.jobs_root.iterdir()
                )
            )

        self.assertEqual(readiness.status_code, 200)
        self.assertEqual(readiness.json()["status"], "degraded")
        checks = {
            item["name"]: item
            for item in readiness.json()["checks"]
        }
        self.assertEqual(
            checks["mineru"],
            {
                "name": "mineru",
                "status": "error",
                "detail": "unavailable",
            },
        )
        self.assertEqual(generated.status_code, 503)
        self.assertNotIn("token", json.dumps(generated.json()).lower())

    def test_generate_uses_hot_reloaded_mineru_readiness_without_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initial = replace(self.ready_settings(root), mineru_api_token="")
            current = [initial]
            repository, service = self.durable_dependencies(initial)
            client = TestClient(
                create_app(
                    settings=initial,
                    job_repository=repository,
                    job_service=service,
                    settings_provider=lambda: current[0],
                )
            )
            self.register_user(client)

            rejected = client.post(
                "/api/generate",
                files={
                    "pdf": (
                        "lecture.pdf",
                        self.make_pdf_bytes(),
                        "application/pdf",
                    )
                },
            )
            current[0] = replace(
                initial,
                mineru_api_token="updated-mineru-token",
            )
            accepted = client.post(
                "/api/generate",
                files={
                    "pdf": (
                        "lecture.pdf",
                        self.make_pdf_bytes(),
                        "application/pdf",
                    )
                },
            )
            queued_count = repository.count_queued()

        self.assertEqual(rejected.status_code, 503)
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["status"], "queued")
        self.assertEqual(queued_count, 1)

    def test_generate_rejects_unready_runtime_config(self):
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
        serialized = json.dumps(body)
        for private_value in (
            root,
            settings.jobs_root,
            settings.soul_path,
            settings.mnemonics_path,
            settings.api_key_path,
        ):
            self.assertNotIn(str(private_value), serialized)
        self.assertNotIn(root.name, serialized)
        self.assertNotIn("missing-soul.md", serialized)
        self.assertNotIn("missing-mnemonics.md", serialized)
        self.assertNotIn("missing-api-key.txt", serialized)

    def test_generate_requires_authenticated_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))

            response = client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )

        self.assertEqual(response.status_code, 401)

    def test_generate_rejects_unsupported_service_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)

            response = client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
                data={"service_mode": "batch_courseware"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"]["code"],
            "unsupported_service_mode",
        )

    def test_generate_rejects_mixed_or_forbidden_multipart_families(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)
            pdf_bytes = self.make_pdf_bytes()
            cases = (
                (
                    "single-mixed-pdfs",
                    "single_courseware",
                    [
                        ("pdf", ("one.pdf", pdf_bytes, "application/pdf")),
                        ("pdfs", ("two.pdf", pdf_bytes, "application/pdf")),
                    ],
                    "invalid_pdf",
                ),
                (
                    "single-outline",
                    "single_courseware",
                    [
                        ("pdf", ("one.pdf", pdf_bytes, "application/pdf")),
                        ("outline", ("outline.md", b"# Outline", "text/markdown")),
                    ],
                    "invalid_outline",
                ),
                (
                    "outline-mixed-pdf",
                    "course_outline",
                    [
                        ("pdf", ("one.pdf", pdf_bytes, "application/pdf")),
                        ("pdfs", ("two.pdf", pdf_bytes, "application/pdf")),
                        ("outline", ("outline.md", b"# Outline", "text/markdown")),
                    ],
                    "invalid_pdf",
                ),
                (
                    "multi-mixed-pdf",
                    "multi_courseware",
                    [
                        ("pdf", ("one.pdf", pdf_bytes, "application/pdf")),
                        ("pdfs", ("two.pdf", pdf_bytes, "application/pdf")),
                        ("pdfs", ("three.pdf", pdf_bytes, "application/pdf")),
                    ],
                    "invalid_pdf",
                ),
                (
                    "multi-outline",
                    "multi_courseware",
                    [
                        ("pdfs", ("one.pdf", pdf_bytes, "application/pdf")),
                        ("pdfs", ("two.pdf", pdf_bytes, "application/pdf")),
                        ("outline", ("outline.md", b"# Outline", "text/markdown")),
                    ],
                    "invalid_outline",
                ),
                (
                    "multi-one-pdf",
                    "multi_courseware",
                    [("pdfs", ("one.pdf", pdf_bytes, "application/pdf"))],
                    "invalid_pdf",
                ),
            )
            responses = []
            for name, service_mode, files, expected_code in cases:
                with self.subTest(name=name):
                    response = client.post(
                        "/api/generate",
                        files=files,
                        data={"service_mode": service_mode},
                        headers={"Idempotency-Key": name},
                    )
                    responses.append((response, expected_code))

            repository = client.app.state.job_repository
            queued_count = repository.count_queued()
            input_directories = list(settings.jobs_root.glob("*/inputs"))
            idempotency_rows = [
                repository.find_by_owner_idempotency_key(
                    client.get("/api/auth/me").json()["id"],
                    name,
                )
                for name, *_ in cases
            ]

        for response, expected_code in responses:
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["detail"]["code"], expected_code)
        self.assertEqual(queued_count, 0)
        self.assertEqual(input_directories, [])
        self.assertEqual(idempotency_rows, [None] * len(cases))

    def test_multi_courseware_accepts_repeated_pdfs_in_upload_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)

            response = client.post(
                "/api/generate",
                files=[
                    ("pdfs", ("second.pdf", self.make_pdf_bytes(), "application/pdf")),
                    ("pdfs", ("first.pdf", self.make_pdf_bytes(), "application/pdf")),
                ],
                data={"service_mode": "multi_courseware"},
            )
            job_id = response.json().get("job_id")
            repository = client.app.state.job_repository
            sources = repository.list_sources(job_id) if job_id else []

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [
                (source.source_id, source.original_filename, source.display_order)
                for source in sources
            ],
            [
                ("S001", "second.pdf", 1),
                ("S002", "first.pdf", 2),
            ],
        )

    def test_course_outline_requires_outline_and_pdfs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)

            missing_outline = client.post(
                "/api/generate",
                files=[("pdfs", ("lecture.pdf", self.make_pdf_bytes(), "application/pdf"))],
                data={"service_mode": "course_outline"},
            )
            missing_pdfs = client.post(
                "/api/generate",
                files={"outline": ("outline.md", b"# Unit One\n", "text/markdown")},
                data={"service_mode": "course_outline"},
            )

        self.assertEqual(missing_outline.status_code, 400)
        self.assertEqual(missing_pdfs.status_code, 400)
        self.assertEqual(missing_outline.json()["detail"]["code"], "invalid_outline")
        self.assertEqual(missing_pdfs.json()["detail"]["code"], "invalid_pdf")

    def test_course_outline_accepts_repeated_pdfs_and_exposes_source_preview_contracts(self):
        captured = {}

        def fake_runner(**kwargs):
            captured.update(kwargs)
            output_dir = kwargs["output_dir"]
            output_prefix = kwargs["output_prefix"]
            source_files = kwargs.get("source_files") or []
            output_dir.mkdir(parents=True, exist_ok=True)
            markdown = output_dir / f"{output_prefix}-output.md"
            evidence = output_dir / f"{output_prefix}-evidence.json"
            evidence_links = output_dir / f"{output_prefix}-evidence_links.json"
            quality = output_dir / f"{output_prefix}-quality.json"
            trace = output_dir / f"{output_prefix}-retrieval_trace.json"
            package = output_dir / f"{output_prefix}-package.json"
            markdown.write_text("Fact <!-- evidence: E001 -->\n", encoding="utf-8")
            evidence.write_text(
                json.dumps(
                    [
                        {
                            "id": "E001",
                            "source_id": "S002",
                            "source_file": "lecture-02.pdf",
                            "page": 1,
                            "chunk_id": "S002-C001",
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
                            "target": {"source_id": "S002", "source_file": "lecture-02.pdf", "page": 1},
                        }
                    ]
                ),
                encoding="utf-8",
            )
            quality.write_text(json.dumps({"status": "pass"}), encoding="utf-8")
            trace.write_text(json.dumps({"selected_chunks": []}), encoding="utf-8")
            package.write_text(
                json.dumps(
                    {
                        "type": "material_package",
                        "service_mode": "course_outline",
                        "source_files": source_files,
                        "sections": [
                            {
                                "id": "section-001",
                                "title": "Unit One",
                                "order": 1,
                                "status": "generated",
                                "quality": {"evidence_count": 1},
                                "artifact_filenames": {
                                    "markdown": markdown.name,
                                },
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

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)
            response = client.post(
                "/api/generate",
                files=[
                    (
                        "outline",
                        ("课程大纲.md", b"# Unit One\n", "text/markdown"),
                    ),
                    ("pdfs", ("lecture-01.pdf", self.make_pdf_bytes(), "application/pdf")),
                    ("pdfs", ("lecture-02.pdf", self.make_pdf_bytes(), "application/pdf")),
                ],
                data={"service_mode": "course_outline", "mode": "metadata-only"},
            )
            job_id = response.json()["job_id"]
            self.run_next_job(client, settings, fake_runner)
            status = client.get(f"/api/jobs/{job_id}").json()
            sources = client.get(f"/api/jobs/{job_id}/pdfs").json()
            manifest_response = client.get(f"/api/jobs/{job_id}/manifest")
            learning_map_response = client.get(f"/api/jobs/{job_id}/learning-map")
            coverage_response = client.get(f"/api/jobs/{job_id}/coverage")
            second_info_response = client.get(f"/api/jobs/{job_id}/pdfs/S002/pdf-info")
            second_page = client.get(f"/api/jobs/{job_id}/pdfs/S002/pdf-page/1.png")
            record = client.app.state.job_repository.get(job_id)
            sections = client.app.state.job_repository.list_sections(job_id)
            manifest_artifact = next(
                artifact
                for artifact in client.app.state.job_repository.list_artifacts(
                    job_id
                )
                if artifact.kind is ArtifactKind.MANIFEST
            )
            manifest_path = (
                settings.jobs_root / manifest_artifact.relative_path
            )
            tampered = json.loads(manifest_path.read_text(encoding="utf-8"))
            tampered["outline"]["sections"][0]["title"] = "tampered-title"
            manifest_path.write_text(
                json.dumps(tampered),
                encoding="utf-8",
            )
            tampered_responses = [
                client.get(f"/api/jobs/{job_id}/manifest"),
                client.get(f"/api/jobs/{job_id}/learning-map"),
                client.get(f"/api/jobs/{job_id}/coverage"),
            ]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(record.service_mode, "course_outline")
        self.assertEqual(captured["service_mode"], "course_outline")
        self.assertEqual([path.name for path in captured["pdf_paths"]], ["S001.pdf", "S002.pdf"])
        self.assertEqual(status["service_mode"], "course_outline")
        self.assertEqual([item["source_id"] for item in status["source_files"]], ["S001", "S002"])
        self.assertEqual(
            [
                (
                    item["source_id"],
                    item["original_filename"],
                    item["display_title"],
                    item["display_order"],
                )
                for item in status["source_files"]
            ],
            [
                ("S001", "lecture-01.pdf", "lecture-01", 1),
                ("S002", "lecture-02.pdf", "lecture-02", 2),
            ],
        )
        self.assertIn("pdfs_url", status)
        self.assertEqual(status["manifest_url"], f"/api/jobs/{job_id}/manifest")
        self.assertEqual(
            status["learning_map_url"],
            f"/api/jobs/{job_id}/learning-map",
        )
        self.assertEqual(status["coverage_url"], f"/api/jobs/{job_id}/coverage")
        self.assertEqual([item["source_id"] for item in sources["source_files"]], ["S001", "S002"])
        self.assertEqual(manifest_response.status_code, 200)
        self.assertEqual(
            manifest_response.json()["schema_version"],
            "courseware-manifest.v1",
        )
        self.assertEqual(
            manifest_response.json()["outline"]["original_filename"],
            "课程大纲.md",
        )
        self.assertEqual(learning_map_response.status_code, 200)
        self.assertEqual(
            learning_map_response.json()["schema_version"],
            "learning-map.v1",
        )
        self.assertEqual(coverage_response.status_code, 200)
        self.assertEqual(
            coverage_response.json()["schema_version"],
            "coverage-ledger.v1",
        )
        self.assertEqual(
            [item.status_code for item in tampered_responses],
            [500, 500, 500],
        )
        self.assertEqual(
            {
                manifest_response.headers["cache-control"],
                learning_map_response.headers["cache-control"],
                coverage_response.headers["cache-control"],
            },
            {"private, max-age=0, must-revalidate"},
        )
        self.assertEqual(second_info_response.status_code, 200)
        self.assertEqual(second_info_response.json()["source_id"], "S002")
        self.assertEqual(second_page.headers["content-type"], "image/png")
        self.assertTrue(second_page.content.startswith(b"\x89PNG"))
        self.assertEqual(
            [
                (
                    section.section_id,
                    section.position,
                    section.status,
                    json.loads(section.quality_json),
                )
                for section in sections
            ],
            [("section-001", 1, "generated", {"evidence_count": 1})],
        )

    def test_coverage_endpoint_rejects_learning_unit_identity_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)
            generated = client.post(
                "/api/generate",
                files={
                    "pdf": (
                        "lecture.pdf",
                        self.make_pdf_bytes(),
                        "application/pdf",
                    )
                },
            )
            job_id = generated.json()["job_id"]
            self.run_next_job(client, settings, self.v2_runner)
            repository = client.app.state.job_repository
            learning_artifact = next(
                item
                for item in repository.list_artifacts(job_id)
                if item.kind.value == "learning_map"
            )
            learning_path = settings.jobs_root / learning_artifact.relative_path
            learning_payload = json.loads(
                learning_path.read_text(encoding="utf-8")
            )
            learning_payload["units"][0]["order"] = 2
            learning_path.write_text(
                json.dumps(learning_payload),
                encoding="utf-8",
            )
            invalid_map = client.get(f"/api/jobs/{job_id}/learning-map")
            learning_payload["units"][0]["order"] = 1
            learning_payload["units"][0]["page_end"] = 999
            learning_path.write_text(
                json.dumps(learning_payload),
                encoding="utf-8",
            )
            invalid_span = client.get(f"/api/jobs/{job_id}/learning-map")
            learning_payload["units"][0]["page_end"] = 1
            learning_path.write_text(
                json.dumps(learning_payload),
                encoding="utf-8",
            )
            coverage_artifact = next(
                item
                for item in repository.list_artifacts(job_id)
                if item.kind.value == "coverage"
            )
            coverage_path = settings.jobs_root / coverage_artifact.relative_path
            payload = json.loads(coverage_path.read_text(encoding="utf-8"))
            payload["entries"][0]["learning_unit_id"] = "unit-999"
            coverage_path.write_text(
                json.dumps(payload),
                encoding="utf-8",
            )

            response = client.get(f"/api/jobs/{job_id}/coverage")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "Coverage ledger is invalid")
        self.assertEqual(invalid_map.status_code, 500)
        self.assertEqual(
            invalid_map.json()["detail"],
            "Learning map is invalid",
        )
        self.assertEqual(invalid_span.status_code, 500)
        self.assertEqual(
            invalid_span.json()["detail"],
            "Learning map is invalid",
        )

    def test_sync_endpoints_reject_map_and_coverage_hash_mismatches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)
            generated = client.post(
                "/api/generate",
                files={
                    "pdf": (
                        "lecture.pdf",
                        self.make_pdf_bytes(),
                        "application/pdf",
                    )
                },
            )
            job_id = generated.json()["job_id"]
            self.run_next_job(client, settings, self.v2_runner)
            repository = client.app.state.job_repository
            artifacts = {
                item.kind: item
                for item in repository.list_artifacts(job_id)
            }
            learning_path = (
                settings.jobs_root
                / artifacts[ArtifactKind.LEARNING_MAP].relative_path
            )
            coverage_path = (
                settings.jobs_root
                / artifacts[ArtifactKind.COVERAGE].relative_path
            )
            original_learning = learning_path.read_bytes()
            learning_payload = json.loads(original_learning)
            learning_payload["units"][0][
                "material_section_id"
            ] = "tampered-section"
            learning_path.write_text(
                json.dumps(learning_payload),
                encoding="utf-8",
            )
            map_tamper_responses = [
                client.get(f"/api/jobs/{job_id}/manifest"),
                client.get(f"/api/jobs/{job_id}/learning-map"),
                client.get(f"/api/jobs/{job_id}/coverage"),
            ]

            learning_path.write_bytes(original_learning)
            coverage_payload = json.loads(
                coverage_path.read_text(encoding="utf-8")
            )
            coverage_payload["metrics"]["remote_reference_ratio"] = 0.5
            coverage_path.write_text(
                json.dumps(coverage_payload),
                encoding="utf-8",
            )
            coverage_tamper_responses = [
                client.get(f"/api/jobs/{job_id}/manifest"),
                client.get(f"/api/jobs/{job_id}/learning-map"),
                client.get(f"/api/jobs/{job_id}/coverage"),
            ]

        self.assertEqual(
            [response.status_code for response in map_tamper_responses],
            [500, 500, 500],
        )
        self.assertEqual(
            [response.status_code for response in coverage_tamper_responses],
            [500, 500, 500],
        )

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
            generation_mode="",
        ):
            captured.update(
                {
                    "soul_path": soul_path,
                    "mnemonics_path": mnemonics_path,
                    "api_key_path": api_key_path,
                    "chat_model": chat_model,
                    "embed_model": embed_model,
                    "generation_mode": generation_mode,
                }
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            markdown = output_dir / f"{output_prefix}-output.md"
            evidence = output_dir / f"{output_prefix}-evidence.json"
            evidence_links = output_dir / f"{output_prefix}-evidence_links.json"
            quality = output_dir / f"{output_prefix}-quality.json"
            trace = output_dir / f"{output_prefix}-retrieval_trace.json"
            package = output_dir / f"{output_prefix}-package.json"
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
                                "artifact_urls": {
                                    "markdown": markdown.name,
                                },
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

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)
            response = client.post(
                "/api/generate",
                files={
                    "pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf"),
                },
                data={"mode": "exam-quick"},
            )

            self.assertEqual(response.status_code, 200)
            job_id = response.json()["job_id"]
            self.run_next_job(client, settings, fake_runner)
            status_response = client.get(f"/api/jobs/{job_id}")
            status = status_response.json()
            output_response = client.get(f"/api/jobs/{job_id}/output")
            output = output_response.json()
            evidence_response = client.get(f"/api/jobs/{job_id}/evidence")
            evidence = evidence_response.json()
            trace_response = client.get(f"/api/jobs/{job_id}/trace")
            trace = trace_response.json()
            package_response = client.get(f"/api/jobs/{job_id}/package")
            package = package_response.json()
            export_response = client.get(f"/api/jobs/{job_id}/export")
            pdf_response = client.get(f"/api/jobs/{job_id}/pdf")
            pdf_info_response = client.get(f"/api/jobs/{job_id}/pdf-info")
            pdf_info = pdf_info_response.json()
            page_png = client.get(f"/api/jobs/{job_id}/pdf-page/2.png")
            record = client.app.state.job_repository.get(job_id)
            source = client.app.state.job_repository.list_sources(job_id)[0]
            sections = client.app.state.job_repository.list_sections(job_id)

        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(status_response.headers["cache-control"], "no-store")
        self.assertEqual(output_response.headers["cache-control"], "private, max-age=0, must-revalidate")
        self.assertEqual(evidence_response.headers["cache-control"], "private, max-age=0, must-revalidate")
        self.assertEqual(trace_response.headers["cache-control"], "private, max-age=0, must-revalidate")
        self.assertEqual(package_response.headers["cache-control"], "private, max-age=0, must-revalidate")
        self.assertEqual(export_response.headers["cache-control"], "private, max-age=0, must-revalidate")
        self.assertEqual(pdf_response.headers["cache-control"], "private, max-age=0, must-revalidate")
        self.assertEqual(pdf_info_response.headers["cache-control"], "private, max-age=0, must-revalidate")
        self.assertEqual(page_png.headers["cache-control"], "private, max-age=0, must-revalidate")
        self.assertEqual(status["status"], "completed")
        self.assertEqual(record.state, JobState.COMPLETED)
        self.assertEqual(source.original_filename, "lecture.pdf")
        self.assertEqual(captured["soul_path"], settings.soul_path)
        self.assertEqual(captured["mnemonics_path"], settings.mnemonics_path)
        self.assertEqual(captured["api_key_path"], settings.api_key_path)
        self.assertEqual(captured["chat_model"], "chat-model")
        self.assertEqual(captured["embed_model"], "embed-model")
        self.assertEqual(captured["generation_mode"], "exam-quick")
        self.assertEqual(record.generation_mode, "exam-quick")
        self.assertEqual(status["quality"]["status"], "pass")
        self.assertIn("evidence_links_url", status)
        self.assertIn("trace_url", status)
        self.assertIn("package_url", status)
        self.assertIn("export_url", status)
        self.assertIn("Fact", output["markdown"])
        self.assertEqual(evidence["evidence"][0]["id"], "E001")
        self.assertEqual(evidence["evidence_links"][0]["target"]["page"], 2)
        self.assertEqual(trace["selected_chunks"][0]["id"], "C001")
        self.assertEqual(trace["query_traces"][0]["query"]["id"], "sample")
        self.assertEqual(package["type"], "material_package")
        self.assertEqual(
            [
                (
                    section.section_id,
                    section.position,
                    section.status,
                    section.artifact_filename,
                )
                for section in sections
            ],
            [("full-material", 1, "generated", "result-output.md")],
        )
        self.assertEqual(export_response.headers["content-type"], "text/markdown; charset=utf-8")
        self.assertIn('attachment; filename="jstudy-', export_response.headers["content-disposition"])
        self.assertIn(b"Fact", export_response.content)
        self.assertEqual(pdf_info["page_count"], 2)
        self.assertEqual(page_png.headers["content-type"], "image/png")
        self.assertTrue(page_png.content.startswith(b"\x89PNG"))

    def test_package_endpoint_validates_v2_and_publishes_openapi_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)
            response = client.post(
                "/api/generate",
                files={
                    "pdf": (
                        "lecture.pdf",
                        self.make_pdf_bytes(),
                        "application/pdf",
                    )
                },
            )
            self.assertEqual(response.status_code, 200)
            job_id = response.json()["job_id"]
            self.run_next_job(client, settings, self.v2_runner)

            package_response = client.get(f"/api/jobs/{job_id}/package")
            package = package_response.json()
            openapi = client.get("/openapi.json").json()

            self.assertEqual(package_response.status_code, 200)
            self.assertEqual(
                package["schema_version"],
                "material-package.v2",
            )
            self.assertEqual(package["package_id"], job_id)
            schemas = openapi["components"]["schemas"]
            for name in (
                "MaterialPackageV2",
                "MaterialSection",
                "ParagraphBlock",
                "CitationRun",
            ):
                self.assertIn(name, schemas)

            package_path = (
                settings.jobs_root
                / job_id
                / "attempts"
                / "1"
                / "output"
                / "result-package.json"
            )
            evidence_path = package_path.with_name("result-evidence.json")
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            cases = {
                "unexpected-field": lambda candidate, items: candidate.update(
                    {"unexpected": "field"}
                ),
                "unknown-source": lambda candidate, items: candidate.update(
                    {"source_ids": ["S999"]}
                ),
                "package-id-mismatch": lambda candidate, items: candidate.update(
                    {"package_id": "another-job"}
                ),
                "service-mode-mismatch": lambda candidate, items: candidate.update(
                    {"service_mode": "course_outline"}
                ),
                "evidence-source-mismatch": lambda candidate, items: items[
                    0
                ].update({"source_id": "S999"}),
                "duplicate-evidence": lambda candidate, items: items.append(
                    dict(items[0])
                ),
                "quality-mismatch": lambda candidate, items: candidate[
                    "sections"
                ][0]["quality"].update({"evidence_count": 999}),
            }
            for name, mutate in cases.items():
                with self.subTest(name=name):
                    candidate = copy.deepcopy(package)
                    items = copy.deepcopy(evidence)
                    mutate(candidate, items)
                    package_path.write_text(
                        json.dumps(candidate),
                        encoding="utf-8",
                    )
                    evidence_path.write_text(
                        json.dumps(items),
                        encoding="utf-8",
                    )
                    invalid_response = client.get(
                        f"/api/jobs/{job_id}/package"
                    )
                    self.assertEqual(invalid_response.status_code, 500)
                    self.assertEqual(
                        invalid_response.json()["detail"],
                        "Material package is invalid",
                    )

    def test_package_endpoint_rejects_oversized_legacy_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)
            response = client.post(
                "/api/generate",
                files={
                    "pdf": (
                        "lecture.pdf",
                        self.make_pdf_bytes(),
                        "application/pdf",
                    )
                },
            )
            job_id = response.json()["job_id"]
            self.run_next_job(client, settings, self.v2_runner)
            package_path = (
                settings.jobs_root
                / job_id
                / "attempts"
                / "1"
                / "output"
                / "result-package.json"
            )
            section = {
                "id": "full-material",
                "title": "完整资料",
                "order": 1,
                "artifact_urls": {"markdown": "result-output.md"},
            }
            legacy = {
                "type": "material_package",
                "service_mode": "single_courseware",
                "sections": [section],
            }
            cases = {
                "too-many-sections": {
                    **legacy,
                    "sections": [
                        {
                            **section,
                            "id": f"section-{index:03d}",
                            "order": index,
                        }
                        for index in range(1, 122)
                    ],
                },
                "oversized-field": {
                    **legacy,
                    "sections": [{**section, "title": "x" * 501}],
                },
            }
            for name, candidate in cases.items():
                with self.subTest(name=name):
                    package_path.write_text(
                        json.dumps(candidate),
                        encoding="utf-8",
                    )
                    invalid_response = client.get(
                        f"/api/jobs/{job_id}/package"
                    )
                    self.assertEqual(invalid_response.status_code, 500)
                    self.assertEqual(
                        invalid_response.json()["detail"],
                        "Material package is invalid",
                    )

            package_path.write_bytes(b" " * (2 * 1024 * 1024 + 1))
            oversized_response = client.get(f"/api/jobs/{job_id}/package")
            self.assertEqual(oversized_response.status_code, 500)
            self.assertEqual(
                oversized_response.json()["detail"],
                "Material package is invalid",
            )

    def test_package_endpoint_normalizes_deep_json_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)
            response = client.post(
                "/api/generate",
                files={
                    "pdf": (
                        "lecture.pdf",
                        self.make_pdf_bytes(),
                        "application/pdf",
                    )
                },
            )
            job_id = response.json()["job_id"]
            self.run_next_job(client, settings, self.v2_runner)
            package_path = (
                settings.jobs_root
                / job_id
                / "attempts"
                / "1"
                / "output"
                / "result-package.json"
            )
            package_path.write_text(
                '{"nested":' * 1100 + "null" + "}" * 1100,
                encoding="utf-8",
            )

            invalid_response = client.get(f"/api/jobs/{job_id}/package")

            self.assertEqual(invalid_response.status_code, 500)
            self.assertEqual(
                invalid_response.json()["detail"],
                "Material package is invalid",
            )

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
            settings = self.ready_settings(root)
            first_client = TestClient(create_app(settings=settings))
            first_user = self.register_user(first_client, email="one@example.com", invite_code="ONE")
            response = first_client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )
            job_id = response.json()["job_id"]
            record = first_client.app.state.job_repository.get(job_id)

            second_client = TestClient(create_app(settings=settings))
            self.register_user(second_client, email="two@example.com", invite_code="TWO")
            blocked = second_client.get(f"/api/jobs/{job_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(record.owner_user_id, first_user["id"])
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
            payload["runtime"]["parser"]["mineru"]["api_token"] = "mineru-key"
            service.save_all(payload)
            settings = RuntimeSettings.from_env(root)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)

            response = client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )
            self.run_next_job(client, settings, fake_runner)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["api_key"], "catalog-key")
        self.assertEqual(captured["chat_base_url"], "https://chat.example/v1")
        self.assertEqual(captured["embed_base_url"], "https://embed.example/v1")
        self.assertEqual(captured["chat_model"], "catalog-chat")
        self.assertEqual(captured["embed_model"], "catalog-embed")
        self.assertEqual(captured["rag_config"].chunk_max_chars, 888)
        self.assertEqual(captured["rag_config"].per_query_limit, 4)

    def test_generate_uses_default_scenario_and_worker_owned_mineru_parser(self):
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
            payload["runtime"]["parser"]["mineru"]["api_token"] = "mineru-key"
            service.save_all(payload)
            settings = RuntimeSettings.from_env(root, jobs_root=root / "jobs")
            settings.soul_path.write_text("soul", encoding="utf-8")
            settings.mnemonics_path.write_text("mnemonics", encoding="utf-8")
            settings.api_key_path.write_text("key", encoding="utf-8")
            client = TestClient(create_app(settings=settings))
            self.register_user(client)

            response = client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )
            self.run_next_job(client, settings, fake_runner)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["parser_backend"], "mineru")
        self.assertEqual(captured["routing_metadata"]["scenario"]["resolved_scenario_id"], "medicine-default")
        self.assertEqual(captured["routing_metadata"]["parser_profile"]["resolved_parser_profile_id"], "mineru")

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
            payload["runtime"]["parser"]["mineru"]["api_token"] = "mineru-key"
            service.save_all(payload)
            settings = RuntimeSettings.from_env(root, jobs_root=root / "jobs")
            settings.soul_path.write_text("medicine soul", encoding="utf-8")
            settings.mnemonics_path.write_text("mnemonics", encoding="utf-8")
            general_soul = root / "souls" / "general.md"
            general_soul.parent.mkdir(parents=True, exist_ok=True)
            general_soul.write_text("general soul", encoding="utf-8")
            settings.api_key_path.write_text("key", encoding="utf-8")
            client = TestClient(create_app(settings=settings))
            self.register_user(client)

            response = client.post(
                "/api/generate",
                data={"scenario_id": "general-default"},
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )
            self.run_next_job(client, settings, fake_runner)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["soul_path"], general_soul)
        self.assertEqual(captured["routing_metadata"]["scenario"]["resolved_scenario_id"], "general-default")
        self.assertEqual(captured["routing_metadata"]["scenario"]["soul_profile_id"], "general-blank")

    def test_generate_accepts_legacy_quality_parser_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = AdminSettingsService(root / "data" / "settings")
            payload = service.load_all()
            quality = next(item for item in payload["runtime"]["parser_profiles"]["profiles"] if item["id"] == "quality")
            quality["enabled"] = True
            payload["runtime"]["parser"]["mineru"]["api_token"] = "mineru-key"
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

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "queued")

    def test_generate_rejects_unknown_parser_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)

            response = client.post(
                "/api/generate",
                data={"parser_profile_id": "custom-parser"},
                files={
                    "pdf": (
                        "lecture.pdf",
                        self.make_pdf_bytes(),
                        "application/pdf",
                    )
                },
            )

        self.assertEqual(response.status_code, 400)

    def test_generate_accepts_public_mineru_profile_from_environment_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "soul.md").write_text("soul", encoding="utf-8")
            (root / "mnemonics.md").write_text("mnemonics", encoding="utf-8")
            service = AdminSettingsService(root / "data" / "settings")
            payload = service.load_all()
            profile = payload["model_catalog"]["services"]["llm"]["profiles"][0]
            profile["api_key"] = "configured-test-key"
            quality = next(
                item
                for item in payload["runtime"]["parser_profiles"]["profiles"]
                if item["id"] == "quality"
            )
            quality["enabled"] = True
            quality["visible_to_users"] = True
            quality["requires_admin"] = False
            payload["runtime"]["parser"]["mineru"]["api_token"] = ""
            service.save_all(payload)

            with patch.dict(
                os.environ,
                {
                    "MINERU_API_TOKEN": "environment-mineru-token",
                },
                clear=True,
            ):
                settings = RuntimeSettings.from_env(root)
                client = TestClient(create_app(settings=settings))
                self.register_user(client)
                response = client.post(
                    "/api/generate",
                    data={"parser_profile_id": "quality"},
                    files={
                        "pdf": (
                            "lecture.pdf",
                            self.make_pdf_bytes(),
                            "application/pdf",
                        )
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "queued")

    def test_durable_repository_persists_completed_job_status_between_app_instances(self):
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
                                "artifact_urls": {
                                    "markdown": markdown.name,
                                },
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

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            first_client = TestClient(create_app(settings=settings))
            self.register_user(first_client)
            response = first_client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )
            job_id = response.json()["job_id"]
            self.run_next_job(first_client, settings, fake_runner)

            second_client = TestClient(create_app(settings=settings))
            self.login_user(second_client)
            restored = second_client.get(f"/api/jobs/{job_id}").json()

        self.assertEqual(restored["status"], "completed")
        self.assertEqual(restored["quality"]["status"], "pass")

    def test_failed_job_status_exposes_only_safe_worker_error(self):
        def failing_runner(**kwargs):
            raise TimeoutError("provider timeout")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)
            response = client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )
            job_id = response.json()["job_id"]
            self.run_next_job(client, settings, failing_runner)
            self.run_next_job(client, settings, failing_runner)

            status = client.get(f"/api/jobs/{job_id}").json()

        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["error_code"], "worker_error")
        self.assertEqual(status["error"], "The job could not be processed.")
        self.assertNotIn("provider timeout", json.dumps(status))

    def test_create_app_does_not_run_retention_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root, job_retention_hours=1)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)
            generated = client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )
            job_id = generated.json()["job_id"]

            restarted = TestClient(create_app(settings=settings))
            self.login_user(restarted)

            self.assertEqual(restarted.get(f"/api/jobs/{job_id}").status_code, 200)
            self.assertTrue((settings.jobs_root / job_id).is_dir())

    def test_queued_job_result_endpoints_return_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root)
            client = TestClient(create_app(settings=settings), raise_server_exceptions=False)
            self.register_user(client)
            generated = client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf")},
            )
            job_id = generated.json()["job_id"]

            output = client.get(f"/api/jobs/{job_id}/output")
            evidence = client.get(f"/api/jobs/{job_id}/evidence")
            evidence_links = client.get(f"/api/jobs/{job_id}/evidence-links")
            trace = client.get(f"/api/jobs/{job_id}/trace")
            package = client.get(f"/api/jobs/{job_id}/package")
            export = client.get(f"/api/jobs/{job_id}/export")

        self.assertEqual(output.status_code, 404)
        self.assertEqual(evidence.status_code, 404)
        self.assertEqual(evidence_links.status_code, 404)
        self.assertEqual(trace.status_code, 404)
        self.assertEqual(package.status_code, 404)
        self.assertEqual(export.status_code, 404)

    def test_generate_rejects_non_pdf_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root, max_pdf_bytes=1024)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)

            response = client.post(
                "/api/generate",
                files={"pdf": ("notes.txt", b"not a pdf", "text/plain")},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "invalid_pdf")

    def test_generate_rejects_pdf_above_configured_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self.ready_settings(root, max_pdf_bytes=5)
            client = TestClient(create_app(settings=settings))
            self.register_user(client)

            response = client.post(
                "/api/generate",
                files={"pdf": ("lecture.pdf", b"%PDF- too large", "application/pdf")},
            )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["detail"]["code"], "pdf_too_large")


if __name__ == "__main__":
    unittest.main()
