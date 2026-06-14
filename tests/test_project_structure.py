import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class ProjectStructureTest(unittest.TestCase):
    def test_backend_imports_have_canonical_and_legacy_paths(self):
        from apps.api.jstudy_api.app import INDEX_HTML, app, create_app
        from apps.api.jstudy_api.ui import INDEX_HTML as ui_index_html
        from packages.core.jstudy_core.pipeline import RagConfig, run_mvp
        from mvp_runner import run_mvp as legacy_run_mvp
        from web_mvp import create_app as legacy_create_app

        self.assertTrue(INDEX_HTML.startswith("<!doctype html>"))
        self.assertIs(INDEX_HTML, ui_index_html)
        self.assertEqual(app.title, "J Study MVP")
        self.assertIs(legacy_create_app, create_app)
        self.assertIs(legacy_run_mvp, run_mvp)
        self.assertEqual(RagConfig().per_query_limit, 2)

    def test_api_app_does_not_own_temporary_html(self):
        source = (ROOT / "apps" / "api" / "jstudy_api" / "app.py").read_text(encoding="utf-8")

        self.assertIn("from apps.api.jstudy_api.ui import INDEX_HTML", source)
        self.assertNotIn('INDEX_HTML = r"""', source)


if __name__ == "__main__":
    unittest.main()
