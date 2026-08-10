import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/providers/Providers";

export const metadata: Metadata = {
  title: "Wagwan — AI Backoffice OS",
  description: "AI-powered operations layer for SMB businesses.",
  openGraph: {
    title: "Wagwan — AI Backoffice OS",
    description: "AI-powered operations layer for SMB businesses.",
    siteName: "Wagwan",
  },
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
