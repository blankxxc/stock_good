import assert from 'node:assert/strict';
import test from 'node:test';

import {
  adminSectionFromHash,
  auditRisk,
  buildUserCreationSeries,
  isAuditEventWithinWindow,
  isActiveUser,
  isUserLocked,
  reportingDayKey,
  type AdminUser,
} from '../src/lib/adminDashboard';
import { safeNextPath } from '../src/lib/auth';

function user(id: number, createdAt: string, active: boolean | number = true): AdminUser {
  return {
    id,
    username: `user${id}`,
    display_name: `User ${id}`,
    role: 'user',
    is_active: active,
    created_at: createdAt,
    last_login_at: null,
    watchlist_count: 0,
    active_sessions: 0,
    failed_attempts: 0,
    locked_until: null,
    password_changed_at: createdAt,
  };
}

test('admin reporting days use the Asia/Shanghai boundary', () => {
  assert.equal(reportingDayKey('2026-07-22T15:59:59Z'), '2026-07-22');
  assert.equal(reportingDayKey('2026-07-22T16:00:00Z'), '2026-07-23');
});

test('admin sections are restored from safe URL hashes', () => {
  assert.equal(adminSectionFromHash('#audit'), 'audit');
  assert.equal(adminSectionFromHash('USERS'), 'users');
  assert.equal(adminSectionFromHash('#unknown'), 'overview');
});

test('account locks and audit windows use real timestamps', () => {
  const now = new Date('2026-07-26T12:00:00Z');
  assert.equal(isUserLocked({ locked_until: '2026-07-26T12:01:00Z' }, now), true);
  assert.equal(isUserLocked({ locked_until: '2026-07-26T11:59:00Z' }, now), false);
  assert.equal(isAuditEventWithinWindow('2026-07-25T12:00:00Z', '24h', now), true);
  assert.equal(isAuditEventWithinWindow('2026-07-25T11:59:59Z', '24h', now), false);
  assert.equal(isAuditEventWithinWindow('2026-07-18T12:00:00Z', '7d', now), false);
  assert.equal(isAuditEventWithinWindow('invalid', 'all', now), true);
});

test('user creation series fills empty days and groups real created_at values', () => {
  const series = buildUserCreationSeries([
    user(1, '2026-07-21T03:00:00Z'),
    user(2, '2026-07-23T01:00:00Z'),
    user(3, '2026-07-23T04:00:00Z'),
  ], 3, new Date('2026-07-23T04:00:00Z'));

  assert.deepEqual(series.map(({ key, count }) => ({ key, count })), [
    { key: '2026-07-21', count: 1 },
    { key: '2026-07-22', count: 0 },
    { key: '2026-07-23', count: 2 },
  ]);
});

test('audit risks and SQLite boolean values are normalized for the UI', () => {
  assert.equal(auditRisk('csrf_denied'), 'danger');
  assert.equal(auditRisk('login_failed'), 'warning');
  assert.equal(auditRisk('login_success'), 'normal');
  assert.equal(isActiveUser(user(1, '2026-07-23T00:00:00Z', 1)), true);
  assert.equal(isActiveUser(user(2, '2026-07-23T00:00:00Z', 0)), false);
});

test('admin login redirects accept only the canonical or legacy local admin path', () => {
  assert.equal(safeNextPath('/admin-console', '/', true), '/admin-console');
  assert.equal(safeNextPath('/backend-admin', '/', true), '/backend-admin');
  assert.equal(safeNextPath('//attacker.example/admin-console', '/', true), '/');
  assert.equal(safeNextPath('/admin-console', '/', false), '/');
});
