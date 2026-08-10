"use client";

import Link from "next/link";
import { AlertTriangle, Clock, ShieldAlert } from "lucide-react";
import { useMySubscription } from "@/lib/hooks";

/**
 * Not dismissible on purpose — unlike BetaBanner, this reflects billing
 * state the user needs to act on (or it self-resolves when status changes
 * on the next request via the backend's lazy refresh_status). Hiding a
 * "you're about to be blocked" or "you are blocked" signal would defeat
 * the point.
 */
export function SubscriptionBanner() {
  const { data: sub } = useMySubscription();
  if (!sub) return null;

  if (sub.status === "suspended") {
    return (
      <div className="flex items-center gap-3 border-b border-[hsl(var(--danger)/0.3)] bg-danger-bg px-4 py-2 text-[12.5px] text-foreground">
        <ShieldAlert className="h-4 w-4 text-[hsl(var(--danger))] shrink-0" />
        <div className="flex-1">
          <b>Подписка приостановлена.</b> Генерация документов заблокирована — все данные по-прежнему доступны.
        </div>
        <Link href="/settings" className="underline shrink-0">Продлить подписку</Link>
      </div>
    );
  }

  if (sub.status === "past_due") {
    return (
      <div className="flex items-center gap-3 border-b border-[hsl(var(--warning)/0.3)] bg-warning-bg px-4 py-2 text-[12.5px] text-foreground">
        <AlertTriangle className="h-4 w-4 text-[hsl(var(--warning))] shrink-0" />
        <div className="flex-1">
          <b>Оплаченный период истёк.</b>{" "}
          {sub.days_until_suspend != null && sub.days_until_suspend >= 0
            ? `Продлите подписку в течение ${sub.days_until_suspend} дн., иначе генерация документов будет заблокирована.`
            : "Продлите подписку, чтобы избежать блокировки."}
        </div>
        <Link href="/settings" className="underline shrink-0">Продлить подписку</Link>
      </div>
    );
  }

  if (sub.status === "trialing" && sub.days_until_period_end <= 5) {
    return (
      <div className="flex items-center gap-3 border-b border-[hsl(var(--info)/0.3)] bg-info-bg px-4 py-2 text-[12.5px] text-foreground">
        <Clock className="h-4 w-4 text-[hsl(var(--info))] shrink-0" />
        <div className="flex-1">
          Пробный период заканчивается {sub.days_until_period_end <= 0 ? "сегодня" : `через ${sub.days_until_period_end} дн.`}
        </div>
        <Link href="/settings" className="underline shrink-0">Выбрать тариф</Link>
      </div>
    );
  }

  return null;
}
