"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAdminCreateCompany } from "@/lib/admin-hooks";
import { useAdminPlans } from "@/lib/admin-hooks";
import { toast } from "@/components/Toaster";

export default function NewCompanyPage() {
  const router = useRouter();
  const { data: plans } = useAdminPlans();
  const create = useAdminCreateCompany();

  const [companyName, setCompanyName] = useState("");
  const [bin, setBin] = useState("");
  const [planCode, setPlanCode] = useState("trial");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [ownerName, setOwnerName] = useState("");
  const [ownerPassword, setOwnerPassword] = useState("");

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    create.mutate(
      {
        company_name: companyName, bin: bin || undefined, plan_code: planCode,
        owner_email: ownerEmail, owner_name: ownerName || undefined, owner_password: ownerPassword,
      },
      {
        onSuccess: (r) => {
          toast.success("Компания создана", companyName);
          router.push(`/admin/companies/${r.company_id}`);
        },
        onError: (e) => toast.error("Не удалось создать", (e as Error).message),
      },
    );
  };

  return (
    <>
      <PageHeader title="Создать компанию" description="Компания, план подписки и первый пользователь (OWNER) одной формой." />
      <Card className="max-w-xl">
        <CardContent className="p-6">
          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Название компании</label>
              <Input value={companyName} onChange={(e) => setCompanyName(e.target.value)} required />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">БИН (необязательно)</label>
              <Input value={bin} onChange={(e) => setBin(e.target.value)} />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Тариф</label>
              <select
                value={planCode} onChange={(e) => setPlanCode(e.target.value)}
                className="h-8 w-full rounded-md border border-input bg-card px-3 text-[13px]"
              >
                {(plans ?? []).filter((p) => p.is_active).map((p) => (
                  <option key={p.code} value={p.code}>{p.name} ({p.price_amount} {p.price_currency}/мес)</option>
                ))}
              </select>
            </div>
            <div className="pt-2 border-t border-border" />
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Email владельца (OWNER)</label>
              <Input type="email" value={ownerEmail} onChange={(e) => setOwnerEmail(e.target.value)} required />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Имя владельца</label>
              <Input value={ownerName} onChange={(e) => setOwnerName(e.target.value)} />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Пароль</label>
              <Input type="password" value={ownerPassword} onChange={(e) => setOwnerPassword(e.target.value)} required minLength={8} />
            </div>
            <div className="flex justify-end pt-2">
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? "Создаю…" : "Создать компанию"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </>
  );
}
