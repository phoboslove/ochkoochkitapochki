"use client";

import { useState } from "react";
import {
  Search, Bell, LogOut, Rows3, Rows,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge, StatusDot } from "@/components/ui/badge";
import { useApprovals, useLogout, useMe, useMySubscription } from "@/lib/hooks";
import { useWorkspace } from "@/lib/workspace";
import { CommandPalette, useCommandPaletteShortcut } from "@/components/CommandPalette";
import { ThemeSwitcher } from "@/components/layout/ThemeSwitcher";
import { useT } from "@/lib/i18n";

export function Topbar() {
  const t = useT();
  const { data: me } = useMe();
  const { data: subscription } = useMySubscription();
  const { data: approvals } = useApprovals();
  const logout = useLogout();
  const density = useWorkspace((s) => s.density);
  const setDensity = useWorkspace((s) => s.setDensity);
  const pending = approvals?.filter((a) => a.status === "PENDING").length ?? 0;

  const [cmdOpen, setCmdOpen] = useState(false);
  useCommandPaletteShortcut(() => setCmdOpen(true));

  const initial = (me?.email ?? "?").charAt(0).toUpperCase();
  const mod = typeof navigator !== "undefined" && /Mac|iPhone|iPod|iPad/.test(navigator.platform) ? "⌘" : "Ctrl";

  return (
    <header className="h-14 flex items-center gap-3 border-b border-border bg-surface-2/80 backdrop-blur-md px-4 sm:px-6 pl-14 md:pl-6 sticky top-0 z-30">
      <button
        onClick={() => setCmdOpen(true)}
        className="group flex items-center gap-2 h-8 max-w-md w-full sm:w-72 lg:w-96 rounded-md border border-border bg-card px-2.5 text-left text-muted-foreground hover:border-[hsl(var(--brand)/0.4)] hover:text-foreground transition-all duration-150"
      >
        <Search className="h-3.5 w-3.5 group-hover:text-[hsl(var(--brand))] transition-colors" />
        <span className="text-[12.5px] flex-1 truncate">{t("topbar.search")}</span>
        <span className="hidden sm:inline-flex items-center gap-0.5">
          <span className="kbd">{mod}</span><span className="kbd">K</span>
        </span>
      </button>

      <div className="ml-auto flex items-center gap-1.5">
        {subscription?.plan && (
          <Badge tone={subscription.plan.code === "trial" ? "neutral" : "info"} className="hidden sm:inline-flex uppercase tracking-wider">
            {subscription.plan.code}
          </Badge>
        )}

        <Button
          variant="ghost" size="icon" aria-label="Density"
          onClick={() => setDensity(density === "compact" ? "comfortable" : "compact")}
          title={density === "compact" ? t("topbar.density.comfortable") : t("topbar.density.compact")}
        >
          {density === "compact" ? <Rows className="h-4 w-4" /> : <Rows3 className="h-4 w-4" />}
        </Button>

        <div className="relative">
          <Button variant="ghost" size="icon" aria-label={t("topbar.notifications")}>
            <Bell className="h-4 w-4" />
          </Button>
          {pending > 0 && (
            <span className="absolute top-1.5 right-1.5"><StatusDot tone="warn" /></span>
          )}
        </div>

        <ThemeSwitcher />

        <div className="hidden sm:flex items-center gap-2 pl-2 ml-1 border-l border-border">
          <div className="h-7 w-7 rounded-full bg-accent text-foreground grid place-items-center text-[11px] font-medium">
            {initial}
          </div>
          <div className="text-[11px] leading-tight">
            <div className="font-medium text-foreground truncate max-w-[160px]">{me?.email ?? "—"}</div>
            <div className="text-muted-foreground">{me?.role ?? ""}</div>
          </div>
          <Button variant="ghost" size="icon" onClick={logout} aria-label={t("topbar.logout")}>
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
        <Button variant="ghost" size="icon" className="sm:hidden" onClick={logout} aria-label={t("topbar.logout")}>
          <LogOut className="h-4 w-4" />
        </Button>
      </div>

      <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />
    </header>
  );
}
