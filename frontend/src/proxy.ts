import { NextRequest, NextResponse } from 'next/server';

const backendOnlyPrefixes = [
  '/dashboard',
  '/data-quality',
  '/lineage',
  '/lakehouse',
  '/spark-jobs',
  '/realtime',
  '/flink-jobs',
  '/ops',
  '/rag',
  '/simulation',
  '/reports',
  '/settings/licenses',
  '/settings/users',
  '/settings/audit',
];

function configuredPublicOrigins(): string[] {
  const raw = process.env.PUBLIC_SITE_ORIGINS
    || 'http://localhost:3000,http://127.0.0.1:3000';
  const origins = raw.split(',').map((value) => value.trim()).filter(Boolean).map((value) => {
    const parsed = new URL(value);
    if (!['http:', 'https:'].includes(parsed.protocol)
        || parsed.username
        || parsed.password
        || parsed.pathname !== '/'
        || parsed.search
        || parsed.hash) {
      throw new Error('PUBLIC_SITE_ORIGINS must contain only http(s) origins');
    }
    return parsed.origin;
  });
  if (!origins.length) throw new Error('PUBLIC_SITE_ORIGINS must contain at least one origin');
  return Array.from(new Set(origins));
}

const trustedPublicOrigins = configuredPublicOrigins();

function isBackendOnlyPath(pathname: string) {
  return backendOnlyPrefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (!isBackendOnlyPath(pathname)) return NextResponse.next();

  // NextResponse requires an absolute redirect URL. Use the request origin only
  // after an exact allowlist match, otherwise fall back to a configured origin.
  const publicOrigin = trustedPublicOrigins.includes(request.nextUrl.origin)
    ? request.nextUrl.origin
    : trustedPublicOrigins[0];
  const redirectUrl = new URL('/backend-admin', publicOrigin);
  redirectUrl.searchParams.set('from', pathname);
  redirectUrl.searchParams.set('reason', 'backend_admin_only');
  return NextResponse.redirect(redirectUrl, 307);
}

export const config = {
  matcher: [
    '/dashboard/:path*',
    '/data-quality/:path*',
    '/lineage/:path*',
    '/lakehouse/:path*',
    '/spark-jobs/:path*',
    '/realtime/:path*',
    '/flink-jobs/:path*',
    '/ops/:path*',
    '/rag/:path*',
    '/simulation/:path*',
    '/reports/:path*',
    '/settings/licenses/:path*',
    '/settings/users/:path*',
    '/settings/audit/:path*',
  ],
};
