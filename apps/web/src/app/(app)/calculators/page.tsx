"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { formatKZT } from "@/lib/utils";

type SalaryResult = {
  gross: number; opv: number; vosms: number; ipn_base: number; ipn: number; net: number;
  opvr: number; so: number; oosms: number; social_tax: number; employer_total_cost: number;
  progressive_ipn_applied: boolean; rates_effective_date: string; disclaimer: string;
  warnings: string[];
};

type TurnoverResult = {
  turnover: number; rate: number; tax: number; regime_label: string;
  rates_effective_date: string; disclaimer: string; self_payments_note: string;
};

export default function CalculatorsPage() {
  return (
    <>
      <PageHeader
        title="Калькуляторы"
        description="Детерминированный расчёт по ставкам 2026 года — без участия ИИ в арифметике."
      />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SalaryCalculator />
        <TurnoverCalculator />
      </div>
    </>
  );
}

function SalaryCalculator() {
  const [gross, setGross] = useState("300000");
  const [result, setResult] = useState<SalaryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit() {
    setError(null);
    const value = Number(gross);
    if (!value || value <= 0) { setError("Укажите оклад больше нуля."); return; }
    setLoading(true);
    try {
      const r = await api.post<SalaryResult>("/tax/calculate/salary", { gross: value });
      setResult(r);
    } catch (e: any) {
      setError(e.message ?? "Не удалось посчитать.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader><CardTitle>Зарплатный калькулятор</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-end gap-2">
          <div className="flex-1">
            <label className="text-[11px] text-muted-foreground mb-1 block">
              Оклад (KZT / месяц)
            </label>
            <Input
              type="number" min={0} value={gross}
              onChange={(e) => setGross(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
            />
          </div>
          <Button onClick={submit} disabled={loading}>
            {loading ? "Считаю…" : "Посчитать"}
          </Button>
        </div>
        {error && <div className="text-[13px] text-destructive">{error}</div>}
        {result && (
          <div className="space-y-3">
            <table className="w-full text-[13px] tabular-nums">
              <tbody>
                <Row label="Оклад (начислено)" value={result.gross} />
                <Row label="ОПВ (10%, работник)" value={-result.opv} />
                <Row label="ВОСМС (2%, работник)" value={-result.vosms} />
                <Row label="ИПН" value={-result.ipn} />
                <Row label="На руки" value={result.net} bold />
                <tr><td colSpan={2} className="pt-3 pb-1 text-[11px] uppercase tracking-wide text-muted-foreground">
                  Дополнительно у работодателя
                </td></tr>
                <Row label="ОПВР (3.5%)" value={result.opvr} />
                <Row label="СО (5%)" value={result.so} />
                <Row label="ООСМС (3%)" value={result.oosms} />
                <Row label="Социальный налог (6%)" value={result.social_tax} />
                <Row label="Стоимость сотрудника для работодателя" value={result.employer_total_cost} bold />
              </tbody>
            </table>
            {result.progressive_ipn_applied && (
              <div className="text-[12px] text-warning bg-warning-bg rounded-md px-3 py-2">
                Применена повышенная ставка ИПН 15% (доход превышает 8500 МРП/год).
              </div>
            )}
            {result.warnings.map((w, i) => (
              <div key={i} className="text-[12px] text-muted-foreground">{w}</div>
            ))}
            <Disclaimer text={result.disclaimer} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function TurnoverCalculator() {
  const [turnover, setTurnover] = useState("5000000");
  const [rate, setRate] = useState("");
  const [result, setResult] = useState<TurnoverResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit() {
    setError(null);
    const value = Number(turnover);
    if (!value || value <= 0) { setError("Укажите оборот больше нуля."); return; }
    const rateValue = rate.trim() ? Number(rate) / 100 : undefined;
    setLoading(true);
    try {
      const r = await api.post<TurnoverResult>("/tax/calculate/turnover", {
        turnover: value, rate: rateValue,
      });
      setResult(r);
    } catch (e: any) {
      setError(e.message ?? "Не удалось посчитать.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader><CardTitle>Налоги с оборота (упрощёнка, форма 910)</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-[1fr_120px] gap-2">
          <div>
            <label className="text-[11px] text-muted-foreground mb-1 block">
              Оборот за период (KZT)
            </label>
            <Input
              type="number" min={0} value={turnover}
              onChange={(e) => setTurnover(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
            />
          </div>
          <div>
            <label className="text-[11px] text-muted-foreground mb-1 block">
              Ставка, % (необязательно)
            </label>
            <Input
              type="number" min={2} max={6} step={0.5} placeholder="4"
              value={rate} onChange={(e) => setRate(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
            />
          </div>
        </div>
        <Button onClick={submit} disabled={loading}>
          {loading ? "Считаю…" : "Посчитать"}
        </Button>
        {error && <div className="text-[13px] text-destructive">{error}</div>}
        {result && (
          <div className="space-y-3">
            <table className="w-full text-[13px] tabular-nums">
              <tbody>
                <Row label="Оборот" value={result.turnover} />
                <Row label={`Ставка (${result.regime_label})`} value={null} display={`${(result.rate * 100).toFixed(1)}%`} />
                <Row label="Налог к уплате" value={result.tax} bold />
              </tbody>
            </table>
            <div className="text-[12px] text-muted-foreground bg-muted rounded-md px-3 py-2">
              {result.self_payments_note}
            </div>
            <Disclaimer text={result.disclaimer} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Row({ label, value, bold, display }: { label: string; value: number | null; bold?: boolean; display?: string }) {
  return (
    <tr className={bold ? "border-t border-border font-semibold" : ""}>
      <td className="py-1 pr-3 text-muted-foreground">{label}</td>
      <td className="py-1 text-right">{display ?? (value !== null ? formatKZT(value) : "")}</td>
    </tr>
  );
}

function Disclaimer({ text }: { text: string }) {
  return (
    <div className="text-[11px] text-muted-foreground border-t border-border pt-2">
      {text}
    </div>
  );
}
