"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useSession } from "./session";

export function HomeRedirect() {
  const router = useRouter();
  const session = useSession();
  useEffect(() => {
    if (session.isSuccess) router.replace(session.data ? "/modes" : "/login");
  }, [router, session.data, session.isSuccess]);
  return <main className="route-loading"><Loader2 className="animate-spin" /><span>Opening J-Study</span></main>;
}
