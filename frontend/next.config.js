/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async rewrites() {
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${apiBase}/api/:path*`
      },
      {
        source: '/health',
        destination: `${apiBase}/health`
      }
    ];
  }
};
module.exports = nextConfig;
