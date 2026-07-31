from __future__ import annotations

from dataclasses import asdict, replace
import re
from pathlib import Path
from typing import Any, Callable

from packages.core.jstudy_core import citations
from packages.core.jstudy_core import providers
from packages.core.jstudy_core.courseware import (
    CoursewareManifestV1,
    CoverageLedgerV1,
    LearningMapV1,
)
from packages.core.jstudy_core.documents import ParsedDocument
from packages.core.jstudy_core.settings import read_api_key
from packages.core.jstudy_core.storage import build_output_paths, write_json
from packages.core.jstudy_core.job_system.states import JobState
from packages.core.jstudy_core.materials.compatibility import (
    render_compatibility_markdown,
)
from packages.core.jstudy_core.materials.generation import (
    generate_material_section,
)
from packages.core.jstudy_core.materials.models import (
    MaterialPackageV2,
    MaterialSection,
)
from packages.core.jstudy_core.materials.validation import (
    audit_material_package,
    validate_material_package,
)
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
ProgressCallback = Callable[[JobState], None]
SectionGenerator = Callable[..., MaterialSection]


def _report_progress(
    callback: ProgressCallback | None,
    state: JobState,
) -> None:
    if callback is not None:
        callback(state)


def source_id_for_index(index: int) -> str:
    return f"S{index + 1:03d}"


def _package_subject(routing_metadata: dict[str, Any] | None) -> str:
    subject = str(
        ((routing_metadata or {}).get("scenario") or {}).get("subject") or ""
    ).strip()
    return subject or "medicine"


def _material_package(
    *,
    package_id: str,
    service_mode: str,
    title: str,
    subject: str,
    source_ids: list[str],
    sections: list[MaterialSection],
) -> MaterialPackageV2:
    return MaterialPackageV2(
        schema_version="material-package.v2",
        package_id=package_id,
        service_mode=service_mode,
        title=title,
        subject=subject,
        language="zh-CN",
        source_ids=source_ids,
        sections=sections,
        rendering={
            "default_theme": {
                "theme_id": "clinical-standard",
                "theme_version": "1.0.0",
            }
        },
    )


