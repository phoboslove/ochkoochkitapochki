import * as React from "react";
import { cn } from "@/lib/utils";

export function Table({ className, ...p }: React.TableHTMLAttributes<HTMLTableElement>) {
  return <table className={cn("w-full text-[13px]", className)} {...p} />;
}

export function THead({ className, ...p }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead className={cn(
      "sticky top-0 z-10 bg-card/95 backdrop-blur",
      "text-left text-[11px] uppercase tracking-wider text-muted-foreground",
      className,
    )} {...p} />
  );
}

export function TR({ className, ...p }: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr className={cn(
      "border-b border-border last:border-0 transition-colors hover:bg-accent/40",
      className,
    )} {...p} />
  );
}

export function TH({ className, ...p }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th className={cn("font-medium border-b border-border", className)}
        style={{ padding: "calc(var(--density-y) - 2px) var(--density-x)" }} {...p} />
  );
}

export function TD({ className, ...p }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={cn("align-middle", className)}
        style={{ padding: "var(--density-y) var(--density-x)" }} {...p} />
  );
}

export function SkeletonRow({ cols }: { cols: number }) {
  return (
    <TR>
      {Array.from({ length: cols }).map((_, i) => (
        <TD key={i}>
          <div className="h-3 w-2/3 rounded bg-muted animate-pulse" />
        </TD>
      ))}
    </TR>
  );
}
