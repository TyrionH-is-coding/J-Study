from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from packages.core.jstudy_core import citations
from packages.core.jstudy_core import providers
from packages.core.jstudy_core.settings import read_api_key
from packages.core.jstudy_core.storage import build_output_paths, write_json
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
    chat_base_url: str = SILICONFLOW_BASE_URL,
    embed_base_url: str = SILICONFLOW_BASE_URL,
    parser_backend: str = "pymupdf",
    routing_metadata: dict[str, Any] | None = None,
    parser_config: dict[str, Any] | None = None,
) -> dict[str, Path]:
    rag_config = rag_config or RagConfig()
    embedding_cache_path = embedding_cache_path or output_dir / ".mvp_cache" / "embeddings.json"
    resolved_api_key = api_key or read_api_key(api_key_path)
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
        api_key=resolved_api_key,
        model=embed_model,
        cache_path=embedding_cache_path,
        base_url=embed_base_url,
    )

    study_queries = build_study_queries()
    query_embeddings = providers.embed_texts_cached(
        [study_query.query for study_query in study_queries],
        api_key=resolved_api_key,
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
    mnemonics = parse_mnemonics(mnemonics_path.read_text(encoding="utf-8"))
    retrieval_query = "\n".join(study_query.query for study_query in study_queries)
    mnemonic_hits = retrieve_mnemonics(
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
        },
    )
    write_json(output_paths.evidence, evidence)

    messages = build_generation_prompt(
        soul_path.read_text(encoding="utf-8"),
        evidence,
        mnemonic_hits,
        outline=outline_path.read_text(encoding="utf-8") if outline_path else "",
    )
    if chat_base_url == SILICONFLOW_BASE_URL:
        markdown = providers.generate_markdown(messages, api_key=resolved_api_key, model=chat_model)
    else:
        markdown = providers.generate_markdown(
            messages,
            api_key=resolved_api_key,
            model=chat_model,
            base_url=chat_base_url,
        )
    output_paths.markdown.write_text(markdown + "\n", encoding="utf-8")
    write_json(output_paths.evidence_links, citations.build_evidence_links(markdown, evidence))
    write_json(output_paths.quality, audit_output_quality(markdown, evidence))

    return output_paths.as_dict()
