'use client';

import { useEffect, useRef } from 'react';
import {
  auditRisk,
  formatAdminDate,
  isActiveUser,
  isUserLocked,
  type AdminOverview,
  type AdminUser,
  type AuditEvent,
  type RouteLink,
} from '../lib/adminDashboard';

export type AdminAuthStatus = {
  setup_required: boolean;
  registration_open: boolean;
  authenticated: boolean;
};

function statusReady(status: string): boolean {
  return status.endsWith('ready');
}

function moduleMatches(name: string, terms: string[]): boolean {
  const value = name.toLowerCase();
  return terms.some((term) => value.includes(term));
}

function ModuleHealthList({ modules }: { modules: Array<[string, string]> }) {
  if (!modules.length) {
    return <div className="admin-inline-empty">当前快照没有匹配的模块。</div>;
  }
  return (
    <div className="admin-module-grid">
      {modules.map(([name, status]) => (
        <div key={name}>
          <i className={statusReady(status) ? 'ready' : ''} />
          <span>{name}</span>
          <code>{status}</code>
        </div>
      ))}
    </div>
  );
}

function RouteRegistry({ routes, emptyMessage = '当前没有可显示的入口。' }: {
  routes: RouteLink[];
  emptyMessage?: string;
}) {
  if (!routes.length) return <div className="admin-inline-empty">{emptyMessage}</div>;
  return (
    <div className="admin-route-grid">
      {routes.map((route) => (
        <a href={route.path} target="_blank" rel="noreferrer" key={route.path}>
          <span>{route.label}</span>
          <code>{route.method} {route.path}</code>
          <b aria-hidden="true">↗</b>
        </a>
      ))}
    </div>
  );
}

