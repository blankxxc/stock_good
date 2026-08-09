'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  adminSectionFromHash,
  auditRisk,
  buildUserCreationSeries,
  formatAdminDate,
  isAuditEventWithinWindow,
  isActiveUser,
  isUserLocked,
  type AdminOverview,
  type AdminSection,
  type AdminUser,
  type AuditEvent,
  type AuditRisk,
  type AuditWindow,
  type DailyUserPoint,
} from '../lib/adminDashboard';
import {
  AdminDataGovernance,
  AdminResearchOperations,
  AdminSystemOperations,
  AdminUserDrawer,
  downloadCsv,
  type AdminAuthStatus,
} from './AdminOperations';
import {
  getSessionStatus,
  invalidateSessionStatus,
  readCsrfToken,
  responseError,
  type SessionUser,
} from '../lib/auth';

type UserStatusFilter = 'all' | 'active' | 'disabled' | 'locked';
type UserRoleFilter = 'all' | 'admin' | 'user';
type AuditRiskFilter = 'all' | AuditRisk;
type ActionFeedback = { tone: 'success' | 'warning' | 'error'; message: string };

type UsersPayload = { users: AdminUser[]; count: number };
type AuditPayload = { events: AuditEvent[]; count: number };

const sectionItems: Array<{ id: AdminSection; label: string; kicker: string; glyph: string }> = [
  { id: 'overview', label: '运营总览', kicker: 'Overview', glyph: '⌁' },
  { id: 'users', label: '用户管理', kicker: 'Accounts', glyph: '◎' },
  { id: 'audit', label: '安全审计', kicker: 'Audit', glyph: '◇' },
  { id: 'data', label: '数据治理', kicker: 'Data fabric', glyph: '◫' },
  { id: 'research', label: '研究运行', kicker: 'Research ops', glyph: '△' },
  { id: 'system', label: '运行健康', kicker: 'System', glyph: '▦' },
];

const sectionDescriptions: Record<AdminSection, string> = {
  overview: '账户增长、平台使用与安全状态的真实数据快照。',
  users: '管理真实登录账户；研究治理角色与此处权限模型分开。',
  audit: '检查最近最多 200 条认证、权限与管理操作事件。',
  data: '检查数据质量、血缘、湖仓、批流任务与内部数据入口。',
  research: '复核因子、模型、评分、回测、证据与报告运行边界。',
  system: '查看服务模块、认证策略、接口契约与完整运行矩阵。',
};

async function fetchAdminPayload<T>(path: string): Promise<T> {
  const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store' });
  if (response.status === 401) {
    window.location.assign('/login?next=/admin-console');
    throw new Error('登录状态已失效，正在跳转登录页。');
  }
  if (!response.ok) throw new Error(await responseError(response));
  return response.json() as Promise<T>;
}

function percent(part: number, total: number): number {
  if (!total) return 0;
  return Math.round((part / total) * 100);
}

function shortEventName(value: string): string {
  const names: Record<string, string> = {
    login_success: '登录成功',
    login_failed: '登录失败',
    register_success: '注册成功',
    logout: '安全退出',
    admin_user_status: '用户状态变更',
    admin_user_unlock: '账户解锁',
    admin_user_sessions_revoked: '强制下线',
    csrf_denied: 'CSRF 拒绝',
    origin_denied: '来源拒绝',
    admin_access_denied: '后台访问拒绝',
  };
  return names[value] ?? value.replaceAll('_', ' ');
}

function riskLabel(risk: AuditRisk): string {
  return risk === 'danger' ? '高风险' : risk === 'warning' ? '需关注' : '常规';
}

function KpiCard({ label, value, note, tone = 'cyan' }: {
  label: string;
  value: number | string;
  note: string;
  tone?: 'cyan' | 'green' | 'gold' | 'purple';
}) {
  return (
    <article className={`admin-kpi admin-tone--${tone}`}>
      <div className="admin-kpi__top"><span>{label}</span><i aria-hidden="true" /></div>
      <strong>{value}</strong>
      <p>{note}</p>
    </article>
  );
}

function LoadingDashboard() {
  return (
    <div className="admin-loading" role="status" aria-live="polite">
      <span className="admin-visually-hidden">正在加载管理数据</span>
      <div className="admin-skeleton admin-skeleton--heading" />
      <div className="admin-kpi-grid">
        {Array.from({ length: 4 }, (_, index) => <div className="admin-skeleton admin-skeleton--kpi" key={index} />)}
      </div>
      <div className="admin-overview-grid">
        <div className="admin-skeleton admin-skeleton--chart" />
        <div className="admin-skeleton admin-skeleton--chart" />
      </div>
    </div>
  );
}

