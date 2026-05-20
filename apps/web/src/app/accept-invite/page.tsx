"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, tokenStore } from "@/lib/api";

export default function AcceptInvitePage() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token") ?? "";
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <Card className="w-[380px]">
        <CardHeader><CardTitle>Accept your invite</CardTitle></CardHeader>
        <CardContent>
          {!token && <div className="text-sm text-destructive">Missing invite token.</div>}
          <form onSubmit={async (e) => {
            e.preventDefault(); setErr(null); setBusy(true);
            try {
              const res = await api.postNoAuth<{ access_token: string }>("/invitations/accept",
                { token, name, password });
              tokenStore.set(res.access_token);
              router.replace("/dashboard");
            } catch (e) { setErr((e as Error).message); }
            finally { setBusy(false); }
          }} className="space-y-3">
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Your name</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Password</label>
              <Input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required minLength={8} />
            </div>
            {err && <div className="text-xs text-destructive">{err}</div>}
            <Button type="submit" className="w-full" disabled={busy || !token}>
              {busy ? "Activating…" : "Accept and continue"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
