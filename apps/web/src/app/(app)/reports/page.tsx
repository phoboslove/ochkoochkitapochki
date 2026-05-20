import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatKZT } from "@/lib/utils";

export default function ReportsPage() {
  const data = { month: "April 2026", revenue: 4_280_000, expenses: 1_120_000, tax_estimate: 128_000 };
  const profit = data.revenue - data.expenses;
  return (
    <>
      <PageHeader title="Reports" description="Monthly accounting summary and tax estimates." />
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Stat label="Period"        value={data.month} />
        <Stat label="Revenue"       value={formatKZT(data.revenue)} />
        <Stat label="Expenses"      value={formatKZT(data.expenses)} />
        <Stat label="Tax estimate"  value={formatKZT(data.tax_estimate)} />
      </div>
      <Card className="mt-6">
        <CardHeader><CardTitle>Net profit</CardTitle></CardHeader>
        <CardContent><div className="text-3xl font-semibold">{formatKZT(profit)}</div></CardContent>
      </Card>
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardHeader><CardTitle>{label}</CardTitle></CardHeader>
      <CardContent><div className="text-xl font-semibold">{value}</div></CardContent>
    </Card>
  );
}
