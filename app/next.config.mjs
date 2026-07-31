/** @type {import('next').NextConfig} */
const nextConfig = {
  // Helper processes + agent runs are long-lived; keep dev server patient.
  experimental: {
    proxyTimeout: 600_000,
  },
  serverExternalPackages: ["@anthropic-ai/claude-agent-sdk"],
};

export default nextConfig;
