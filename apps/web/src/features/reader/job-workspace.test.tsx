import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { JobWorkspace } from "@/features/reader/job-workspace";
import {
  getJob,
  getJobEvidenceLinks,
  getJobOutput,
  getJobPackage,
  getJobSources,
  getSourcePdfInfo,
} from "@/lib/api";
import { renderWithQuery } from "@/test/render";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getJob: vi.fn(),
  getJobOutput: vi.fn(),
  getJobPackage: vi.fn(),
  getJobEvidenceLinks: vi.fn(),
  getJobSources: vi.fn(),
  getSourcePdfInfo: vi.fn(),
}));

describe("JobWorkspace", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads the completed material package and marks weak evidence", async () => {
    vi.mocked(getJob).mockResolvedValue({
      job_id: "job-123",
      status: "completed",
      error: "",
      quality: {},
      service_mode: "course_outline",
      source_files: [{ source_id: "S001", file_name: "lecture.pdf", page_count: 1 }],
      output_url: "/api/jobs/job-123/output",
      evidence_url: "/api/jobs/job-123/evidence",
      evidence_links_url: "/api/jobs/job-123/evidence-links",
      trace_url: "/api/jobs/job-123/trace",
      package_url: "/api/jobs/job-123/package",
      export_url: "/api/jobs/job-123/export",
      pdfs_url: "/api/jobs/job-123/pdfs",
      source_pdf_url_template: "",
      source_pdf_info_url_template: "",
      source_pdf_page_url_template: "",
    });
    vi.mocked(getJobPackage).mockResolvedValue({
      type: "material_package",
      service_mode: "course_outline",
      generation_mode: "",
      source_files: [{ source_id: "S001", file_name: "lecture.pdf", page_count: 1 }],
      sections: [{ id: "section-001", title: "Unit One", order: 1, status: "weak_evidence", quality: { evidence_count: 0 }, source_files: [], evidence_ids: [], artifact_filenames: {} }],
    });
    vi.mocked(getJobOutput).mockResolvedValue({ markdown: "## Unit One\n\nEvidence is limited." });
    vi.mocked(getJobEvidenceLinks).mockResolvedValue([]);
    vi.mocked(getJobSources).mockResolvedValue({ source_files: [{ source_id: "S001", file_name: "lecture.pdf", page_count: 1 }] });
    vi.mocked(getSourcePdfInfo).mockResolvedValue({ source_id: "S001", page_count: 1, pages: [{ page: 1, width: 612, height: 792 }] });

    renderWithQuery(<JobWorkspace jobId="job-123" />);

    await waitFor(() => expect(screen.getByRole("heading", { level: 1, name: "Unit One" })).toBeInTheDocument());
    expect(screen.getByText("Weak evidence")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Export Markdown" })).toHaveAttribute("href", "/api/jobs/job-123/export");
    expect(screen.getByText("S001")).toBeInTheDocument();
  });

  it("shows the backend failure without loading reader artifacts", async () => {
    vi.mocked(getJob).mockResolvedValue({
      job_id: "job-failed",
      status: "failed",
      error: "RuntimeError: generation stopped",
      quality: {},
      service_mode: "course_outline",
      source_files: [],
      output_url: "",
      evidence_url: "",
      evidence_links_url: "",
      trace_url: "",
      package_url: "",
      export_url: "",
      pdfs_url: "",
      source_pdf_url_template: "",
      source_pdf_info_url_template: "",
      source_pdf_page_url_template: "",
    });

    renderWithQuery(<JobWorkspace jobId="job-failed" />);

    expect(await screen.findByText("Generation failed")).toBeInTheDocument();
    expect(screen.getByText("RuntimeError: generation stopped")).toBeInTheDocument();
    expect(getJobPackage).not.toHaveBeenCalled();
  });
});
