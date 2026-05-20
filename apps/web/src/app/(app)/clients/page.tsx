"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Table, THead, TR, TH, TD } from "@/components/ui/table";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

type Client = { id: string; name: string; bin: string | null; phone: string | null; email: string | null };

export default function ClientsPage() {
  const { data = [], isLoading } = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.get<Client[]>("/clients"),
  });

  return (
    <>
      <PageHeader title="Clients" description="Counterparties seen by AI tools and invoices." />
      <Card>
        <CardContent className="p-0">
          <Table>
            <THead><TR><TH>Name</TH><TH>BIN</TH><TH>Phone</TH><TH>Email</TH></TR></THead>
            <tbody>
              {isLoading && <TR><TD colSpan={4} className="text-center text-muted-foreground py-6">Loading…</TD></TR>}
              {data.map((c) => (
                <TR key={c.id}>
                  <TD className="font-medium">{c.name}</TD>
                  <TD className="font-mono text-xs text-muted-foreground">{c.bin ?? "—"}</TD>
                  <TD>{c.phone ?? "—"}</TD>
                  <TD className="text-muted-foreground">{c.email ?? "—"}</TD>
                </TR>
              ))}
            </tbody>
          </Table>
        </CardContent>
      </Card>
    </>
  );
}
