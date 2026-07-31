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
    parse_outline_sections,
    read_api_key,
    retrieve_mnemonics,
    run_course_outline,
    run_mvp,
    select_evidence_chunks,
    siliconflow_post,
)
from packages.core.jstudy_core.providers import probe_siliconflow_provider  # noqa: E402
from packages.core.jstudy_core.job_system.states import JobState  # noqa: E402
from packages.core.jstudy_core.materials.models import (  # noqa: E402
    MaterialSection,
    SectionQuality,
)
from packages.core.jstudy_core.courseware import (  # noqa: E402
    CoursewareManifestV1,
    CoverageLedgerV1,
    LearningMapV1,
)
from packages.core.jstudy_core.documents import (  # noqa: E402
    ParsedBlock,
    ParsedDocument,
    ParsedPage,
)


def fake_section_generator(**kwargs):
    evidence = kwargs["evidence"]
    if not evidence:
        return MaterialSection(
            id=kwargs["section_id"],
            order=kwargs["order"],
            title=kwargs["title"],
            status="weak_evidence",
            quality=SectionQuality(
                evidence_status="weak",
                evidence_count=0,
                cited_evidence_count=0,
                citation_coverage=0,
            ),
            source_ids=[],
            evidence_ids=[],
            blocks=[
                {
                    "id": f"{kwargs['section_id']}-note",
                    "type": "callout",
                    "variant": "note",
                    "runs": [{"type": "text", "text": "资料不足"}],
                }
            ],
        )
    evidence_id = evidence[0]["id"]
    return MaterialSection(
        id=kwargs["section_id"],
        order=kwargs["order"],
        title=kwargs["title"],
        status="generated",
        quality=SectionQuality(
            evidence_status="sufficient",
            evidence_count=len(evidence),
            cited_evidence_count=1,
            citation_coverage=1 / len(evidence),
        ),
        source_ids=kwargs["source_ids"],
        evidence_ids=[item["id"] for item in evidence],
        blocks=[
            {
                "id": f"{kwargs['section_id']}-paragraph",
                "type": "paragraph",
                "runs": [
                    {"type": "text", "text": "Generated fact "},
                    {"type": "citation", "evidence_id": evidence_id},
                ],
            }
        ],
    )


class FakeHttpResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return b'{"ok": true}'


