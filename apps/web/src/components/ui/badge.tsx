import { cn } from "@/lib/utils";

/**
 * Premium status pills — desaturated, dark-mode-first.
 * Backgrounds use *-bg tokens (already adapted per theme).
 */
const tones: Record<string, string> = {
  neutral: "bg-muted text-muted-foreground border border-border",
  success: "bg-success-bg text-[hsl(var(--success))] border border-[hsl(var(--success)/0.30)]",
  warn:    "bg-warning-bg text-[hsl(var(--warning))] border border-[hsl(var(--warning)/0.30)]",
  danger:  "bg-danger-bg  text-[hsl(var(--danger))]  border border-[hsl(var(--danger)/0.30)]",
  info:    "bg-info-bg    text-[hsl(var(--info))]    border border-[hsl(var(--info)/0.30)]",
  brand:   "bg-[hsl(var(--brand-subtle))] text-[hsl(var(--brand))] border border-[hsl(var(--brand)/0.30)]",
};

export function Badge({ tone = "neutral", className, children }: {
  tone?: keyof typeof tones; className?: string; children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium leading-none",
        tones[tone], className,
      )}
    >
      {children}
    </span>
  );
}

export function StatusDot({ tone = "neutral", className }: {
  tone?: keyof typeof tones; className?: string;
}) {
  const color: Record<string, string> = {
    neutral: "bg-muted-foreground",
    success: "bg-[hsl(var(--success))]",
    warn:    "bg-[hsl(var(--warning))]",
    danger:  "bg-[hsl(var(--danger))]",
    info:    "bg-[hsl(var(--info))]",
    brand:   "bg-[hsl(var(--brand))]",
  };
  return <span className={cn("inline-block h-1.5 w-1.5 rounded-full", color[tone], className)} />;
}
