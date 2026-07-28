"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { ReactNode, useEffect } from "react";

import { useSession } from "./session";

export function AuthGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const session = useSession();

  useEffect(() => {
    if (session.isSuccess && !session.data) router.replace("/login");
  }, [router, session.data, session.isSuccess]);

  if (session.isLoading) return <main className="route-loading"><Loader2 className="animate-spin" /><span>Opening workspace</span></main>;
  if (session.error) return <main className="route-loading error"><strong>Session check failed</strong><span>{session.error.message}</span></main>;
  if (!session.data) return null;
  return children;
}
