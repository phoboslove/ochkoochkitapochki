"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard, Sparkles, FileText, Receipt, BarChart3, Workflow,
  Users, Plug, ScrollText, Building2, ShieldCheck, Menu, X,
  Activity, LifeBuoy, UserPlus, Gauge, Rocket,
  PanelLeftClose, PanelLeftOpen, ChevronDown,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useApprovals } from "@/lib/hooks";
import { useWorkspace } from "@/lib/workspace";
import { useT } from "@/lib/i18n";
import type { TranslationKey } from "@/lib/translations";

type NavItem = {
  href: string;
  labelKey: TranslationKey;
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  badge?: "approvals";
};

type NavGroup = { key: string; labelKey: TranslationKey; items: NavItem[] };

const GROUPS: NavGroup[] = [
  {
    key: "operations", labelKey: "nav.group.operations",
    items: [
      { href: "/dashboard", labelKey: "nav.dashboard", icon: LayoutDashboard },
      { href: "/invoices",  labelKey: "nav.invoices",  icon: Receipt },
      { href: "/documents", labelKey: "nav.documents", icon: FileText },
      { href: "/approvals", labelKey: "nav.approvals", icon: ShieldCheck, badge: "approvals" },
    ],
  },
  {
    key: "automation", labelKey: "nav.group.automation",
    items: [
      { href: "/assistant", labelKey: "nav.assistant", icon: Sparkles },
      { href: "/workflows", labelKey: "nav.workflows", icon: Workflow },
      { href: "/recovery",  labelKey: "nav.recovery",  icon: LifeBuoy },
    ],
  },
  {
    key: "management", labelKey: "nav.group.management",
    items: [
      { href: "/clients",   labelKey: "nav.clients",    icon: Users },
      { href: "/team",      labelKey: "nav.team",       icon: UserPlus },
      { href: "/reports",   labelKey: "nav.reports",    icon: BarChart3 },
      { href: "/settings",  labelKey: "nav.settings",   icon: Building2 },
      { href: "/onboarding",labelKey: "nav.onboarding", icon: Rocket },
    ],
  },
  {
    key: "system", labelKey: "nav.group.system",
    items: [
      { href: "/integrations", labelKey: "nav.integrations", icon: Plug },
      { href: "/activity",     labelKey: "nav.activity",     icon: Activity },
      { href: "/ops",          labelKey: "nav.ops",          icon: Gauge },
      { href: "/logs",         labelKey: "nav.logs",         icon: ScrollText },
    ],
  },
];

export function Sidebar() {
  const path = usePathname();
  const t = useT();
  const [open, setOpen] = useState(false);
  const collapsed = useWorkspace((s) => s.sidebarCollapsed);
  const toggleCollapsed = useWorkspace((s) => s.toggleCollapsed);
  const groupsExpanded = useWorkspace((s) => s.groupsExpanded);
  const toggleGroup = useWorkspace((s) => s.toggleGroup);
  const { data: approvals } = useApprovals();
  const pendingCount = approvals?.filter((a) => a.status === "PENDING").length ?? 0;

  const body = (
    <>
      <div className={cn(
        "h-14 flex items-center gap-2 px-4 border-b border-border",
        collapsed ? "justify-center px-2" : "",
      )}>
        <div className="h-7 w-7 rounded-md bg-[hsl(var(--brand))] text-[hsl(var(--brand-foreground))] grid place-items-center text-[12px] font-semibold shadow-brand">
          B
        </div>
        {!collapsed && (
          <>
            <div className="leading-tight">
              <div className="text-[13px] font-semibold">Buchuchet</div>
              <div className="text-[10px] text-muted-foreground -mt-0.5">{t("sidebar.brand_tagline")}</div>
            </div>
            <button
              onClick={toggleCollapsed}
              className="ml-auto hidden md:inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent"
              title={t("sidebar.collapse")}
            >
              <PanelLeftClose className="h-3.5 w-3.5" />
            </button>
          </>
        )}
        {collapsed && (
          <button
            onClick={toggleCollapsed}
            className="absolute right-1 top-3 h-6 w-6 grid place-items-center rounded-md text-muted-foreground hover:bg-accent"
            title={t("sidebar.expand")}
          >
            <PanelLeftOpen className="h-3.5 w-3.5" />
          </button>
        )}
        <button className="md:hidden ml-auto p-1 text-muted-foreground" onClick={() => setOpen(false)} aria-label="Close">
          <X className="h-4 w-4" />
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-3">
        {GROUPS.map((g) => {
          const expanded = groupsExpanded[g.key] ?? true;
          return (
            <div key={g.key}>
              {!collapsed && (
                <button
                  onClick={() => toggleGroup(g.key)}
                  className="w-full flex items-center gap-1 px-2 mb-1 text-[10px] uppercase tracking-wider text-muted-foreground hover:text-foreground"
                >
                  <ChevronDown className={cn("h-3 w-3 transition-transform", !expanded && "-rotate-90")} />
                  {t(g.labelKey)}
                </button>
              )}
              {(expanded || collapsed) && (
                <ul className="space-y-0.5">
                  {g.items.map((item) => {
                    const active = path === item.href || path.startsWith(item.href + "/");
                    const Icon = item.icon;
                    return (
                      <li key={item.href}>
                        <Link
                          href={item.href}
                          onClick={() => setOpen(false)}
                          title={collapsed ? t(item.labelKey) : undefined}
                          className={cn(
                            "group relative flex items-center gap-2.5 rounded-md text-[13px] transition-all duration-150",
                            collapsed ? "justify-center h-8 w-8 mx-auto" : "px-2.5 py-1.5",
                            active
                              ? "bg-[hsl(var(--brand-subtle))] text-foreground font-medium"
                              : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                          )}
                        >
                          {active && !collapsed && (
                            <span className="absolute left-0 top-1.5 bottom-1.5 w-[2.5px] rounded-r bg-[hsl(var(--brand))]
                                             shadow-[0_0_8px_hsl(var(--brand)/0.6)]" />
                          )}
                          {active && collapsed && (
                            <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-[hsl(var(--brand))]
                                             shadow-[0_0_6px_hsl(var(--brand)/0.7)]" />
                          )}
                          <Icon className={cn(
                            "h-4 w-4 shrink-0 transition-colors",
                            active ? "text-[hsl(var(--brand))]" : "group-hover:text-foreground",
                          )} strokeWidth={1.75} />
                          {!collapsed && <span className="flex-1 truncate">{t(item.labelKey)}</span>}
                          {!collapsed && item.badge === "approvals" && pendingCount > 0 && (
                            <span className="rounded-md bg-warning-bg text-[hsl(var(--warning))] border border-[hsl(var(--warning)/0.3)] px-1.5 py-0.5 text-[10px] font-medium tabular-nums">
                              {pendingCount}
                            </span>
                          )}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          );
        })}
      </nav>
    </>
  );

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="md:hidden fixed top-3 left-3 z-40 h-9 w-9 rounded-md bg-card border border-border shadow-xs flex items-center justify-center"
        aria-label="Open menu"
      >
        <Menu className="h-4 w-4" />
      </button>

      <aside className={cn(
        "hidden md:flex flex-col shrink-0 border-r border-border bg-surface-2 relative",
        collapsed ? "w-[56px]" : "w-[228px]",
        "transition-[width] duration-200",
      )}>
        {body}
      </aside>

      {open && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-[hsl(var(--shadow-color)/0.5)]" onClick={() => setOpen(false)} />
          <aside className="relative flex w-[260px] flex-col bg-card border-r border-border">{body}</aside>
        </div>
      )}
    </>
  );
}
