import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The API's CORS list and the e2e tests use 127.0.0.1; dev-mode assets are blocked from other origins.
  allowedDevOrigins: ["127.0.0.1"],
  cacheComponents: true,
  partialPrefetching: true,
};

export default nextConfig;
