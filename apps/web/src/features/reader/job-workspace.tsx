"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Download, Loader2, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  getJob,
  getJobEvidenceLinks,
  getJobOutput,
  getJobPackage,
  getJobSources,
  jobExportUrl,
} from "@/lib/api";
import type { EvidenceTarget } from "@/lib/api";
import { SourcePreview } from "@/features/source-preview/source-preview";
import { MarkdownSection } from "./markdown-section";
import { splitMarkdownBySections } from "./markdown";

export function JobWorkspace({ jobId }: { jobId: string }) {
  const [sectionId, setSectionId] = useState("");
  const [citation, setCitation] = useState<EvidenceTarget | null>(null);
  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 1200;
    },
  });
  const isComplete = jobQuery.data?.status === "completed";
  const packageQuery = useQuery({ queryKey: ["job-package", jobId], queryFn: () => getJobPackage(jobId), enabled: isComplete });
  const outputQuery = useQuery({ queryKey: ["job-output", jobId], queryFn: () => getJobOutput(jobId), enabled: isComplete });
  const evidenceQuery = useQuery({ queryKey: ["job-evidence-links", jobId], queryFn: () => getJobEvidenceLinks(jobId), enabled: isComplete });
  const sourcesQuery = useQuery({ queryKey: ["job-sources", jobId], queryFn: () => getJobSources(jobId), enabled: isComplete });

  const sections = useMemo(
    () => splitMarkdownBySections(outputQuery.data?.markdown ?? "", packageQuery.data?.sections ?? []),
    [outputQuery.data?.markdown, packageQuery.data?.sections],
  );
  const selectedSection = sections.find((section) => section.id === sectionId) ?? sections[0];
  const sources = sourcesQuery.data?.source_files ?? packageQuery.data?.source_files ?? jobQuery.data?.source_files ?? [];

  if (jobQuery.isLoading) return <JobProgress title="Opening job" detail="Checking the latest backend state." />;
  if (jobQuery.error) return <JobError title="Unable to open job" detail={jobQuery.error.message} onRetry={() => jobQuery.refetch()} />;
  if (jobQuery.data?.status === "failed") return <JobError title="Generation failed" detail={jobQuery.data.error || "The backend did not provide an error message."} onRetry={() => jobQuery.refetch()} />;
  if (!isComplete) {
    return <JobProgress title={jobQuery.data?.status === "running" ? "Building course material" : "Job queued"} detail="The workspace will open automatically when the material package is ready." />;
  }
  if (packageQuery.isLoading || outputQuery.isLoading || evidenceQuery.isLoading || sourcesQuery.isLoading) {
    return <JobProgress title="Preparing reader" detail="Loading sections, citations, and source PDFs." />;
  }
  const artifactError = packageQuery.error || outputQuery.error || evidenceQuery.error || sourcesQuery.error;
  if (artifactError) return <JobError title="Reader artifacts unavailable" detail={artifactError.message} onRetry={() => { packageQuery.refetch(); outputQuery.refetch(); evidenceQuery.refetch(); sourcesQuery.refetch(); }} />;
  if (!selectedSection) return <JobError title="No sections found" detail="The material package completed without readable section metadata." onRetry={() => packageQuery.refetch()} />;

  return (
    <main className="reader-shell" data-testid="app-shell">
      <header className="reader-header">
        <div>
          <span className="eyebrow"><CheckCircle2 size={14} /> Course Outline complete</span>
          <h1>{selectedSection.title}</h1>
        </div>
        <a className={buttonVariants({ variant: "outline" })} href={jobExportUrl(jobId)}><Download /> Export Markdown</a>
      </header>
      <div className="reader-grid">
        <aside className="reader-index" aria-label="Material navigation">
          <div className="index-block">
            <span className="panel-label">Sections</span>
            <nav>
              {sections.map((section) => (
                <button key={section.id} type="button" className={section.id === selectedSection.id ? "active" : ""} onClick={() => setSectionId(section.id)}>
                  <span className="section-order">{String(section.order).padStart(2, "0")}</span>
                  <span>{section.title}</span>
                  {section.status === "weak_evidence" && <AlertTriangle aria-label="Weak evidence" />}
                </button>
              ))}
            </nav>
          </div>
          <div className="index-block sources-index">
            <span className="panel-label">Sources</span>
            <ul>{sources.map((source) => <li key={source.source_id}><span>{source.source_id}</span><span title={source.file_name}>{source.file_name}</span></li>)}</ul>
          </div>
        </aside>
        <article className="material-pane">
          <div className="material-heading">
            <div>
              <span>Section {selectedSection.order}</span>
              <h2>{selectedSection.title}</h2>
            </div>
            {selectedSection.status === "weak_evidence" && <Badge variant="outline" className="weak-badge"><AlertTriangle /> Weak evidence</Badge>}
          </div>
          <MarkdownSection markdown={selectedSection.markdown} evidenceLinks={evidenceQuery.data ?? []} onCitation={setCitation} />
        </article>
        <SourcePreview key={citation ? `${citation.source_id}-${citation.page}-${citation.chunk_id}` : "source-preview"} jobId={jobId} sources={sources} citation={citation} />
      </div>
    </main>
  );
}

function JobProgress({ title, detail }: { title: string; detail: string }) {
  return <main className="job-state"><div className="job-state-icon"><Loader2 className="animate-spin" /></div><span className="eyebrow">Generation pipeline</span><h1>{title}</h1><p>{detail}</p><Progress value={58} className="job-progress" /></main>;
}

function JobError({ title, detail, onRetry }: { title: string; detail: string; onRetry: () => void }) {
  return <main className="job-state"><Alert variant="destructive"><AlertTriangle /><AlertTitle>{title}</AlertTitle><AlertDescription>{detail}</AlertDescription></Alert><Button type="button" variant="outline" onClick={onRetry}><RefreshCw /> Check again</Button></main>;
}