function UserGrowthChart({ points }: { points: DailyUserPoint[] }) {
  const width = 760;
  const height = 250;
  const baseline = 210;
  const max = Math.max(1, ...points.map((point) => point.count));
  const step = points.length > 1 ? 690 / (points.length - 1) : 0;
  const coordinates = points.map((point, index) => ({
    ...point,
    x: 35 + index * step,
    y: baseline - (point.count / max) * 150,
  }));
  const path = coordinates.map((point, index) => `${index ? 'L' : 'M'} ${point.x} ${point.y}`).join(' ');
  const ticks = [0, Math.floor((points.length - 1) / 2), points.length - 1].filter((value, index, all) => all.indexOf(value) === index);

  return (
    <div className="admin-growth-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`最近 ${points.length} 天每日创建用户趋势`}>
        <defs>
          <linearGradient id="adminGrowthFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#38bdf8" stopOpacity=".30" />
            <stop offset="1" stopColor="#38bdf8" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[60, 110, 160, 210].map((y) => <line className="admin-chart-gridline" x1="35" x2="725" y1={y} y2={y} key={y} />)}
        {path ? <path className="admin-chart-area" d={`${path} L ${coordinates.at(-1)?.x ?? 35} ${baseline} L 35 ${baseline} Z`} /> : null}
        {path ? <path className="admin-chart-line" d={path} /> : null}
        {coordinates.map((point) => (
          <g key={point.key}>
            <circle className="admin-chart-dot" cx={point.x} cy={point.y} r={point.count ? 4 : 2.5}>
              <title>{point.key}：创建 {point.count} 个用户</title>
            </circle>
          </g>
        ))}
        {ticks.map((index) => (
          <text className="admin-chart-label" x={coordinates[index]?.x ?? 35} y="238" textAnchor={index === 0 ? 'start' : index === points.length - 1 ? 'end' : 'middle'} key={index}>
            {points[index]?.label}
          </text>
        ))}
      </svg>
    </div>
  );
}

function EmptyState({ title, detail, onReset }: { title: string; detail: string; onReset?: () => void }) {
  return (
    <div className="admin-empty">
      <span aria-hidden="true">∅</span>
      <strong>{title}</strong>
      <p>{detail}</p>
      {onReset ? <button type="button" onClick={onReset}>清除筛选</button> : null}
    </div>
  );
}

