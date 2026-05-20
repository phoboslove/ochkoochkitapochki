import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/providers/Providers";

export const metadata: Metadata = {
  title: "Buchuchet — AI Backoffice OS",
  description: "AI-powered operations layer for SMB businesses.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
