import json
import sys
import tempfile
import unittest
from pathlib import Path

import fitz
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from web_mvp import INDEX_HTML, create_app  # noqa: E402


class WebMvpTest(unittest.TestCase):
    def make_pdf_bytes(self) -> bytes:
        doc = fitz.open()
        for page_no in (1, 2):
            page = doc.new_page(width=240, height=320)
            page.insert_text((40, 80), f"Page {page_no}")
        return doc.tobytes()

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

    def test_generate_job_exposes_output_and_evidence_contracts(self):
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
            return {
                "markdown": markdown,
                "evidence": evidence,
                "evidence_links": evidence_links,
                "quality": quality,
            }

        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(base_dir=Path(tmp), runner=fake_runner))
            response = client.post(
                "/api/generate",
                files={
                    "pdf": ("lecture.pdf", self.make_pdf_bytes(), "application/pdf"),
                    "outline": ("outline.md", b"# outline\n", "text/markdown"),
                },
            )

            self.assertEqual(response.status_code, 200)
            job_id = response.json()["job_id"]
            status = client.get(f"/api/jobs/{job_id}").json()
            output = client.get(f"/api/jobs/{job_id}/output").json()
            evidence = client.get(f"/api/jobs/{job_id}/evidence").json()
            pdf_info = client.get(f"/api/jobs/{job_id}/pdf-info").json()
            page_png = client.get(f"/api/jobs/{job_id}/pdf-page/2.png")

        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["quality"]["status"], "pass")
        self.assertIn("evidence_links_url", status)
        self.assertIn("Fact", output["markdown"])
        self.assertEqual(evidence["evidence"][0]["id"], "E001")
        self.assertEqual(evidence["evidence_links"][0]["target"]["page"], 2)
        self.assertEqual(pdf_info["page_count"], 2)
        self.assertEqual(page_png.headers["content-type"], "image/png")
        self.assertTrue(page_png.content.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
