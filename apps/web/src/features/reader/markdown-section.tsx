"use client";

import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";

import type { EvidenceLink, EvidenceTarget } from "@/lib/api";
import { replaceEvidenceComments } from "./markdown";

interface MarkdownSectionProps {
  markdown: string;
  evidenceLinks: EvidenceLink[];
  onCitation: (target: EvidenceTarget) => void;
}

export function MarkdownSection({ markdown, evidenceLinks, onCitation }: MarkdownSectionProps) {
  const evidenceById = new Map(evidenceLinks.map((link) => [link.ref_id, link.target]));

  return (
    <div className="material-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        urlTransform={(url) => /^citation:E\d{3}$/.test(url) ? url : defaultUrlTransform(url)}
        components={{
          a: ({ href, children }) => {
            const reference = href?.match(/^citation:(E\d{3})$/)?.[1];
            const target = reference ? evidenceById.get(reference) : undefined;
            if (reference && target) {
              return (
                <button className="citation-button" type="button" aria-label={`Open citation ${reference}`} onClick={() => onCitation(target)}>
                  {children}
                </button>
              );
            }
            return <a href={href} target="_blank" rel="noreferrer">{children}</a>;
          },
        }}
      >
        {replaceEvidenceComments(markdown)}
      </ReactMarkdown>
    </div>
  );
}
