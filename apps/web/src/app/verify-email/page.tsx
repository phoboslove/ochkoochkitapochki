"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Wordmark } from "@/components/brand/Wordmark";
import { useVerifyEmail, useResendCode } from "@/lib/hooks";

const RESEND_COOLDOWN_S = 60;

function VerifyEmailForm() {
  const router = useRouter();
  const params = useSearchParams();
  const email = params.get("email") ?? "";
  const verify = useVerifyEmail();
  const resend = useResendCode();

  const [code, setCode] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [sentNotice, setSentNotice] = useState<string | null>("Мы отправили код на вашу почту.");
  const [cooldown, setCooldown] = useState(RESEND_COOLDOWN_S);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setInterval(() => setCooldown((c) => Math.max(0, c - 1)), 1000);
    return () => clearInterval(t);
  }, [cooldown]);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setSentNotice(null);
    verify.mutate({ email, code: code.trim() }, {
      onSuccess: () => router.replace("/dashboard"),
      onError: (e) => setErr((e as Error).message),
    });
  }

  function onResend() {
    setErr(null);
    resend.mutate(email, {
      onSuccess: () => {
        setSentNotice("Новый код отправлен на вашу почту.");
        setCooldown(RESEND_COOLDOWN_S);
      },
      onError: (e) => setErr((e as Error).message),
    });
  }

  return (
    <div className="min-h-screen grid place-items-center p-6 bg-background relative overflow-hidden">
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 h-[520px] w-[820px] rounded-full
                        bg-[hsl(var(--brand)/0.18)] blur-3xl" />
      </div>

      <div className="relative w-[380px] max-w-full">
        <div className="mb-8 flex flex-col items-center text-center">
          <Wordmark className="h-10 w-auto text-foreground" />
          <div className="text-[11px] text-muted-foreground mt-2">AI backoffice operating system</div>
        </div>

        <Card>
          <CardContent className="p-6 sm:p-7">
            <h1 className="text-[17px] font-semibold mb-1">Подтвердите почту</h1>
            <p className="text-[12.5px] text-muted-foreground mb-5">
              Код отправлен на <span className="text-foreground font-medium">{email || "вашу почту"}</span>.
              Действует 15 минут.
            </p>

            <form onSubmit={onSubmit} className="space-y-3">
              <div>
                <label className="text-[11px] text-muted-foreground mb-1 block">Код из письма</label>
                <Input
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  inputMode="numeric" autoComplete="one-time-code" autoFocus
                  placeholder="000000" maxLength={6}
                  className="text-center text-[22px] tracking-[0.5em] font-mono"
                />
              </div>

              {err && (
                <div className="rounded-md border border-[hsl(var(--danger)/0.3)] bg-danger-bg text-[hsl(var(--danger))] text-[12px] px-3 py-2">
                  {err}
                </div>
              )}
              {sentNotice && !err && (
                <div className="rounded-md border border-[hsl(var(--info)/0.3)] bg-info-bg text-[hsl(var(--info))] text-[12px] px-3 py-2">
                  {sentNotice}
                </div>
              )}

              <Button className="w-full" size="lg" type="submit" disabled={verify.isPending || code.length !== 6}>
                {verify.isPending ? "Проверяем…" : "Подтвердить"}
              </Button>
            </form>

            <div className="mt-5 pt-4 border-t border-border text-center text-[12px] text-muted-foreground">
              Не пришёл код?{" "}
              {cooldown > 0 ? (
                <span>Повторная отправка через {cooldown} сек.</span>
              ) : (
                <button
                  type="button" onClick={onResend} disabled={resend.isPending}
                  className="text-foreground hover:underline disabled:opacity-50"
                >
                  {resend.isPending ? "Отправляем…" : "Отправить снова"}
                </button>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmailForm />
    </Suspense>
  );
}
