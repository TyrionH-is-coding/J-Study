import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SourcePreview } from "@/features/source-preview/source-preview";
import { getSourcePdfInfo } from "@/lib/api";
import { renderWithQuery } from "@/test/render";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getSourcePdfInfo: vi.fn(),
}));

describe("SourcePreview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("uses source_id and scrolls only its own preview for citation jumps", async () => {
    vi.mocked(getSourcePdfInfo).mockResolvedValue({
      source_id: "S002",
      page_count: 3,
      pages: [
        { page: 1, width: 612, height: 792 },
        { page: 2, width: 612, height: 792 },
        { page: 3, width: 612, height: 792 },
      ],
    });
    const elementScrollTo = vi.fn();
    HTMLElement.prototype.scrollTo = elementScrollTo;
    const windowScrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => {});

    renderWithQuery(
      <SourcePreview
        jobId="job-123"
        sources={[
          { source_id: "S001", file_name: "duplicate.pdf" },
          { source_id: "S002", file_name: "duplicate.pdf" },
        ]}
        citation={{
          source_id: "S002",
          source_file: "duplicate.pdf",
          page: 2,
          chunk_id: "S002-C004",
          quote: "Supporting statement",
        }}
      />,
    );

    await waitFor(() => {
      expect(getSourcePdfInfo).toHaveBeenCalledWith("job-123", "S002");
      expect(screen.getByAltText("duplicate.pdf page 2")).toBeInTheDocument();
      expect(elementScrollTo).toHaveBeenCalled();
    });
    expect(windowScrollTo).not.toHaveBeenCalled();
  });
});
