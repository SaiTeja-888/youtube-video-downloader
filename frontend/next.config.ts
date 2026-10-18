import type { NextConfig } from "next";

const getBackendUrl = () => {
  const envUrl = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
  const trimmed = envUrl.trim().replace(/\/+$/, "");
  return trimmed.endsWith("/api") ? trimmed : `${trimmed}/api`;
};

const nextConfig: NextConfig = {
  async rewrites() {
    const backend = getBackendUrl();
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/:path*`,
      },
    ];
  },
};

export default nextConfig;
