"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Wordmark } from "@/components/brand/Wordmark";
import { useRegister } from "@/lib/hooks";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD = 8;
const BIN_RE = /^\d{12}$/;  // КЗ БИН — ровно 12 цифр; пустая строка тоже допустима.

type FieldErrors = Partial<Record<
  "company_name" | "name" | "email" | "password" | "bin", string
>>;

export default function RegisterPage() {
  const router = useRouter();
  const reg = useRegister();

  const [companyName, setCompanyName] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [bin, setBin] = useState("");
  const [errs, setErrs] = useState<FieldErrors>({});
  const [topErr, setTopErr] = useState<string | null>(null);

  function validate(): FieldErrors {
    const e: FieldErrors = {};
    if (!companyName.trim()) e.company_name = "Укажите название компании.";
    if (!name.trim()) e.name = "Укажите ваше имя.";
    if (!email.trim()) e.email = "Укажите email.";
    else if (!EMAIL_RE.test(email.trim())) e.email = "Похоже, в email опечатка.";
    if (!password) e.password = "Придумайте пароль.";
    else if (password.length < MIN_PASSWORD) e.password = `Минимум ${MIN_PASSWORD} символов.`;
    const binTrim = bin.trim();
    if (binTrim && !BIN_RE.test(binTrim)) e.bin = "БИН — 12 цифр (или оставьте пустым).";
    return e;
  }

  function onSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    setTopErr(null);
    const v = validate();
    setErrs(v);
    if (Object.keys(v).length > 0) return;

    reg.mutate(
      {
        company_name: companyName.trim(),
        name: name.trim(),
        email: email.trim().toLowerCase(),
        password,
        bin: bin.trim() || undefined,
      },
      {
        onSuccess: () => router.replace("/dashboard"),
        onError: (e) => setTopErr((e as Error).message),
      },
    );
  }

  return (
    <div className="min-h-screen grid place-items-center p-6 bg-background relative overflow-hidden">
      {/* Ambient brand spotlight — same treatment as /login */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 h-[520px] w-[820px] rounded-full
                        bg-[hsl(var(--brand)/0.18)] blur-3xl" />
      </div>

      <div className="relative w-[400px] max-w-full">
        <div className="mb-8 flex flex-col items-center text-center">
          <Wordmark className="h-10 w-auto text-foreground" />
          <div className="text-[11px] text-muted-foreground mt-2">AI backoffice operating system</div>
        </div>

        <Card>
          <CardContent className="p-6 sm:p-7">
            <h1 className="text-[17px] font-semibold mb-1">Создать аккаунт</h1>
            <p className="text-[12.5px] text-muted-foreground mb-5">
              Заполните форму — мы создадим вашу компанию и сразу войдём.
            </p>

            <form onSubmit={onSubmit} className="space-y-3" noValidate>
              <Field label="Название компании" error={errs.company_name}>
                <Input value={companyName} onChange={(e) => setCompanyName(e.target.value)}
                       autoFocus autoComplete="organization" placeholder="ТОО «Альфа»" />
              </Field>

              <Field label="Ваше имя" error={errs.name}>
                <Input value={name} onChange={(e) => setName(e.target.value)}
                       autoComplete="name" placeholder="Иван Петров" />
              </Field>

              <Field label="Рабочий email" error={errs.email}>
                <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                       autoComplete="email" placeholder="ivan@alpha.kz" />
              </Field>

              <Field label="Пароль" error={errs.password} hint={`Минимум ${MIN_PASSWORD} символов`}>
                <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                       autoComplete="new-password" />
              </Field>

              <Field label="БИН (необязательно)" error={errs.bin} hint="12 цифр">
                <Input value={bin} onChange={(e) => setBin(e.target.value)}
                       inputMode="numeric" placeholder="123456789012" maxLength={12} />
              </Field>

              {topErr && (
                <div className="rounded-md border border-[hsl(var(--danger)/0.3)] bg-danger-bg text-[hsl(var(--danger))] text-[12px] px-3 py-2">
                  {topErr}
                </div>
              )}

              <Button className="w-full" size="lg" type="submit" disabled={reg.isPending}>
                {reg.isPending ? "Создаём аккаунт…" : "Создать аккаунт"}
              </Button>
            </form>

            <div className="mt-5 pt-4 border-t border-border text-center text-[12px] text-muted-foreground">
              Уже есть аккаунт?{" "}
              <Link href="/login" className="text-foreground hover:underline">
                Войти
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Field({
  label, error, hint, children,
}: {
  label: string;
  error?: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="text-[11px] text-muted-foreground mb-1 block">{label}</label>
      {children}
      {error
        ? <div className="text-[11px] text-[hsl(var(--danger))] mt-1">{error}</div>
        : hint
          ? <div className="text-[10.5px] text-muted-foreground/80 mt-1">{hint}</div>
          : null}
    </div>
  );
}
