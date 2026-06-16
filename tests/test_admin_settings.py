import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.core.jstudy_core.admin_settings import (  # noqa: E402
    AdminSettingsService,
    render_mnemonics_markdown,
)


class AdminSettingsTest(unittest.TestCase):
    def test_load_all_creates_default_settings_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = AdminSettingsService(Path(tmp) / "settings")

            payload = service.load_all()

            self.assertEqual(payload["model_catalog"]["version"], 1)
            self.assertEqual(payload["runtime"]["parser"]["backend"], "pymupdf")
            self.assertEqual(payload["runtime"]["rag"]["chunk_max_chars"], 512)
            self.assertEqual(payload["content_pack"]["active_pack_id"], "medicine-default")
            self.assertEqual(payload["mnemonics"], {"version": 1, "items": []})
            self.assertTrue((Path(tmp) / "settings" / "model_catalog.json").is_file())
            self.assertTrue((Path(tmp) / "settings" / "runtime.json").is_file())
            self.assertTrue((Path(tmp) / "settings" / "content_pack.json").is_file())
            self.assertTrue((Path(tmp) / "settings" / "mnemonics.json").is_file())

    def test_content_pack_defaults_include_scenarios(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = AdminSettingsService(Path(tmp) / "settings")

            payload = service.load_content_pack()

        self.assertEqual(payload["default_scenario_id"], "medicine-default")
        scenario_ids = {item["id"] for item in payload["scenarios"]}
        self.assertIn("medicine-default", scenario_ids)
        self.assertIn("general-default", scenario_ids)

    def test_content_pack_defaults_include_soul_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = AdminSettingsService(Path(tmp) / "settings")

            payload = service.load_content_pack()

        profiles = {item["id"]: item for item in payload["soul_profiles"]}
        self.assertEqual(profiles["medicine-default"]["soul_path"], "soul.md")
        self.assertEqual(profiles["general-blank"]["soul_path"], "")
        self.assertEqual(profiles["engineering-blank"]["soul_path"], "")
        self.assertEqual(profiles["law-blank"]["soul_path"], "")
        scenarios = {item["id"]: item for item in payload["scenarios"]}
        self.assertFalse(scenarios["general-default"]["enabled"])
        self.assertFalse(scenarios["engineering-default"]["enabled"])
        self.assertFalse(scenarios["law-default"]["enabled"])

    def test_runtime_defaults_include_parser_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = AdminSettingsService(Path(tmp) / "settings")

            payload = service.load_runtime()

        profiles = payload["parser_profiles"]
        self.assertEqual(profiles["default_profile_id"], "fast")
        by_id = {item["id"]: item for item in profiles["profiles"]}
        self.assertEqual(by_id["fast"]["backend"], "pymupdf")
        self.assertTrue(by_id["fast"]["visible_to_users"])
        self.assertEqual(by_id["quality"]["backend"], "mineru")
        self.assertFalse(by_id["quality"]["visible_to_users"])
        self.assertTrue(by_id["quality"]["requires_admin"])

    def test_public_payload_redacts_api_keys_but_marks_presence(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = AdminSettingsService(Path(tmp) / "settings")
            payload = service.load_all()
            payload["model_catalog"]["services"]["llm"]["profiles"][0]["api_key"] = "sk-secret"
            service.save_all(payload)

            public = service.load_public()
            profile = public["model_catalog"]["services"]["llm"]["profiles"][0]

            self.assertEqual(profile["api_key"], "")
            self.assertTrue(profile["api_key_set"])

    def test_save_public_preserves_existing_key_when_redacted_field_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = AdminSettingsService(Path(tmp) / "settings")
            payload = service.load_all()
            payload["model_catalog"]["services"]["llm"]["profiles"][0]["api_key"] = "sk-secret"
            service.save_all(payload)

            public = service.load_public()
            public["model_catalog"]["services"]["llm"]["profiles"][0]["name"] = "Renamed"
            service.save_public(public)

            saved = service.load_all()
            profile = saved["model_catalog"]["services"]["llm"]["profiles"][0]
            self.assertEqual(profile["name"], "Renamed")
            self.assertEqual(profile["api_key"], "sk-secret")

    def test_render_mnemonics_json_to_prompt_markdown(self):
        markdown = render_mnemonics_markdown(
            {
                "version": 1,
                "items": [
                    {
                        "id": "m-1",
                        "title": "Coagulation Factors",
                        "subject": "medicine",
                        "topic": "hematology",
                        "tags": ["exam", "memory"],
                        "content": "Mnemonic text",
                        "notes": "Use for review",
                        "enabled": True,
                    },
                    {
                        "id": "m-2",
                        "title": "Disabled",
                        "content": "Hidden",
                        "enabled": False,
                    },
                ],
            }
        )

        self.assertIn("### Coagulation Factors", markdown)
        self.assertIn("- ID: m-1", markdown)
        self.assertIn("- Tags: exam, memory", markdown)
        self.assertIn("Mnemonic text", markdown)
        self.assertNotIn("Hidden", markdown)

    def test_runtime_rag_settings_are_clamped_to_valid_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = AdminSettingsService(Path(tmp) / "settings")

            saved = service.save_runtime(
                {
                    "rag": {
                        "chunk_max_chars": 10,
                        "chunk_overlap": 99,
                        "top_k_candidates": 0,
                        "per_query_limit": 0,
                        "mnemonic_limit": 0,
                    }
                }
            )

        self.assertEqual(saved["rag"]["chunk_overlap"], 9)
        self.assertEqual(saved["rag"]["top_k_candidates"], 1)
        self.assertEqual(saved["rag"]["per_query_limit"], 1)
        self.assertEqual(saved["rag"]["mnemonic_limit"], 1)

    def test_sync_mnemonics_markdown_writes_active_pack_markdown_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = AdminSettingsService(root / "settings")
            payload = service.load_all()
            payload["mnemonics"]["items"].append(
                {
                    "id": "m-1",
                    "title": "Active Mnemonic",
                    "content": "Rendered from JSON",
                    "enabled": True,
                }
            )
            payload["content_pack"]["packs"][0]["mnemonics_path"] = "config/mnemonics.md"
            service.save_all(payload)

            target = service.sync_mnemonics_markdown(root)

            self.assertEqual(target, root / "config" / "mnemonics.md")
            self.assertIn("Rendered from JSON", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
