"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Loader2, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { login, register } from "@/lib/api";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      mode === "login"
        ? login(email, password)
        : register(email, password, inviteCode),
    onSuccess: (user) => {
      queryClient.setQueryData(["session"], user);
      router.replace("/modes");
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    mutation.mutate();
  }

  const isLogin = mode === "login";

  return (
    <main className="auth-page">
      <section className="auth-panel" aria-labelledby="auth-heading">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">J</span>
          <div>
            <strong>J-Study</strong>
            <span>Clinical Workbench</span>
          </div>
        </div>
        <div className="auth-copy">
          <div className="eyebrow"><ShieldCheck size={15} /> Secure workspace</div>
          <h1 id="auth-heading">{isLogin ? "Return to your study workspace" : "Create your learner account"}</h1>
          <p>{isLogin ? "Continue your course material jobs and source-linked reading." : "Set up access for the controlled J-Study pilot."}</p>
        </div>
        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="field-stack">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </div>
          <div className="field-stack">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" autoComplete={isLogin ? "current-password" : "new-password"} minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} required />
          </div>
          {!isLogin && (
            <div className="field-stack">
              <Label htmlFor="invite-code">Invite code <span className="optional-label">when required</span></Label>
              <Input id="invite-code" autoComplete="off" value={inviteCode} onChange={(event) => setInviteCode(event.target.value)} />
            </div>
          )}
          {mutation.error && (
            <Alert variant="destructive">
              <AlertDescription>{mutation.error.message}</AlertDescription>
            </Alert>
          )}
          <Button type="submit" size="lg" disabled={mutation.isPending}>
            {mutation.isPending ? <Loader2 className="animate-spin" /> : <ArrowRight />}
            {isLogin ? "Sign in" : "Create account"}
          </Button>
        </form>
        <p className="auth-switch">
          {isLogin ? "New to J-Study?" : "Already registered?"}{" "}
          <Link href={isLogin ? "/register" : "/login"}>{isLogin ? "Create account" : "Sign in"}</Link>
        </p>
      </section>
      <aside className="auth-context" aria-label="Workspace context">
        <div className="context-grid" aria-hidden="true" />
        <div className="context-copy">
          <span>COURSE OUTLINE MODE</span>
          <h2>One outline. Every source in context.</h2>
          <p>Build sectioned study material while keeping every claim linked to its source PDF and page.</p>
        </div>
      </aside>
    </main>
  );
}
