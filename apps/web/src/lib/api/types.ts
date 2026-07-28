export interface User {
  id: string;
  email: string;
  email_verified: boolean;
}

export interface ScenarioOption {
  id: string;
  display_name: string;
  subject: string;
}

export interface ParserProfileOption {
  id: string;
  display_name?: string;
  [key: string]: unknown;
}

export interface OptionsResponse {
  default_scenario_id: string;
  scenarios: ScenarioOption[];
  default_parser_profile_id: string;
  parser_profiles: ParserProfileOption[];
}

export interface GenerateResponse {
  job_id: string;
  status: "queued";
  status_url: string;
}

export type JobState = "queued" | "running" | "completed" | "failed";

export interface SourceFile {
  source_id: string;
  file_name: string;
  page_count?: number;
  parser_backend?: string;
}

export interface JobStatus {
  job_id: string;
  status: JobState;
  error: string;
  quality: Record<string, unknown>;
  service_mode: "single_courseware" | "course_outline";
  source_files: SourceFile[];
  output_url: string;
  evidence_url: string;
  evidence_links_url: string;
  trace_url: string;
  package_url: string;
  export_url: string;
  pdfs_url: string;
  source_pdf_url_template: string;
  source_pdf_info_url_template: string;
  source_pdf_page_url_template: string;
}

export interface MaterialSection {
  id: string;
  title: string;
  order: number;
  status?: "generated" | "weak_evidence" | string;
  quality?: { evidence_count?: number; [key: string]: unknown };
  source_files?: string[];
  evidence_ids?: string[];
  artifact_filenames?: Record<string, string>;
}

export interface MaterialPackage {
  type: "material_package";
  service_mode: "single_courseware" | "course_outline";
  generation_mode: string;
  source_files: SourceFile[];
  sections: MaterialSection[];
}

export interface EvidenceTarget {
  source_id: string;
  source_file: string;
  page: number;
  chunk_id: string;
  quote: string;
}

export interface EvidenceLink {
  ref_id: string;
  occurrence: number;
  comment_index: number;
  target: EvidenceTarget;
}

export interface PdfInfo {
  source_id: string;
  page_count: number;
  pages: Array<{ page: number; width: number; height: number }>;
}

export interface CourseOutlineInput {
  outline: File;
  pdfs: File[];
  scenarioId?: string;
  parserProfileId?: string;
}