export function AdminDashboard() {
  const [section, setSection] = useState<AdminSection>('overview');
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [authStatus, setAuthStatus] = useState<AdminAuthStatus | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [currentUser, setCurrentUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [range, setRange] = useState<7 | 30 | 90>(30);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<UserStatusFilter>('all');
  const [roleFilter, setRoleFilter] = useState<UserRoleFilter>('all');
  const [auditQuery, setAuditQuery] = useState('');
  const [auditFilter, setAuditFilter] = useState<AuditRiskFilter>('all');
  const [auditWindow, setAuditWindow] = useState<AuditWindow>('7d');
  const [updatingUserId, setUpdatingUserId] = useState<number | null>(null);
  const [revokingUserId, setRevokingUserId] = useState<number | null>(null);
  const [unlockingUserId, setUnlockingUserId] = useState<number | null>(null);
  const [actionFeedback, setActionFeedback] = useState<ActionFeedback | null>(null);
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const requestSequence = useRef(0);

  const loadDashboard = useCallback(async (refresh = false): Promise<boolean> => {
    const sequence = ++requestSequence.current;
    if (refresh) setRefreshing(true);
    else setLoading(true);
    setErrors({});

    const results = await Promise.allSettled([
      fetchAdminPayload<AdminOverview>('/api/admin/overview'),
      fetchAdminPayload<UsersPayload>('/api/admin/users'),
      fetchAdminPayload<AuditPayload>('/api/admin/audit?limit=200'),
      fetchAdminPayload<AdminAuthStatus>('/api/auth/status'),
      getSessionStatus({ refresh }),
    ]);
    if (sequence !== requestSequence.current) return false;

    const nextErrors: Record<string, string> = {};
    if (results[0].status === 'fulfilled') setOverview(results[0].value);
    else {
      setOverview(null);
      nextErrors.overview = results[0].reason instanceof Error ? results[0].reason.message : '总览加载失败';
    }
    if (results[1].status === 'fulfilled') {
      const loadedUsers = results[1].value.users;
      setUsers(loadedUsers);
      setSelectedUser((current) => current
        ? loadedUsers.find((user) => user.id === current.id) ?? null
        : null);
    }
    else nextErrors.users = results[1].reason instanceof Error ? results[1].reason.message : '用户加载失败';
    if (results[2].status === 'fulfilled') setEvents(results[2].value.events);
    else nextErrors.audit = results[2].reason instanceof Error ? results[2].reason.message : '审计加载失败';
    if (results[3].status === 'fulfilled') setAuthStatus(results[3].value);
    else {
      setAuthStatus(null);
      nextErrors.authStatus = results[3].reason instanceof Error ? results[3].reason.message : '认证策略加载失败';
    }
    if (results[4].status === 'fulfilled') {
      const user = results[4].value.user ?? null;
      setCurrentUser(user);
      if (user && user.role !== 'admin') nextErrors.access = '当前账号没有管理员权限。';
    } else {
      nextErrors.session = results[4].reason instanceof Error ? results[4].reason.message : '会话读取失败';
    }
    setErrors(nextErrors);
    if (results.some((result) => result.status === 'fulfilled')) setLastUpdated(new Date());
    setLoading(false);
    setRefreshing(false);
    return Object.keys(nextErrors).length === 0;
  }, []);

  useEffect(() => {
    void loadDashboard();
    return () => { requestSequence.current += 1; };
  }, [loadDashboard]);

  useEffect(() => {
    const syncSection = () => setSection(adminSectionFromHash(window.location.hash));
    syncSection();
    window.addEventListener('hashchange', syncSection);
    return () => window.removeEventListener('hashchange', syncSection);
  }, []);

  const navigateToSection = useCallback((next: AdminSection) => {
    setSection(next);
    const nextHash = `#${next}`;
    if (window.location.hash !== nextHash) window.location.hash = nextHash;
  }, []);
  const closeUserDrawer = useCallback(() => setSelectedUser(null), []);

  useEffect(() => {
    if (!autoRefresh) return;
    const timer = window.setInterval(() => { void loadDashboard(true); }, 30_000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, loadDashboard]);

  const creationSeries = useMemo(() => buildUserCreationSeries(users, range), [users, range]);
  const todayCreated = creationSeries.at(-1)?.count ?? 0;
  const periodCreated = creationSeries.reduce((sum, point) => sum + point.count, 0);
  const activeUsers = users.filter(isActiveUser).length;
  const disabledUsers = Math.max(0, users.length - activeUsers);
  const lockedUsers = users.filter((user) => isUserLocked(user)).length;
  const securityEvents = events.filter((event) => auditRisk(event.event_type) !== 'normal');
  const warningEvents = events.filter((event) => auditRisk(event.event_type) === 'warning');
  const dangerousEvents = events.filter((event) => auditRisk(event.event_type) === 'danger');

  const auditDistribution = useMemo(() => {
    const counts = new Map<string, number>();
    events.forEach((event) => counts.set(event.event_type, (counts.get(event.event_type) ?? 0) + 1));
    return Array.from(counts, ([type, count]) => ({ type, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 6);
  }, [events]);
  const maxAuditCount = Math.max(1, ...auditDistribution.map((item) => item.count));

  const filteredUsers = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return users.filter((user) => {
      const matchesQuery = !normalized || `${user.display_name} ${user.username}`.toLowerCase().includes(normalized);
      const matchesStatus = statusFilter === 'all'
        || (statusFilter === 'active' && isActiveUser(user))
        || (statusFilter === 'disabled' && !isActiveUser(user))
        || (statusFilter === 'locked' && isUserLocked(user));
      const matchesRole = roleFilter === 'all' || user.role === roleFilter;
      return matchesQuery && matchesStatus && matchesRole;
    });
  }, [query, roleFilter, statusFilter, users]);

  const filteredEvents = useMemo(() => {
    const normalized = auditQuery.trim().toLowerCase();
    return events.filter((event) => {
      const risk = auditRisk(event.event_type);
      const matchesRisk = auditFilter === 'all' || auditFilter === risk;
      const matchesWindow = isAuditEventWithinWindow(event.created_at, auditWindow);
      const haystack = `${event.event_type} ${event.username ?? ''} ${event.detail ?? ''}`.toLowerCase();
      return matchesRisk && matchesWindow && (!normalized || haystack.includes(normalized));
    });
  }, [auditFilter, auditQuery, auditWindow, events]);

  function openUsers(status: UserStatusFilter = 'all') {
    setStatusFilter(status);
    setQuery('');
    navigateToSection('users');
  }

  function openAudit(risk: AuditRiskFilter = 'all') {
    setAuditFilter(risk);
    setAuditQuery('');
    setAuditWindow('all');
    navigateToSection('audit');
  }

  const attentionItems = [
    { label: '禁用账户', value: disabledUsers, tone: disabledUsers ? 'warning' : 'ok', detail: disabledUsers ? '点击查看并复核禁用原因' : '全部账户处于启用状态', activate: () => openUsers('disabled') },
    { label: '锁定账户', value: lockedUsers, tone: lockedUsers ? 'danger' : 'ok', detail: lockedUsers ? '点击处理登录锁定' : '当前没有被锁定的账户', activate: () => openUsers('locked') },
    { label: '需关注事件', value: warningEvents.length, tone: warningEvents.length ? 'warning' : 'ok', detail: '失败、限流与一般拒绝事件', activate: () => openAudit('warning') },
    { label: '高风险事件', value: dangerousEvents.length, tone: dangerousEvents.length ? 'danger' : 'ok', detail: dangerousEvents.length ? '点击查看来源、CSRF 或权限拒绝' : '最近事件中未发现高风险项', activate: () => openAudit('danger') },
    { label: '待就绪模块', value: overview?.module_summary.pending_modules ?? '—', tone: overview?.module_summary.pending_modules ? 'warning' : 'ok', detail: overview ? '点击打开完整模块矩阵' : '模块快照当前不可用', activate: () => navigateToSection('system') },
  ];

  async function toggleUser(user: AdminUser) {
    const nextActive = !isActiveUser(user);
    const verb = nextActive ? '启用' : '禁用';
    if (!window.confirm(`${verb}“${user.display_name}（@${user.username}）”？${nextActive ? '' : `\n禁用后将立即撤销 ${user.active_sessions} 个活跃会话，但不会删除自选数据。`}`)) return;
    setUpdatingUserId(user.id);
    setActionFeedback(null);
    try {
      const response = await fetch(`/api/admin/users/${user.id}`, {
        method: 'PATCH',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfToken() },
        body: JSON.stringify({ is_active: nextActive }),
      });
      if (response.status === 401) {
        window.location.assign('/login?next=/admin-console');
        return;
      }
      if (!response.ok) throw new Error(await responseError(response));
      setSelectedUser((current) => current?.id === user.id
        ? { ...current, is_active: nextActive, active_sessions: nextActive ? current.active_sessions : 0 }
        : current);
      const refreshed = await loadDashboard(true);
      setActionFeedback({
        tone: refreshed ? 'success' : 'warning',
        message: refreshed
          ? `${user.display_name} 已${verb}。`
          : `${user.display_name} 已${verb}，但最新列表加载失败；请稍后刷新确认。`,
      });
    } catch (error) {
      setActionFeedback({ tone: 'error', message: error instanceof Error ? error.message : `${verb}失败，请重试。` });
    } finally {
      setUpdatingUserId(null);
    }
  }

  async function revokeUserSessions(user: AdminUser) {
    const isSelf = user.id === currentUser?.id;
    const revocableSessions = Math.max(0, user.active_sessions - (isSelf ? 1 : 0));
    if (!revocableSessions) return;
    const selfNote = isSelf ? '\n系统会保留你当前正在使用的这个管理会话。' : '';
    if (!window.confirm(`强制下线“${user.display_name}（@${user.username}）”的 ${revocableSessions} 个会话？${selfNote}`)) return;
    setRevokingUserId(user.id);
    setActionFeedback(null);
    try {
      const response = await fetch(`/api/admin/users/${user.id}/revoke-sessions`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRF-Token': readCsrfToken() },
      });
      if (response.status === 401) {
        window.location.assign('/login?next=/admin-console');
        return;
      }
      if (!response.ok) throw new Error(await responseError(response));
      const result = await response.json() as { revoked_sessions: number; remaining_active_sessions: number };
      setSelectedUser((current) => current?.id === user.id
        ? { ...current, active_sessions: result.remaining_active_sessions }
        : current);
      const refreshed = await loadDashboard(true);
      setActionFeedback({
        tone: refreshed ? 'success' : 'warning',
        message: refreshed
          ? `${user.display_name} 的 ${result.revoked_sessions} 个会话已撤销。`
          : `会话已撤销，但最新列表加载失败；请稍后刷新确认。`,
      });
    } catch (error) {
      setActionFeedback({ tone: 'error', message: error instanceof Error ? error.message : '强制下线失败，请重试。' });
    } finally {
      setRevokingUserId(null);
    }
  }

  async function unlockUser(user: AdminUser) {
    if (!isUserLocked(user) && user.failed_attempts === 0) return;
    if (!window.confirm(`清除“${user.display_name}（@${user.username}）”的登录失败计数并解除锁定？`)) return;
    setUnlockingUserId(user.id);
    setActionFeedback(null);
    try {
      const response = await fetch(`/api/admin/users/${user.id}/unlock`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRF-Token': readCsrfToken() },
      });
      if (response.status === 401) {
        window.location.assign('/login?next=/admin-console');
        return;
      }
      if (!response.ok) throw new Error(await responseError(response));
      setSelectedUser((current) => current?.id === user.id
        ? { ...current, failed_attempts: 0, locked_until: null }
        : current);
      const refreshed = await loadDashboard(true);
      setActionFeedback({
        tone: refreshed ? 'success' : 'warning',
        message: refreshed ? `${user.display_name} 已解除登录锁定。` : '账户已解锁，但最新列表加载失败；请稍后刷新确认。',
      });
    } catch (error) {
      setActionFeedback({ tone: 'error', message: error instanceof Error ? error.message : '解除锁定失败，请重试。' });
    } finally {
      setUnlockingUserId(null);
    }
  }

  function clearUserFilters() {
    setQuery('');
    setStatusFilter('all');
    setRoleFilter('all');
  }

  function exportUsers() {
    downloadCsv(
      `admin-users-${new Date().toISOString().slice(0, 10)}.csv`,
      ['id', 'username', 'display_name', 'role', 'is_active', 'created_at', 'last_login_at', 'watchlist_count', 'active_sessions'],
      filteredUsers.map((user) => [user.id, user.username, user.display_name, user.role, isActiveUser(user), user.created_at, user.last_login_at, user.watchlist_count, user.active_sessions]),
    );
  }

  function exportAudit() {
    downloadCsv(
      `admin-audit-${new Date().toISOString().slice(0, 10)}.csv`,
      ['id', 'risk', 'event_type', 'user_id', 'username', 'detail', 'created_at'],
      filteredEvents.map((event) => [event.id, auditRisk(event.event_type), event.event_type, event.user_id, event.username, event.detail, event.created_at]),
    );
  }

  async function logoutAdmin() {
    if (loggingOut) return;
    setLoggingOut(true);
    try {
      const response = await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRF-Token': readCsrfToken() },
      });
      if (!response.ok && response.status !== 401) throw new Error(await responseError(response));
      invalidateSessionStatus();
      window.location.replace('/login');
    } catch (error) {
      setActionFeedback({ tone: 'error', message: error instanceof Error ? error.message : '退出失败，请重试。' });
      setLoggingOut(false);
    }
  }

  if (loading) {
    return (
      <section className="admin-dashboard">
        <aside className="admin-sidebar admin-sidebar--loading" aria-hidden="true" />
        <div className="admin-workspace"><LoadingDashboard /></div>
      </section>
    );
  }

  if (errors.access) {
    return (
      <section className="admin-access-denied">
        <span aria-hidden="true">⊘</span>
        <p className="admin-eyebrow">Access denied</p>
        <h1>需要管理员权限</h1>
        <p>{errors.access}后台数据仍由 FastAPI 在每个接口上独立鉴权，隐藏入口并不等于授权。</p>
        <a className="button primary" href="/">返回用户前台</a>
      </section>
    );
  }

  return (
    <section className="admin-dashboard" aria-busy={refreshing}>
      <aside className="admin-sidebar" aria-label="后台管理导航">
        <div className="admin-sidebar__brand">
          <span>OA</span>
          <div><strong>Control Room</strong><small>管理员工作台</small></div>
        </div>
        <nav>
          <p>管理视图</p>
          {sectionItems.map((item) => (
            <button
              type="button"
              className={section === item.id ? 'active' : ''}
              aria-current={section === item.id ? 'page' : undefined}
              aria-label={item.label}
              title={item.label}
              onClick={() => navigateToSection(item.id)}
              key={item.id}
            >
              <span aria-hidden="true">{item.glyph}</span>
              <b>{item.label}<small>{item.kicker}</small></b>
            </button>
          ))}
        </nav>
        <div className="admin-sidebar__footer">
          <div className="admin-avatar">{currentUser?.display_name.slice(0, 1).toUpperCase() ?? 'A'}</div>
          <div><strong>{currentUser?.display_name ?? '管理员'}</strong><small>@{currentUser?.username ?? 'admin'}</small></div>
          <div className="admin-sidebar__footer-actions">
            <a href="/" aria-label="返回用户前台" title="返回用户前台">↗</a>
            <button type="button" onClick={() => void logoutAdmin()} disabled={loggingOut} aria-label="安全退出" title="安全退出">⏻</button>
          </div>
        </div>
      </aside>

      <div className="admin-workspace">
        <header className="admin-page-header">
          <div>
            <p className="admin-eyebrow">Obsidian Alpha · admin</p>
            <h1>{sectionItems.find((item) => item.id === section)?.label}</h1>
            <p>{sectionDescriptions[section]}</p>
          </div>
          <div className="admin-header-actions">
            <label className="admin-auto-refresh"><input type="checkbox" checked={autoRefresh} onChange={(event) => setAutoRefresh(event.target.checked)} /><span>30 秒自动刷新</span></label>
            <div className="admin-freshness"><i /><span>实时快照<small>{lastUpdated ? `${formatAdminDate(lastUpdated.toISOString())} 更新` : '等待数据'}</small></span></div>
            <button type="button" onClick={() => void loadDashboard(true)} disabled={refreshing}>
              {refreshing ? '更新中…' : '刷新数据'}
            </button>
            <div className="admin-mobile-actions" aria-label="账户操作">
              <a href="/">返回前台</a>
              <button type="button" onClick={() => void logoutAdmin()} disabled={loggingOut}>{loggingOut ? '退出中…' : '安全退出'}</button>
            </div>
          </div>
        </header>

        {Object.keys(errors).filter((key) => key !== 'access').length ? (
          <div className="admin-partial-error" role="alert">
            <strong>部分数据暂不可用</strong>
            <span>{Object.values(errors).filter(Boolean).join(' · ')}</span>
            <button type="button" onClick={() => void loadDashboard(true)}>重试</button>
          </div>
        ) : null}

        {actionFeedback ? (
          <div className={`admin-action-message admin-action-message--${actionFeedback.tone}`} role={actionFeedback.tone === 'success' ? 'status' : 'alert'}>
            <span>{actionFeedback.message}</span>
            <button type="button" onClick={() => setActionFeedback(null)} aria-label="关闭操作提示">×</button>
          </div>
        ) : null}

        {section === 'overview' ? (
          <>
            <div className="admin-kpi-grid">
              <KpiCard label="注册用户" value={overview?.auth_summary.total_users ?? users.length} note={`今日新增 ${todayCreated} · ${range} 日新增 ${periodCreated}`} tone="cyan" />
              <KpiCard label="启用账户" value={overview?.auth_summary.active_users ?? activeUsers} note={`启用率 ${percent(activeUsers, users.length)}% · 禁用 ${disabledUsers}`} tone="green" />
              <KpiCard label="有效会话" value={overview?.auth_summary.active_sessions ?? 0} note="当前未撤销且未过期的服务端会话" tone="purple" />
              <KpiCard label="自选记录" value={overview?.auth_summary.watchlist_items ?? 0} note={`${users.filter((user) => user.watchlist_count > 0).length} 位用户已创建自选`} tone="gold" />
            </div>

            <div className="admin-overview-grid">
              <article className="admin-panel admin-panel--wide">
                <div className="admin-panel__heading">
                  <div><span>Growth</span><h2>用户创建趋势</h2><p>按 Asia/Shanghai 自然日统计，不等同于活跃用户。</p></div>
                  <div className="admin-segmented" aria-label="趋势日期范围">
                    {([7, 30, 90] as const).map((days) => <button className={range === days ? 'active' : ''} type="button" onClick={() => setRange(days)} key={days}>{days} 天</button>)}
                  </div>
                </div>
                <UserGrowthChart points={creationSeries} />
                <div className="admin-chart-summary"><strong>{periodCreated}</strong><span>{range} 日创建用户</span><i /><strong>{todayCreated}</strong><span>今日创建</span></div>
              </article>

              <article className="admin-panel admin-panel--status">
                <div className="admin-panel__heading"><div><span>Accounts</span><h2>账户状态</h2><p>启用与管理员禁用账户比例。</p></div></div>
                <div className="admin-donut" style={{ background: `conic-gradient(#4ade80 0 ${percent(activeUsers, users.length)}%, #f87171 ${percent(activeUsers, users.length)}% 100%)` }}>
                  <div><strong>{percent(activeUsers, users.length)}%</strong><span>启用率</span></div>
                </div>
                <div className="admin-legend">
                  <span><i className="active" />启用 <b>{activeUsers}</b></span>
                  <span><i className="disabled" />禁用 <b>{disabledUsers}</b></span>
                </div>
              </article>

              <article className="admin-panel admin-panel--audit-summary">
                <div className="admin-panel__heading"><div><span>Latest 200 events</span><h2>最近认证与安全事件</h2><p>仅展示当前审计保留窗口，不代表长期历史趋势。</p></div><button type="button" onClick={() => openAudit('all')}>查看全部</button></div>
                {auditDistribution.length ? (
                  <div className="admin-bar-list">
                    {auditDistribution.map((item) => (
                      <div key={item.type}>
                        <span>{shortEventName(item.type)}</span>
                        <div><i style={{ width: `${Math.max(4, (item.count / maxAuditCount) * 100)}%` }} /></div>
                        <strong>{item.count}</strong>
                      </div>
                    ))}
                  </div>
                ) : <EmptyState title="还没有审计事件" detail="后续登录和管理操作会显示在这里。" />}
              </article>

              <article className="admin-panel admin-panel--attention">
                <div className="admin-panel__heading"><div><span>Attention</span><h2>待关注事项</h2><p>按当前账户、审计与模块快照生成。</p></div></div>
                <div className="admin-attention-list">
                  {attentionItems.map((item) => (
                    <button type="button" className={`admin-attention admin-attention--${item.tone}`} onClick={item.activate} aria-label={`${item.label}：${item.value}，${item.detail}`} key={item.label}>
                      <i aria-hidden="true" />
                      <span><b>{item.label}</b><small>{item.detail}</small></span>
                      <strong>{item.value}</strong>
                      <em aria-hidden="true">›</em>
                    </button>
                  ))}
                </div>
              </article>
            </div>
          </>
        ) : null}

        {section === 'users' ? (
          <article className="admin-panel admin-user-panel">
            <div className="admin-filterbar">
              <label className="admin-search"><span>搜索账户</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="用户名或显示名" /></label>
              <label><span>状态</span><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as UserStatusFilter)}><option value="all">全部状态</option><option value="active">启用</option><option value="disabled">禁用</option><option value="locked">登录锁定</option></select></label>
              <label><span>登录角色</span><select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value as UserRoleFilter)}><option value="all">全部角色</option><option value="admin">管理员</option><option value="user">普通用户</option></select></label>
              <button type="button" onClick={clearUserFilters}>清除筛选</button>
              <button type="button" onClick={exportUsers}>导出 CSV</button>
              <div><strong>{filteredUsers.length}</strong><span> / {users.length} 个账户</span></div>
            </div>
            {filteredUsers.length ? (
              <div className="admin-table-shell">
                <table className="admin-table">
                  <thead><tr><th>用户</th><th>登录角色</th><th>状态</th><th>登录风险</th><th>注册时间</th><th>最近登录</th><th>自选</th><th>会话</th><th>操作</th></tr></thead>
                  <tbody>
                    {filteredUsers.map((user) => {
                      const active = isActiveUser(user);
                      const isSelf = user.id === currentUser?.id;
                      const locked = isUserLocked(user);
                      const revocableSessions = Math.max(0, user.active_sessions - (isSelf ? 1 : 0));
                      return (
                        <tr key={user.id}>
                          <td data-label="用户"><span className="admin-user-cell"><i>{user.display_name.slice(0, 1).toUpperCase()}</i><b>{user.display_name}<small>@{user.username}</small></b></span></td>
                          <td data-label="登录角色"><span className={`admin-role admin-role--${user.role}`}>{user.role === 'admin' ? '管理员' : '普通用户'}</span></td>
                          <td data-label="状态"><span className={`admin-state admin-state--${active ? 'active' : 'disabled'}`}><i />{active ? '启用' : '禁用'}</span></td>
                          <td data-label="登录风险"><span className={`admin-state admin-state--${locked ? 'locked' : user.failed_attempts ? 'warning' : 'active'}`}><i />{locked ? '已锁定' : user.failed_attempts ? `失败 ${user.failed_attempts}` : '正常'}</span></td>
                          <td data-label="注册时间">{formatAdminDate(user.created_at)}</td>
                          <td data-label="最近登录">{formatAdminDate(user.last_login_at)}</td>
                          <td data-label="自选">{user.watchlist_count}</td>
                          <td data-label="会话">{user.active_sessions}</td>
                          <td data-label="操作"><span className="admin-row-actions">
                            <button className="admin-row-action" type="button" aria-label={`查看 ${user.display_name} 的详情`} onClick={() => setSelectedUser(user)}>详情</button>
                            {locked || user.failed_attempts ? <button className="admin-row-action" type="button" disabled={unlockingUserId === user.id} onClick={() => void unlockUser(user)}>{unlockingUserId === user.id ? '解锁中…' : '解锁'}</button> : null}
                            <button className="admin-row-action admin-row-action--danger" type="button" disabled={!revocableSessions || revokingUserId === user.id} title={!revocableSessions ? isSelf ? '当前管理会话会被保留，没有其他会话可撤销' : '没有有效会话' : undefined} onClick={() => void revokeUserSessions(user)}>{revokingUserId === user.id ? '下线中…' : '下线'}</button>
                            <button className={active ? 'admin-row-action admin-row-action--danger' : 'admin-row-action'} type="button" disabled={isSelf || updatingUserId === user.id} title={isSelf ? '不能禁用当前管理员账号' : undefined} onClick={() => void toggleUser(user)}>{updatingUserId === user.id ? '处理中…' : active ? '禁用' : '启用'}</button>
                          </span></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : <EmptyState title="没有匹配的用户" detail="尝试调整搜索关键词、状态或登录角色。" onReset={clearUserFilters} />}
            <p className="admin-data-note">可独立解除登录锁定或强制撤销会话；禁用账户仍会立即撤销其全部有效会话。当前列表由浏览器筛选，账户规模扩大后应升级为服务端游标分页。</p>
          </article>
        ) : null}

        {section === 'audit' ? (
          <>
            <div className="admin-kpi-grid admin-kpi-grid--audit">
              <KpiCard label="最近事件" value={events.length} note="接口最多返回最近 200 条" />
              <KpiCard label="登录成功" value={events.filter((event) => event.event_type === 'login_success').length} note="审计窗口内的成功认证" tone="green" />
              <KpiCard label="需关注" value={securityEvents.length} note="失败、限流、锁定或拒绝事件" tone="gold" />
              <KpiCard label="高风险" value={dangerousEvents.length} note="来源、CSRF、会话或权限拒绝" tone="purple" />
            </div>
            <article className="admin-panel admin-audit-panel">
              <div className="admin-filterbar">
                <label className="admin-search"><span>检索事件</span><input value={auditQuery} onChange={(event) => setAuditQuery(event.target.value)} placeholder="事件、用户或详情" /></label>
                <label><span>风险级别</span><select value={auditFilter} onChange={(event) => setAuditFilter(event.target.value as AuditRiskFilter)}><option value="all">全部风险</option><option value="danger">高风险</option><option value="warning">需关注</option><option value="normal">常规</option></select></label>
                <label><span>时间范围</span><select value={auditWindow} onChange={(event) => setAuditWindow(event.target.value as AuditWindow)}><option value="24h">最近 24 小时</option><option value="7d">最近 7 天</option><option value="all">当前全部 200 条</option></select></label>
                <button type="button" onClick={() => { setAuditQuery(''); setAuditFilter('all'); setAuditWindow('7d'); }}>清除筛选</button>
                <button type="button" onClick={exportAudit}>导出 CSV</button>
                <div><strong>{filteredEvents.length}</strong><span> 条事件</span></div>
              </div>
              {filteredEvents.length ? (
                <div className="admin-table-shell">
                  <table className="admin-table admin-audit-table">
                    <thead><tr><th>风险</th><th>时间</th><th>事件类型</th><th>账户</th><th>详情</th><th>ID</th></tr></thead>
                    <tbody>
                      {filteredEvents.map((event) => {
                        const risk = auditRisk(event.event_type);
                        return <tr key={event.id}><td data-label="风险"><span className={`admin-risk admin-risk--${risk}`}>{riskLabel(risk)}</span></td><td data-label="时间">{formatAdminDate(event.created_at)}</td><td data-label="事件类型"><code>{shortEventName(event.event_type)}</code></td><td data-label="账户">{event.username ? `@${event.username}` : '系统 / 匿名'}</td><td data-label="详情"><span className="admin-detail" title={event.detail ?? ''}>{event.detail || '—'}</span></td><td data-label="ID">#{event.id}</td></tr>;
                      })}
                    </tbody>
                  </table>
                </div>
              ) : <EmptyState title="没有匹配的审计事件" detail="当前风险、时间或关键词筛选下没有可显示的事件。" onReset={() => { setAuditQuery(''); setAuditFilter('all'); setAuditWindow('7d'); }} />}
              <p className="admin-data-note">审计日志当前保留 90 天且最多 10,000 条；本页与 CSV 仅覆盖最新 200 条中的当前筛选结果，不应当作长期合规归档。</p>
            </article>
          </>
        ) : null}

        {section === 'data' ? <AdminDataGovernance overview={overview} /> : null}
        {section === 'research' ? <AdminResearchOperations overview={overview} /> : null}
        {section === 'system' ? <AdminSystemOperations overview={overview} authStatus={authStatus} /> : null}
      </div>
      {selectedUser ? <AdminUserDrawer user={selectedUser} events={events} onClose={closeUserDrawer} onToggle={(user) => void toggleUser(user)} onRevoke={(user) => void revokeUserSessions(user)} onUnlock={(user) => void unlockUser(user)} updating={updatingUserId === selectedUser.id} revoking={revokingUserId === selectedUser.id} unlocking={unlockingUserId === selectedUser.id} isSelf={selectedUser.id === currentUser?.id} canToggle={selectedUser.id !== currentUser?.id} /> : null}
    </section>
  );
}