def _run_sequence_first(
    *,
    service_mode: str,
    parsed_documents: list[ParsedDocument],
    courseware_manifest: CoursewareManifestV1,
    learning_map: LearningMapV1,
    coverage_ledger: CoverageLedgerV1,
    soul_path: Path,
    api_key_path: Path,
    output_dir: Path,
    chat_model: str,
    output_prefix: str,
    api_key: str | None,
    chat_base_url: str,
    routing_metadata: dict[str, Any] | None,
    progress_callback: ProgressCallback | None,
    package_id: str | None,
    section_generator: SectionGenerator | None,
) -> dict[str, Path]:
    if courseware_manifest.service_mode != service_mode:
        raise ValueError("manifest service mode does not match runner")
    if (
        learning_map.manifest_id != courseware_manifest.manifest_id
        or coverage_ledger.manifest_id != courseware_manifest.manifest_id
    ):
        raise ValueError("sequence artifacts do not share one manifest")
    documents = {item.source_id: item for item in parsed_documents}
    if set(documents) != {
        item.source_id for item in courseware_manifest.sources
    }:
        raise ValueError("parsed documents do not match the manifest")

    block_index = {}
    for document in parsed_documents:
        for page in document.pages:
            for block in page.blocks:
                block_index[block.block_id] = (document, page, block)

    _report_progress(progress_callback, JobState.RETRIEVING)
    evidence = []
    evidence_by_unit: dict[str, list[dict[str, Any]]] = {}
    for unit in learning_map.ordered_units():
        unit_evidence = []
        for block_id in unit.block_ids:
            document, page, block = block_index[block_id]
            if document.source_id != unit.primary_source_id:
                raise ValueError("learning unit block source is invalid")
            item = {
                "id": f"E{len(evidence) + 1:03d}",
                "source_id": document.source_id,
                "source_file": document.source_file,
                "page": page.page_number,
                "chunk_id": block.block_id,
                "excerpt": citations.clean_quote(
                    block.text or block.markdown
                ),
                "relation": "primary",
                "navigation_policy": "interactive",
                "learning_unit_id": unit.id,
            }
            evidence.append(item)
            unit_evidence.append(item)
        evidence_by_unit[unit.id] = unit_evidence

    resolved_api_key = api_key or read_api_key(api_key_path)
    soul = soul_path.read_text(encoding="utf-8")
    generate_section = section_generator or generate_material_section
    outline_titles = (
        {
            section.id: section.title
            for section in courseware_manifest.outline.sections
        }
        if courseware_manifest.outline is not None
        else {}
    )
    source_titles = {
        source.source_id: source.display_title
        for source in courseware_manifest.sources
    }
    sections = []
    _report_progress(progress_callback, JobState.GENERATING)
    for unit in learning_map.ordered_units():
        title = outline_titles.get(
            unit.outline_section_id or "",
            (
                f"{source_titles[unit.primary_source_id]} "
                f"第 {unit.page_start}-{unit.page_end} 页"
            ),
        )
        sections.append(
            generate_section(
                section_id=unit.material_section_id,
                order=unit.order,
                title=title,
                soul=soul,
                evidence=evidence_by_unit[unit.id],
                source_ids=[unit.primary_source_id],
                api_key=resolved_api_key,
                model=chat_model,
                base_url=chat_base_url,
            )
        )

    _report_progress(progress_callback, JobState.PACKAGING)
    source_ids = [
        item.source_id for item in courseware_manifest.ordered_sources()
    ]
    package = _material_package(
        package_id=package_id or output_prefix,
        service_mode=service_mode,
        title=(
            "课程学习资料"
            if service_mode == "course_outline"
            else "完整学习资料"
        ),
        subject=_package_subject(routing_metadata),
        source_ids=source_ids,
        sections=sections,
    )
    validate_material_package(package, evidence, source_ids)
    quality = audit_material_package(package, evidence)
    markdown = render_compatibility_markdown(package)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths = build_output_paths(output_dir, output_prefix)
    ordered_blocks = [
        {
            "block_id": block.block_id,
            "source_id": document.source_id,
            "page": page.page_number,
            "kind": block.kind,
        }
        for source in courseware_manifest.ordered_sources()
        for document in [documents[source.source_id]]
        for page in document.pages
        for block in page.blocks
    ]
    write_json(output_paths.chunks, ordered_blocks)
    write_json(
        output_paths.trace,
        {
            "service_mode": service_mode,
            "chat_model": chat_model,
            "scenario": (routing_metadata or {}).get("scenario", {}),
            "parser": {"backend": "mineru"},
            "generation_strategy": "sequence-first",
            "manifest_schema": "courseware-manifest.v1",
            "learning_map_schema": "learning-map.v1",
            "coverage_schema": "coverage-ledger.v1",
            "learning_unit_ids": [
                item.id for item in learning_map.ordered_units()
            ],
        },
    )
    write_json(output_paths.evidence, evidence)
    write_json(output_paths.package, package.model_dump(mode="json"))
    output_paths.markdown.write_text(markdown, encoding="utf-8")
    write_json(
        output_paths.evidence_links,
        citations.build_evidence_links(markdown, evidence),
    )
    write_json(output_paths.quality, quality)
    write_json(
        output_paths.manifest,
        courseware_manifest.model_dump(mode="json"),
    )
    write_json(
        output_paths.learning_map,
        learning_map.model_dump(mode="json"),
    )
    write_json(
        output_paths.coverage,
        coverage_ledger.model_dump(mode="json"),
    )
    return output_paths.as_dict()


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
    progress_callback: ProgressCallback | None = None,
    package_id: str | None = None,
    section_generator: SectionGenerator | None = None,
    parsed_documents: list[ParsedDocument] | None = None,
    courseware_manifest: CoursewareManifestV1 | None = None,
    learning_map: LearningMapV1 | None = None,
    coverage_ledger: CoverageLedgerV1 | None = None,
) -> dict[str, Path]:
    sequence_inputs = (
        parsed_documents,
        courseware_manifest,
        learning_map,
        coverage_ledger,
    )
    if all(item is not None for item in sequence_inputs):
        return _run_sequence_first(
            service_mode="single_courseware",
            parsed_documents=parsed_documents,
            courseware_manifest=courseware_manifest,
            learning_map=learning_map,
            coverage_ledger=coverage_ledger,
            soul_path=soul_path,
            api_key_path=api_key_path,
            output_dir=output_dir,
            chat_model=chat_model,
            output_prefix=output_prefix,
            api_key=api_key,
            chat_base_url=chat_base_url,
            routing_metadata=routing_metadata,
            progress_callback=progress_callback,
            package_id=package_id,
            section_generator=section_generator,
        )
    if any(item is not None for item in sequence_inputs):
        raise ValueError("sequence-first inputs must be provided together")
    rag_config = rag_config or RagConfig()
    embedding_cache_path = embedding_cache_path or output_dir / ".mvp_cache" / "embeddings.json"
    resolved_api_key = api_key or read_api_key(api_key_path)
    _report_progress(progress_callback, JobState.PARSING)
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
        source_id="S001",
        source_file=pdf_path.name,
    )
    if not chunks:
        raise RuntimeError("No text chunks extracted from PDF")

    _report_progress(progress_callback, JobState.RETRIEVING)
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

    _report_progress(progress_callback, JobState.GENERATING)
    generate_section = section_generator or generate_material_section
    section = generate_section(
        section_id="full-material",
        order=1,
        title="完整资料",
        soul=soul_path.read_text(encoding="utf-8"),
        evidence=evidence,
        source_ids=["S001"],
        api_key=resolved_api_key,
        model=chat_model,
        base_url=chat_base_url,
    )
    _report_progress(progress_callback, JobState.PACKAGING)
    package = _material_package(
        package_id=package_id or output_prefix,
        service_mode="single_courseware",
        title="完整学习资料",
        subject=_package_subject(routing_metadata),
        source_ids=["S001"],
        sections=[section],
    )
    validate_material_package(package, evidence, {"S001"})
    quality = audit_material_package(package, evidence)
    markdown = render_compatibility_markdown(package)

    write_json(output_paths.package, package.model_dump(mode="json"))
    output_paths.markdown.write_text(markdown, encoding="utf-8")
    write_json(output_paths.evidence_links, citations.build_evidence_links(markdown, evidence))
    write_json(output_paths.quality, quality)

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
    progress_callback: ProgressCallback | None = None,
    package_id: str | None = None,
    section_generator: SectionGenerator | None = None,
    parsed_documents: list[ParsedDocument] | None = None,
    courseware_manifest: CoursewareManifestV1 | None = None,
    learning_map: LearningMapV1 | None = None,
    coverage_ledger: CoverageLedgerV1 | None = None,
) -> dict[str, Path]:
    sequence_inputs = (
        parsed_documents,
        courseware_manifest,
        learning_map,
        coverage_ledger,
    )
    if all(item is not None for item in sequence_inputs):
        return _run_sequence_first(
            service_mode="course_outline",
            parsed_documents=parsed_documents,
            courseware_manifest=courseware_manifest,
            learning_map=learning_map,
            coverage_ledger=coverage_ledger,
            soul_path=soul_path,
            api_key_path=api_key_path,
            output_dir=output_dir,
            chat_model=chat_model,
            output_prefix=output_prefix,
            api_key=api_key,
            chat_base_url=chat_base_url,
            routing_metadata=routing_metadata,
            progress_callback=progress_callback,
            package_id=package_id,
            section_generator=section_generator,
        )
    if any(item is not None for item in sequence_inputs):
        raise ValueError("sequence-first inputs must be provided together")
    if not pdf_paths:
        raise RuntimeError("Course Outline Mode requires at least one PDF")
    rag_config = rag_config or RagConfig()
    embedding_cache_path = embedding_cache_path or output_dir / ".mvp_cache" / "embeddings.json"
    resolved_api_key = api_key or read_api_key(api_key_path)
    _report_progress(progress_callback, JobState.PARSING)
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

    _report_progress(progress_callback, JobState.RETRIEVING)
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
    package_sections: list[MaterialSection] = []
    soul_text = soul_path.read_text(encoding="utf-8")
    generate_section = section_generator or generate_material_section

    _report_progress(progress_callback, JobState.GENERATING)
    for section, trace in zip(outline_sections, retrieval_trace):
        kept_ids = [str(chunk.get("id", "")) for chunk in trace.get("kept", [])]
        section_evidence = [evidence_by_chunk[chunk_id] for chunk_id in kept_ids if chunk_id in evidence_by_chunk]
        section_source_ids = sorted({str(item.get("source_id", "")) for item in section_evidence if item.get("source_id")})
        package_sections.append(
            generate_section(
                section_id=section["id"],
                order=section["order"],
                title=section["title"],
                soul=soul_text,
                evidence=section_evidence,
                source_ids=section_source_ids,
                api_key=resolved_api_key,
                model=chat_model,
                base_url=chat_base_url,
            )
        )

    _report_progress(progress_callback, JobState.PACKAGING)
    source_ids = [record["source_id"] for record in source_records]
    package = _material_package(
        package_id=package_id or output_prefix,
        service_mode="course_outline",
        title="课程学习资料",
        subject=_package_subject(routing_metadata),
        source_ids=source_ids,
        sections=package_sections,
    )
    validate_material_package(package, evidence, source_ids)
    quality = audit_material_package(package, evidence)
    markdown = render_compatibility_markdown(package)
    output_paths.markdown.write_text(markdown, encoding="utf-8")
    evidence_links = citations.build_evidence_links(markdown, evidence)

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
    write_json(output_paths.package, package.model_dump(mode="json"))
    return output_paths.as_dict()
