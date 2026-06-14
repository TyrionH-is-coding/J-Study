import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.core.jstudy_core.pipeline import (  # noqa: E402
    Chunk,
    DeepTutorRagAdapter,
    RagConfig,
    StudyQuery,
    audit_output_quality,
    build_evidence_links,
    build_study_queries,
    build_evidence_items,
    build_generation_prompt,
    chunk_pages,
    embed_texts_cached,
    filter_ranked_chunks,
    load_rag_config,
    reciprocal_rank_fusion,
    is_low_value_chunk,
    parse_mnemonics,
    read_api_key,
    retrieve_mnemonics,
    run_mvp,
    select_evidence_chunks,
    siliconflow_post,
)


class FakeHttpResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return b'{"ok": true}'


class MvpRunnerTest(unittest.TestCase):
    def test_chunk_pages_keeps_page_numbers_and_stable_ids(self):
        pages = [
            {"page": 1, "text": "金黄色葡萄球菌 革兰阳性 球菌 葡萄串状排列"},
            {"page": 2, "text": "凝固酶试验 阳性 可鉴定金黄色葡萄球菌"},
        ]

        chunks = chunk_pages(pages, max_chars=20, overlap=4)

        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(chunks[0].id, "C001")
        self.assertEqual(chunks[0].page, 1)
        self.assertIn("金黄色葡萄球菌", chunks[0].text)
        self.assertTrue(all(chunk.id.startswith("C") for chunk in chunks))

    def test_parse_and_retrieve_mnemonics_by_keywords(self):
        text = """
---
id: M001
title: 葡萄球菌记忆
keywords: 葡萄球菌,凝固酶,金黄色葡萄球菌
source: 待审核候选
content: 金葡凝固酶阳性，表葡凝固酶阴性。
---
id: M002
title: 脑神经口诀
keywords: 脑神经,动眼神经
source: 公共口诀库命中
content: 一嗅二视三动眼。
"""

        mnemonics = parse_mnemonics(text)
        hits = retrieve_mnemonics("凝固酶试验用于鉴别金黄色葡萄球菌", mnemonics, limit=1)

        self.assertEqual(len(mnemonics), 2)
        self.assertEqual(hits[0]["id"], "M001")
        self.assertEqual(hits[0]["source"], "待审核候选")

    def test_build_evidence_items_writes_required_fields(self):
        chunks = [
            Chunk(id="C001", page=3, text="凝固酶试验阳性提示金黄色葡萄球菌", score=0.91),
            Chunk(id="C002", page=4, text="药敏试验关注 MRSA", score=0.72),
        ]

        evidence = build_evidence_items(chunks, "12-球菌.pdf")

        self.assertEqual(evidence[0]["id"], "E001")
        self.assertEqual(evidence[0]["source_file"], "12-球菌.pdf")
        self.assertEqual(evidence[0]["page"], 3)
        self.assertEqual(evidence[0]["chunk_id"], "C001")
        self.assertIn("excerpt", evidence[0])

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence.json"
            path.write_text(json.dumps(evidence, ensure_ascii=False), encoding="utf-8")
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded[1]["id"], "E002")

    def test_prompt_requires_visible_mnemonic_source(self):
        messages = build_generation_prompt(
            "口诀必须标注来源。",
            [{"id": "E001", "page": 1, "chunk_id": "C001", "excerpt": "葡萄球菌"}],
            [{"title": "葡萄球菌口诀", "source": "待审核候选", "content": "金葡凝固酶阳"}],
        )

        prompt = messages[1]["content"]
        self.assertIn("口诀来源必须用学生可见的正文标注", prompt)
        self.assertIn("不要用 HTML 注释隐藏口诀来源", prompt)

    def test_prompt_includes_uploaded_outline_when_present(self):
        messages = build_generation_prompt(
            "rules",
            [{"id": "E001", "page": 1, "chunk_id": "C001", "excerpt": "Fact"}],
            [],
            outline="第一章 细菌总论\n第二章 球菌",
        )

        prompt = messages[1]["content"]
        self.assertIn("课程大纲参考", prompt)
        self.assertIn("第一章 细菌总论", prompt)

    def test_low_value_heading_chunks_are_filtered(self):
        heading = Chunk(id="C001", page=8, text="一、生物学性状 Biological characteristics")
        organism_heading = Chunk(id="C003", page=59, text="一、生物学性状 Biological characteristics 化脓链球菌(S. pyogenes)")
        factual = Chunk(id="C002", page=46, text="致病性葡萄球菌的鉴定 凝固酶（+） 耐热核酸酶（+） 金黄色色素（+）")

        filtered = filter_ranked_chunks([heading, organism_heading, factual], per_query_limit=3)

        self.assertTrue(is_low_value_chunk(heading.text))
        self.assertTrue(is_low_value_chunk(organism_heading.text))
        self.assertFalse(is_low_value_chunk(factual.text))
        self.assertEqual([chunk.id for chunk in filtered], ["C002"])

    def test_filter_ranked_chunks_requires_topic_terms(self):
        wrong_topic = Chunk(id="C001", page=142, text="脑膜炎奈瑟菌 肾形或豆形革兰阴性双球菌 荚膜 菌毛")
        right_topic = Chunk(
            id="C002",
            page=10,
            text="葡萄球菌是一群革兰阳性球菌，通常排列成不规则的葡萄串状，无鞭毛和芽胞，触酶试验阳性。",
        )

        filtered = filter_ranked_chunks(
            [wrong_topic, right_topic],
            per_query_limit=2,
            required_any=("葡萄球菌", "staphylococcus", "触酶"),
        )

        self.assertEqual([chunk.id for chunk in filtered], ["C002"])

    def test_staphylococcus_lab_filter_rejects_cross_reference_only(self):
        cross_reference = Chunk(
            id="C001",
            page=92,
            text="微生物学检查法 标本 直接涂片镜检 分离培养 如有β溶血菌落，应与葡萄球菌区别。",
        )
        direct_evidence = Chunk(
            id="C002",
            page=46,
            text="致病性葡萄球菌的鉴定 凝固酶（+） 耐热核酸酶（+） 金黄色色素（+） 溶血性（+） 发酵甘露醇（+）",
        )

        filtered = filter_ranked_chunks(
            [cross_reference, direct_evidence],
            per_query_limit=2,
            required_any=("凝固酶", "耐热核酸酶", "甘露醇", "maldi", "金黄色", "类似葡萄球菌属"),
        )

        self.assertEqual([chunk.id for chunk in filtered], ["C002"])

    def test_study_queries_cover_multiple_learning_modules(self):
        queries = build_study_queries()
        ids = {query.id for query in queries}

        self.assertIn("staphylococcus_lab", ids)
        self.assertIn("gonococcus", ids)
        self.assertGreaterEqual(len(queries), 8)

    def test_reciprocal_rank_fusion_promotes_lexical_match(self):
        chunks = [
            Chunk(id="C001", page=1, text="凝固酶试验阳性 金黄色葡萄球菌", score=0.0),
            Chunk(id="C002", page=2, text="完全无关的背景文字", score=0.0),
            Chunk(id="C003", page=3, text="葡萄球菌微生物学检查 分离培养", score=0.0),
        ]
        vector_scores = {"C001": 0.2, "C002": 0.95, "C003": 0.3}

        ranked = reciprocal_rank_fusion("凝固酶 金黄色葡萄球菌", chunks, vector_scores)

        self.assertEqual(ranked[0].id, "C001")
        self.assertGreater(ranked[0].score, ranked[1].score)

    @patch("packages.core.jstudy_core.pipeline.urllib.request.urlopen")
    def test_siliconflow_post_retries_timeout(self, urlopen):
        urlopen.side_effect = [TimeoutError("read timed out"), FakeHttpResponse()]

        result = siliconflow_post("embeddings", {"model": "x", "input": ["a"]}, "key", retries=1)

        self.assertEqual(result, {"ok": True})
        self.assertEqual(urlopen.call_count, 2)

    @patch("packages.core.jstudy_core.pipeline.extract_pdf_pages")
    @patch("packages.core.jstudy_core.pipeline.embed_texts")
    def test_run_mvp_writes_links_quality_cache_and_uses_outline(self, embed_texts, extract_pdf_pages):
        extract_pdf_pages.return_value = [
            {
                "page": 1,
                "text": "alpha overview: beta detail with enough lecture content for retrieval and evidence citation.",
            }
        ]
        embed_texts.side_effect = lambda texts, api_key, model: [[1.0, 0.0] for _ in texts]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "lecture.pdf"
            soul = root / "soul.md"
            mnemonics = root / "mnemonics.md"
            api_key = root / "api-key.txt"
            outline = root / "outline.md"
            output_dir = root / "out"
            cache = root / "cache" / "embeddings.json"
            pdf.write_bytes(b"%PDF-1.4\n")
            soul.write_text("rules", encoding="utf-8")
            mnemonics.write_text("", encoding="utf-8")
            api_key.write_text("key", encoding="utf-8")
            outline.write_text("第一章 细菌总论", encoding="utf-8")

            with patch(
                "packages.core.jstudy_core.pipeline.build_study_queries",
                return_value=[StudyQuery("sample", "Sample", "alpha overview")],
            ), patch("packages.core.jstudy_core.pipeline.generate_markdown") as generate_markdown:
                generate_markdown.side_effect = lambda messages, api_key, model: (
                    self.assertIn("第一章 细菌总论", messages[1]["content"])
                    or "Fact <!-- evidence: E001 -->"
                )

                outputs = run_mvp(
                    pdf_path=pdf,
                    soul_path=soul,
                    mnemonics_path=mnemonics,
                    api_key_path=api_key,
                    output_dir=output_dir,
                    chat_model="chat",
                    embed_model="embed",
                    output_prefix="case",
                    rag_config=RagConfig(top_k_candidates=1, per_query_limit=1),
                    embedding_cache_path=cache,
                    outline_path=outline,
                )

            quality = json.loads(outputs["quality"].read_text(encoding="utf-8"))
            evidence_links = json.loads(outputs["evidence_links"].read_text(encoding="utf-8"))

            self.assertTrue(outputs["markdown"].exists())
            self.assertTrue(outputs["evidence"].exists())
            self.assertTrue(cache.exists())
            self.assertEqual(quality["status"], "pass")
            self.assertEqual(evidence_links[0]["target"]["page"], 1)

    @patch("packages.core.jstudy_core.pipeline.embed_texts")
    def test_embed_texts_cached_reuses_existing_vectors(self, embed_texts):
        embed_texts.return_value = [[0.1, 0.2]]

        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "embeddings.json"
            first = embed_texts_cached(["alpha"], api_key="key", model="model-a", cache_path=cache_path)
            second = embed_texts_cached(["alpha"], api_key="key", model="model-a", cache_path=cache_path)

        self.assertEqual(first, [[0.1, 0.2]])
        self.assertEqual(second, [[0.1, 0.2]])
        embed_texts.assert_called_once_with(["alpha"], api_key="key", model="model-a")

    def test_load_rag_config_overrides_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "rag-config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "top_k_candidates": 5,
                        "per_query_limit": 1,
                        "mnemonic_limit": 2,
                        "chunk_max_chars": 128,
                    }
                ),
                encoding="utf-8",
            )

            config = load_rag_config(config_path)

        self.assertEqual(config.top_k_candidates, 5)
        self.assertEqual(config.per_query_limit, 1)
        self.assertEqual(config.mnemonic_limit, 2)
        self.assertEqual(config.chunk_max_chars, 128)
        self.assertEqual(config.chunk_overlap, RagConfig().chunk_overlap)

    def test_read_api_key_prefers_environment_for_deployment(self):
        with patch.dict(os.environ, {"SILICONFLOW_API_KEY": " env-key \n"}, clear=False):
            key = read_api_key(Path("missing-api-key.txt"))

        self.assertEqual(key, "env-key")

    def test_audit_output_quality_flags_unknown_evidence_refs(self):
        markdown = "## Section\n\nFact. <!-- evidence: E001 E999 -->\n\nMVP debug text"
        evidence = [{"id": "E001", "page": 1, "chunk_id": "C001", "excerpt": "Fact"}]

        report = audit_output_quality(markdown, evidence)

        self.assertEqual(report["status"], "fail")
        self.assertIn("E999", report["unknown_evidence_refs"])
        self.assertIn("engineering_language", {issue["code"] for issue in report["issues"]})

    def test_build_evidence_links_maps_markdown_refs_to_pdf_targets(self):
        markdown = "Fact A <!-- evidence: E002 E001 -->\n\nFact B <!-- evidence: E001 -->"
        evidence = [
            {"id": "E001", "source_file": "lecture.pdf", "page": 3, "chunk_id": "C001", "excerpt": "alpha"},
            {"id": "E002", "source_file": "lecture.pdf", "page": 7, "chunk_id": "C002", "excerpt": "beta"},
        ]

        links = build_evidence_links(markdown, evidence)

        self.assertEqual([link["ref_id"] for link in links], ["E002", "E001", "E001"])
        self.assertEqual(links[0]["target"]["source_file"], "lecture.pdf")
        self.assertEqual(links[0]["target"]["page"], 7)
        self.assertEqual(links[0]["target"]["quote"], "beta")
        self.assertEqual(links[2]["occurrence"], 2)

    def test_select_evidence_chunks_is_stable_regression_sample(self):
        sample = json.loads(
            (ROOT / "tests" / "fixtures" / "cocci_regression_sample.json").read_text(encoding="utf-8")
        )
        queries = [
            StudyQuery(**sample["query"]),
        ]
        chunks = [
            Chunk(id=row["id"], page=row["page"], text=row["text"], score=0.0)
            for row in sample["chunks"]
        ]
        chunk_embeddings = sample["chunk_embeddings"]
        query_embeddings = sample["query_embeddings"]
        config = RagConfig(top_k_candidates=3, per_query_limit=2)

        selected, trace = select_evidence_chunks(queries, chunks, chunk_embeddings, query_embeddings, config)

        self.assertEqual([chunk.id for chunk in selected], sample["expected_selected_chunk_ids"])
        self.assertEqual(trace[0]["query"]["id"], queries[0].id)
        self.assertEqual([chunk["id"] for chunk in trace[0]["kept"]], sample["expected_selected_chunk_ids"])

    def test_deeptutor_rag_adapter_returns_service_like_result(self):
        chunks = [
            Chunk(id="C001", page=1, text="alpha overview: beta detail with enough lecture content"),
            Chunk(id="C002", page=2, text="unrelated material: gamma detail with enough lecture content"),
        ]
        adapter = DeepTutorRagAdapter(
            chunks=chunks,
            chunk_embeddings=[[1.0, 0.0], [0.0, 1.0]],
            source_file="lecture.pdf",
            rag_config=RagConfig(top_k_candidates=2, per_query_limit=1),
        )

        result = adapter.search(
            StudyQuery("sample", "Sample", "alpha overview"),
            query_embedding=[1.0, 0.0],
        )

        self.assertEqual(result["query"], "alpha overview")
        self.assertEqual(result["answer"], result["content"])
        self.assertEqual(result["provider"], "local_hybrid_rrf")
        self.assertEqual(result["sources"][0]["source"], "lecture.pdf")
        self.assertEqual(result["sources"][0]["page"], 1)
        self.assertEqual(result["sources"][0]["chunk_id"], "C001")
        self.assertIn("trace", result)


if __name__ == "__main__":
    unittest.main()
