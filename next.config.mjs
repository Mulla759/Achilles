/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: {
    // No ESLint dependency is installed in this package; never let a missing
    // config or an interactive setup prompt interrupt a production build.
    ignoreDuringBuilds: true,
  },
  // In dev, /api/* is served by scripts/devapi.py (the same handler classes
  // Vercel runs). In production Vercel routes api/*.py itself, so this rewrite
  // must not apply there.
  async rewrites() {
    if (process.env.NODE_ENV !== 'development') return [];
    const port = process.env.ACHILLES_DEV_API_PORT ?? '8787';
    return [{ source: '/api/:path*', destination: `http://127.0.0.1:${port}/api/:path*` }];
  },
};

export default nextConfig;
