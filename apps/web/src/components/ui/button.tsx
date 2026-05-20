import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md",
    "text-[13px] font-medium tracking-tight",
    "transition-[background,color,border,box-shadow,transform] duration-150",
    "active:scale-[0.98]",
    "disabled:pointer-events-none disabled:opacity-50",
    "focus-visible:outline-none",
  ].join(" "),
  {
    variants: {
      variant: {
        // Default is the brand-cobalt action — primary CTA in premium dark.
        default:     "bg-[hsl(var(--brand))] text-[hsl(var(--brand-foreground))] shadow-sm hover:bg-[hsl(var(--brand)/0.92)] hover:shadow-brand",
        primary:     "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90",
        brand:       "bg-[hsl(var(--brand))] text-[hsl(var(--brand-foreground))] shadow-sm hover:bg-[hsl(var(--brand)/0.92)] hover:shadow-brand",
        secondary:   "bg-muted text-foreground hover:bg-muted/70",
        outline:     "border border-border bg-card text-foreground hover:bg-accent hover:border-[hsl(var(--brand)/0.4)]",
        ghost:       "text-foreground hover:bg-accent",
        link:        "text-foreground underline-offset-4 hover:underline",
        destructive: "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        subtle:      "bg-accent text-accent-foreground hover:bg-muted",
      },
      size: {
        sm:   "h-7 px-2.5",
        md:   "h-8 px-3",
        lg:   "h-9 px-4",
        xl:   "h-10 px-5",
        icon: "h-8 w-8",
      },
    },
    defaultVariants: { variant: "default", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  ),
);
Button.displayName = "Button";
