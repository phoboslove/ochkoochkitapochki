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

type NavItem = {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: "approvals";
};

type NavGroup = { key: string; label: string; items: NavItem[] };

const GROUPS: NavGroup[] = [
  {
    key: "operations", label: "Operations",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/invoices",  label: "Invoices",  icon: Receipt },
      { href: "/documents", label: "Documents", icon: FileText },
      { href: "/approvals", label: "Approvals", icon: ShieldCheck, badge: "approvals" },
    ],
  },
  {
    key: "automation", label: "Automation",
    items: [
      { href: "/assistant", label: "AI Assistant", icon: Sparkles },
      { href: "/workflows", label: "Workflows",    icon: Workflow },
      { href: "/recovery",  label: "Recovery",     icon: LifeBuoy },
    ],
  },
  {
    key: "management", label: "Management",
    items: [
      { href: "/clients",   label: "Clients",  icon: Users },
      { href: "/team",      label: "Team",     icon: UserPlus },
      { href: "/reports",   label: "Reports",  icon: BarChart3 },
      { href: "/settings",  label: "Business", icon: Building2 },
      { href: "/onboarding",label: "Setup guide", icon: Rocket },
    ],
  },
  {
    key: "system", label: "System",
    items: [
      { href: "/integrations", label: "Integrations", icon: Plug },
      { href: "/activity",     label: "Activity",     icon: Activity },
      { href: "/ops",          label: "Operations",   icon: Gauge },
      { href: "/logs",         label: "Logs",         icon: ScrollText },
    ],
  },
];

export function Sidebar() {
  const path = usePathname();
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
              <div className="text-[10px] text-muted-foreground -mt-0.5">Backoffice OS</div>
            </div>
            <button
              onClick={toggleCollapsed}
              className="ml-auto hidden md:inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent"
              title="Collapse sidebar"
            >
              <PanelLeftClose className="h-3.5 w-3.5" />
            </button>
          </>
        )}
        {collapsed && (
          <button
            onClick={toggleCollapsed}
            className="absolute right-1 top-3 h-6 w-6 grid place-items-center rounded-md text-muted-foreground hover:bg-accent"
            title="Expand sidebar"
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
                  {g.label}
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
                          title={collapsed ? item.label : undefined}
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
                          {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
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
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="relative flex w-[260px] flex-col bg-card border-r border-border">{body}</aside>
        </div>
      )}
    </>
  );
}
