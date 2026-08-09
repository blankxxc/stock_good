export type AdminUser = {
  id: number;
  username: string;
  display_name: string;
  role: 'user' | 'admin';
  is_active: boolean | number;
  created_at: string;
  last_login_at: string | null;
  watchlist_count: number;
  active_sessions: number;
  failed_attempts: number;
  locked_until: string | null;
  password_changed_at: string;
};

export type AuditEvent = {
  id: number;
  event_type: string;
  user_id: number | null;
  username: string | null;
  detail: string | null;
  created_at: string;
};

export type RouteLink = { path: string; label: string; method: string };

export type AdminOverview = {
  status: string;
  service: { name: string; version: string; time: string };
  auth_summary: {
    total_users: number;
    active_users: number;
    active_sessions: number;
    watchlist_items: number;
  };
  module_summary: { total_modules: number; ready_modules: number; pending_modules: number };
  factor_summary: {
    factor_count: number;
    category_count: number;
    point_in_time_violations: number | null;
    admission_ready_count: number | null;
  };
  module_statuses: Record<string, string>;
  critical_routes: RouteLink[];
  data_fabric: { policy: string; internal_routes: RouteLink[] };
  documentation_links: Array<{ path: string; label: string }>;
};

export type DailyUserPoint = { key: string; label: string; count: number };
export type AuditRisk = 'danger' | 'warning' | 'normal';
export type AdminSection = 'overview' | 'users' | 'audit' | 'data' | 'research' | 'system';
export type AuditWindow = '24h' | '7d' | 'all';

const ADMIN_SECTIONS = new Set<AdminSection>(['overview', 'users', 'audit', 'data', 'research', 'system']);

const REPORT_TIME_ZONE = 'Asia/Shanghai';

export function reportingDayKey(value: Date | string): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: REPORT_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date);
  const valueFor = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? '';
  return `${valueFor('year')}-${valueFor('month')}-${valueFor('day')}`;
}

export function buildUserCreationSeries(
  users: AdminUser[],
  days: number,
  now: Date = new Date(),
): DailyUserPoint[] {
  const counts = new Map<string, number>();
  users.forEach((user) => {
    const key = reportingDayKey(user.created_at);
    if (key) counts.set(key, (counts.get(key) ?? 0) + 1);
  });

  return Array.from({ length: days }, (_, index) => {
    const date = new Date(now.getTime() - (days - index - 1) * 86_400_000);
    const key = reportingDayKey(date);
    return { key, label: key.slice(5).replace('-', '/'), count: counts.get(key) ?? 0 };
  });
}

export function auditRisk(eventType: string): AuditRisk {
  const value = eventType.toLowerCase();
  if (/(context_mismatch|access_denied|admin_.*denied|account_locked|csrf_denied|origin_denied)/.test(value)) {
    return 'danger';
  }
  if (/(failed|failure|invalid|rate_limit|locked|denied)/.test(value)) return 'warning';
  return 'normal';
}

export function formatAdminDate(value: string | null | undefined): string {
  if (!value) return '从未';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '未知';
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: REPORT_TIME_ZONE,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);
}

export function isActiveUser(user: AdminUser): boolean {
  return user.is_active === true || user.is_active === 1;
}

export function isUserLocked(user: Pick<AdminUser, 'locked_until'>, now: Date = new Date()): boolean {
  if (!user.locked_until) return false;
  const lockedUntil = new Date(user.locked_until);
  return !Number.isNaN(lockedUntil.getTime()) && lockedUntil.getTime() > now.getTime();
}

export function adminSectionFromHash(hash: string): AdminSection {
  const candidate = hash.trim().replace(/^#/, '').toLowerCase() as AdminSection;
  return ADMIN_SECTIONS.has(candidate) ? candidate : 'overview';
}

export function isAuditEventWithinWindow(
  createdAt: string,
  window: AuditWindow,
  now: Date = new Date(),
): boolean {
  if (window === 'all') return true;
  const created = new Date(createdAt);
  if (Number.isNaN(created.getTime())) return false;
  const duration = window === '24h' ? 86_400_000 : 7 * 86_400_000;
  return created.getTime() >= now.getTime() - duration;
}
