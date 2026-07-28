import { describe, expect, it } from "vitest";

import {
  replaceEvidenceComments,
  splitMarkdownBySections,
} from "@/features/reader/markdown";
import type { MaterialSection } from "@/lib/api";

const sections: MaterialSection[] = [
  {
    id: "section-001",
    title: "Unit One",
    order: 1,
    status: "generated",
    quality: { evidence_count: 1 },
    source_files: ["S001"],
    evidence_ids: ["E001"],
    artifact_filenames: {},
  },
  {
    id: "section-002",
    title: "Unit Two",
    order: 2,
    status: "weak_evidence",
    quality: { evidence_count: 0 },
    source_files: [],
    evidence_ids: [],
    artifact_filenames: {},
  },
];

describe("reader markdown", () => {
  it("splits the full output by package section order", () => {
    const markdown = [
      "## Unit One",
      "",
      "First body.",
      "",
      "## Unit Two",
      "",
      "Second body.",
    ].join("\n");

    const result = splitMarkdownBySections(markdown, sections);

    expect(result.map((item) => item.id)).toEqual(["section-001", "section-002"]);
    expect(result[0].markdown).toContain("First body.");
    expect(result[0].markdown).not.toContain("Second body.");
    expect(result[1].markdown).toContain("Second body.");
  });

  it("replaces only recognized evidence comments with safe citation links", () => {
    const markdown = "Claim <!-- evidence: E001, E002 --> <script>alert(1)</script>";

    expect(replaceEvidenceComments(markdown)).toBe(
      "Claim [E001](citation:E001) [E002](citation:E002) <script>alert(1)</script>",
    );
  });
});
