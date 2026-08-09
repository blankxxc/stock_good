from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[3]
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
SYMBOL_RE = re.compile(r"^\d{6}\.(?:SH|SZ)$", re.IGNORECASE)
COMMON_PASSWORDS = {
    "password123!",
    "admin123456!",
    "qwerty123456!",
    "1234567890a!",
    "welcome123!",
    "letmein123!",
}
SCRYPT_N = 32768
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SESSION_IDLE = timedelta(minutes=30)
SESSION_ABSOLUTE = timedelta(hours=8)
LOCKOUT_DURATION = timedelta(minutes=15)
MAX_FAILED_LOGINS = 5
AUTH_RATE_WINDOW = timedelta(minutes=5)
LOGIN_RATE_LIMIT = 30
REGISTER_RATE_LIMIT = 8
SETUP_RATE_LIMIT = 12
MAX_ACTIVE_SESSIONS_PER_USER = 10
MAX_SESSION_RECORDS_PER_USER = 100
MAX_AUDIT_ROWS = 10_000
AUDIT_RETENTION = timedelta(days=90)
SESSION_RECORD_RETENTION = timedelta(days=30)
RATE_LIMIT_RETENTION = timedelta(days=1)
LOCAL_ALLOWED_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _session_generation(session_id: int, csrf_hash: str) -> str:
    return _sha256(f"{session_id}:{csrf_hash}")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def configured_allowed_origins() -> tuple[str, ...]:
    raw = os.getenv("STOCK_GOOD_ALLOWED_ORIGINS", "")
    if not raw.strip():
        origins = LOCAL_ALLOWED_ORIGINS
    else:
        origins = tuple(dict.fromkeys(value.strip().rstrip("/") for value in raw.split(",") if value.strip()))
        if not origins or any(not origin.startswith(("http://", "https://")) for origin in origins):
            raise RuntimeError("STOCK_GOOD_ALLOWED_ORIGINS must contain comma-separated http(s) origins")
    if any(origin.startswith("https://") for origin in origins) and not _env_bool("STOCK_GOOD_SECURE_COOKIE", False):
        raise RuntimeError("STOCK_GOOD_SECURE_COOKIE must be enabled when an HTTPS origin is allowed")
    return origins


@dataclass(frozen=True)
class AuthRuntime:
    db_path: Path = PROJECT_ROOT / ".secrets" / "auth.db"
    bootstrap_token_path: Path = PROJECT_ROOT / ".secrets" / "admin-bootstrap-token.txt"
    allowed_origins: tuple[str, ...] = field(default_factory=configured_allowed_origins)
    secure_cookie: bool = field(default_factory=lambda: _env_bool("STOCK_GOOD_SECURE_COOKIE", False))
    registration_open: bool = field(default_factory=lambda: _env_bool("STOCK_GOOD_REGISTRATION_OPEN", True))
    clock: Callable[[], datetime] = utc_now


@dataclass(frozen=True)
class AuthPrincipal:
    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    session_id: int
    csrf_hash: str
    expires_at: str

    @property
    def session_generation(self) -> str:
        return _session_generation(self.session_id, self.csrf_hash)

    def public_user(self) -> dict[str, object]:
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "role": self.role,
        }


