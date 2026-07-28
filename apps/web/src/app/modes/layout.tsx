import type { ReactNode } from "react";

import { WorkspaceShell } from "@/features/auth/workspace-shell";

export default function ModesLayout({ children }: { children: ReactNode }) {
  return <WorkspaceShell>{children}</WorkspaceShell>;
}
