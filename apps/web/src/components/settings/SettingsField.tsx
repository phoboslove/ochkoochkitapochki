"use client";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export function Field({ label, hint, children, span = 1 }: {
  label: string; hint?: string; children: React.ReactNode; span?: 1 | 2;
}) {
  return (
    <div className={cn(span === 2 && "sm:col-span-2")}>
      <label className="mb-1 block text-xs text-muted-foreground">{label}</label>
      {children}
      {hint && <p className="mt-1 text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

export function Text({ value, onChange, ...rest }: {
  value: string | number | undefined;
  onChange: (v: string) => void;
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange">) {
  return (
    <Input value={value ?? ""} onChange={(e) => onChange(e.target.value)} {...rest} />
  );
}

export function Toggle({ label, checked, onChange, hint }: {
  label: string; checked: boolean; onChange: (v: boolean) => void; hint?: string;
}) {
  return (
    <label className="flex items-start gap-2 cursor-pointer">
      <input type="checkbox" className="mt-1" checked={checked}
             onChange={(e) => onChange(e.target.checked)} />
      <span>
        <span className="text-sm">{label}</span>
        {hint && <span className="block text-[11px] text-muted-foreground">{hint}</span>}
      </span>
    </label>
  );
}

export function Select<T extends string>({ value, onChange, options }: {
  value: T; onChange: (v: T) => void; options: { value: T; label: string }[];
}) {
  return (
    <select className="h-9 w-full rounded-md border bg-background px-3 text-sm"
            value={value} onChange={(e) => onChange(e.target.value as T)}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}
