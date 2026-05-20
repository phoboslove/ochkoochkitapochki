"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, THead, TR, TH, TD } from "@/components/ui/table";
import { useInvoices } from "@/lib/hooks";
import { formatKZT } from "@/lib/utils";

const tone = (s: string) =>
  s === "PAID" ? "success" :
  s === "OVERDUE" ? "danger" :
  s === "PENDING_APPROVAL" ? "warn" :
  s === "SENT" || s === "APPROVED" ? "info" :
  s === "CANCELLED" ? "danger" : "neutral";

export default function InvoicesPage() {
  const { data, isLoading } = useInvoices();
  return (
    <>
      <PageHeader title="Invoices" description="Drafts, pending approvals, sent and paid." />
      <Card>
        <CardContent className="p-0">
          <Table>
            <THead>
              <TR><TH>Number</TH><TH>Issue date</TH><TH>Total</TH><TH>Status</TH><TH></TH></TR>
            </THead>
            <tbody>
              {isLoading && <TR><TD colSpan={5} className="text-center text-muted-foreground py-8">Loading…</TD></TR>}
              {!isLoading && (data?.length ?? 0) === 0 && (
                <TR><TD colSpan={5} className="text-center text-muted-foreground py-8">No invoices yet. Try the AI assistant or simulate a WhatsApp message.</TD></TR>
              )}
              {data?.map((i) => (
                <TR key={i.id}>
                  <TD className="font-medium">{i.number}</TD>
                  <TD className="text-muted-foreground">{i.issue_date}</TD>
                  <TD className="tabular-nums">{formatKZT(Number(i.total))}</TD>
                  <TD><Badge tone={tone(i.status) as any}>{i.status}</Badge></TD>
                  <TD className="text-right">
                    <Link href={`/invoices/${i.id}`}>
                      <Button variant="ghost" size="sm">View</Button>
                    </Link>
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
