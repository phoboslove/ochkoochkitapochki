"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AuthGuard } from "@/components/AuthGuard";
import { Wordmark } from "@/components/brand/Wordmark";
import { useMe, useLogout } from "@/lib/hooks";
import { LayoutDashboard, Building2, CreditCard, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/admin", label: "Дашборд", icon: LayoutDashboard, exact: true },
  { href: "/admin/companies", label: "Компании", icon: Building2 },
  { href: "/admin/plans", label: "Тарифы", icon: CreditCard },
];

function AdminShell({ children }: { children: React.ReactNode }) {
  const { data: me, isLoading } = useMe();
  const logout = useLogout();
  const path = usePathname();

  // Real security is the backend 404 on every /admin/* call — this is just
  // UX so a non-admin who lands here (shouldn't be linkable to, but direct
  // URL entry is always possible) sees a plain not-found, not a broken shell.
  if (!isLoading && me && !me.is_platform_admin) {
    return (
      <div className="min-h-screen grid place-items-center bg-background text-foreground">
        <div className="text-center">
          <div className="text-2xl font-semibold mb-1">404</div>
          <div className="text-sm text-muted-foreground">Страница не найдена.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      <aside className="w-[220px] shrink-0 border-r border-border flex flex-col">
        <div className="h-14 flex items-center px-4 border-b border-border">
          <Wordmark className="h-5 w-auto text-foreground" />
        </div>
        <div className="px-4 py-2 text-[10px] uppercase tracking-wider text-muted-foreground">
          Platform Admin
        </div>
        <nav className="flex-1 px-2 space-y-0.5">
          {NAV.map((item) => {
            const active = item.exact ? path === item.href : path?.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] transition-colors",
                  active ? "bg-accent text-foreground font-medium" : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4" strokeWidth={1.75} />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-3 border-t border-border">
          <div className="text-[11px] text-muted-foreground truncate mb-2">{me?.email}</div>
          <button
            onClick={logout}
            className="flex items-center gap-2 text-[12.5px] text-muted-foreground hover:text-foreground"
          >
            <LogOut className="h-3.5 w-3.5" /> Выйти
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[1200px] p-6 lg:p-8">{children}</div>
      </main>
    </div>
  );
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AdminShell>{children}</AdminShell>
    </AuthGuard>
  );
}
