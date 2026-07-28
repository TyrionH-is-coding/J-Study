import type { MaterialSection } from "@/lib/api";

export interface SectionMarkdown extends MaterialSection {
  markdown: string;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function splitMarkdownBySections(
  markdown: string,
  sections: MaterialSection[],
): SectionMarkdown[] {
  const ordered = [...sections].sort((left, right) => left.order - right.order);
  return ordered.map((section, index) => {
    const heading = new RegExp(`^#{1,6}\\s+${escapeRegExp(section.title)}\\s*$`, "im");
    const startMatch = heading.exec(markdown);
    if (!startMatch) return { ...section, markdown: index === 0 ? markdown : "" };

    const start = startMatch.index;
    const laterStarts = ordered.slice(index + 1).flatMap((candidate) => {
      const candidateHeading = new RegExp(
        `^#{1,6}\\s+${escapeRegExp(candidate.title)}\\s*$`,
        "im",
      );
      const match = candidateHeading.exec(markdown.slice(start + startMatch[0].length));
      return match ? [start + startMatch[0].length + match.index] : [];
    });
    const end = laterStarts.length > 0 ? Math.min(...laterStarts) : markdown.length;
    return { ...section, markdown: markdown.slice(start, end).trim() };
  });
}

export function replaceEvidenceComments(markdown: string): string {
  return markdown.replace(
    /<!--\s*evidence:\s*([^>]+?)\s*-->/gi,
    (_, references: string) =>
      (references.match(/\bE\d{3}\b/g) ?? [])
        .map((reference) => `[${reference}](citation:${reference})`)
        .join(" "),
  );
}
