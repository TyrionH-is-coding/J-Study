import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MarkdownSection } from "@/features/reader/markdown-section";
import type { EvidenceLink } from "@/lib/api";

describe("MarkdownSection", () => {
  it("resolves a citation through the backend evidence target", () => {
    const target: EvidenceLink["target"] = {
      source_id: "S002",
      source_file: "lecture-two.pdf",
      page: 2,
      chunk_id: "S002-C004",
      quote: "Supporting statement",
    };
    const onCitation = vi.fn();

    render(
      <MarkdownSection
        markdown="Claim <!-- evidence: E001 -->"
        evidenceLinks={[
          { ref_id: "E001", occurrence: 1, comment_index: 1, target },
        ]}
        onCitation={onCitation}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open citation E001" }));
    expect(onCitation).toHaveBeenCalledWith(target);
  });
});
