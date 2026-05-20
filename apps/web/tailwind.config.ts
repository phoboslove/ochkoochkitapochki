import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        subtle: "hsl(var(--subtle))",
        muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
        card: { DEFAULT: "hsl(var(--card))", foreground: "hsl(var(--card-foreground))" },
        primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
        accent: { DEFAULT: "hsl(var(--accent))", foreground: "hsl(var(--accent-foreground))" },
        destructive: { DEFAULT: "hsl(var(--destructive))", foreground: "hsl(var(--destructive-foreground))" },
        brand: { DEFAULT: "hsl(var(--brand))", foreground: "hsl(var(--brand-foreground))", subtle: "hsl(var(--brand-subtle))" },
        "surface-2": "hsl(var(--surface-2))",
        "surface-3": "hsl(var(--surface-3))",
        success: { DEFAULT: "hsl(var(--success))", bg: "hsl(var(--success-bg))" },
        warning: { DEFAULT: "hsl(var(--warning))", bg: "hsl(var(--warning-bg))" },
        danger:  { DEFAULT: "hsl(var(--danger))",  bg: "hsl(var(--danger-bg))"  },
        info:    { DEFAULT: "hsl(var(--info))",    bg: "hsl(var(--info-bg))"    },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["ui-sans-serif", "-apple-system", "Inter", "Segoe UI", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        xs:   "0 1px 0 hsl(var(--shadow-color) / 0.04)",
        sm:   "0 1px 2px hsl(var(--shadow-color) / 0.10), 0 1px 0 hsl(var(--shadow-color) / 0.04)",
        md:   "0 6px 14px -4px hsl(var(--shadow-color) / 0.18), 0 2px 4px -2px hsl(var(--shadow-color) / 0.10)",
        lg:   "0 18px 34px -10px hsl(var(--shadow-color) / 0.24), 0 6px 12px -4px hsl(var(--shadow-color) / 0.12)",
        brand: "0 0 0 1px hsl(var(--brand) / 0.18), 0 10px 30px -10px hsl(var(--brand) / 0.45)",
      },
      keyframes: {
        in:        { from: { opacity: "0", transform: "translateY(2px)" }, to: { opacity: "1", transform: "none" } },
        fadeIn:    { from: { opacity: "0" }, to: { opacity: "1" } },
        slideIn:   { from: { transform: "translateY(8px)", opacity: "0" }, to: { transform: "none", opacity: "1" } },
        shimmer:   { "100%": { transform: "translateX(100%)" } },
      },
      animation: {
        in:      "in .18s ease-out",
        fadeIn:  "fadeIn .15s ease-out",
        slideIn: "slideIn .2s ease-out",
        shimmer: "shimmer 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
