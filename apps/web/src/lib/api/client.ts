import type {
  CourseOutlineInput,
  EvidenceLink,
  GenerateResponse,
  JobStatus,
  MaterialPackage,
  OptionsResponse,
  PdfInfo,
  SourceFile,
  User,
} from "./types";

export class ApiClientError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (body.detail) return JSON.stringify(body.detail);
  } catch {
    // Fall through to the status text when the backend did not return JSON.
  }
  return response.statusText || `Request failed (${response.status})`;
}

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "include",
    headers: {
      ...(init.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...init.headers,
    },
  });
  if (!response.ok) {
    throw new ApiClientError(await readError(response), response.status);
  }
  return (await response.json()) as T;
}

export function getCurrentUser(): Promise<User> {
  return apiFetch<User>("/api/auth/me");
}

export function login(email: string, password: string): Promise<User> {
  return apiFetch<User>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function register(email: string, password: string, inviteCode: string): Promise<User> {
  return apiFetch<User>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, invite_code: inviteCode }),
  });
}

export function logout(): Promise<{ status: "ok" }> {
  return apiFetch<{ status: "ok" }>("/api/auth/logout", { method: "POST" });
}

export function getOptions(): Promise<OptionsResponse> {
  return apiFetch<OptionsResponse>("/api/options");
}

export function createCourseOutlineFormData(input: CourseOutlineInput): FormData {
  const formData = new FormData();
  formData.append("service_mode", "course_outline");
  formData.append("outline", input.outline);
  input.pdfs.forEach((pdf) => formData.append("pdfs", pdf));
  if (input.scenarioId) formData.append("scenario_id", input.scenarioId);
  if (input.parserProfileId) formData.append("parser_profile_id", input.parserProfileId);
  return formData;
}

export function generateCourseOutline(input: CourseOutlineInput): Promise<GenerateResponse> {
  return apiFetch<GenerateResponse>("/api/generate", {
    method: "POST",
    body: createCourseOutlineFormData(input),
  });
}

export function getJob(jobId: string): Promise<JobStatus> {
  return apiFetch<JobStatus>(`/api/jobs/${encodeURIComponent(jobId)}`);
}

export function getJobOutput(jobId: string): Promise<{ markdown: string }> {
  return apiFetch<{ markdown: string }>(`/api/jobs/${encodeURIComponent(jobId)}/output`);
}

export function getJobPackage(jobId: string): Promise<MaterialPackage> {
  return apiFetch<MaterialPackage>(`/api/jobs/${encodeURIComponent(jobId)}/package`);
}

export function getJobEvidenceLinks(jobId: string): Promise<EvidenceLink[]> {
  return apiFetch<EvidenceLink[]>(`/api/jobs/${encodeURIComponent(jobId)}/evidence-links`);
}

export function getJobSources(jobId: string): Promise<{ source_files: SourceFile[] }> {
  return apiFetch<{ source_files: SourceFile[] }>(`/api/jobs/${encodeURIComponent(jobId)}/pdfs`);
}

export function getSourcePdfInfo(jobId: string, sourceId: string): Promise<PdfInfo> {
  return apiFetch<PdfInfo>(
    `/api/jobs/${encodeURIComponent(jobId)}/pdfs/${encodeURIComponent(sourceId)}/pdf-info`,
  );
}

export function sourcePageUrl(jobId: string, sourceId: string, page: number): string {
  return `/api/jobs/${encodeURIComponent(jobId)}/pdfs/${encodeURIComponent(sourceId)}/pdf-page/${page}.png`;
}

export function jobExportUrl(jobId: string): string {
  return `/api/jobs/${encodeURIComponent(jobId)}/export`;
}
