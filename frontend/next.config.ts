import { type NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Rewrite /api/* to the backend so the browser hits same-origin during dev.
  // Override via `NAGARA_API_URL` for deployments where the backend lives
  // behind its own ingress.
  async rewrites() {
    const backend = process.env.NAGARA_API_URL ?? 'http://127.0.0.1:8000';
    return [{ source: '/api/:path*', destination: `${backend}/:path*` }];
  },
};

export default nextConfig;
