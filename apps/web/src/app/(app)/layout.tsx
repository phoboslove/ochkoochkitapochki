"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { AuthGuard } from "@/components/AuthGuard";
import { Toaster } from "@/components/Toaster";
import { AlertWatcher } from "@/components/AlertWatcher";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { OfflineBanner } from "@/components/OfflineBanner";
import { SupportWidget } from "@/components/SupportWidget";
import { WorkspaceEffects } from "@/lib/workspace";
import { useOnboarding } from "@/lib/hooks";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const { data: onboarding } = useOnboarding();

  // Redirect only when user lands on the absolute root. Clicking Dashboard
  // explicitly should never bounce them back to the wizard.
  useEffect(() => {
    if (!onboarding || onboarding.completed) return;
    if (path === "/") router.replace("/onboarding");
  }, [onboarding, path, router]);

  return (
    <AuthGuard>
      <WorkspaceEffects />
      <div className="flex h-screen w-screen overflow-hidden flex-col bg-background">
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
