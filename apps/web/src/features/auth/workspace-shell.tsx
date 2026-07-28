"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BookOpenText, LogOut } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { logout } from "@/lib/api";
import { AuthGate } from "./auth-gate";
import { useSession } from "./session";

export function WorkspaceShell({ children }: { children: ReactNode }) {
  return <AuthGate><WorkspaceChrome>{children}</WorkspaceChrome></AuthGate>;
}

function WorkspaceChrome({ children }: { children: ReactNode }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const session = useSession();
  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.setQueryData(["session"], null);
      router.replace("/login");
    },
  });

  return (
    <div className="workspace-frame">
      <header className="app-header">
        <Link className="brand-lockup compact" href="/modes"><span className="brand-mark" aria-hidden="true">J</span><div><strong>J-Study</strong><span>Clinical Workbench</span></div></Link>
        <div className="header-context"><BookOpenText /><span>Course workspace</span></div>
        <div className="account-block"><span title={session.data?.email}>{session.data?.email}</span><Button type="button" variant="ghost" size="icon" title="Sign out" aria-label="Sign out" disabled={logoutMutation.isPending} onClick={() => logoutMutation.mutate()}><LogOut /></Button></div>
      </header>
      {children}
    </div>
  );
}
