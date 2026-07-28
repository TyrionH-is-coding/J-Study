from __future__ import annotations

from dataclasses import asdict, replace
import re
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


OUTLINE_SECTION_LIMIT = 12


def source_id_for_index(index: int) -> str:
    return f"S{index + 1:03d}"


def extract_pages_with_backend(
    pdf_path: Path,
    parser_backend: str,
    parser_config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if parser_backend == "pymupdf":
        return extract_pdf_pages(pdf_path)
    if parser_backend == "mineru":
        return extract_pdf_pages_with_mineru(pdf_path, parser_config or {})
    raise RuntimeError(f"Unknown parser backend: {parser_backend}")


def read_outline_text(
    outline_path: Path,
    parser_backend: str = "pymupdf",
    parser_config: dict[str, Any] | None = None,
) -> str:
    if outline_path.suffix.lower() == ".pdf":
        pages = extract_pages_with_backend(outline_path, parser_backend, parser_config)
        return "\n".join(str(page.get("text", "")) for page in pages)
    return outline_path.read_text(encoding="utf-8")


def parse_outline_sections(outline_text: str, limit: int = OUTLINE_SECTION_LIMIT) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for raw_line in outline_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        title = ""
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        numbered = re.match(r"^(?:\d+[.)]|[A-Za-z][.)])\s+(.+)$", line)
        if heading:
            title = heading.group(2).strip()
        elif numbered:
            title = numbered.group(1).strip()
        if not title:
            continue
        order = len(sections) + 1
        sections.append(
            {
                "id": f"section-{order:03d}",
                "title": title[:120],
                "order": order,
                "raw_text": line,
            }
        )
        if len(sections) >= limit:
            break
    if not sections:
        raise RuntimeError("Course outline contains no usable sections")
    return sections

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
    generation_mode: str = "",
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

    outline_text = outline_path.read_text(encoding="utf-8") if outline_path else ""
    study_queries = build_study_queries(
        source_text="\n".join(chunk.text for chunk in chunks),
        outline=outline_text,
    )
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

    package = {
        "type": "material_package",
        "service_mode": "single_courseware",
        "generation_mode": generation_mode or "",
        "source_files": [
            {
                "file_name": pdf_path.name,
                "parser_backend": parser_backend,
            }
        ],
        "sections": [
            {
                "id": "full-material",
                "title": "完整资料",
                "order": 1,
                "source_files": [pdf_path.name],
                "evidence_ids": [item["id"] for item in evidence],
                "artifact_urls": {
                    "markdown": output_paths.markdown.name,
                    "evidence": output_paths.evidence.name,
                    "evidence_links": output_paths.evidence_links.name,
                    "quality": output_paths.quality.name,
                },
            }
        ],
    }
    write_json(output_paths.package, package)

    messages = build_generation_prompt(
        soul_path.read_text(encoding="utf-8"),
        evidence,
        mnemonic_hits,
        outline=outline_text,
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


def run_course_outline(
    outline_path: Path,
    pdf_paths: list[Path],
    soul_path: Path,
    mnemonics_path: Path,
    api_key_path: Path,
    output_dir: Path,
    chat_model: str,
    embed_model: str,
    output_prefix: str = "mvp",
    rag_config: RagConfig | None = None,
    embedding_cache_path: Path | None = None,
    api_key: str | None = None,
    chat_base_url: str = SILICONFLOW_BASE_URL,
    embed_base_url: str = SILICONFLOW_BASE_URL,
    parser_backend: str = "pymupdf",
    routing_metadata: dict[str, Any] | None = None,
    parser_config: dict[str, Any] | None = None,
    generation_mode: str = "",
    source_files: list[dict[str, Any]] | None = None,
    service_mode: str = "course_outline",
) -> dict[str, Path]:
    if not pdf_paths:
        raise RuntimeError("Course Outline Mode requires at least one PDF")
    rag_config = rag_config or RagConfig()
    embedding_cache_path = embedding_cache_path or output_dir / ".mvp_cache" / "embeddings.json"
    resolved_api_key = api_key or read_api_key(api_key_path)
    outline_text = read_outline_text(outline_path, parser_backend, parser_config)
    outline_sections = parse_outline_sections(outline_text)

    chunks: list[Chunk] = []
    source_records: list[dict[str, Any]] = []
    for index, pdf_path in enumerate(pdf_paths):
        source_id = source_id_for_index(index)
        pages = extract_pages_with_backend(pdf_path, parser_backend, parser_config)
        record = {
            "source_id": source_id,
            "file_name": pdf_path.name,
            "page_count": len(pages),
            "parser_backend": parser_backend,
        }
        if source_files and index < len(source_files):
            record = {**source_files[index], **record}
        source_records.append(record)
        chunks.extend(
            chunk_pages(
                pages,
                max_chars=rag_config.chunk_max_chars,
                overlap=rag_config.chunk_overlap,
                source_id=source_id,
                source_file=pdf_path.name,
            )
        )
    if not chunks:
        raise RuntimeError("No text chunks extracted from course PDFs")

    chunk_embeddings = providers.embed_texts_cached(
        [chunk.text for chunk in chunks],
        api_key=resolved_api_key,
        model=embed_model,
        cache_path=embedding_cache_path,
        base_url=embed_base_url,
    )
    study_queries = [
        StudyQuery(
            id=section["id"],
            title=section["title"],
            query=f"{section['title']}\n{section.get('raw_text', '')}",
        )
        for section in outline_sections
    ]
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
    evidence = citations.build_evidence_items(selected_chunks, "")
    evidence_by_chunk = {item["chunk_id"]: item for item in evidence}

    mnemonics = parse_mnemonics(mnemonics_path.read_text(encoding="utf-8"))
    mnemonic_hits = retrieve_mnemonics(
        outline_text + "\n" + "\n".join(chunk.text for chunk in selected_chunks),
        mnemonics,
        limit=rag_config.mnemonic_limit,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths = build_output_paths(output_dir, output_prefix)
    section_markdown_parts: list[str] = []
    package_sections: list[dict[str, Any]] = []
    soul_text = soul_path.read_text(encoding="utf-8")

    for section, trace in zip(outline_sections, retrieval_trace):
        kept_ids = [str(chunk.get("id", "")) for chunk in trace.get("kept", [])]
        section_evidence = [evidence_by_chunk[chunk_id] for chunk_id in kept_ids if chunk_id in evidence_by_chunk]
        if section_evidence:
            messages = build_generation_prompt(
                soul_text,
                section_evidence,
                mnemonic_hits,
                outline=section.get("raw_text", ""),
            )
            if chat_base_url == SILICONFLOW_BASE_URL:
                section_markdown = providers.generate_markdown(messages, api_key=resolved_api_key, model=chat_model)
            else:
                section_markdown = providers.generate_markdown(
                    messages,
                    api_key=resolved_api_key,
                    model=chat_model,
                    base_url=chat_base_url,
                )
            status = "generated"
        else:
            section_markdown = "Evidence for this outline section is currently weak."
            status = "weak_evidence"
        section_markdown_parts.append(f"## {section['title']}\n\n{section_markdown.strip()}")
        section_source_ids = sorted({str(item.get("source_id", "")) for item in section_evidence if item.get("source_id")})
        package_sections.append(
            {
                "id": section["id"],
                "title": section["title"],
                "order": section["order"],
                "status": status,
                "quality": {"evidence_count": len(section_evidence)},
                "source_files": section_source_ids,
                "evidence_ids": [item["id"] for item in section_evidence],
                "artifact_filenames": {
                    "markdown": output_paths.markdown.name,
                    "evidence": output_paths.evidence.name,
                    "evidence_links": output_paths.evidence_links.name,
                    "quality": output_paths.quality.name,
                    "package": output_paths.package.name,
                },
            }
        )

    markdown = "\n\n".join(section_markdown_parts)
    output_paths.markdown.write_text(markdown + "\n", encoding="utf-8")
    evidence_links = citations.build_evidence_links(markdown, evidence)
    quality = audit_output_quality(markdown, evidence)

    write_json(output_paths.chunks, [{**asdict(chunk), "embedding_saved": False} for chunk in chunks])
    write_json(
        output_paths.trace,
        {
            "service_mode": service_mode,
            "outline": str(outline_path),
            "pdfs": [str(path) for path in pdf_paths],
            "source_files": source_records,
            "chat_model": chat_model,
            "embed_model": embed_model,
            "scenario": (routing_metadata or {}).get("scenario", {}),
            "parser_profile": (routing_metadata or {}).get("parser_profile", {}),
            "parser": {"backend": parser_backend},
            "rag_config": asdict(rag_config),
            "embedding_cache": str(embedding_cache_path),
            "retrieval_strategy": "outline-section hybrid retrieval across source PDFs",
            "outline_sections": outline_sections,
            "study_queries": [asdict(study_query) for study_query in study_queries],
            "selected_chunks": [asdict(chunk) for chunk in selected_chunks],
            "query_traces": retrieval_trace,
            "mnemonic_hits": mnemonic_hits,
        },
    )
    write_json(output_paths.evidence, evidence)
    write_json(output_paths.evidence_links, evidence_links)
    write_json(output_paths.quality, quality)
    write_json(
        output_paths.package,
        {
            "type": "material_package",
            "service_mode": "course_outline",
            "generation_mode": generation_mode or "",
            "source_files": source_records,
            "sections": package_sections,
        },
    )
    return output_paths.as_dict()