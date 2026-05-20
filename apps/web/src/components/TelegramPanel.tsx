"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  useTelegramStatus, useTelegramLink, useTelegramDisconnect, useUpdateNotificationPrefs,
} from "@/lib/hooks";
import { toast } from "@/components/Toaster";
import { MessageSquare, ExternalLink, Copy, X } from "lucide-react";

export function TelegramPanel() {
  const { data, isLoading } = useTelegramStatus();
  const link = useTelegramLink();
  const disconnect = useTelegramDisconnect();
  const prefs = useUpdateNotificationPrefs();
  const [deepLink, setDeepLink] = useState<string | null>(null);

  if (isLoading) return null;

  const linked = !!data?.linked;
  const botConnected = !!data?.bot_connected;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-muted-foreground" /> Telegram
          {botConnected
            ? <Badge tone="info" className="ml-auto">bot connected</Badge>
            : <Badge tone="neutral" className="ml-auto">bot not connected</Badge>}
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-4 text-sm">
        {!botConnected && (
          <p className="text-xs text-muted-foreground">
            Admins can connect the org's bot in <a href="/integrations" className="underline">Integrations → Telegram</a>
            {" "}— provide a <code className="font-mono">bot_token</code> and <code className="font-mono">bot_username</code>.
          </p>
        )}

        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">Status:</span>
          {linked ? (
            <Badge tone="success">Linked{data?.telegram_username ? ` · @${data.telegram_username}` : ""}</Badge>
          ) : (
            <Badge tone="warn">Not linked</Badge>
          )}
        </div>

        {!linked && botConnected && (
          <div className="space-y-2">
            <Button size="sm" disabled={link.isPending}
              onClick={() => link.mutate(undefined, {
                onSuccess: (r) => { setDeepLink(r.deep_link); toast.info("Open the link in Telegram", "Tap Start in the bot"); },
                onError:   (e) => toast.error("Could not start link", (e as Error).message),
              })}>
              <MessageSquare className="h-3.5 w-3.5" /> Connect my Telegram
            </Button>
            {deepLink && (
              <div className="rounded border p-3 space-y-2">
                <div className="text-xs text-muted-foreground">
                  Open in Telegram → tap <b>Start</b>. Token expires in 15 min.
                </div>
                <div className="flex flex-wrap gap-2">
                  <a href={deepLink} target="_blank" rel="noreferrer">
                    <Button size="sm" variant="outline"><ExternalLink className="h-3.5 w-3.5" /> Open Telegram</Button>
                  </a>
                  <Button size="sm" variant="ghost"
                    onClick={() => { navigator.clipboard.writeText(deepLink); toast.success("Link copied"); }}>
                    <Copy className="h-3.5 w-3.5" /> Copy link
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}

        {linked && (
          <Button size="sm" variant="outline" disabled={disconnect.isPending}
            onClick={() => disconnect.mutate(undefined, { onSuccess: () => toast.success("Telegram unlinked") })}>
            <X className="h-3.5 w-3.5" /> Unlink Telegram
          </Button>
        )}

        <div className="pt-3 border-t space-y-2">
          <div className="text-xs uppercase tracking-wider text-muted-foreground">Notification channels</div>
          <Toggle label="Telegram alerts (approvals, overdue, failures)"
                  checked={!!data?.notify_telegram} disabled={!linked}
                  onChange={(v) => prefs.mutate({ notify_telegram: v })} />
          <Toggle label="Email alerts"
                  checked={!!data?.notify_email}
                  onChange={(v) => prefs.mutate({ notify_email: v })} />
        </div>
      </CardContent>
    </Card>
  );
}

function Toggle({ label, checked, disabled, onChange }: {
  label: string; checked: boolean; disabled?: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span className={disabled ? "text-muted-foreground" : ""}>{label}</span>
    </label>
  );
}
