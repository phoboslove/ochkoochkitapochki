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

/** Apply density to the document root. Mount once near top of tree.
 *
 * `accent`/`setAccent` are kept in the store for a future per-user accent
 * picker, but are intentionally NOT applied here: forcing a hardcoded
 * inline `--brand` on <html> would outrank every theme's own `--brand`
 * token (inline style beats any selector), silently flattening all six
 * themes to one accent color the moment this component mounts. */
export function WorkspaceEffects() {
  const density = useWorkspace((s) => s.density);

  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.classList.toggle("density-compact", density === "compact");
  }, [density]);

  return null;
}
