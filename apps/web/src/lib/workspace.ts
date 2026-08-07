"use client";

import { useEffect } from "react";
import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Per-user workspace preferences. Persisted to localStorage; in production
 * mirror to backend via /companies/settings.user_prefs (out of scope here).
 */
type Density = "comfortable" | "compact";
export type ClockStyle = "digital" | "analog" | "minimal";

interface WorkspaceState {
  sidebarCollapsed: boolean;
  density: Density;
  accent: string;           // hex
  pinnedWidgets: string[];
  groupsExpanded: Record<string, boolean>;
  clockStyle: ClockStyle;
  setCollapsed:  (v: boolean) => void;
  toggleCollapsed: () => void;
  setDensity:    (v: Density) => void;
  setAccent:     (hex: string) => void;
  toggleGroup:   (k: string) => void;
  pin:           (key: string) => void;
  unpin:         (key: string) => void;
  setClockStyle: (v: ClockStyle) => void;
}

export const useWorkspace = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      sidebarCollapsed: false,
      density: "comfortable",
      accent: "#4f46e5",
      pinnedWidgets: [],
      groupsExpanded: { operations: true, automation: true, management: true, system: true },
      clockStyle: "digital",
      setCollapsed:    (v) => set({ sidebarCollapsed: v }),
      toggleCollapsed: () => set({ sidebarCollapsed: !get().sidebarCollapsed }),
      setDensity:      (v) => set({ density: v }),
      setAccent:       (hex) => set({ accent: hex }),
      toggleGroup:     (k) => set({ groupsExpanded: { ...get().groupsExpanded, [k]: !get().groupsExpanded[k] } }),
      pin:             (key) => set({ pinnedWidgets: [...new Set([...get().pinnedWidgets, key])] }),
      unpin:           (key) => set({ pinnedWidgets: get().pinnedWidgets.filter((k) => k !== key) }),
      setClockStyle:   (v) => set({ clockStyle: v }),
    }),
    { name: "buchuchet.workspace" },
  ),
);

/** Apply density + accent to the document root. Mount once near top of tree. */
export function WorkspaceEffects() {
  const density = useWorkspace((s) => s.density);
  const accent = useWorkspace((s) => s.accent);

  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.classList.toggle("density-compact", density === "compact");
  }, [density]);

  useEffect(() => {
    if (typeof document === "undefined") return;
    const hsl = hexToHslTriplet(accent);
    if (hsl) document.documentElement.style.setProperty("--brand", hsl);
  }, [accent]);

  return null;
}

function hexToHslTriplet(hex: string): string | null {
  const m = hex.replace("#", "").match(/^([0-9a-f]{6}|[0-9a-f]{3})$/i);
  if (!m) return null;
  let h = m[0];
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  const r = parseInt(h.slice(0, 2), 16) / 255;
  const g = parseInt(h.slice(2, 4), 16) / 255;
  const b = parseInt(h.slice(4, 6), 16) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const l = (max + min) / 2;
  let s = 0, hue = 0;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: hue = (g - b) / d + (g < b ? 6 : 0); break;
      case g: hue = (b - r) / d + 2; break;
      case b: hue = (r - g) / d + 4; break;
    }
    hue /= 6;
  }
  return `${Math.round(hue * 360)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
}
