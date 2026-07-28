import { ArrowRight, BookOpenCheck, Files, ListTree } from "lucide-react";
import Link from "next/link";

export default function ModesPage() {
  return (
    <main className="mode-page" data-testid="app-shell">
      <header className="page-heading"><span className="eyebrow">Service modes</span><h1>Choose how your material is organized</h1><p>Start with the structure of your course, then keep every generated section connected to its sources.</p></header>
      <section className="mode-list" aria-label="Available service modes">
        <Link className="mode-card" href="/modes/course-outline">
          <div className="mode-icon"><ListTree /></div>
          <div className="mode-copy"><div><span className="status-dot" /> Available now</div><h2>Course Outline</h2><p>Upload a course outline and its matching lecture PDFs. J-Study builds an ordered, source-linked material package.</p><ul><li><BookOpenCheck /> Sectioned material</li><li><Files /> Multiple source PDFs</li></ul></div>
          <span className="mode-arrow" aria-hidden="true"><ArrowRight /></span>
        </Link>
      </section>
    </main>
  );
}