class AuthError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class AuthService:
    def __init__(self, runtime: AuthRuntime | None = None) -> None:
        self.runtime = runtime or AuthRuntime()
        if any(origin.startswith("https://") for origin in self.runtime.allowed_origins) and not self.runtime.secure_cookie:
            raise RuntimeError("STOCK_GOOD_SECURE_COOKIE must be enabled when an HTTPS origin is allowed")
        self.runtime.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()
        self._prune_security_state()
        self._ensure_bootstrap_token()
        self._dummy_salt = b"stock-good-auth"
        self._dummy_digest = self._derive_password("DummySecure!Password2026", self._dummy_salt)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.runtime.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize_schema(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS auth_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS auth_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    username_normalized TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    password_salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    password_params TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'admin')),
                    is_active INTEGER NOT NULL DEFAULT 1,
                    failed_attempts INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT,
                    created_at TEXT NOT NULL,
                    password_changed_at TEXT NOT NULL,
                    last_login_at TEXT
                );
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_hash TEXT NOT NULL UNIQUE,
                    csrf_hash TEXT NOT NULL,
                    user_id INTEGER NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    idle_expires_at TEXT NOT NULL,
                    absolute_expires_at TEXT NOT NULL,
                    revoked_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id);
                CREATE TABLE IF NOT EXISTS user_watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
                    symbol TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, symbol)
                );
                CREATE INDEX IF NOT EXISTS idx_watchlist_user ON user_watchlist(user_id, created_at);
                CREATE TABLE IF NOT EXISTS auth_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    user_id INTEGER,
                    username TEXT,
                    detail TEXT,
                    client_hash TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS auth_rate_limits (
                    action TEXT NOT NULL,
                    client_hash TEXT NOT NULL,
                    window_started_at TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    PRIMARY KEY(action, client_hash)
                );
                """
            )
        try:
            os.chmod(self.runtime.db_path, 0o600)
        except OSError:
            pass

    def _ensure_bootstrap_token(self) -> None:
        now = _iso(self.runtime.clock())
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            admin_exists = connection.execute(
                "SELECT 1 FROM auth_users WHERE role = 'admin' LIMIT 1"
            ).fetchone()
            existing = connection.execute(
                "SELECT value FROM auth_meta WHERE key = 'bootstrap_token_sha256'"
            ).fetchone()
            if admin_exists:
                connection.execute("DELETE FROM auth_meta WHERE key = 'bootstrap_token_sha256'")
                self.runtime.bootstrap_token_path.unlink(missing_ok=True)
                return
            if existing:
                try:
                    raw_existing = self.runtime.bootstrap_token_path.read_text(encoding="utf-8").strip()
                except OSError:
                    raw_existing = ""
                if raw_existing and hmac.compare_digest(existing["value"], _sha256(raw_existing)):
                    return
                connection.execute("DELETE FROM auth_meta WHERE key = 'bootstrap_token_sha256'")
            raw_token = secrets.token_urlsafe(32)
            self._atomic_secret_write(self.runtime.bootstrap_token_path, raw_token + "\n")
            connection.execute(
                "INSERT INTO auth_meta(key, value, updated_at) VALUES (?, ?, ?)",
                ("bootstrap_token_sha256", _sha256(raw_token), now),
            )

    @staticmethod
    def _atomic_secret_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        temporary.replace(path)

    @staticmethod
    def normalize_username(username: str) -> str:
        normalized = username.strip().lower()
        if not USERNAME_RE.fullmatch(username.strip()):
            raise AuthError(400, "invalid_username", "用户名需为 3–32 位字母、数字、点、下划线或连字符。")
        return normalized

    @staticmethod
    def validate_display_name(display_name: str) -> str:
        value = display_name.strip()
        if not 1 <= len(value) <= 40:
            raise AuthError(400, "invalid_display_name", "昵称长度需为 1–40 个字符。")
        return value

    @classmethod
    def validate_password(cls, username: str, password: str) -> None:
        if not 12 <= len(password) <= 128:
            raise AuthError(400, "weak_password", "密码长度需为 12–128 个字符。")
        categories = sum(
            bool(pattern.search(password))
            for pattern in (re.compile(r"[a-z]"), re.compile(r"[A-Z]"), re.compile(r"\d"), re.compile(r"[^A-Za-z0-9]"))
        )
        normalized = password.lower()
        if categories < 3 or normalized in COMMON_PASSWORDS:
            raise AuthError(400, "weak_password", "密码强度不足，请混合使用字母、数字和符号。")
        compact_username = re.sub(r"[._-]", "", username.lower())
        compact_password = re.sub(r"[._-]", "", normalized)
        if len(compact_username) >= 3 and compact_username in compact_password:
            raise AuthError(400, "weak_password", "密码不能包含用户名。")

    @staticmethod
    def _derive_password(password: str, salt: bytes) -> bytes:
        return hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=SCRYPT_N,
            r=SCRYPT_R,
            p=SCRYPT_P,
            dklen=SCRYPT_DKLEN,
            maxmem=64 * 1024 * 1024,
        )

    def hash_password(self, password: str) -> tuple[bytes, bytes]:
        salt = secrets.token_bytes(16)
        return salt, self._derive_password(password, salt)

    def verify_password(self, password: str, salt: bytes, expected: bytes) -> bool:
        candidate = self._derive_password(password, salt)
        return hmac.compare_digest(candidate, expected)

    def _audit(
        self,
        connection: sqlite3.Connection,
        event_type: str,
        *,
        user_id: int | None = None,
        username: str | None = None,
        detail: str | None = None,
        client_key: str | None = None,
    ) -> None:
        connection.execute(
            """INSERT INTO auth_audit_log(event_type, user_id, username, detail, client_hash, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                event_type,
                user_id,
                username[:64] if username else None,
                detail[:160] if detail else None,
                _sha256(client_key) if client_key else None,
                _iso(self.runtime.clock()),
            ),
        )
        connection.execute(
            "DELETE FROM auth_audit_log WHERE created_at < ?",
            (_iso(self.runtime.clock() - AUDIT_RETENTION),),
        )
        connection.execute(
            """DELETE FROM auth_audit_log
               WHERE id <= COALESCE(
                   (SELECT id FROM auth_audit_log ORDER BY id DESC LIMIT 1 OFFSET ?),
                   0
               )""",
            (MAX_AUDIT_ROWS,),
        )

    def record_security_event(
        self,
        event_type: str,
        *,
        principal: AuthPrincipal | None = None,
        detail: str | None = None,
        client_key: str | None = None,
    ) -> None:
        with self._connection() as connection:
            self._audit(
                connection,
                event_type,
                user_id=principal.id if principal else None,
                username=principal.username if principal else None,
                detail=detail,
                client_key=client_key,
            )

    def _prune_security_state(self) -> None:
        now = self.runtime.clock()
        with self._connection() as connection:
            connection.execute(
                "DELETE FROM auth_rate_limits WHERE window_started_at < ?",
                (_iso(now - RATE_LIMIT_RETENTION),),
            )
            connection.execute(
                "DELETE FROM auth_audit_log WHERE created_at < ?",
                (_iso(now - AUDIT_RETENTION),),
            )
            connection.execute(
                """DELETE FROM auth_sessions
                   WHERE absolute_expires_at < ?
                      OR (revoked_at IS NOT NULL AND revoked_at < ?)""",
                (
                    _iso(now - SESSION_RECORD_RETENTION),
                    _iso(now - SESSION_RECORD_RETENTION),
                ),
            )

    def _enforce_rate_limit(self, action: str, client_key: str | None, limit: int) -> None:
        if not client_key:
            return
        now = self.runtime.clock()
        client_hash = _sha256(client_key)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM auth_rate_limits WHERE window_started_at < ?",
                (_iso(now - RATE_LIMIT_RETENTION),),
            )
            row = connection.execute(
                "SELECT window_started_at, attempts FROM auth_rate_limits WHERE action = ? AND client_hash = ?",
                (action, client_hash),
            ).fetchone()
            window_started = _parse(row["window_started_at"]) if row else None
            if not row or not window_started or now - window_started >= AUTH_RATE_WINDOW:
                connection.execute(
                    """INSERT INTO auth_rate_limits(action, client_hash, window_started_at, attempts)
                       VALUES (?, ?, ?, 1)
                       ON CONFLICT(action, client_hash) DO UPDATE SET
                           window_started_at = excluded.window_started_at,
                           attempts = excluded.attempts""",
                    (action, client_hash, _iso(now)),
                )
                return
            if int(row["attempts"]) >= limit:
                self._audit(
                    connection,
                    "auth_rate_limited",
                    detail=action,
                    client_key=client_key,
                )
                connection.commit()
                raise AuthError(429, "rate_limited", "请求过于频繁，请稍后重试。")
            connection.execute(
                "UPDATE auth_rate_limits SET attempts = attempts + 1 WHERE action = ? AND client_hash = ?",
                (action, client_hash),
            )

    def _insert_session(
        self, connection: sqlite3.Connection, user_id: int, now: datetime
    ) -> tuple[str, str, str, str]:
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        absolute_expires = now + SESSION_ABSOLUTE
        now_iso = _iso(now)
        connection.execute(
            """UPDATE auth_sessions SET revoked_at = ?
               WHERE user_id = ? AND revoked_at IS NULL
                 AND (idle_expires_at <= ? OR absolute_expires_at <= ?)""",
            (now_iso, user_id, now_iso, now_iso),
        )
        connection.execute(
            """UPDATE auth_sessions SET revoked_at = ?
               WHERE user_id = ? AND revoked_at IS NULL AND id NOT IN (
                   SELECT id FROM auth_sessions
                   WHERE user_id = ? AND revoked_at IS NULL
                   ORDER BY id DESC LIMIT ?
               )""",
            (now_iso, user_id, user_id, MAX_ACTIVE_SESSIONS_PER_USER - 1),
        )
        cursor = connection.execute(
            """INSERT INTO auth_sessions(
                   token_hash, csrf_hash, user_id, created_at, last_seen_at,
                   idle_expires_at, absolute_expires_at, revoked_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)""",
            (
                _sha256(token),
                _sha256(csrf),
                user_id,
                now_iso,
                now_iso,
                _iso(now + SESSION_IDLE),
                _iso(absolute_expires),
            ),
        )
        connection.execute(
            """DELETE FROM auth_sessions
               WHERE user_id = ? AND id NOT IN (
                   SELECT id FROM auth_sessions WHERE user_id = ?
                   ORDER BY id DESC LIMIT ?
               )""",
            (user_id, user_id, MAX_SESSION_RECORDS_PER_USER),
        )
        generation = _session_generation(int(cursor.lastrowid), _sha256(csrf))
        return token, csrf, _iso(absolute_expires), generation

    @staticmethod
    def _public_user(row: sqlite3.Row) -> dict[str, object]:
        return {
            "id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"],
            "role": row["role"],
        }

    def setup_required(self) -> bool:
        with self._connection() as connection:
            return connection.execute(
                "SELECT 1 FROM auth_users WHERE role = 'admin' LIMIT 1"
            ).fetchone() is None

    def register(
        self,
        username: str,
        display_name: str,
        password: str,
        password_confirm: str,
        *,
        client_key: str | None = None,
    ) -> dict[str, object]:
        self._enforce_rate_limit("register", client_key, REGISTER_RATE_LIMIT)
        if not self.runtime.registration_open:
            raise AuthError(403, "registration_closed", "当前暂未开放新用户注册。")
        normalized = self.normalize_username(username)
        display = self.validate_display_name(display_name)
        if not hmac.compare_digest(password.encode("utf-8"), password_confirm.encode("utf-8")):
            raise AuthError(400, "password_mismatch", "两次输入的密码不一致。")
        self.validate_password(normalized, password)
        salt, digest = self.hash_password(password)
        now = self.runtime.clock()
        try:
            with self._connection() as connection:
                cursor = connection.execute(
                    """INSERT INTO auth_users(
                           username, username_normalized, display_name, password_salt, password_hash,
                           password_params, role, is_active, created_at, password_changed_at
                       ) VALUES (?, ?, ?, ?, ?, ?, 'user', 1, ?, ?)""",
                    (
                        username.strip(),
                        normalized,
                        display,
                        salt,
                        digest,
                        json.dumps({"n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P, "dklen": SCRYPT_DKLEN}),
                        _iso(now),
                        _iso(now),
                    ),
                )
                user_id = int(cursor.lastrowid)
                token, csrf, expires_at, session_generation = self._insert_session(connection, user_id, now)
                self._audit(connection, "register_success", user_id=user_id, username=normalized, client_key=client_key)
                row = connection.execute("SELECT * FROM auth_users WHERE id = ?", (user_id,)).fetchone()
        except sqlite3.IntegrityError as exc:
            raise AuthError(409, "username_exists", "该用户名已被使用。") from exc
        return {
            "user": self._public_user(row),
            "session_token": token,
            "csrf_token": csrf,
            "expires_at": expires_at,
            "session_generation": session_generation,
        }

    def setup_admin(
        self,
        bootstrap_token: str,
        username: str,
        display_name: str,
        password: str,
        password_confirm: str,
        *,
        client_key: str | None = None,
    ) -> dict[str, object]:
        self._enforce_rate_limit("setup_admin", client_key, SETUP_RATE_LIMIT)
        normalized = self.normalize_username(username)
        display = self.validate_display_name(display_name)
        if not hmac.compare_digest(password.encode("utf-8"), password_confirm.encode("utf-8")):
            raise AuthError(400, "password_mismatch", "两次输入的密码不一致。")
        self.validate_password(normalized, password)
        salt, digest = self.hash_password(password)
        now = self.runtime.clock()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM auth_users WHERE role = 'admin' LIMIT 1").fetchone():
                raise AuthError(409, "admin_exists", "管理员已完成初始化。")
            meta = connection.execute(
                "SELECT value FROM auth_meta WHERE key = 'bootstrap_token_sha256'"
            ).fetchone()
            supplied_hash = _sha256(bootstrap_token)
            if not meta or not hmac.compare_digest(meta["value"], supplied_hash):
                self._audit(connection, "admin_setup_failed", username=normalized, detail="invalid_bootstrap", client_key=client_key)
                connection.commit()
                raise AuthError(403, "setup_denied", "管理员初始化信息无效。")
            try:
                cursor = connection.execute(
                    """INSERT INTO auth_users(
                           username, username_normalized, display_name, password_salt, password_hash,
                           password_params, role, is_active, created_at, password_changed_at
                       ) VALUES (?, ?, ?, ?, ?, ?, 'admin', 1, ?, ?)""",
                    (
                        username.strip(), normalized, display, salt, digest,
                        json.dumps({"n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P, "dklen": SCRYPT_DKLEN}),
                        _iso(now), _iso(now),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise AuthError(409, "username_exists", "该用户名已被使用。") from exc
            user_id = int(cursor.lastrowid)
            connection.execute("DELETE FROM auth_meta WHERE key = 'bootstrap_token_sha256'")
            token, csrf, expires_at, session_generation = self._insert_session(connection, user_id, now)
            self._audit(connection, "admin_setup_success", user_id=user_id, username=normalized, client_key=client_key)
            row = connection.execute("SELECT * FROM auth_users WHERE id = ?", (user_id,)).fetchone()
        self.runtime.bootstrap_token_path.unlink(missing_ok=True)
        return {
            "user": self._public_user(row),
            "session_token": token,
            "csrf_token": csrf,
            "expires_at": expires_at,
            "session_generation": session_generation,
        }

    def login(
        self,
        username: str,
        password: str,
        *,
        client_key: str | None = None,
    ) -> dict[str, object]:
        self._enforce_rate_limit("login", client_key, LOGIN_RATE_LIMIT)
        try:
            normalized = self.normalize_username(username)
        except AuthError:
            normalized = username.strip().lower()[:32]
        now = self.runtime.clock()
        generic = AuthError(401, "invalid_credentials", "用户名或密码错误。")
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM auth_users WHERE username_normalized = ?", (normalized,)
            ).fetchone()
            if row is None:
                self.verify_password(password[:128], self._dummy_salt, self._dummy_digest)
                self._audit(connection, "login_failed", username=normalized, detail="invalid_credentials", client_key=client_key)
                connection.commit()
                raise generic

            # Always pay the password-verification cost for existing accounts, including
            # locked and disabled users, so the generic error does not expose account state
            # through a cheap timing distinction. Keep the expensive scrypt work outside
            # the write transaction, then serialize only the counter/session mutation.
            password_matches = self.verify_password(
                password[:128], row["password_salt"], row["password_hash"]
            )
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT * FROM auth_users WHERE id = ?", (row["id"],)
            ).fetchone()
            if current is None:
                self._audit(connection, "login_failed", username=normalized, detail="invalid_credentials", client_key=client_key)
                connection.commit()
                raise generic

            locked_until = _parse(current["locked_until"])
            if locked_until and locked_until > now:
                self._audit(
                    connection,
                    "login_failed",
                    user_id=current["id"],
                    username=normalized,
                    detail="locked",
                    client_key=client_key,
                )
                connection.commit()
                raise generic

            failed_attempts = 0 if locked_until else int(current["failed_attempts"])
            valid = bool(current["is_active"]) and password_matches
            if not valid:
                failed_attempts += 1
                new_lock = _iso(now + LOCKOUT_DURATION) if failed_attempts >= MAX_FAILED_LOGINS else None
                connection.execute(
                    "UPDATE auth_users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                    (failed_attempts, new_lock, current["id"]),
                )
                self._audit(
                    connection,
                    "login_failed",
                    user_id=current["id"],
                    username=normalized,
                    detail="invalid_credentials",
                    client_key=client_key,
                )
                connection.commit()
                raise generic

            connection.execute(
                "UPDATE auth_users SET failed_attempts = 0, locked_until = NULL, last_login_at = ? WHERE id = ?",
                (_iso(now), current["id"]),
            )
            token, csrf, expires_at, session_generation = self._insert_session(connection, current["id"], now)
            self._audit(connection, "login_success", user_id=current["id"], username=normalized, client_key=client_key)
        return {
            "user": self._public_user(current),
            "session_token": token,
            "csrf_token": csrf,
            "expires_at": expires_at,
            "session_generation": session_generation,
        }

    def authenticate(self, token: str | None, *, touch: bool = True) -> AuthPrincipal | None:
        if not token or len(token) > 256:
            return None
        now = self.runtime.clock()
        with self._connection() as connection:
            row = connection.execute(
                """SELECT s.*, u.username, u.display_name, u.role, u.is_active
                   FROM auth_sessions s JOIN auth_users u ON u.id = s.user_id
                   WHERE s.token_hash = ?""",
                (_sha256(token),),
            ).fetchone()
            if not row or row["revoked_at"] or not bool(row["is_active"]):
                return None
            idle_expires = _parse(row["idle_expires_at"])
            absolute_expires = _parse(row["absolute_expires_at"])
            if not idle_expires or not absolute_expires or idle_expires <= now or absolute_expires <= now:
                connection.execute(
                    "UPDATE auth_sessions SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                    (_iso(now), row["id"]),
                )
                return None
            last_seen = _parse(row["last_seen_at"]) or now
            if touch and now - last_seen >= timedelta(minutes=1):
                next_idle = min(now + SESSION_IDLE, absolute_expires)
                connection.execute(
                    "UPDATE auth_sessions SET last_seen_at = ?, idle_expires_at = ? WHERE id = ?",
                    (_iso(now), _iso(next_idle), row["id"]),
                )
            return AuthPrincipal(
                id=int(row["user_id"]),
                username=row["username"],
                display_name=row["display_name"],
                role=row["role"],
                is_active=bool(row["is_active"]),
                session_id=int(row["id"]),
                csrf_hash=row["csrf_hash"],
                expires_at=_iso(absolute_expires),
            )

    @staticmethod
    def require_csrf(principal: AuthPrincipal, csrf_token: str | None) -> None:
        if not csrf_token or len(csrf_token) > 256 or not hmac.compare_digest(principal.csrf_hash, _sha256(csrf_token)):
            raise AuthError(403, "csrf_failed", "请求安全校验失败，请刷新页面后重试。")

    def logout(self, principal: AuthPrincipal, *, client_key: str | None = None) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE auth_sessions SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                (_iso(self.runtime.clock()), principal.session_id),
            )
            self._audit(connection, "logout", user_id=principal.id, username=principal.username, client_key=client_key)

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        value = symbol.strip().upper()
        if not SYMBOL_RE.fullmatch(value):
            raise AuthError(400, "invalid_symbol", "股票代码格式无效。")
        return value

    def list_watchlist(self, user_id: int) -> list[dict[str, object]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT symbol, created_at FROM user_watchlist WHERE user_id = ? ORDER BY created_at DESC, id DESC",
                (user_id,),
            ).fetchall()
        return [{"symbol": row["symbol"], "created_at": row["created_at"]} for row in rows]

    def add_watchlist(self, user_id: int, symbol: str) -> dict[str, object]:
        value = self.normalize_symbol(symbol)
        now = _iso(self.runtime.clock())
        with self._connection() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO user_watchlist(user_id, symbol, created_at) VALUES (?, ?, ?)",
                (user_id, value, now),
            )
            row = connection.execute(
                "SELECT symbol, created_at FROM user_watchlist WHERE user_id = ? AND symbol = ?",
                (user_id, value),
            ).fetchone()
            self._audit(connection, "watchlist_add", user_id=user_id, detail=value)
        return {"symbol": row["symbol"], "created_at": row["created_at"]}

    def remove_watchlist(self, user_id: int, symbol: str) -> bool:
        value = self.normalize_symbol(symbol)
        with self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM user_watchlist WHERE user_id = ? AND symbol = ?", (user_id, value)
            )
            if cursor.rowcount:
                self._audit(connection, "watchlist_remove", user_id=user_id, detail=value)
            return bool(cursor.rowcount)

    def list_users(self) -> list[dict[str, object]]:
        now = _iso(self.runtime.clock())
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT u.id, u.username, u.display_name, u.role, u.is_active,
                          u.failed_attempts, u.locked_until, u.created_at,
                          u.password_changed_at, u.last_login_at,
                          COUNT(DISTINCT w.id) AS watchlist_count,
                          COUNT(DISTINCT CASE WHEN s.revoked_at IS NULL AND s.idle_expires_at > ?
                                                AND s.absolute_expires_at > ? THEN s.id END) AS active_sessions
                   FROM auth_users u
                   LEFT JOIN user_watchlist w ON w.user_id = u.id
                   LEFT JOIN auth_sessions s ON s.user_id = u.id
                   GROUP BY u.id ORDER BY u.created_at DESC""",
                (now, now),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_user_active(
        self, actor: AuthPrincipal, user_id: int, is_active: bool, *, client_key: str | None = None
    ) -> dict[str, object]:
        if actor.role != "admin":
            self.record_security_event(
                "admin_user_status_denied",
                principal=actor,
                detail="admin_required",
                client_key=client_key,
            )
            raise AuthError(403, "admin_required", "仅管理员可执行此操作。")
        if actor.id == user_id and not is_active:
            self.record_security_event(
                "admin_user_status_denied",
                principal=actor,
                detail="cannot_disable_self",
                client_key=client_key,
            )
            raise AuthError(400, "cannot_disable_self", "不能禁用当前管理员账号。")
        now = _iso(self.runtime.clock())
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM auth_users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                raise AuthError(404, "user_not_found", "用户不存在。")
            connection.execute("UPDATE auth_users SET is_active = ? WHERE id = ?", (int(is_active), user_id))
            if not is_active:
                connection.execute(
                    "UPDATE auth_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                    (now, user_id),
                )
            self._audit(
                connection,
                "admin_user_status",
                user_id=actor.id,
                username=actor.username,
                detail=f"target={user_id};active={int(is_active)}",
                client_key=client_key,
            )
            updated = connection.execute(
                "SELECT id, username, display_name, role, is_active, created_at, last_login_at FROM auth_users WHERE id = ?",
                (user_id,),
            ).fetchone()
        result = dict(updated)
        result["is_active"] = bool(result["is_active"])
        return result

    def unlock_user(
        self, actor: AuthPrincipal, user_id: int, *, client_key: str | None = None
    ) -> dict[str, object]:
        if actor.role != "admin":
            self.record_security_event(
                "admin_user_unlock_denied",
                principal=actor,
                detail="admin_required",
                client_key=client_key,
            )
            raise AuthError(403, "admin_required", "仅管理员可执行此操作。")
        with self._connection() as connection:
            target = connection.execute(
                "SELECT id, username FROM auth_users WHERE id = ?", (user_id,)
            ).fetchone()
            if target is None:
                raise AuthError(404, "user_not_found", "用户不存在。")
            connection.execute(
                "UPDATE auth_users SET failed_attempts = 0, locked_until = NULL WHERE id = ?",
                (user_id,),
            )
            self._audit(
                connection,
                "admin_user_unlock",
                user_id=actor.id,
                username=actor.username,
                detail=f"target={user_id};username={target['username']}",
                client_key=client_key,
            )
        return {"user_id": user_id, "failed_attempts": 0, "locked_until": None}

    def revoke_user_sessions(
        self, actor: AuthPrincipal, user_id: int, *, client_key: str | None = None
    ) -> dict[str, int]:
        if actor.role != "admin":
            self.record_security_event(
                "admin_user_sessions_revoke_denied",
                principal=actor,
                detail="admin_required",
                client_key=client_key,
            )
            raise AuthError(403, "admin_required", "仅管理员可执行此操作。")
        now = _iso(self.runtime.clock())
        with self._connection() as connection:
            target = connection.execute(
                "SELECT id, username FROM auth_users WHERE id = ?", (user_id,)
            ).fetchone()
            if target is None:
                raise AuthError(404, "user_not_found", "用户不存在。")
            if actor.id == user_id:
                cursor = connection.execute(
                    """UPDATE auth_sessions SET revoked_at = ?
                       WHERE user_id = ? AND id != ? AND revoked_at IS NULL
                         AND idle_expires_at > ? AND absolute_expires_at > ?""",
                    (now, user_id, actor.session_id, now, now),
                )
            else:
                cursor = connection.execute(
                    """UPDATE auth_sessions SET revoked_at = ?
                       WHERE user_id = ? AND revoked_at IS NULL
                         AND idle_expires_at > ? AND absolute_expires_at > ?""",
                    (now, user_id, now, now),
                )
            remaining = connection.execute(
                """SELECT COUNT(*) FROM auth_sessions
                   WHERE user_id = ? AND revoked_at IS NULL
                     AND idle_expires_at > ? AND absolute_expires_at > ?""",
                (user_id, now, now),
            ).fetchone()[0]
            revoked = max(0, cursor.rowcount)
            self._audit(
                connection,
                "admin_user_sessions_revoked",
                user_id=actor.id,
                username=actor.username,
                detail=(
                    f"target={user_id};username={target['username']};"
                    f"revoked={revoked};remaining={int(remaining)}"
                ),
                client_key=client_key,
            )
        return {
            "user_id": user_id,
            "revoked_sessions": revoked,
            "remaining_active_sessions": int(remaining),
        }

    def recent_audit(self, limit: int = 100) -> list[dict[str, object]]:
        safe_limit = max(1, min(limit, 200))
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT id, event_type, user_id, username, detail, created_at
                   FROM auth_audit_log ORDER BY id DESC LIMIT ?""",
                (safe_limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def auth_summary(self) -> dict[str, int]:
        now = _iso(self.runtime.clock())
        with self._connection() as connection:
            users = connection.execute(
                "SELECT COUNT(*) AS total, SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active FROM auth_users"
            ).fetchone()
            sessions = connection.execute(
                """SELECT COUNT(*) FROM auth_sessions
                   WHERE revoked_at IS NULL AND idle_expires_at > ? AND absolute_expires_at > ?""",
                (now, now),
            ).fetchone()[0]
            watchlist_items = connection.execute("SELECT COUNT(*) FROM user_watchlist").fetchone()[0]
        return {
            "total_users": int(users["total"] or 0),
            "active_users": int(users["active"] or 0),
            "active_sessions": int(sessions or 0),
            "watchlist_items": int(watchlist_items or 0),
        }
