"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Plug } from "lucide-react";
import { useConnectIntegration, useIntegrations } from "@/lib/hooks";

export default function IntegrationsPage() {
  const { data = [], isLoading } = useIntegrations();
  const [openProvider, setOpenProvider] = useState<string | null>(null);

  return (
    <>
      <PageHeader title="Integrations" description="Connect messaging, CRM, marketplaces, accounting." />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {isLoading && <div className="text-sm text-muted-foreground">Loading…</div>}
        {data.map((i) => (
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
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" onClick={onClose}>
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