class MvpRunnerTest(unittest.TestCase):
    def test_sequence_generation_uses_learning_map_not_parsing_or_scores(self):
        manifest = CoursewareManifestV1.model_validate(
            {
                "schema_version": "courseware-manifest.v1",
                "manifest_id": "job-1",
                "job_id": "job-1",
                "service_mode": "course_outline",
                "outline": None,
                "sources": [
                    {
                        "source_id": "S001",
                        "original_filename": "late.pdf",
                        "sha256": "a" * 64,
                        "display_title": "Late",
                        "display_order": 2,
                        "primary_outline_section_id": None,
                        "title_origin": "upload",
                        "order_origin": "upload",
                    },
                    {
                        "source_id": "S002",
                        "original_filename": "early.pdf",
                        "sha256": "b" * 64,
                        "display_title": "Early",
                        "display_order": 1,
                        "primary_outline_section_id": None,
                        "title_origin": "upload",
                        "order_origin": "upload",
                    },
                ],
            }
        )
        documents = []
        for source_id, sha in (("S001", "a"), ("S002", "b")):
            documents.append(
                ParsedDocument(
                    contract_version="1",
                    source_id=source_id,
                    source_file=f"{source_id}.pdf",
                    source_sha256=sha * 64,
                    parser_name="mineru",
                    parser_version="v4",
                    parser_model="vlm",
                    page_count=2,
                    pages=[
                        ParsedPage(
                            page_number=page,
                            text=f"{source_id} page {page}",
                            markdown=f"{source_id} page {page}",
                            blocks=[
                                ParsedBlock(
                                    block_id=(
                                        f"{source_id}-P{page:03d}-B001"
                                    ),
                                    kind="text",
                                    text=f"{source_id} page {page}",
                                    markdown=f"{source_id} page {page}",
                                )
                            ],
                        )
                        for page in (1, 2)
                    ],
                    warnings=[],
                    provider_trace_id="trace",
                )
            )
        learning_map = LearningMapV1.model_validate(
            {
                "schema_version": "learning-map.v1",
                "manifest_id": "job-1",
                "units": [
                    {
                        "id": "unit-001",
                        "order": 1,
                        "outline_section_id": None,
                        "primary_source_id": "S002",
                        "page_start": 1,
                        "page_end": 1,
                        "block_ids": ["S002-P001-B001"],
                        "material_section_id": "unit-001",
                    },
                    {
                        "id": "unit-002",
                        "order": 2,
                        "outline_section_id": None,
                        "primary_source_id": "S002",
                        "page_start": 2,
                        "page_end": 2,
                        "block_ids": ["S002-P002-B001"],
                        "material_section_id": "unit-002",
                    },
                    {
                        "id": "unit-003",
                        "order": 3,
                        "outline_section_id": None,
                        "primary_source_id": "S001",
                        "page_start": 1,
                        "page_end": 2,
                        "block_ids": [
                            "S001-P001-B001",
                            "S001-P002-B001",
                        ],
                        "material_section_id": "unit-003",
                    },
                ],
            }
        )
        coverage = CoverageLedgerV1.model_validate(
            {
                "schema_version": "coverage-ledger.v1",
                "manifest_id": "job-1",
                "entries": [
                    {
                        "block_id": block_id,
                        "source_id": block_id.split("-P", 1)[0],
                        "page_number": int(
                            block_id.split("-P", 1)[1].split("-", 1)[0]
                        ),
                        "disposition": "used",
                        "reason": "learning_unit",
                        "learning_unit_id": unit_id,
                    }
                    for unit_id, block_ids in (
                        ("unit-001", ["S002-P001-B001"]),
                        ("unit-002", ["S002-P002-B001"]),
                        (
                            "unit-003",
                            ["S001-P001-B001", "S001-P002-B001"],
                        ),
                    )
                    for block_id in block_ids
                ],
                "metrics": {
                    "usable_block_count": 4,
                    "used_block_count": 4,
                    "ignored_block_count": 0,
                    "duplicate_block_count": 0,
                    "unsupported_block_count": 0,
                    "coverage_rate": 1.0,
                    "ignored_reason_counts": {},
                    "primary_backward_jump_count": 0,
                    "large_jump_count": 0,
                    "remote_reference_ratio": 0.0,
                    "page_distance_p90": 0.0,
                },
            }
        )
        captured = []

        def generator(**kwargs):
            captured.append(kwargs)
            return fake_section_generator(**kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            soul = root / "soul.md"
            mnemonics = root / "mnemonics.md"
            soul.write_text("soul", encoding="utf-8")
            mnemonics.write_text(
                "---\n"
                "id: M001\n"
                "title: Source sequence\n"
                "keywords: S002,page\n"
                "source: test\n"
                "content: Sequence hint.\n",
                encoding="utf-8",
            )
            with (
                patch(
                    "packages.core.jstudy_core.pipeline.extract_pdf_pages",
                    side_effect=AssertionError("must not parse"),
                ),
                patch(
                    "packages.core.jstudy_core.pipeline.extract_pdf_pages_with_mineru",
                    side_effect=AssertionError("must not parse"),
                ),
                patch(
                    "packages.core.jstudy_core.pipeline.select_evidence_chunks",
                    side_effect=AssertionError("must not rank"),
                ),
            ):
                outputs = run_course_outline(
                    outline_path=root / "missing-outline.md",
                    pdf_paths=[root / "missing.pdf"],
                    soul_path=soul,
                    mnemonics_path=mnemonics,
                    api_key_path=root / "missing-key",
                    output_dir=root / "output",
                    chat_model="chat",
                    embed_model="embed",
                    api_key="test-key",
                    package_id="job-1",
                    section_generator=generator,
                    parsed_documents=documents,
                    courseware_manifest=manifest,
                    learning_map=learning_map,
                    coverage_ledger=coverage,
                )

            package = json.loads(
                outputs["package"].read_text(encoding="utf-8")
            )
            trace = json.loads(outputs["trace"].read_text(encoding="utf-8"))
            evidence = json.loads(
                outputs["evidence"].read_text(encoding="utf-8")
            )

        self.assertEqual(
            [section["id"] for section in package["sections"]],
            ["unit-001", "unit-002", "unit-003"],
        )
        self.assertEqual(
            [call["source_ids"] for call in captured],
            [["S002"], ["S002"], ["S001"]],
        )
        self.assertEqual(trace["generation_strategy"], "sequence-first")
        self.assertEqual(
            [
                (
                    item["source_id"],
                    item["original_filename"],
                    item["file_name"],
                    item["page_count"],
                    item["parser_backend"],
                )
                for item in trace["source_files"]
            ],
            [
                ("S002", "early.pdf", "early.pdf", 2, "mineru"),
                ("S001", "late.pdf", "late.pdf", 2, "mineru"),
            ],
        )
        self.assertEqual(trace["mnemonic_hits"][0]["id"], "M001")
        source_files = {
            item["source_id"]: item["source_file"] for item in evidence
        }
        self.assertEqual(
            source_files,
            {"S001": "late.pdf", "S002": "early.pdf"},
        )
        self.assertTrue(
            all(item["relation"] == "primary" for item in evidence)
        )

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

    def test_chunk_and_evidence_items_preserve_source_identity(self):
        chunks = chunk_pages(
            [{"page": 2, "text": "alpha source two content with enough detail for a citation target"}],
            max_chars=80,
            overlap=0,
            source_id="S002",
            source_file="lecture-02.pdf",
        )

        evidence = build_evidence_items(chunks, "")
        links = build_evidence_links("Fact <!-- evidence: E001 -->", evidence)

        self.assertEqual(chunks[0].id, "S002-C001")
        self.assertEqual(chunks[0].source_id, "S002")
        self.assertEqual(chunks[0].source_file, "lecture-02.pdf")
        self.assertEqual(evidence[0]["source_id"], "S002")
        self.assertEqual(evidence[0]["source_file"], "lecture-02.pdf")
        self.assertEqual(links[0]["target"]["source_id"], "S002")
        self.assertEqual(links[0]["target"]["source_file"], "lecture-02.pdf")
    def test_build_evidence_items_cleans_pdf_artifact_quotes(self):
        chunks = [
            Chunk(
                id="C001",
                page=3,
                text="正常内容 \uE000\uE001\n++++ + + + +\nMRSA 相关内容",
                score=0.91,
            )
        ]

        evidence = build_evidence_items(chunks, "lecture.pdf")

        self.assertEqual(evidence[0]["excerpt"], "正常内容 MRSA 相关内容")

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
        queries = build_study_queries(
            source_text=(
                "免疫学总论 抗原 抗体 补体 细胞因子 超敏反应 "
                "主要组织相容性复合体 免疫应答"
            ),
            outline="第一章 免疫学总论\n第二章 抗原\n第三章 抗体和补体",
        )
        ids = {query.id for query in queries}
        query_text = "\n".join(query.query for query in queries)

        self.assertIn("overview", ids)
        self.assertIn("key_concepts", ids)
        self.assertIn("mechanisms", ids)
        self.assertIn("comparisons", ids)
        self.assertIn("抗原", query_text)
        self.assertIn("补体", query_text)
        self.assertNotIn("staphylococcus", query_text.lower())
        self.assertNotIn("gonococcus", query_text.lower())
        self.assertNotIn("葡萄球菌", query_text)
        self.assertGreaterEqual(len(queries), 6)

    def test_empty_study_queries_use_neutral_medicine_fallbacks(self):
        queries = build_study_queries()
        query_text = "\n".join(query.query for query in queries)

        self.assertIn("医学", query_text)
        self.assertNotIn("staphylococcus", query_text.lower())
        self.assertNotIn("gonococcus", query_text.lower())
        self.assertNotIn("葡萄球菌", query_text)

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

    @patch("packages.core.jstudy_core.providers.urllib.request.urlopen")
    def test_siliconflow_post_retries_timeout(self, urlopen):
        urlopen.side_effect = [TimeoutError("read timed out"), FakeHttpResponse()]

        result = siliconflow_post("embeddings", {"model": "x", "input": ["a"]}, "key", retries=1)

        self.assertEqual(result, {"ok": True})
        self.assertEqual(urlopen.call_count, 2)

    @patch("packages.core.jstudy_core.providers.urllib.request.urlopen")
    def test_siliconflow_post_accepts_custom_base_url(self, urlopen):
        urlopen.return_value = FakeHttpResponse()

        siliconflow_post(
            "embeddings",
            {"model": "x", "input": ["a"]},
            "key",
            base_url="https://models.example/v1",
        )

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://models.example/v1/embeddings")

    @patch("packages.core.jstudy_core.providers.siliconflow_post")
    def test_probe_siliconflow_provider_checks_chat_and_embedding(self, post):
        calls = []

        def fake_post(endpoint, payload, api_key, timeout, retries):
            calls.append((endpoint, payload, api_key, timeout, retries))
            if endpoint == "embeddings":
                return {"data": [{"embedding": [0.1, 0.2]}]}
            return {"choices": [{"message": {"content": "ok"}}]}

        post.side_effect = fake_post

        check = probe_siliconflow_provider(
            api_key="key",
            chat_model="chat-model",
            embed_model="embed-model",
            timeout=3,
        )

        self.assertEqual(check["status"], "ok")
        self.assertEqual([call[0] for call in calls], ["embeddings", "chat/completions"])
        self.assertEqual(calls[0][1], {"model": "embed-model", "input": ["ping"]})
        self.assertEqual(calls[1][1]["model"], "chat-model")
        self.assertEqual(calls[1][1]["max_tokens"], 1)
        self.assertTrue(all(call[2] == "key" and call[3] == 3 and call[4] == 0 for call in calls))

    @patch("packages.core.jstudy_core.pipeline.extract_pdf_pages")
    @patch("packages.core.jstudy_core.providers.embed_texts")
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
            progress_states = []
            pdf.write_bytes(b"%PDF-1.4\n")
            soul.write_text("rules", encoding="utf-8")
            mnemonics.write_text("", encoding="utf-8")
            api_key.write_text("key", encoding="utf-8")
            outline.write_text("第一章 细菌总论", encoding="utf-8")

            with patch(
                "packages.core.jstudy_core.pipeline.build_study_queries",
                return_value=[StudyQuery("sample", "Sample", "alpha overview")],
            ) as query_builder:
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
                    parser_backend="pymupdf",
                    package_id="job-single-001",
                    section_generator=fake_section_generator,
                    routing_metadata={
                        "scenario": {
                            "resolved_scenario_id": "medicine-default",
                            "subject": "medicine",
                        },
                        "parser_profile": {
                            "resolved_parser_profile_id": "fast",
                            "backend": "pymupdf",
                        },
                    },
                    progress_callback=progress_states.append,
                )

            quality = json.loads(outputs["quality"].read_text(encoding="utf-8"))
            evidence_links = json.loads(outputs["evidence_links"].read_text(encoding="utf-8"))
            trace = json.loads(outputs["trace"].read_text(encoding="utf-8"))
            package = json.loads(outputs["package"].read_text(encoding="utf-8"))

            self.assertTrue(outputs["markdown"].exists())
            self.assertTrue(outputs["evidence"].exists())
            self.assertTrue(outputs["package"].exists())
            self.assertTrue(cache.exists())
            self.assertEqual(quality["status"], "pass")
            self.assertEqual(evidence_links[0]["target"]["page"], 1)
            self.assertEqual(trace["scenario"]["resolved_scenario_id"], "medicine-default")
            self.assertEqual(trace["parser_profile"]["resolved_parser_profile_id"], "fast")
            self.assertEqual(trace["parser"]["backend"], "pymupdf")
            self.assertEqual(package["schema_version"], "material-package.v2")
            self.assertEqual(package["package_id"], "job-single-001")
            self.assertEqual(package["service_mode"], "single_courseware")
            self.assertEqual(package["sections"][0]["id"], "full-material")
            self.assertEqual(package["source_ids"], ["S001"])
            self.assertNotIn("lecture.pdf", package["source_ids"])
            self.assertEqual(package["subject"], "medicine")
            self.assertEqual(
                outputs["markdown"].read_text(encoding="utf-8"),
                "# 完整学习资料\n\n## 完整资料\n\nGenerated fact <!-- evidence: E001 -->\n",
            )
            self.assertEqual(quality["metrics"]["referenced_evidence_count"], 1)
            query_builder.assert_called_once()
            self.assertIn("alpha overview", query_builder.call_args.kwargs["source_text"])
            self.assertIn(outline.read_text(encoding="utf-8"), query_builder.call_args.kwargs["outline"])
            self.assertEqual(
                progress_states,
                [
                    JobState.PARSING,
                    JobState.RETRIEVING,
                    JobState.GENERATING,
                    JobState.PACKAGING,
                ],
            )

    @patch("packages.core.jstudy_core.pipeline.extract_pdf_pages")
    @patch("packages.core.jstudy_core.providers.embed_texts")
    def test_run_mvp_uses_runtime_api_key_and_base_urls(self, embed_texts, extract_pdf_pages):
        extract_pdf_pages.return_value = [
            {
                "page": 1,
                "text": "alpha overview: beta detail with enough lecture content for retrieval and evidence citation.",
            }
        ]
        embed_calls = []

        def fake_embed(texts, api_key, model, base_url):
            embed_calls.append((texts, api_key, model, base_url))
            return [[1.0, 0.0] for _ in texts]

        embed_texts.side_effect = fake_embed

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "lecture.pdf"
            soul = root / "soul.md"
            mnemonics = root / "mnemonics.md"
            api_key = root / "api-key.txt"
            output_dir = root / "out"
            pdf.write_bytes(b"%PDF-1.4\n")
            soul.write_text("rules", encoding="utf-8")
            mnemonics.write_text("", encoding="utf-8")
            api_key.write_text("file-key", encoding="utf-8")

            generator_calls = []

            def capture_generator(**kwargs):
                generator_calls.append(kwargs)
                return fake_section_generator(**kwargs)

            with patch(
                "packages.core.jstudy_core.pipeline.build_study_queries",
                return_value=[StudyQuery("sample", "Sample", "alpha overview")],
            ):
                run_mvp(
                    pdf_path=pdf,
                    soul_path=soul,
                    mnemonics_path=mnemonics,
                    api_key_path=api_key,
                    output_dir=output_dir,
                    chat_model="chat",
                    embed_model="embed",
                    output_prefix="case",
                    rag_config=RagConfig(top_k_candidates=1, per_query_limit=1),
                    api_key="runtime-key",
                    chat_base_url="https://chat.example/v1",
                    embed_base_url="https://embed.example/v1",
                    section_generator=capture_generator,
                )

        self.assertTrue(embed_calls)
        self.assertTrue(all(call[1] == "runtime-key" for call in embed_calls))
        self.assertTrue(all(call[3] == "https://embed.example/v1" for call in embed_calls))
        self.assertEqual(len(generator_calls), 1)
        self.assertEqual(generator_calls[0]["api_key"], "runtime-key")
        self.assertEqual(generator_calls[0]["base_url"], "https://chat.example/v1")

    @patch("packages.core.jstudy_core.providers.embed_texts")
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

    def test_audit_output_quality_reports_section_citation_coverage(self):
        markdown = "## Cited\n\nFact. <!-- evidence: E001 -->\n\n## Uncited\n\nExplanation without citation."
        evidence = [{"id": "E001", "page": 1, "chunk_id": "C001", "excerpt": "Fact"}]

        report = audit_output_quality(markdown, evidence)

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["metrics"]["section_count"], 2)
        self.assertEqual(report["metrics"]["cited_section_count"], 1)
        self.assertEqual(report["metrics"]["section_citation_coverage"], 0.5)
        self.assertEqual(report["uncited_sections"], ["Uncited"])
        issue = next(issue for issue in report["issues"] if issue["code"] == "uncited_sections")
        self.assertEqual(issue["severity"], "warning")

    def test_audit_output_quality_ignores_empty_container_headings(self):
        markdown = "# Title\n\n## Cited\n\nFact. <!-- evidence: E001 -->"
        evidence = [{"id": "E001", "page": 1, "chunk_id": "C001", "excerpt": "Fact"}]

        report = audit_output_quality(markdown, evidence)

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["metrics"]["section_count"], 1)
        self.assertEqual(report["uncited_sections"], [])

    def test_build_evidence_links_maps_markdown_refs_to_pdf_targets(self):
        markdown = "Fact A <!-- evidence: E002 E001 -->\n\nFact B <!-- evidence: E001 -->"
        evidence = [
            {
                "id": "E001",
                "source_id": "S001",
                "source_file": "lecture.pdf",
                "page": 3,
                "chunk_id": "C001",
                "excerpt": "alpha",
            },
            {
                "id": "E002",
                "source_id": "S002",
                "source_file": "lecture-02.pdf",
                "page": 7,
                "chunk_id": "C002",
                "excerpt": "beta",
                "relation": "cross_source",
                "navigation_policy": "non_interactive",
            },
        ]

        links = build_evidence_links(markdown, evidence)

        self.assertEqual([link["ref_id"] for link in links], ["E002", "E001", "E001"])
        self.assertEqual(links[0]["target"]["source_id"], "S002")
        self.assertEqual(links[0]["target"]["source_file"], "lecture-02.pdf")
        self.assertEqual(links[0]["target"]["page"], 7)
        self.assertEqual(links[0]["target"]["quote"], "beta")
        self.assertEqual(links[0]["target"]["relation"], "cross_source")
        self.assertEqual(
            links[0]["target"]["navigation_policy"],
            "non_interactive",
        )
        self.assertEqual(links[2]["occurrence"], 2)

    def test_parse_outline_sections_extracts_headings_and_numbered_lines(self):
        sections = parse_outline_sections(
            "# Course\n\n## Unit One\nDetails\n\n1. Unit Two\n2) Unit Three",
            limit=3,
        )

        self.assertEqual([section["id"] for section in sections], ["section-001", "section-002", "section-003"])
        self.assertEqual([section["title"] for section in sections], ["Course", "Unit One", "Unit Two"])
        self.assertEqual([section["order"] for section in sections], [1, 2, 3])

    @patch("packages.core.jstudy_core.pipeline.extract_pdf_pages")
    @patch("packages.core.jstudy_core.providers.embed_texts")
    def test_run_course_outline_writes_multi_source_material_package(self, embed_texts, extract_pdf_pages):
        def fake_pages(pdf_path):
            return [
                {
                    "page": 1,
                    "text": f"{Path(pdf_path).stem} alpha beta content with enough detail for evidence retrieval.",
                }
            ]

        extract_pdf_pages.side_effect = fake_pages
        embed_texts.side_effect = lambda texts, api_key, model, **kwargs: [[1.0, 0.0] for _ in texts]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outline = root / "outline.md"
            pdf_one = root / "lecture-01.pdf"
            pdf_two = root / "lecture-02.pdf"
            soul = root / "soul.md"
            mnemonics = root / "mnemonics.md"
            api_key = root / "api-key.txt"
            output_dir = root / "out"
            cache = root / "cache" / "embeddings.json"
            progress_states = []
            outline.write_text("# Unit One\n\n## Unit Two\n", encoding="utf-8")
            pdf_one.write_bytes(b"%PDF-1.4\n")
            pdf_two.write_bytes(b"%PDF-1.4\n")
            soul.write_text("rules", encoding="utf-8")
            mnemonics.write_text("", encoding="utf-8")
            api_key.write_text("key", encoding="utf-8")

            outputs = run_course_outline(
                outline_path=outline,
                pdf_paths=[pdf_one, pdf_two],
                soul_path=soul,
                mnemonics_path=mnemonics,
                api_key_path=api_key,
                output_dir=output_dir,
                chat_model="chat",
                embed_model="embed",
                output_prefix="course",
                rag_config=RagConfig(top_k_candidates=2, per_query_limit=1),
                embedding_cache_path=cache,
                parser_backend="pymupdf",
                generation_mode="metadata-only",
                package_id="job-course-001",
                section_generator=fake_section_generator,
                progress_callback=progress_states.append,
            )

            package = json.loads(outputs["package"].read_text(encoding="utf-8"))
            evidence = json.loads(outputs["evidence"].read_text(encoding="utf-8"))
            links = json.loads(outputs["evidence_links"].read_text(encoding="utf-8"))
            quality = json.loads(outputs["quality"].read_text(encoding="utf-8"))

        self.assertEqual(package["schema_version"], "material-package.v2")
        self.assertEqual(package["package_id"], "job-course-001")
        self.assertEqual(package["service_mode"], "course_outline")
        self.assertEqual(package["source_ids"], ["S001", "S002"])
        self.assertEqual([section["title"] for section in package["sections"]], ["Unit One", "Unit Two"])
        self.assertEqual(
            [(section["id"], section["order"]) for section in package["sections"]],
            [("section-001", 1), ("section-002", 2)],
        )
        self.assertIn(evidence[0]["source_id"], {"S001", "S002"})
        self.assertIn("source_id", links[0]["target"])
        self.assertEqual(quality["metrics"]["section_count"], 2)
        self.assertEqual(
            progress_states,
            [
                JobState.PARSING,
                JobState.RETRIEVING,
                JobState.GENERATING,
                JobState.PACKAGING,
            ],
        )
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
