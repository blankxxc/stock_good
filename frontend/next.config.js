/** @type {import('next').NextConfig} */
function backendInternalOrigin() {
  const configured = process.env.BACKEND_INTERNAL_ORIGIN
    || process.env.BACKEND_API_BASE_URL
    || 'http://127.0.0.1:8000';

  let parsed;
  try {
    parsed = new URL(configured);
  } catch {
    throw new Error('BACKEND_INTERNAL_ORIGIN must be an absolute http(s) origin');
  }
  if (!['http:', 'https:'].includes(parsed.protocol)
      || parsed.username
      || parsed.password
      || parsed.pathname !== '/'
      || parsed.search
      || parsed.hash) {
    throw new Error('BACKEND_INTERNAL_ORIGIN must be an http(s) origin without credentials, path, query, or fragment');
  }
  return parsed.origin;
}

const nextConfig = {
  output: 'standalone',
  allowedDevOrigins: ['127.0.0.1', 'localhost'],
  async rewrites() {
    // Next resolves rewrites at build time. Set this server-only value before `npm run build`.
    const apiBase = backendInternalOrigin();
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
