from __future__ import annotations

import argparse
import re
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from packages.core.jstudy_core import providers
from packages.core.jstudy_core.settings import RuntimeSettings, read_api_key
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


def build_evidence_items(chunks: list[Chunk], source_file: str) -> list[dict[str, Any]]:
    evidence = []
    for idx, chunk in enumerate(chunks, start=1):
        item = {
            "id": f"E{idx:03d}",
            "source_file": source_file,
            "page": chunk.page,
            "chunk_id": chunk.id,
            "score": round(chunk.score, 4),
            "excerpt": chunk.text[:500],
        }
        if chunk.query_id:
            item["query_id"] = chunk.query_id
        if chunk.query_title:
            item["query_title"] = chunk.query_title
        if chunk.retrieval_method:
            item["retrieval_method"] = chunk.retrieval_method
        evidence.append(item)
    return evidence


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


def build_evidence_links(markdown: str, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence_by_id = {str(item.get("id")): item for item in evidence if item.get("id")}
    occurrence_counts: dict[str, int] = {}
    links: list[dict[str, Any]] = []

    for comment_index, match in enumerate(
        re.finditer(r"<!--\s*evidence:\s*([^>]+?)\s*-->", markdown, re.IGNORECASE),
        start=1,
    ):
        for ref_id in re.findall(r"\bE\d{3}\b", match.group(1)):
            item = evidence_by_id.get(ref_id)
            if item is None:
                continue
            occurrence_counts[ref_id] = occurrence_counts.get(ref_id, 0) + 1
            links.append(
                {
                    "ref_id": ref_id,
                    "occurrence": occurrence_counts[ref_id],
                    "comment_index": comment_index,
                    "target": {
                        "source_file": item.get("source_file", ""),
                        "page": item.get("page", ""),
                        "chunk_id": item.get("chunk_id", ""),
                        "quote": item.get("excerpt", ""),
                    },
                }
            )

    return links


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
) -> dict[str, Path]:
    rag_config = rag_config or RagConfig()
    embedding_cache_path = embedding_cache_path or output_dir / ".mvp_cache" / "embeddings.json"
    api_key = read_api_key(api_key_path)
    pages = extract_pdf_pages(pdf_path)
    chunks = chunk_pages(
        pages,
        max_chars=rag_config.chunk_max_chars,
        overlap=rag_config.chunk_overlap,
    )
    if not chunks:
        raise RuntimeError("No text chunks extracted from PDF")

    chunk_embeddings = providers.embed_texts_cached(
        [chunk.text for chunk in chunks],
        api_key=api_key,
        model=embed_model,
        cache_path=embedding_cache_path,
    )

    study_queries = build_study_queries()
    query_embeddings = providers.embed_texts_cached(
        [study_query.query for study_query in study_queries],
        api_key=api_key,
        model=embed_model,
        cache_path=embedding_cache_path,
    )

    selected_chunks, retrieval_trace = select_evidence_chunks(
        study_queries,
        chunks,
        chunk_embeddings,
        query_embeddings,
        rag_config,
    )

    evidence = build_evidence_items(selected_chunks, pdf_path.name)
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
    markdown = providers.generate_markdown(messages, api_key=api_key, model=chat_model)
    output_paths.markdown.write_text(markdown + "\n", encoding="utf-8")
    write_json(output_paths.evidence_links, build_evidence_links(markdown, evidence))
    write_json(output_paths.quality, audit_output_quality(markdown, evidence))

    return output_paths.as_dict()


def parse_args(argv: list[str]) -> argparse.Namespace:
    root = PROJECT_ROOT
    settings = RuntimeSettings.from_env(root)
    parser = argparse.ArgumentParser(description="Run the single-courseware DeepTutor MVP.")
    parser.add_argument("--pdf", type=Path, default=root / "12-球菌.pdf")
    parser.add_argument("--soul", type=Path, default=settings.soul_path)
    parser.add_argument("--mnemonics", type=Path, default=settings.mnemonics_path)
    parser.add_argument("--api-key", type=Path, default=settings.api_key_path)
    parser.add_argument("--outline", type=Path)
    parser.add_argument("--output-dir", type=Path, default=root)
    parser.add_argument("--output-prefix", default="mvp")
    parser.add_argument("--chat-model", default=settings.chat_model)
    parser.add_argument("--embed-model", default=settings.embed_model)
    parser.add_argument("--rag-config", type=Path)
    parser.add_argument("--embedding-cache", type=Path, default=root / ".mvp_cache" / "embeddings.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    outputs = run_mvp(
        pdf_path=args.pdf,
        soul_path=args.soul,
        mnemonics_path=args.mnemonics,
        api_key_path=args.api_key,
        output_dir=args.output_dir,
        chat_model=args.chat_model,
        embed_model=args.embed_model,
        output_prefix=args.output_prefix,
        rag_config=load_rag_config(args.rag_config),
        embedding_cache_path=args.embedding_cache,
        outline_path=args.outline,
    )
    print("MVP outputs:")
    for name, path in outputs.items():
        print(f"- {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
