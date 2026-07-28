"use client";

import { useMutation } from "@tanstack/react-query";
import { ArrowRight, FileText, Files, Loader2, UploadCloud, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { generateCourseOutline } from "@/lib/api";

export function CourseOutlineForm() {
  const router = useRouter();
  const [outline, setOutline] = useState<File | null>(null);
  const [pdfs, setPdfs] = useState<File[]>([]);
  const mutation = useMutation({
    mutationFn: () => {
      if (!outline || pdfs.length === 0) throw new Error("Add an outline and at least one PDF.");
      return generateCourseOutline({ outline, pdfs });
    },
    onSuccess: ({ job_id }) => router.push(`/jobs/${job_id}`),
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <form className="outline-form" onSubmit={handleSubmit}>
      <div className="workflow-step">
        <div className="step-number">01</div>
        <div className="step-body">
          <div className="step-heading">
            <div>
              <h2>Course outline</h2>
              <p>Upload the structure that should organize the generated material.</p>
            </div>
            <FileText aria-hidden="true" />
          </div>
          <Label className="upload-zone" htmlFor="outline">
            <UploadCloud aria-hidden="true" />
            <span>{outline?.name ?? "Choose an outline"}</span>
            <small>.md, .txt, or .pdf</small>
          </Label>
          <Input id="outline" aria-label="Course outline" className="sr-only" type="file" accept=".md,.txt,.pdf" onChange={(event) => setOutline(event.target.files?.[0] ?? null)} required />
        </div>
      </div>

      <div className="workflow-step">
        <div className="step-number">02</div>
        <div className="step-body">
          <div className="step-heading">
            <div>
              <h2>Matching course PDFs</h2>
              <p>Add every lecture or courseware PDF needed to cover the outline.</p>
            </div>
            <Files aria-hidden="true" />
          </div>
          <Label className="upload-zone" htmlFor="pdfs">
            <UploadCloud aria-hidden="true" />
            <span>{pdfs.length ? `${pdfs.length} PDF${pdfs.length === 1 ? "" : "s"} selected` : "Choose course PDFs"}</span>
            <small>PDF files only</small>
          </Label>
          <Input id="pdfs" aria-label="Course PDFs" className="sr-only" type="file" accept="application/pdf,.pdf" multiple onChange={(event) => setPdfs(Array.from(event.target.files ?? []))} required />
          {pdfs.length > 0 && (
            <ul className="file-list" aria-label="Selected PDFs">
              {pdfs.map((pdf, index) => (
                <li key={`${pdf.name}-${pdf.lastModified}-${index}`}>
                  <span className="source-seed">S{String(index + 1).padStart(3, "0")}</span>
                  <span title={pdf.name}>{pdf.name}</span>
                  <Button type="button" variant="ghost" size="icon-sm" aria-label={`Remove ${pdf.name}`} onClick={() => setPdfs((current) => current.filter((_, currentIndex) => currentIndex !== index))}>
                    <X />
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {mutation.error && (
        <Alert variant="destructive"><AlertDescription>{mutation.error.message}</AlertDescription></Alert>
      )}
      <div className="form-actions">
        <div><strong>Ready to generate</strong><span>Files remain private to your account.</span></div>
        <Button type="submit" size="lg" disabled={!outline || pdfs.length === 0 || mutation.isPending}>
          {mutation.isPending ? <Loader2 className="animate-spin" /> : <ArrowRight />}
          Generate material
        </Button>
      </div>
    </form>
  );
}
