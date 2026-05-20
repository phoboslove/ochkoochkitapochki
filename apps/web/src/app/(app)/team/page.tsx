"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, THead, TR, TH, TD } from "@/components/ui/table";
import { useInviteTeammate, useMe, useRevokeInvite, useTeam, useUpdateMemberRole } from "@/lib/hooks";
import { toast } from "@/components/Toaster";
import { Copy, X, Mail } from "lucide-react";

const ROLES = ["MEMBER", "ACCOUNTANT", "ADMIN", "VIEWER"];

export default function TeamPage() {
  const { data, isLoading } = useTeam();
  const { data: me } = useMe();
  const invite = useInviteTeammate();
  const revoke = useRevokeInvite();
  const update = useUpdateMemberRole();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("MEMBER");

  const isAdmin = me?.role === "OWNER" || me?.role === "ADMIN";
  const acceptUrl = (token: string) =>
    `${typeof window !== "undefined" ? window.location.origin : ""}/accept-invite?token=${token}`;

  return (
    <>
      <PageHeader title="Team" description="Members, roles, and pending invites." />

      <Card className="mb-6">
        <CardContent className="p-4 sm:p-5">
          <div className="text-sm font-medium mb-2">Invite a teammate</div>
          {!isAdmin && <p className="text-xs text-muted-foreground">Only admins/owners can invite.</p>}
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto_auto] gap-2 items-stretch">
            <Input placeholder="email@company.com" value={email} onChange={(e) => setEmail(e.target.value)} disabled={!isAdmin} />
            <select className="h-9 rounded-md border bg-background px-3 text-sm" value={role}
                    onChange={(e) => setRole(e.target.value)} disabled={!isAdmin}>
              {ROLES.map((r) => <option key={r}>{r}</option>)}
            </select>
            <Button disabled={!isAdmin || !email || invite.isPending}
              onClick={() => invite.mutate({ email, role }, {
                onSuccess: () => { setEmail(""); toast.success("Invite created", "Share the link from the table below"); },
                onError:   (e) => toast.error("Invite failed", (e as Error).message),
              })}>
              <Mail className="h-3.5 w-3.5" /> Invite
            </Button>
          </div>
        </CardContent>
      </Card>

      <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-2">Members ({data?.members.length ?? 0})</h3>
      <Card className="mb-6">
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <THead><TR><TH>Email</TH><TH>Name</TH><TH>Role</TH><TH></TH></TR></THead>
            <tbody>
              {isLoading && <TR><TD colSpan={4} className="text-center text-muted-foreground py-6">Loading…</TD></TR>}
              {data?.members.map((m: any) => (
                <TR key={m.id}>
                  <TD className="font-medium">{m.email}</TD>
                  <TD className="text-muted-foreground">{m.name ?? "—"}</TD>
                  <TD>
                    {isAdmin && m.role !== "OWNER" ? (
                      <select className="h-7 rounded border bg-background px-2 text-xs" defaultValue={m.role}
                        onChange={(e) => update.mutate({ id: m.id, role: e.target.value }, {
                          onSuccess: () => toast.success("Role updated", `${m.email} → ${e.target.value}`),
                        })}>
                        {ROLES.concat(["OWNER"]).map((r) => <option key={r}>{r}</option>)}
                      </select>
                    ) : <Badge tone={m.role === "OWNER" ? "success" : "info"}>{m.role}</Badge>}
                  </TD>
                  <TD></TD>
                </TR>
              ))}
            </tbody>
          </Table>
        </CardContent>
      </Card>

      <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-2">Pending invites</h3>
      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <THead><TR><TH>Email</TH><TH>Role</TH><TH>Status</TH><TH>Invite link</TH><TH></TH></TR></THead>
            <tbody>
              {(data?.invites ?? []).length === 0 && (
                <TR><TD colSpan={5} className="text-center text-muted-foreground py-6 text-sm">No pending invites.</TD></TR>
              )}
              {data?.invites.map((i: any) => (
                <TR key={i.id}>
                  <TD>{i.email}</TD>
                  <TD><Badge tone="info">{i.role}</Badge></TD>
                  <TD><Badge tone={i.status === "PENDING" ? "warn" : i.status === "ACCEPTED" ? "success" : "neutral"}>{i.status}</Badge></TD>
                  <TD>
                    {i.status === "PENDING" && (
                      <Button variant="ghost" size="sm"
                        onClick={() => { navigator.clipboard.writeText(acceptUrl(i.token)); toast.success("Link copied"); }}>
                        <Copy className="h-3.5 w-3.5" /> Copy
                      </Button>
                    )}
                  </TD>
                  <TD className="text-right">
                    {i.status === "PENDING" && (
                      <Button variant="ghost" size="sm"
                        onClick={() => revoke.mutate(i.id, { onSuccess: () => toast.success("Invite revoked") })}>
                        <X className="h-3.5 w-3.5" /> Revoke
                      </Button>
                    )}
                  </TD>
                </TR>
              ))}
            </tbody>
          </Table>
        </CardContent>
      </Card>
    </>
  );
}
