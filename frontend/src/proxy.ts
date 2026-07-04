import { NextRequest, NextResponse } from 'next/server';

const BACKEND_ADMIN_URL = process.env.NEXT_PUBLIC_BACKEND_ADMIN_URL ?? 'http://127.0.0.1:8000/admin';

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

function isBackendOnlyPath(pathname: string) {
  return backendOnlyPrefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (!isBackendOnlyPath(pathname)) return NextResponse.next();

  const redirectUrl = new URL(BACKEND_ADMIN_URL);
  redirectUrl.searchParams.set('from', pathname);
  redirectUrl.searchParams.set('reason', 'backend_admin_only');
  return NextResponse.redirect(redirectUrl);
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
