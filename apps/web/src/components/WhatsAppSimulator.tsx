"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useSimulateWhatsApp } from "@/lib/hooks";

export function WhatsAppSimulator() {
  const [text, setText] = useState("Create invoice for TOO ABC for 450000 KZT");
  const [reply, setReply] = useState<string | null>(null);
  const sim = useSimulateWhatsApp();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Simulate WhatsApp inbound</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Input value={text} onChange={(e) => setText(e.target.value)} />
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            disabled={sim.isPending}
            onClick={() => sim.mutate({ text }, { onSuccess: (r) => setReply(r.reply) })}
          >
            {sim.isPending ? "Sending…" : "Send"}
          </Button>
          {reply && <Badge tone="success">draft + approval created</Badge>}
        </div>
        {reply && <div className="text-xs text-muted-foreground border-l-2 pl-3">{reply}</div>}
      </CardContent>
    </Card>
  );
}
