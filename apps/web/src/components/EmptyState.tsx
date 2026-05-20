"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export function EmptyState({ icon: Icon, title, description, action, secondary, className }: {
  icon?: React.ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  action?: React.ReactNode;
  secondary?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn(
      "rounded-lg border border-dashed border-border bg-card",
      "px-6 py-10 sm:py-14 text-center flex flex-col items-center",
      className,
    )}>
      {Icon && (
        <div className="mb-3 h-10 w-10 rounded-full bg-accent flex items-center justify-center">
          <Icon className="h-4 w-4 text-muted-foreground" />
        </div>
      )}
      <h3 className="text-sm font-medium">{title}</h3>
      {description && (
        <p className="mt-1 max-w-md text-xs text-muted-foreground leading-relaxed">{description}</p>
      )}
      {(action || secondary) && (
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
          {action}
          {secondary}
        </div>
      )}
    </div>
  );
}
