"use client";

import { useEffect, useState } from "react";
import { WifiOff } from "lucide-react";

export function OfflineBanner() {
  const [online, setOnline] = useState(true);
  useEffect(() => {
    setOnline(navigator.onLine);
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);
  if (online) return null;
  return (
    <div className="bg-amber-500/10 border-b border-amber-500/30 text-amber-700 dark:text-amber-300 text-xs px-4 py-1.5 flex items-center gap-2">
      <WifiOff className="h-3 w-3" /> You're offline — changes will retry once you're back online.
    </div>
  );
}