export function downloadCsv(filename: string, headers: string[], rows: Array<Array<string | number | boolean | null | undefined>>) {
  const escapeCell = (value: string | number | boolean | null | undefined) => {
    const text = value == null ? '' : String(value);
    return `"${text.replaceAll('"', '""')}"`;
  };
  const content = [headers, ...rows].map((row) => row.map(escapeCell).join(',')).join('\r\n');
  const blob = new Blob([`\ufeff${content}`], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function AdminDataGovernance({ overview }: { overview: AdminOverview | null }) {
  const snapshotAvailable = overview !== null;
  const modules = Object.entries(overview?.module_statuses ?? {});
  const dataModules = modules.filter(([name]) => moduleMatches(name, [
    'data', 'lakehouse', 'lineage', 'spark', 'flink', 'realtime', 'stream', 'warehouse', 'feature',
  ]));
  const readyCount = dataModules.filter(([, status]) => statusReady(status)).length;
  const routes = overview?.data_fabric.internal_routes ?? [];
  const violations = overview?.factor_summary.point_in_time_violations;

  return (
    <div className="admin-system-grid">
      <article className="admin-panel admin-domain-hero admin-domain-hero--data">
        <div>
          <span className={`admin-live-dot${snapshotAvailable ? '' : ' admin-live-dot--unknown'}`}><i />{snapshotAvailable ? '快照已连接' : '状态未知'}</span>
          <h2>Data Fabric 治理面</h2>
          <p>{overview?.data_fabric.policy ?? '内部数据链路状态暂不可用，请重试加载。'}</p>
        </div>
        <strong>{snapshotAvailable ? readyCount : '—'}<small> / {snapshotAvailable ? dataModules.length : '—'} 数据模块 Ready</small></strong>
      </article>

      <article className="admin-panel">
        <div className="admin-panel__heading"><div><span>Governance gates</span><h2>治理检查</h2><p>由当前后台契约和真实快照生成。</p></div></div>
        <div className="admin-governance-checks">
          <div className={snapshotAvailable && routes.length ? 'ok' : 'unknown'}><i /><span><b>内部链路隔离</b><small>{snapshotAvailable ? 'Data Fabric 路由由服务端 require_admin 保护' : '未取得治理快照，无法验证保护状态'}</small></span><strong>{snapshotAvailable && routes.length ? 'VERIFIED' : 'UNKNOWN'}</strong></div>
          <div className={violations == null ? 'unknown' : violations ? 'danger' : 'ok'}><i /><span><b>点时间一致性</b><small>available_time 不得晚于 prediction_time</small></span><strong>{violations ?? 'UNKNOWN'}</strong></div>
          <div className={!snapshotAvailable ? 'unknown' : overview.module_summary.pending_modules ? 'warning' : 'ok'}><i /><span><b>模块就绪度</b><small>未 Ready 模块需要部署人员复核</small></span><strong>{overview?.module_summary.pending_modules ?? 'UNKNOWN'}</strong></div>
          <div className={snapshotAvailable ? 'ok' : 'unknown'}><i /><span><b>用户侧最小暴露</b><small>{snapshotAvailable ? '普通选股导航不展示数据血缘和运维明细' : '未取得快照，暂不宣告策略已验证'}</small></span><strong>{snapshotAvailable ? 'CONFIGURED' : 'UNKNOWN'}</strong></div>
        </div>
      </article>

      <article className="admin-panel">
        <div className="admin-panel__heading"><div><span>Inventory</span><h2>数据入口清单</h2><p>用于检查质量、血缘、湖仓与流处理状态。</p></div></div>
        <RouteRegistry routes={routes} />
      </article>

      <article className="admin-panel admin-module-panel">
        <div className="admin-panel__heading"><div><span>Data modules</span><h2>数据模块健康</h2><p>状态来自后端 health payload，不进行前端推断。</p></div></div>
        <ModuleHealthList modules={dataModules} />
      </article>
    </div>
  );
}

export function AdminResearchOperations({ overview }: { overview: AdminOverview | null }) {
  const modules = Object.entries(overview?.module_statuses ?? {});
  const researchModules = modules.filter(([name]) => moduleMatches(name, [
    'factor', 'model', 'score', 'backtest', 'rag', 'report', 'simulation', 'graph', 'research', 'candidate',
  ]));
  const researchRoutes = (overview?.critical_routes ?? []).filter((route) => !['/health', '/api/site'].includes(route.path));
  const factor = overview?.factor_summary;

  return (
    <>
      <div className="admin-kpi-grid">
        <article className="admin-kpi admin-tone--cyan"><div className="admin-kpi__top"><span>因子总数</span><i /></div><strong>{factor?.factor_count ?? '—'}</strong><p>当前研究因子目录规模</p></article>
        <article className="admin-kpi admin-tone--green"><div className="admin-kpi__top"><span>可准入因子</span><i /></div><strong>{factor?.admission_ready_count ?? '—'}</strong><p>通过当前准入规则的因子</p></article>
        <article className="admin-kpi admin-tone--purple"><div className="admin-kpi__top"><span>因子分类</span><i /></div><strong>{factor?.category_count ?? '—'}</strong><p>category summary 覆盖范围</p></article>
        <article className="admin-kpi admin-tone--gold"><div className="admin-kpi__top"><span>点时间违规</span><i /></div><strong>{factor?.point_in_time_violations ?? '—'}</strong><p>应保持为 0 的研究红线</p></article>
      </div>
      <div className="admin-system-grid">
        <article className="admin-panel admin-module-panel">
          <div className="admin-panel__heading"><div><span>Research runtime</span><h2>研究模块运行状态</h2><p>因子、模型、评分、回测、RAG 与报告链路。</p></div></div>
          <ModuleHealthList modules={researchModules} />
        </article>
        <article className="admin-panel">
          <div className="admin-panel__heading"><div><span>Control points</span><h2>研究控制要点</h2><p>后台需要持续复核的研究治理边界。</p></div></div>
          <div className="admin-control-list">
            <div><b>数据截止时间</b><span>所有模型与报告必须携带 data_cutoff_time</span></div>
            <div><b>防泄漏检查</b><span>训练、验证、回测保持点时间一致性</span></div>
            <div><b>模型版本</b><span>评分与报告必须可追溯到 model_version</span></div>
            <div><b>人工复核</b><span>页面结果只用于研究排序，不构成投资建议</span></div>
          </div>
        </article>
        <article className="admin-panel">
          <div className="admin-panel__heading"><div><span>Research APIs</span><h2>研究服务入口</h2><p>打开接口响应进行开发与验收核对。</p></div></div>
          <RouteRegistry routes={researchRoutes} />
        </article>
      </div>
    </>
  );
}

export function AdminSystemOperations({ overview, authStatus }: {
  overview: AdminOverview | null;
  authStatus: AdminAuthStatus | null;
}) {
  const snapshotAvailable = overview !== null;
  const modules = Object.entries(overview?.module_statuses ?? {});
  const routes = [
    ...(overview?.critical_routes ?? []),
    ...(overview?.data_fabric.internal_routes ?? []),
  ].filter((route, index, all) => all.findIndex((item) => item.path === route.path) === index);

  return (
    <div className="admin-system-grid">
      <article className="admin-panel admin-system-hero">
        <div><span className={`admin-live-dot${snapshotAvailable ? '' : ' admin-live-dot--unknown'}`}><i />{snapshotAvailable ? '快照已连接' : '状态未知'}</span><h2>{overview?.service.name ?? 'stock-research-platform'}</h2><p>版本 {overview?.service.version ?? 'unknown'} · {overview?.status ?? '状态未知'}{overview?.service.time ? ` · ${formatAdminDate(overview.service.time)} 快照` : ''}</p></div>
        <strong>{overview?.module_summary.ready_modules ?? '—'}<small> / {overview?.module_summary.total_modules ?? '—'} 模块 Ready</small></strong>
      </article>

      <article className="admin-panel">
        <div className="admin-panel__heading"><div><span>Authentication</span><h2>认证与开放策略</h2><p>当前公开认证状态，不包含任何凭据。</p></div></div>
        <dl className="admin-stat-list">
          <div><dt>管理员初始化</dt><dd>{authStatus ? authStatus.setup_required ? '待完成' : '已完成' : '状态未知'}</dd></div>
          <div><dt>公开注册</dt><dd>{authStatus ? authStatus.registration_open ? '开放' : '关闭' : '状态未知'}</dd></div>
          <div><dt>后台鉴权</dt><dd>{snapshotAvailable ? 'Server' : '状态未知'}</dd></div>
          <div><dt>缓存策略</dt><dd>{snapshotAvailable ? 'no-store' : '状态未知'}</dd></div>
        </dl>
        <p className="admin-data-note">登录鉴权当前只有 admin / user 两级；研究治理角色仍是独立目录，尚未绑定到账户权限。</p>
      </article>

      <article className="admin-panel">
        <div className="admin-panel__heading"><div><span>Documentation</span><h2>接口与契约</h2><p>生产环境默认关闭 API 文档；仅在显式授权后开放。</p></div></div>
        <div className="admin-doc-links">
          {(overview?.documentation_links ?? []).map((item) => <a href={item.path} target="_blank" rel="noreferrer" key={item.path}><span>{item.label}</span><b>↗</b></a>)}
          <a href="/health" target="_blank" rel="noreferrer"><span>Health endpoint</span><b>↗</b></a>
        </div>
      </article>

      <article className="admin-panel admin-module-panel">
        <div className="admin-panel__heading"><div><span>All modules</span><h2>完整模块矩阵</h2><p>全量后端模块及其当前契约状态。</p></div></div>
        <ModuleHealthList modules={modules} />
      </article>

      <article className="admin-panel admin-route-panel">
        <div className="admin-panel__heading"><div><span>Endpoint registry</span><h2>API 与内部入口</h2><p>{routes.length} 个当前控制面入口；访问仍由各接口服务端鉴权。</p></div></div>
        <RouteRegistry routes={routes} />
      </article>
    </div>
  );
}

export function AdminUserDrawer({
  user,
  events,
  onClose,
  onToggle,
  onRevoke,
  onUnlock,
  updating,
  revoking,
  unlocking,
  isSelf,
  canToggle = true,
}: {
  user: AdminUser;
  events: AuditEvent[];
  onClose: () => void;
  onToggle: (user: AdminUser) => void;
  onRevoke: (user: AdminUser) => void;
  onUnlock: (user: AdminUser) => void;
  updating: boolean;
  revoking: boolean;
  unlocking: boolean;
  isSelf: boolean;
  canToggle?: boolean;
}) {
  const active = isActiveUser(user);
  const locked = isUserLocked(user);
  const canRevoke = user.active_sessions > (isSelf ? 1 : 0);
  const userEvents = events.filter((event) => (
    event.user_id === user.id
    || event.username === user.username
    || event.detail?.includes(`target=${user.id};`)
  )).slice(0, 8);
  const drawerRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const drawer = drawerRef.current;
    if (!drawer) return;
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const backdrop = drawer.parentElement;
    const dashboard = backdrop?.parentElement;
    const backgroundElements = dashboard
      ? Array.from(dashboard.children).filter((element) => element !== backdrop) as HTMLElement[]
      : [];
    const previousInert = backgroundElements.map((element) => element.inert);
    backgroundElements.forEach((element) => { element.inert = true; });
    closeButtonRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab') return;
      const focusable = Array.from(drawer.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      )).filter((element) => element.getClientRects().length > 0);
      if (!focusable.length) {
        event.preventDefault();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    drawer.addEventListener('keydown', handleKeyDown);
    return () => {
      drawer.removeEventListener('keydown', handleKeyDown);
      backgroundElements.forEach((element, index) => { element.inert = previousInert[index]; });
      previouslyFocused?.focus();
    };
  }, [onClose]);

  return (
    <div className="admin-drawer-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside ref={drawerRef} className="admin-user-drawer" role="dialog" aria-modal="true" aria-labelledby="admin-user-drawer-title" aria-describedby="admin-user-drawer-description">
        <header>
          <div className="admin-avatar admin-avatar--large">{user.display_name.slice(0, 1).toUpperCase()}</div>
          <div><p className="admin-eyebrow">Account #{user.id}</p><h2 id="admin-user-drawer-title">{user.display_name}</h2><span>@{user.username}</span></div>
          <button ref={closeButtonRef} type="button" onClick={onClose} aria-label="关闭用户详情">×</button>
        </header>
        <section>
          <h3>账户概况</h3>
          <dl className="admin-drawer-stats">
            <div><dt>登录角色</dt><dd>{user.role === 'admin' ? '管理员' : '普通用户'}</dd></div>
            <div><dt>账户状态</dt><dd>{active ? '启用' : '禁用'}</dd></div>
            <div><dt>注册时间</dt><dd>{formatAdminDate(user.created_at)}</dd></div>
            <div><dt>最近登录</dt><dd>{formatAdminDate(user.last_login_at)}</dd></div>
            <div><dt>自选记录</dt><dd>{user.watchlist_count}</dd></div>
            <div><dt>有效会话</dt><dd>{user.active_sessions}</dd></div>
            <div><dt>登录风险</dt><dd>{locked ? `锁定至 ${formatAdminDate(user.locked_until)}` : user.failed_attempts ? `${user.failed_attempts} 次失败` : '正常'}</dd></div>
            <div><dt>密码更新时间</dt><dd>{formatAdminDate(user.password_changed_at)}</dd></div>
          </dl>
        </section>
        <section>
          <h3>最近账户事件</h3>
          {userEvents.length ? <div className="admin-drawer-events">{userEvents.map((event) => <div key={event.id}><i className={`risk-${auditRisk(event.event_type)}`} /><span><b>{event.event_type.replaceAll('_', ' ')}</b><small>{formatAdminDate(event.created_at)} · {event.detail || '无附加详情'}</small></span></div>)}</div> : <div className="admin-inline-empty">最近审计窗口内没有该账户事件。</div>}
        </section>
        <footer>
          <p id="admin-user-drawer-description">{canToggle === false ? '当前管理员不能禁用自己的账户；强制下线时会保留当前管理会话。' : active ? '禁用会撤销该用户全部有效会话；也可只解除锁定或强制下线。' : '重新启用后，用户可再次登录。'}</p>
          <div className="admin-drawer-actions">
            {locked || user.failed_attempts ? <button type="button" disabled={unlocking} onClick={() => onUnlock(user)}>{unlocking ? '解锁中…' : '解除登录锁定'}</button> : null}
            <button type="button" className="danger" disabled={!canRevoke || revoking} title={!canRevoke ? '没有可撤销的其他有效会话' : undefined} onClick={() => onRevoke(user)}>{revoking ? '下线中…' : isSelf ? '撤销其他会话' : '强制全部下线'}</button>
            <button type="button" className={active ? 'danger' : ''} disabled={updating || canToggle === false} onClick={() => onToggle(user)}>{canToggle === false ? '当前账户不可禁用' : updating ? '处理中…' : active ? '禁用账户' : '启用账户'}</button>
          </div>
        </footer>
      </aside>
    </div>
  );
}
