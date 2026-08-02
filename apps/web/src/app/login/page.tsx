"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useLogin } from "@/lib/hooks";

export default function LoginPage() {
  const router = useRouter();
  const login = useLogin();
  const [email, setEmail] = useState("demo@buchuchet.io");
  const [password, setPassword] = useState("demo1234");
  const [err, setErr] = useState<string | null>(null);

  return (
    <div className="min-h-screen grid place-items-center p-6 bg-background relative overflow-hidden">
      {/* Ambient brand spotlight */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 h-[520px] w-[820px] rounded-full
                        bg-[hsl(var(--brand)/0.18)] blur-3xl" />
      </div>

      <div className="relative w-[380px] max-w-full">
        <div className="flex items-center gap-2 mb-6">
          <div className="h-8 w-8 rounded-md bg-[hsl(var(--brand))] text-[hsl(var(--brand-foreground))] grid place-items-center text-[13px] font-semibold shadow-brand">B</div>
          <div className="leading-tight">
            <div className="text-[15px] font-semibold">Buchuchet</div>
            <div className="text-[11px] text-muted-foreground">AI backoffice operating system</div>
          </div>
        </div>

        <Card>
          <CardContent className="p-6 sm:p-7">
            <h1 className="text-[17px] font-semibold mb-1">Sign in</h1>
            <p className="text-[12.5px] text-muted-foreground mb-5">Use your work email to continue.</p>
            <form
              onSubmit={(e) => {
                e.preventDefault(); setErr(null);
                login.mutate({ email, password }, {
                  onSuccess: () => router.replace("/dashboard"),
                  onError:   (e) => setErr((e as Error).message),
                });
              }}
              className="space-y-3"
            >
              <div>
                <label className="text-[11px] text-muted-foreground mb-1 block">Work email</label>
                <Input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required autoFocus />
              </div>
              <div>
                <label className="text-[11px] text-muted-foreground mb-1 block">Password</label>
                <Input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />
              </div>
              {err && <div className="rounded-md border border-[hsl(var(--danger)/0.3)] bg-danger-bg text-[hsl(var(--danger))] text-[12px] px-3 py-2">{err}</div>}
              <Button className="w-full" size="lg" type="submit" disabled={login.isPending}>
                {login.isPending ? "Signing in…" : "Sign in"}
              </Button>
            </form>

            <div className="mt-5 pt-4 border-t border-border text-center text-[12px] text-muted-foreground">
              Нет аккаунта?{" "}
              <Link href="/register" className="text-foreground hover:underline">
                Зарегистрироваться
              </Link>
            </div>
          </CardContent>
        </Card>
        <p className="mt-4 text-center text-[11px] text-muted-foreground">
          Demo · <span className="font-mono">demo@buchuchet.io</span> / <span className="font-mono">demo1234</span>
        </p>
      </div>
    </div>
  );
}
