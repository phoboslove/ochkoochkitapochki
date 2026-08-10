/**
 * Inline SVG (not <img>) so `fill="currentColor"` resolves against the CSS
 * `color` of whatever wraps it — each of the 6 themes sets that via a text
 * utility class, so the wordmark never needs a per-theme asset swap.
 */
export function Wordmark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 480 110"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Wagwan"
      className={className}
    >
      <text
        x="240" y="62" textAnchor="middle" fill="currentColor"
        fontFamily="Georgia, 'Times New Roman', serif" fontSize="42"
        letterSpacing="22" fontWeight="400"
      >
        WAGWAN
      </text>
      <line x1="85" y1="90" x2="395" y2="90" stroke="currentColor" strokeOpacity="0.35" strokeWidth="0.5" />
    </svg>
  );
}
