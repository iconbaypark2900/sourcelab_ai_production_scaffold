import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The Run Studio talks to the FastAPI backend entirely from the browser via
  // NEXT_PUBLIC_SOURCELAB_API_URL, so no server-side rewrites are required.
};

export default nextConfig;
