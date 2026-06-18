from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
import re
from typing import Any

from packages.core.jstudy_core import citations
from packages.core.jstudy_core import providers
from packages.core.jstudy_core.settings import read_api_key
from packages.core.jstudy_core.storage import build_output_paths, write_json
from packages.domains import medicine as domain_medicine
from packages.domains import general as domain_general
from packages.domains import engineering as domain_engineering
from packages.domains.medicine import (
    StudyQuery,
    audit_output_quality,
    build_generation_prompt,
    build_study_queries,
    extract_evidence_refs,
    parse_mnemonics,
    retrieve_mnemonics,
)
from packages.parsers.mineru_parser import extract_pdf_pages_with_mineru
from packages.parsers.pymupdf_parser import extract_pdf_pages
from packages.retrieval.hybrid import (
    Chunk,
    DeepTutorRagAdapter,
    RagConfig,
    chunk_pages,
    cosine_similarity,
    filter_ranked_chunks,
    is_low_value_chunk,
    load_rag_config,
    reciprocal_rank_fusion,
    select_evidence_chunks,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CHAT_MODEL = providers.DEFAULT_CHAT_MODEL
DEFAULT_EMBED_MODEL = providers.DEFAULT_EMBED_MODEL
SILICONFLOW_BASE_URL = providers.SILICONFLOW_BASE_URL
siliconflow_post = providers.siliconflow_post
embed_texts = providers.embed_texts
embedding_cache_key = providers.embedding_cache_key
embed_texts_cached = providers.embed_texts_cached
generate_markdown = providers.generate_markdown
build_evidence_items = citations.build_evidence_items
build_evidence_links = citations.build_evidence_links


DOMAIN_MODULES = {
    "medicine": domain_medicine,
    "general": domain_general,
    "engineering": domain_engineering,
}


def _resolve_domain(routing_metadata: dict[str, Any] | None) -> Any:
    """Select domain module based on scenario domain_rules."""
    rules = (routing_metadata or {}).get("scenario", {}).get("domain_rules", [])
    primary = rules[0] if rules else "medicine"
    return DOMAIN_MODULES.get(primary, domain_medicine)


def retrieve_chunks(
    query: str,
    chunks: list[Chunk],
    chunk_embeddings: list[list[float]],
    api_key: str,
    model: str = DEFAULT_EMBED_MODEL,
    top_k: int = 18,
) -> list[Chunk]:
    query_embedding = providers.embed_texts([query], api_key=api_key, model=model)[0]
    scored = [
        replace(
            chunk,
            score=cosine_similarity(query_embedding, embedding),
            embedding_index=index,
        )
        for index, (chunk, embedding) in enumerate(zip(chunks, chunk_embeddings))
    ]
    return sorted(scored, key=lambda chunk: chunk.score, reverse=True)[:top_k]


def parse_outline_sections(outline_text: str) -> list[dict[str, Any]]:
    """Parse markdown outline into a list of section headings.

    Returns [{title, level}] where level is the heading depth (1=#, 2=##, etc.).
    Falls back to numbered lines (\"1. Topic\", \"一、Topic\") when no markdown headers found.
    Returns empty list when no sections can be parsed.
    """
    sections: list[dict[str, Any]] = []
    for line in outline_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            level = 0
            for ch in stripped:
                if ch == "#":
                    level += 1
                else:
                    break
            title = stripped[level:].strip()
            if title:
                sections.append({"title": title, "level": level})
        # Fallback: numbered list items as level-1 headings
        elif re.match(r"^\d+[.．、)]\s", stripped) or re.match(
            r"^[一二三四五六七八九十百]+[.、]", stripped
        ):
            sections.append({"title": stripped, "level": 1})

    return sections


def run_mvp(
    pdf_path: Path,
    soul_path: Path,
    mnemonics_path: Path,
    api_key_path: Path,
    output_dir: Path,
    chat_model: str,
    embed_model: str,
    output_prefix: str = "mvp",
    rag_config: RagConfig | None = None,
    embedding_cache_path: Path | None = None,
    outline_path: Path | None = None,
    api_key: str | None = None,
    embed_api_key: str | None = None,
    chat_base_url: str = SILICONFLOW_BASE_URL,
    embed_base_url: str = SILICONFLOW_BASE_URL,
    parser_backend: str = "pymupdf",
    soul_profile_id: str | None = None,
    routing_metadata: dict[str, Any] | None = None,
    parser_config: dict[str, Any] | None = None,
    generation_mode: str | None = None,
) -> dict[str, Path]:
    rag_config = rag_config or RagConfig()
    embedding_cache_path = embedding_cache_path or output_dir / ".mvp_cache" / "embeddings.json"
    resolved_api_key = api_key or read_api_key(api_key_path)
    resolved_embed_key = embed_api_key or resolved_api_key
    domain = _resolve_domain(routing_metadata)

    if parser_backend == "pymupdf":
        pages = extract_pdf_pages(pdf_path)
    elif parser_backend == "mineru":
        pages = extract_pdf_pages_with_mineru(pdf_path, parser_config or {})
    else:
        raise RuntimeError(f"Unknown parser backend: {parser_backend}")
    chunks = chunk_pages(
        pages,
        max_chars=rag_config.chunk_max_chars,
        overlap=rag_config.chunk_overlap,
    )
    if not chunks:
        raise RuntimeError("No text chunks extracted from PDF")

    chunk_embeddings = providers.embed_texts_cached(
        [chunk.text for chunk in chunks],
        api_key=resolved_embed_key,
        model=embed_model,
        cache_path=embedding_cache_path,
        base_url=embed_base_url,
    )

    outline_text = outline_path.read_text(encoding="utf-8") if outline_path else ""
    study_queries = domain.build_study_queries(
        source_text="\n".join(chunk.text for chunk in chunks),
        outline=outline_text,
    )
    query_embeddings = providers.embed_texts_cached(
        [study_query.query for study_query in study_queries],
        api_key=resolved_embed_key,
        model=embed_model,
        cache_path=embedding_cache_path,
        base_url=embed_base_url,
    )

    selected_chunks, retrieval_trace = select_evidence_chunks(
        study_queries,
        chunks,
        chunk_embeddings,
        query_embeddings,
        rag_config,
    )

    evidence = citations.build_evidence_items(selected_chunks, pdf_path.name)
    mnemonics = domain.parse_mnemonics(mnemonics_path.read_text(encoding="utf-8"))
    retrieval_query = "\n".join(study_query.query for study_query in study_queries)
    mnemonic_hits = domain.retrieve_mnemonics(
        retrieval_query + "\n" + "\n".join(chunk.text for chunk in selected_chunks),
        mnemonics,
        limit=rag_config.mnemonic_limit,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths = build_output_paths(output_dir, output_prefix)

    write_json(
        output_paths.chunks,
        [
            {
                **asdict(chunk),
                "embedding_saved": False,
            }
            for chunk in chunks
        ],
    )
    write_json(
        output_paths.trace,
        {
            "pdf": str(pdf_path),
            "chat_model": chat_model,
            "embed_model": embed_model,
            "scenario": (routing_metadata or {}).get("scenario", {}),
            "parser_profile": (routing_metadata or {}).get("parser_profile", {}),
            "parser": {"backend": parser_backend},
            "rag_config": asdict(rag_config),
            "embedding_cache": str(embedding_cache_path),
            "retrieval_strategy": "deeptutor-style multi-query hybrid reciprocal-rank fusion",
            "study_queries": [asdict(study_query) for study_query in study_queries],
            "retrieval_query_text": retrieval_query,
            "selected_chunks": [asdict(chunk) for chunk in selected_chunks],
            "query_traces": retrieval_trace,
            "mnemonic_hits": mnemonic_hits,
            "generation_mode": generation_mode or "summary",
            "domain": _resolve_domain(routing_metadata).__name__,
        },
    )
    write_json(output_paths.evidence, evidence)

    # --- Outline-driven sectional generation or single-pass fallback ---
    sections = parse_outline_sections(outline_text) if outline_text else []
    soul_text = soul_path.read_text(encoding="utf-8")

    if len(sections) >= 2:
        section_outputs: list[dict[str, Any]] = []

        for i, section in enumerate(sections):
            section_title = section["title"]
            # Per-section evidence: retrieve top-K chunks focused on this section title
            section_chunks = retrieve_chunks(
                section_title, chunks, chunk_embeddings,
                api_key=resolved_embed_key, model=embed_model,
                top_k=rag_config.evidence_per_query or 8,
            )
            section_chunk_ids = {c.id for c in section_chunks}
            section_evidence = [
                item for item in evidence if item["chunk_id"] in section_chunk_ids
            ]
            # Fallback: if no direct evidence match, use first 3 global evidence items
            if not section_evidence:
                section_evidence = evidence[:3]

            section_messages = domain.build_generation_prompt(
                soul_text, section_evidence, mnemonic_hits,
                outline=outline_text, mode=generation_mode or "",
                section_title=section_title,
            )
            section_md = providers.generate_markdown(
                section_messages,
                api_key=resolved_api_key, model=chat_model,
                base_url=chat_base_url, max_tokens=4000,
            )

            slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", section_title).strip("-")[:30]
            section_dir = output_dir / "sections" / f"{i:02d}-{slug}"
            section_dir.mkdir(parents=True, exist_ok=True)
            (section_dir / "markdown.md").write_text(section_md + "\n", encoding="utf-8")
            write_json(section_dir / "evidence.json", section_evidence)

            section_outputs.append({
                "title": section_title,
                "level": section.get("level", 1),
                "markdown": section_md,
            })

        # Merge: table of contents + concatenated sections
        merged_parts: list[str] = ["# 目录\n"]
        for i, sec in enumerate(section_outputs):
            merged_parts.append(f"- [{sec['title']}](#{sec['title']})")
        merged_parts.append("")
        merged_parts.append("---\n")
        for sec in section_outputs:
            heading_level = min(sec["level"], 2)
            merged_parts.append(f"{'#' * heading_level} {sec['title']}\n")
            merged_parts.append(sec["markdown"])
            merged_parts.append("")
            merged_parts.append("---")

        merged_md = "\n".join(merged_parts)

        # Save section index metadata
        sections_meta = [
            {
                "index": i,
                "title": s["title"],
                "level": s.get("level", 1),
                "slug": re.sub(r"[^\w\u4e00-\u9fff]+", "-", s["title"]).strip("-")[:30],
            }
            for i, s in enumerate(sections)
        ]
        write_json(output_dir / "result-sections.json", sections_meta)
    else:
        # --- Single-pass generation (original path, no outline or <2 sections) ---
        messages = domain.build_generation_prompt(
            soul_text, evidence, mnemonic_hits,
            outline=outline_text, mode=generation_mode or "",
        )
        if chat_base_url == SILICONFLOW_BASE_URL:
            merged_md = providers.generate_markdown(messages, api_key=resolved_api_key, model=chat_model)
        else:
            merged_md = providers.generate_markdown(
                messages,
                api_key=resolved_api_key,
                model=chat_model,
                base_url=chat_base_url,
            )

    output_paths.markdown.write_text(merged_md + "\n", encoding="utf-8")
    write_json(output_paths.evidence_links, citations.build_evidence_links(merged_md, evidence))
    write_json(output_paths.quality, domain.audit_output_quality(merged_md, evidence))

    return output_paths.as_dict()
