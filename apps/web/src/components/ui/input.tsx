import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "h-8 w-full rounded-md border border-input bg-card px-3 text-[13px] shadow-xs",
        "placeholder:text-muted-foreground/70",
        "transition-[border-color,box-shadow,background] focus-visible:outline-none",
        "focus-visible:border-[hsl(var(--brand))]",
        "hover:border-border/80",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";
