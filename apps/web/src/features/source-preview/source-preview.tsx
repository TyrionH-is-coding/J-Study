/* eslint-disable @next/next/no-img-element */
"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, FileSearch } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { getSourcePdfInfo, sourcePageUrl } from "@/lib/api";
import type { EvidenceTarget, SourceFile } from "@/lib/api";

interface SourcePreviewProps {
  jobId: string;
  sources: SourceFile[];
  citation?: EvidenceTarget | null;
}

export function SourcePreview({ jobId, sources, citation }: SourcePreviewProps) {
  const [sourceId, setSourceId] = useState(citation?.source_id || sources[0]?.source_id || "");
  const [page, setPage] = useState(citation?.page || 1);
  const scrollRef = useRef<HTMLDivElement>(null);
  const selectedSource = sources.find((source) => source.source_id === sourceId) ?? sources[0];
  const infoQuery = useQuery({
    queryKey: ["source-pdf-info", jobId, selectedSource?.source_id],
    queryFn: () => getSourcePdfInfo(jobId, selectedSource!.source_id),
    enabled: Boolean(selectedSource),
  });

  useEffect(() => {
    if (citation) scrollRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }, [citation]);

  if (!selectedSource) {
    return <div className="source-empty"><FileSearch /><p>No source PDFs are available.</p></div>;
  }

  const pageCount = infoQuery.data?.page_count ?? selectedSource.page_count ?? 1;
  const visiblePage = Math.min(page, pageCount);

  return (
    <section className="source-preview" aria-label="Source PDF preview">
      <div className="source-toolbar">
        <label htmlFor="source-select">Source</label>
        <select id="source-select" value={selectedSource.source_id} onChange={(event) => { setSourceId(event.target.value); setPage(1); }}>
          {sources.map((source) => <option key={source.source_id} value={source.source_id}>{source.source_id} · {source.file_name}</option>)}
        </select>
        <div className="page-controls">
          <Button type="button" variant="outline" size="icon-sm" aria-label="Previous page" disabled={visiblePage <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}><ChevronLeft /></Button>
          <span>Page {visiblePage} / {pageCount}</span>
          <Button type="button" variant="outline" size="icon-sm" aria-label="Next page" disabled={visiblePage >= pageCount} onClick={() => setPage((current) => Math.min(pageCount, current + 1))}><ChevronRight /></Button>
        </div>
      </div>
      <div className="source-scroll" ref={scrollRef} data-testid="source-preview-scroll">
        {infoQuery.isLoading ? <div className="preview-loading">Loading source page…</div> : (
          <img src={sourcePageUrl(jobId, selectedSource.source_id, visiblePage)} alt={`${selectedSource.file_name} page ${visiblePage}`} />
        )}
        {citation?.source_id === selectedSource.source_id && citation.page === visiblePage && (
          <aside className="citation-context"><strong>{citation.chunk_id}</strong><p>{citation.quote}</p></aside>
        )}
      </div>
    </section>
  );
}
