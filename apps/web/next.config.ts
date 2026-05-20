import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  typedRoutes: false,
  devIndicators: false,
  poweredByHeader: false,
  async rewrites() {
    return [
      { source: "/api/v1/:path*", destination: `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/:path*` },
    ];
  },
};

export default config;
