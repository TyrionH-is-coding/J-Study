import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from packages.core.jstudy_core.settings import RuntimeSettings
from packages.core.jstudy_core.admin_settings import AdminSettingsService


class SettingsTest(unittest.TestCase):
    def test_runtime_settings_loads_deployment_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {
                "JSTUDY_JOBS_DIR": str(root / "data" / "jobs"),
                "JSTUDY_SOUL_PATH": str(root / "config" / "soul.md"),
                "JSTUDY_MNEMONICS_PATH": str(root / "config" / "mnemonics.md"),
                "SILICONFLOW_API_KEY_FILE": str(root / "secrets" / "api-key.txt"),
                "SILICONFLOW_CHAT_MODEL": "chat-model",
                "SILICONFLOW_EMBED_MODEL": "embed-model",
                "JSTUDY_MAX_PDF_BYTES": "12345",
                "JSTUDY_JOB_RETENTION_HOURS": "12",
            }

            with patch.dict(os.environ, env, clear=False):
                settings = RuntimeSettings.from_env(root)

        self.assertEqual(settings.jobs_root, Path(env["JSTUDY_JOBS_DIR"]))
        self.assertEqual(settings.soul_path, Path(env["JSTUDY_SOUL_PATH"]))
        self.assertEqual(settings.mnemonics_path, Path(env["JSTUDY_MNEMONICS_PATH"]))
        self.assertEqual(settings.api_key_path, Path(env["SILICONFLOW_API_KEY_FILE"]))
        self.assertEqual(settings.chat_model, "chat-model")
        self.assertEqual(settings.embed_model, "embed-model")
        self.assertEqual(settings.max_pdf_bytes, 12345)
        self.assertEqual(settings.job_retention_hours, 12)

    def test_runtime_settings_keep_mvp_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.dict(os.environ, {}, clear=True):
                settings = RuntimeSettings.from_env(root)

        self.assertEqual(settings.jobs_root, root / "web_jobs")
        self.assertEqual(settings.soul_path, root / "soul.md")
        self.assertEqual(settings.mnemonics_path, root / "mnemonics.md")
        self.assertEqual(settings.api_key_path, root / "siliconflow api key.txt")
        self.assertEqual(settings.max_pdf_bytes, 50 * 1024 * 1024)
        self.assertEqual(settings.job_retention_hours, 0)

    def test_runtime_settings_reads_admin_json_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = AdminSettingsService(root / "data" / "settings")
            payload = service.load_all()
            payload["model_catalog"]["services"]["llm"]["profiles"][0]["api_key"] = "catalog-key"
            payload["model_catalog"]["services"]["llm"]["profiles"][0]["base_url"] = "https://chat.example/v1"
            payload["model_catalog"]["services"]["llm"]["profiles"][0]["models"][0]["model"] = "catalog-chat"
            payload["model_catalog"]["services"]["embedding"]["profiles"][0]["base_url"] = "https://embed.example/v1"
            payload["model_catalog"]["services"]["embedding"]["profiles"][0]["models"][0]["model"] = "catalog-embed"
            payload["runtime"]["rag"]["chunk_max_chars"] = 768
            payload["runtime"]["rag"]["per_query_limit"] = 3
            payload["runtime"]["parser"]["backend"] = "pymupdf"
            payload["runtime"]["jobs"]["max_pdf_bytes"] = 98765
            payload["runtime"]["jobs"]["job_retention_hours"] = 24
            payload["content_pack"]["packs"][0]["soul_path"] = "content/soul.md"
            payload["content_pack"]["packs"][0]["mnemonics_path"] = "content/mnemonics.md"
            service.save_all(payload)

            with patch.dict(os.environ, {}, clear=True):
                settings = RuntimeSettings.from_env(root)

        self.assertEqual(settings.admin_settings_dir, root / "data" / "settings")
        self.assertEqual(settings.api_key, "catalog-key")
        self.assertEqual(settings.chat_base_url, "https://chat.example/v1")
        self.assertEqual(settings.embed_base_url, "https://embed.example/v1")
        self.assertEqual(settings.chat_model, "catalog-chat")
        self.assertEqual(settings.embed_model, "catalog-embed")
        self.assertEqual(settings.rag_config.chunk_max_chars, 768)
        self.assertEqual(settings.rag_config.per_query_limit, 3)
        self.assertEqual(settings.parser_config["backend"], "pymupdf")
        self.assertEqual(settings.max_pdf_bytes, 98765)
        self.assertEqual(settings.job_retention_hours, 24)
        self.assertEqual(settings.soul_path, root / "content" / "soul.md")
        self.assertEqual(settings.mnemonics_path, root / "content" / "mnemonics.md")

    def test_runtime_environment_overrides_admin_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = AdminSettingsService(root / "data" / "settings")
            payload = service.load_all()
            payload["model_catalog"]["services"]["llm"]["profiles"][0]["models"][0]["model"] = "catalog-chat"
            payload["runtime"]["jobs"]["max_pdf_bytes"] = 98765
            service.save_all(payload)

            with patch.dict(
                os.environ,
                {
                    "SILICONFLOW_CHAT_MODEL": "env-chat",
                    "JSTUDY_MAX_PDF_BYTES": "12345",
                },
                clear=True,
            ):
                settings = RuntimeSettings.from_env(root)

        self.assertEqual(settings.chat_model, "env-chat")
        self.assertEqual(settings.max_pdf_bytes, 12345)

    def test_readiness_accepts_admin_json_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            soul = root / "soul.md"
            mnemonics = root / "mnemonics.md"
            soul.write_text("soul", encoding="utf-8")
            mnemonics.write_text("mnemonics", encoding="utf-8")
            service = AdminSettingsService(root / "data" / "settings")
            payload = service.load_all()
            payload["model_catalog"]["services"]["llm"]["profiles"][0]["api_key"] = "catalog-key"
            payload["model_catalog"]["services"]["llm"]["profiles"][0]["api_key_path"] = ""
            service.save_all(payload)

            with patch.dict(os.environ, {}, clear=True):
                settings = RuntimeSettings.from_env(root)
                readiness = settings.readiness()

        self.assertEqual(readiness["status"], "ready")
        checks = {check["name"]: check for check in readiness["checks"]}
        self.assertEqual(checks["api_key"]["detail"], "admin settings")

    def test_readiness_reports_missing_required_runtime_files_and_api_key(self):
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

            with patch.dict(os.environ, {}, clear=True):
                readiness = settings.readiness()

        self.assertEqual(readiness["status"], "degraded")
        checks = {check["name"]: check for check in readiness["checks"]}
        self.assertEqual(checks["jobs_root"]["status"], "ok")
        self.assertEqual(checks["soul_path"]["status"], "error")
        self.assertEqual(checks["mnemonics_path"]["status"], "error")
        self.assertEqual(checks["api_key"]["status"], "error")

    def test_readiness_accepts_existing_files_and_environment_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            soul = root / "soul.md"
            mnemonics = root / "mnemonics.md"
            soul.write_text("soul", encoding="utf-8")
            mnemonics.write_text("mnemonics", encoding="utf-8")
            settings = RuntimeSettings(
                project_root=root,
                jobs_root=root / "jobs",
                soul_path=soul,
                mnemonics_path=mnemonics,
                api_key_path=root / "missing-api-key.txt",
                chat_model="chat-model",
                embed_model="embed-model",
            )

            with patch.dict(os.environ, {"SILICONFLOW_API_KEY": "key"}, clear=True):
                readiness = settings.readiness()

        self.assertEqual(readiness["status"], "ready")
        self.assertTrue(all(check["status"] == "ok" for check in readiness["checks"]))

    def test_readiness_can_include_provider_probe_when_requested(self):
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
            api_key = root / "api-key.txt"
            soul.write_text("soul", encoding="utf-8")
            mnemonics.write_text("mnemonics", encoding="utf-8")
            api_key.write_text("key", encoding="utf-8")
            settings = RuntimeSettings(
                project_root=root,
                jobs_root=root / "jobs",
                soul_path=soul,
                mnemonics_path=mnemonics,
                api_key_path=api_key,
                chat_model="chat-model",
                embed_model="embed-model",
            )

            readiness = settings.readiness(probe_provider=True, provider_probe=probe)

        checks = {check["name"]: check for check in readiness["checks"]}
        self.assertEqual(readiness["status"], "ready")
        self.assertEqual(calls, [("key", "chat-model", "embed-model")])
        self.assertEqual(checks["provider_connectivity"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
