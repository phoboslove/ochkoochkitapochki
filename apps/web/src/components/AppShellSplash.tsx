"use client";

import { useEffect, useState } from "react";
import { Wordmark } from "@/components/brand/Wordmark";

// Upper bound only — never an artificial floor. The overlay hides as soon as
// `ready` flips true OR this cap elapses, whichever comes first, so a fast
// connection never sits through a needless full-length animation.
const CAP_MS = 1400;
const EXIT_MS = 380;

export function AppShellSplash({ ready }: { ready: boolean }) {
  const [mounted, setMounted] = useState(true);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    const cap = setTimeout(() => setLeaving(true), CAP_MS);
    return () => clearTimeout(cap);
  }, []);

  useEffect(() => {
    if (ready) setLeaving(true);
  }, [ready]);

  useEffect(() => {
    if (!leaving) return;
    const t = setTimeout(() => setMounted(false), EXIT_MS);
    return () => clearTimeout(t);
  }, [leaving]);

  if (!mounted) return null;

  return (
    <div
      aria-hidden="true"
      className="fixed inset-0 z-[999] flex items-center justify-center bg-background transition-opacity ease-out"
      style={{ transitionDuration: `${EXIT_MS}ms`, opacity: leaving ? 0 : 1 }}
    >
      <div className="splash-wordmark w-56 sm:w-64 text-foreground">
        <Wordmark />
      </div>
    </div>
  );
}
