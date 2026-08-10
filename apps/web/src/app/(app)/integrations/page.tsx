"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Plug, Send, ShieldCheck, AlertTriangle, Loader2, ExternalLink, Copy,
} from "lucide-react";
import {
  useConnectIntegration, useIntegrations,
  useTelegramStatus, useTelegramBotConnect, useTelegramBotDisconnect, useTelegramLink,
} from "@/lib/hooks";
import { toast } from "@/components/Toaster";

export default function IntegrationsPage() {
  const { data = [], isLoading } = useIntegrations();
  const [openProvider, setOpenProvider] = useState<string | null>(null);

  return (
    <>
      <PageHeader title="Integrations" description="Connect messaging, CRM, marketplaces, accounting." />

      <TelegramPanel />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
        {isLoading && <div className="text-sm text-muted-foreground">Loading…</div>}
        {data.filter((i) => i.provider !== "telegram").map((i) => (
          <Card key={i.provider}>
            <CardContent className="p-5">
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-md bg-muted flex items-center justify-center">
                  <Plug className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="flex-1">
                  <div className="text-sm font-medium capitalize">{i.provider}</div>
                  <div className="text-xs text-muted-foreground">{i.provider}</div>
                </div>
                <Badge tone={i.status === "connected" ? "success" : "neutral"}>{i.status}</Badge>
              </div>
              <div className="mt-4 flex gap-2">
                <Button size="sm" onClick={() => setOpenProvider(i.provider)}>
                  {i.status === "connected" ? "Reconfigure" : "Connect"}
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      {openProvider && <ConnectModal provider={openProvider} onClose={() => setOpenProvider(null)} />}
    </>
  );
}

function ConnectModal({ provider, onClose }: { provider: string; onClose: () => void }) {
  const connect = useConnectIntegration();
  const [config, setConfig] = useState("{}");
  const [secrets, setSecrets] = useState("{}");

  const presets: Record<string, { config: string; secrets: string; help: string }> = {
    whatsapp: {
      config:  JSON.stringify({ provider: "meta_cloud", phone_number_id: "" }, null, 2),
      secrets: JSON.stringify({ access_token: "", verify_token: "" }, null, 2),
      help: "Choose provider: meta_cloud or twilio. Provider-specific fields go in config + secrets.",
    },
  };
  const preset = presets[provider];

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-[hsl(var(--shadow-color)/0.5)] p-4" onClick={onClose}>
      <Card className="w-[520px] max-w-full" onClick={(e) => e.stopPropagation()}>
        <CardContent className="p-5 space-y-3">
          <div className="text-base font-semibold capitalize">Connect {provider}</div>
          {preset && <p className="text-xs text-muted-foreground">{preset.help}</p>}
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">config (JSON)</label>
            <textarea className="w-full h-28 rounded-md border bg-background p-2 text-xs font-mono"
                      defaultValue={preset?.config ?? config}
                      onChange={(e) => setConfig(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">secrets (JSON)</label>
            <textarea className="w-full h-28 rounded-md border bg-background p-2 text-xs font-mono"
                      defaultValue={preset?.secrets ?? secrets}
                      onChange={(e) => setSecrets(e.target.value)} />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button
              disabled={connect.isPending}
              onClick={() => {
                try {
                  const cfg = JSON.parse(config || preset?.config || "{}");
                  const sec = JSON.parse(secrets || preset?.secrets || "{}");
                  connect.mutate({ provider, config: cfg, secrets: sec }, { onSuccess: onClose });
                } catch { alert("Invalid JSON"); }
              }}
            >
              {connect.isPending ? "Saving…" : "Save"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}


// ── Telegram bot panel ─────────────────────────────────────────────────────
//
// Dedicated UX for connecting a per-workspace Telegram bot. The generic
// "paste JSON" modal is wrong for this flow because:
//   - the user has ONE field (the token from @BotFather)
//   - they need to SEE the verified bot @username before deciding to save
//   - they need to know whether the webhook actually registered
//   - they need a deep-link to bind their personal Telegram account
//
// All of those signals live in /telegram/me which polls every few seconds.

function TelegramPanel() {
  const { data: status, isLoading } = useTelegramStatus();
  const connect = useTelegramBotConnect();
  const disconnect = useTelegramBotDisconnect();
  const link = useTelegramLink();
  const [token, setToken] = useState("");
  // Public HTTPS URL of the API (where Telegram should POST webhooks).
  // For local dev this is a tunnel URL like https://abc.ngrok-free.app;
  // for production it's the deployed API origin. Without HTTPS Telegram
  // refuses to register a webhook — we leave it blank by default so users
  // can verify the token first and add the public URL after spinning up
  // their tunnel.
  const [publicApiUrl, setPublicApiUrl] = useState("");

  const connected = !!status?.bot_connected;
  const wh = !!status?.webhook_registered;
  const lastEvent = status?.last_event_at ? new Date(status.last_event_at) : null;
  const minutesSinceEvent = lastEvent ? Math.floor((Date.now() - lastEvent.getTime()) / 60000) : null;

  const onConnect = () => {
    const trimmed = token.trim();
    if (!trimmed || !/^\d{6,12}:[\w-]{20,}$/.test(trimmed)) {
      toast.error("Неверный формат токена", "Ожидался токен от @BotFather: 12345:AA...");
      return;
    }
    const url = publicApiUrl.trim();
    if (url && !/^https:\/\//i.test(url)) {
      toast.error("Public URL должен быть HTTPS",
                  "Telegram отклоняет http:// webhooks. Используй ngrok или cloudflared.");
      return;
    }
    connect.mutate(
      { bot_token: trimmed, public_webhook_base: url || undefined },
      {
        onSuccess: (r) => {
          setToken("");
          if (r.webhook_registered) {
            toast.success("Бот подключён", `@${r.bot_username} · webhook активен`);
          } else {
            toast.warn(
              `@${r.bot_username} подключён, webhook не зарегистрирован`,
              r.webhook_error ?? "Добавьте публичный HTTPS URL для активации webhook.",
            );
          }
        },
        onError: (e) => toast.error("Не удалось подключить", (e as Error).message),
      },
    );
  };

  const onLink = () => {
    link.mutate(undefined, {
      onSuccess: (r) => {
        navigator.clipboard?.writeText(r.deep_link).catch(() => {});
        toast.info("Ссылка скопирована", "Откройте её в Telegram, чтобы привязать аккаунт.");
        window.open(r.deep_link, "_blank");
      },
      onError: (e) => toast.error("Линк недоступен", (e as Error).message),
    });
  };

  return (
    <Card>
      <CardContent className="p-5 space-y-4">
        <div className="flex items-start gap-3">
          <div className="h-10 w-10 rounded-md bg-info-bg ring-1 ring-[hsl(var(--info)/0.25)] flex items-center justify-center">
            <Send className="h-4 w-4 text-[hsl(var(--info))]" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold">Telegram bot</div>
            <div className="text-[12px] text-muted-foreground">
              Подключите СВОЙ бот от @BotFather. Каждая компания работает со
              своим ботом — токены не пересекаются.
            </div>
          </div>
          {isLoading ? (
            <Badge tone="neutral">…</Badge>
          ) : connected ? (
            <Badge tone="success">Connected</Badge>
          ) : (
            <Badge tone="neutral">Disconnected</Badge>
          )}
        </div>

        {connected ? (
          <ConnectedView
            status={status}
            wh={wh}
            minutesSinceEvent={minutesSinceEvent}
            onLink={onLink}
            linkPending={link.isPending}
            onDisconnect={() =>
              disconnect.mutate(undefined, {
                onSuccess: () => toast.success("Telegram отключён", "Webhook снят с бота."),
                onError: (e) => toast.error("Не удалось отключить", (e as Error).message),
              })
            }
            disconnectPending={disconnect.isPending}
          />
        ) : (
          <DisconnectedView
            token={token} setToken={setToken}
            publicApiUrl={publicApiUrl} setPublicApiUrl={setPublicApiUrl}
            onConnect={onConnect} pending={connect.isPending}
          />
        )}
      </CardContent>
    </Card>
  );
}

function DisconnectedView({
  token, setToken, publicApiUrl, setPublicApiUrl, onConnect, pending,
}: {
  token: string; setToken: (s: string) => void;
  publicApiUrl: string; setPublicApiUrl: (s: string) => void;
  onConnect: () => void; pending: boolean;
}) {
  return (
    <div className="space-y-3 pt-2 border-t border-border">
      <ol className="space-y-1 text-[11.5px] text-muted-foreground list-decimal pl-4">
        <li>
          В Telegram открой <code className="font-mono">@BotFather</code>, команда{" "}
          <code className="font-mono">/newbot</code>. Скопируй полученный токен.
        </li>
        <li>
          Запусти публичный туннель к API (порт 8000), например:{" "}
          <code className="font-mono">ngrok http 8000</code> или{" "}
          <code className="font-mono">cloudflared tunnel --url http://localhost:8000</code>. Получишь URL{" "}
          <code className="font-mono">https://что-то.ngrok-free.app</code>.
        </li>
        <li>
          Вставь ниже токен и публичный URL. Wagwan проверит токен через Telegram
          и зарегистрирует webhook автоматически.
        </li>
      </ol>

      <div className="space-y-2">
        <div>
          <label className="text-[11px] text-muted-foreground mb-1 block">Bot token</label>
          <Input
            type="password" placeholder="123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
            value={token} onChange={(e) => setToken(e.target.value)}
            className="font-mono"
          />
        </div>
        <div>
          <label className="text-[11px] text-muted-foreground mb-1 block">
            Public API URL <span className="opacity-70">(HTTPS — необязательно, без него токен будет валидирован, но webhook не активируется)</span>
          </label>
          <Input
            type="url" placeholder="https://abc-123-45.ngrok-free.app"
            value={publicApiUrl} onChange={(e) => setPublicApiUrl(e.target.value)}
            className="font-mono"
          />
        </div>
        <div className="flex justify-end">
          <Button onClick={onConnect} disabled={pending || !token.trim()}>
            {pending ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Проверка…</> : "Подключить"}
          </Button>
        </div>
      </div>

      <div className="text-[10.5px] text-muted-foreground/80">
        Токен хранится в БД, не показывается в ответах API и не пишется в логи. Перед сохранением
        Wagwan вызывает Telegram <code className="font-mono">getMe</code> — если токен невалиден,
        ничего не сохраняется.
      </div>
    </div>
  );
}

function ConnectedView({
  status, wh, minutesSinceEvent, onLink, linkPending, onDisconnect, disconnectPending,
}: {
  status: any; wh: boolean; minutesSinceEvent: number | null;
  onLink: () => void; linkPending: boolean;
  onDisconnect: () => void; disconnectPending: boolean;
}) {
  return (
    <div className="space-y-2.5 pt-2 border-t border-border">
      <dl className="grid grid-cols-[120px_1fr] gap-x-3 gap-y-1 text-[12.5px]">
        <dt className="text-muted-foreground">Bot</dt>
        <dd className="font-mono">
          <a href={`https://t.me/${status?.bot_username}`} target="_blank" rel="noreferrer"
             className="hover:underline inline-flex items-center gap-1">
            @{status?.bot_username} <ExternalLink className="h-3 w-3 opacity-60" />
          </a>
        </dd>

        <dt className="text-muted-foreground">Webhook</dt>
        <dd className="flex flex-wrap items-center gap-2">
          {wh ? (
            <span className="inline-flex items-center gap-1 text-[hsl(var(--success))]">
              <ShieldCheck className="h-3.5 w-3.5" /> Registered
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-[hsl(var(--warning))]">
              <AlertTriangle className="h-3.5 w-3.5" /> Not registered
            </span>
          )}
          {status?.webhook_url && (
            <code className="text-[11px] text-muted-foreground font-mono truncate max-w-[300px]">
              {status.webhook_url}
            </code>
          )}
        </dd>

        {status?.webhook_error && (
          <>
            <dt className="text-muted-foreground">Last error</dt>
            <dd className="text-[11.5px] text-[hsl(var(--warning))]">{status.webhook_error}</dd>
          </>
        )}

        <dt className="text-muted-foreground">Last message</dt>
        <dd className="text-[11.5px]">
          {minutesSinceEvent == null
            ? <span className="text-muted-foreground">— no inbound messages yet</span>
            : minutesSinceEvent < 1
              ? <span className="text-[hsl(var(--success))]">just now</span>
              : <span className="text-muted-foreground">{minutesSinceEvent} min ago</span>}
        </dd>

        <dt className="text-muted-foreground">Your account</dt>
        <dd>
          {status?.linked
            ? <span>linked as <b className="font-mono">@{status.telegram_username ?? "—"}</b></span>
            : <span className="text-[hsl(var(--warning))]">not linked — Telegram won't see you yet</span>}
        </dd>
      </dl>

      <div className="flex flex-wrap gap-2 pt-2">
        {!status?.linked && (
          <Button size="sm" variant="outline" onClick={onLink} disabled={linkPending}>
            {linkPending ? "…" : <><Copy className="h-3.5 w-3.5" /> Link my Telegram</>}
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={onDisconnect} disabled={disconnectPending}
                className="text-[hsl(var(--danger))] hover:text-[hsl(var(--danger))]">
          {disconnectPending ? "Отключаю…" : "Отключить бота"}
        </Button>
      </div>
    </div>
  );
}
