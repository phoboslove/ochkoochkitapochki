"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { tokenStore } from "@/lib/api";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  useEffect(() => {
    if (!tokenStore.get()) router.replace("/login");
  }, [router]);
  return <>{children}</>;
}
