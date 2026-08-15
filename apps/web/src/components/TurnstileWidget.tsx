"use client";

import { useEffect, useId, useRef } from "react";

const SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js";

declare global {
  interface Window {
    turnstile?: {
      render: (el: HTMLElement, opts: Record<string, unknown>) => string;
      remove: (id: string) => void;
    };
  }
}

let scriptPromise: Promise<void> | null = null;
function loadScript(): Promise<void> {
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise((resolve, reject) => {
    if (window.turnstile) return resolve();
    const s = document.createElement("script");
    s.src = SCRIPT_SRC;
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("turnstile script failed to load"));
    document.head.appendChild(s);
  });
  return scriptPromise;
}

/**
 * Renders nothing when NEXT_PUBLIC_TURNSTILE_SITE_KEY isn't set (local dev
 * without a Cloudflare account) — the backend treats a missing token the
 * same way when TURNSTILE_SECRET_KEY is unset, so both sides degrade
 * together without special-casing "dev mode" anywhere.
 */
export function TurnstileWidget({ onToken }: { onToken: (token: string | null) => void }) {
  const containerId = useId().replace(/:/g, "");
  const widgetId = useRef<string | null>(null);

  useEffect(() => {
    if (!SITE_KEY) return;
    let cancelled = false;
    loadScript().then(() => {
      if (cancelled) return;
      const el = document.getElementById(containerId);
      if (!el || !window.turnstile) return;
      widgetId.current = window.turnstile.render(el, {
        sitekey: SITE_KEY,
        callback: (token: string) => onToken(token),
        "expired-callback": () => onToken(null),
        "error-callback": () => onToken(null),
      });
    });
    return () => {
      cancelled = true;
      if (widgetId.current && window.turnstile) window.turnstile.remove(widgetId.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [containerId]);

  if (!SITE_KEY) return null;
  return <div id={containerId} className="flex justify-center" />;
}
