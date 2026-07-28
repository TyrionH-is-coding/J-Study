import { ChevronLeft } from "lucide-react";
import Link from "next/link";

import { CourseOutlineForm } from "@/features/course-outline/course-outline-form";

export default function CourseOutlinePage() {
  return (
    <main className="outline-page" data-testid="app-shell">
      <Link className="back-link" href="/modes"><ChevronLeft /> Service modes</Link>
      <header className="page-heading compact-heading"><span className="eyebrow">Course Outline Mode</span><h1>Build a course-wide material package</h1><p>The outline sets the order. Your PDFs provide the evidence.</p></header>
      <CourseOutlineForm />
    </main>
  );
}
