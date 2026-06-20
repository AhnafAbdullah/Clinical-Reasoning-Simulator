/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Allow importing the @crs/sdk package source from outside apps/frontend
  // (monorepo without a JS workspace).
  experimental: { externalDir: true },
};

export default nextConfig;
