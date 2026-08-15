"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { AuthGuard } from "@/components/AuthGuard";
import { AppShellSplash } from "@/components/AppShellSplash";
import { Toaster } from "@/components/Toaster";
import { AlertWatcher } from "@/components/AlertWatcher";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { OfflineBanner } from "@/components/OfflineBanner";
import { BetaBanner } from "@/components/BetaBanner";
import { SubscriptionBanner } from "@/components/SubscriptionBanner";
import { SupportWidget } from "@/components/SupportWidget";
import { WorkspaceEffects } from "@/lib/workspace";
import { I18nRehydrate } from "@/lib/i18n";
import { useOnboarding, useMe } from "@/lib/hooks";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const { data: onboarding } = useOnboarding();
  // Gates the splash overlay — the identity check every app-shell page
  // depends on, so "ready" means "the data behind this screen actually
  // loaded", not a fixed delay.
  const { isSuccess: meReady } = useMe();

  // Redirect only when user lands on the absolute root. Clicking Dashboard
  // explicitly should never bounce them back to the wizard.
  useEffect(() => {
    if (!onboarding || onboarding.completed) return;
    if (path === "/") router.replace("/onboarding");
  }, [onboarding, path, router]);

  return (
    <AuthGuard>
      <AppShellSplash ready={meReady} />
      <WorkspaceEffects />
      <I18nRehydrate />
      <div className="flex h-screen w-screen overflow-hidden flex-col bg-background">
        <BetaBanner />
        <SubscriptionBanner />
        <OfflineBanner />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar />
          <div className="flex flex-1 flex-col overflow-hidden">
            <Topbar />
            <main className="flex-1 overflow-y-auto">
              <div className="mx-auto max-w-[1400px] p-4 sm:p-6 lg:p-8">
                <ErrorBoundary>{children}</ErrorBoundary>
              </div>
            </main>
          </div>
        </div>
        <Toaster />
        <AlertWatcher />
        <SupportWidget />
      </div>
    </AuthGuard>
  );
}
