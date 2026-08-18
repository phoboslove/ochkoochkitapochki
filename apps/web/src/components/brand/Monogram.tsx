/**
 * Collapsed-sidebar mark — a real glyph in the Wordmark's own serif family,
 * not a generic letter dropped in a div. Self-contained (background + glyph
 * both live in the SVG) since it needs a filled badge, unlike Wordmark's
 * currentColor-only text.
 */
export function Monogram({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 40 40"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Wagwan"
      className={className}
    >
      <rect width="40" height="40" rx="9" fill="hsl(var(--brand))" />
      <text
        x="20" y="27" textAnchor="middle" fill="hsl(var(--brand-foreground))"
        fontFamily="Georgia, 'Times New Roman', serif" fontSize="19" fontWeight="400"
      >
        W
      </text>
    </svg>
  );
}
