import { WorkspaceShell } from "@/features/auth/workspace-shell";
import { JobWorkspace } from "@/features/reader/job-workspace";

export default async function JobPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  return <WorkspaceShell><JobWorkspace jobId={jobId} /></WorkspaceShell>;
}
