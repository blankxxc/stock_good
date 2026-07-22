from __future__ import annotations

import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import auth_service as auth_service_module
from backend.app.services.auth_service import AuthError, AuthRuntime, AuthService


@dataclass
class MutableClock:
    value: datetime

    def __call__(self) -> datetime:
        return self.value

    def advance(self, **delta: int) -> None:
        self.value += timedelta(**delta)


@pytest.fixture
def auth_runtime(tmp_path: Path):
    clock = MutableClock(datetime(2026, 7, 20, tzinfo=timezone.utc))
    secret_dir = tmp_path / ".secrets"
    runtime = AuthRuntime(
        db_path=secret_dir / "auth.db",
        bootstrap_token_path=secret_dir / "admin-bootstrap-token.txt",
        allowed_origins=("http://testserver",),
        secure_cookie=False,
        clock=clock,
    )
    service = AuthService(runtime)
    previous = getattr(app.state, "auth_service", None)
    app.state.auth_service = service
    yield service, clock, secret_dir
    if previous is None:
        delattr(app.state, "auth_service")
    else:
        app.state.auth_service = previous


def new_client() -> TestClient:
    return TestClient(app, base_url="http://testserver")


def csrf_token(client: TestClient) -> str:
    value = client.cookies.get("oa_csrf")
    assert value
    return value


def session_context_headers(client: TestClient) -> dict[str, str]:
    status = client.get("/api/auth/status")
    assert status.status_code == 200
    payload = status.json()
    assert payload["authenticated"] is True
    assert payload["session_generation"]
    return {
        "X-Expected-User-Id": str(payload["user"]["id"]),
        "X-Expected-Session-Generation": payload["session_generation"],
    }


def register(client: TestClient, username: str, password: str = "UserSecure!Pass2026"):
    return client.post(
        "/api/auth/register",
        headers={"Origin": "http://testserver"},
        json={
            "username": username,
            "display_name": username.title(),
            "password": password,
            "password_confirm": password,
        },
    )


def setup_admin(client: TestClient, secret_dir: Path):
    client.get("/api/auth/status")
    token = (secret_dir / "admin-bootstrap-token.txt").read_text(encoding="utf-8").strip()
    response = client.post(
        "/api/auth/setup-admin",
        headers={"Origin": "http://testserver"},
        json={
            "bootstrap_token": token,
            "username": "platform.admin",
            "display_name": "平台管理员",
            "password": "AdminSecure!Pass2026",
            "password_confirm": "AdminSecure!Pass2026",
        },
    )
    assert response.status_code == 201, response.text
    return response, token


def login(client: TestClient, username: str, password: str):
    return client.post(
        "/api/auth/login",
        headers={"Origin": "http://testserver"},
        json={"username": username, "password": password},
    )


def test_public_registration_creates_only_users_and_admin_setup_is_one_time(auth_runtime) -> None:
    _, _, secret_dir = auth_runtime
    client = new_client()

    status = client.get("/api/auth/status")
    assert status.status_code == 200
    assert status.headers["cache-control"] == "no-store"
    assert status.json()["setup_required"] is True
    assert status.json()["registration_open"] is True
    token_file = secret_dir / "admin-bootstrap-token.txt"
    assert token_file.is_file()
    raw_token = token_file.read_text(encoding="utf-8").strip()
    assert raw_token not in status.text

    user = register(client, "alice")
    assert user.status_code == 201, user.text
    assert user.json()["user"]["role"] == "user"
    assert user.json()["user"]["username"] == "alice"
    assert "password" not in user.text.lower()

    duplicate = register(new_client(), "ALICE")
    assert duplicate.status_code == 409

    admin_client = new_client()
    admin, used_token = setup_admin(admin_client, secret_dir)
    assert admin.json()["user"]["role"] == "admin"
    assert not token_file.exists()
    assert used_token not in admin.text

    second = admin_client.post(
        "/api/auth/setup-admin",
        headers={"Origin": "http://testserver"},
        json={
            "bootstrap_token": used_token,
            "username": "second.admin",
            "display_name": "Second",
            "password": "AnotherSecure!Pass2026",
            "password_confirm": "AnotherSecure!Pass2026",
        },
    )
    assert second.status_code == 409


def test_registration_policy_can_be_closed_without_hiding_only_the_frontend(auth_runtime, tmp_path: Path) -> None:
    open_service, _, _ = auth_runtime
    secret_dir = tmp_path / "closed-registration"
    closed_service = AuthService(
        AuthRuntime(
            db_path=secret_dir / "auth.db",
            bootstrap_token_path=secret_dir / "admin-bootstrap-token.txt",
            allowed_origins=("http://testserver",),
            secure_cookie=False,
            registration_open=False,
        )
    )
    app.state.auth_service = closed_service
    try:
        client = new_client()
        status = client.get("/api/auth/status")
        assert status.status_code == 200
        assert status.json()["registration_open"] is False
        denied = register(client, "closed.user")
        assert denied.status_code == 403
        assert denied.json()["detail"]["code"] == "registration_closed"
    finally:
        app.state.auth_service = open_service


def test_https_allowed_origin_requires_secure_cookies(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="SECURE_COOKIE"):
        AuthService(
            AuthRuntime(
                db_path=tmp_path / "https-auth.db",
                bootstrap_token_path=tmp_path / "https-bootstrap.txt",
                allowed_origins=("https://stocks.example.com",),
                secure_cookie=False,
            )
        )


def test_concurrent_admin_setup_creates_exactly_one_administrator(auth_runtime) -> None:
    service, _, secret_dir = auth_runtime
    token_path = secret_dir / "admin-bootstrap-token.txt"
    token = token_path.read_text(encoding="utf-8").strip()

    def attempt(index: int) -> tuple[str, str]:
        try:
            result = service.setup_admin(
                token,
                f"admin.{index}",
                f"管理员 {index}",
                "AdminSecure!Pass2026",
                "AdminSecure!Pass2026",
                client_key=f"concurrent-{index}",
            )
            return "created", str(result["user"])
        except AuthError as error:
            return "rejected", error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, (1, 2)))

    assert [status for status, _ in results].count("created") == 1
    assert [status for status, _ in results].count("rejected") == 1
    assert next(detail for status, detail in results if status == "rejected") in {"admin_exists", "bootstrap_invalid"}
    with sqlite3.connect(secret_dir / "auth.db") as connection:
        assert connection.execute("SELECT COUNT(*) FROM auth_users WHERE role = 'admin'").fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM auth_meta WHERE key = 'bootstrap_token_sha256'"
        ).fetchone()[0] == 0
    assert not token_path.exists()


def test_passwords_and_session_tokens_are_hashed_and_never_returned(auth_runtime) -> None:
    service, _, secret_dir = auth_runtime
    client = new_client()
    password = "UserSecure!Pass2026"
    response = register(client, "alice", password)
    assert response.status_code == 201

    with sqlite3.connect(secret_dir / "auth.db") as connection:
        salt, digest = connection.execute(
            "SELECT password_salt, password_hash FROM auth_users WHERE username_normalized = ?",
            ("alice",),
        ).fetchone()
        token_hash, csrf_hash = connection.execute(
            "SELECT token_hash, csrf_hash FROM auth_sessions ORDER BY id DESC LIMIT 1"
        ).fetchone()

    assert isinstance(salt, bytes) and len(salt) == 16
    assert isinstance(digest, bytes) and len(digest) == 32
    assert service.verify_password(password, salt, digest) is True
    assert service.verify_password("WrongSecure!Pass2026", salt, digest) is False
    assert password not in response.text
    cookie = client.cookies.get("oa_session")
    csrf = csrf_token(client)
    assert cookie and token_hash == hashlib.sha256(cookie.encode()).hexdigest()
    assert csrf_hash == hashlib.sha256(csrf.encode()).hexdigest()
    assert cookie not in {token_hash, csrf_hash}
    generation = response.json()["session_generation"]
    assert len(generation) == 64
    assert generation == client.get("/api/auth/status").json()["session_generation"]
    assert generation not in {cookie, csrf, token_hash, csrf_hash}
    assert "session_token" not in response.json()
    assert "csrf_token" not in response.json()
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]


def test_session_and_audit_security_state_are_bounded(auth_runtime, monkeypatch) -> None:
    service, clock, secret_dir = auth_runtime
    monkeypatch.setattr(auth_service_module, "MAX_ACTIVE_SESSIONS_PER_USER", 2)
    monkeypatch.setattr(auth_service_module, "MAX_SESSION_RECORDS_PER_USER", 3)
    monkeypatch.setattr(auth_service_module, "MAX_AUDIT_ROWS", 3)

    client = new_client()
    assert register(client, "bounded.user").status_code == 201
    with service._connection() as connection:
        user_id = connection.execute(
            "SELECT id FROM auth_users WHERE username_normalized = ?",
            ("bounded.user",),
        ).fetchone()["id"]
        for _ in range(5):
            service._insert_session(connection, user_id, clock())
        for index in range(5):
            service._audit(connection, f"bounded_event_{index}", user_id=user_id)

    with sqlite3.connect(secret_dir / "auth.db") as connection:
        total_sessions = connection.execute(
            "SELECT COUNT(*) FROM auth_sessions WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        active_sessions = connection.execute(
            "SELECT COUNT(*) FROM auth_sessions WHERE user_id = ? AND revoked_at IS NULL", (user_id,)
        ).fetchone()[0]
        audit_count = connection.execute("SELECT COUNT(*) FROM auth_audit_log").fetchone()[0]
    assert total_sessions == 3
    assert active_sessions == 2
    assert audit_count == 3


def test_missing_bootstrap_token_file_is_rotated_instead_of_bricking_setup(auth_runtime) -> None:
    service, _, secret_dir = auth_runtime
    token_path = secret_dir / "admin-bootstrap-token.txt"
    original = token_path.read_text(encoding="utf-8").strip()
    token_path.unlink()

    AuthService(service.runtime)

    replacement = token_path.read_text(encoding="utf-8").strip()
    assert replacement
    assert replacement != original
    with sqlite3.connect(secret_dir / "auth.db") as connection:
        stored_hash = connection.execute(
            "SELECT value FROM auth_meta WHERE key = 'bootstrap_token_sha256'"
        ).fetchone()[0]
    assert stored_hash == hashlib.sha256(replacement.encode("utf-8")).hexdigest()
    assert stored_hash != replacement


def test_each_user_has_an_isolated_watchlist(auth_runtime) -> None:
    alice = new_client()
    bob = new_client()
    register(alice, "alice")
    register(bob, "bob")
    alice_context = session_context_headers(alice)
    bob_context = session_context_headers(bob)

    added = alice.post(
        "/api/watchlist",
        headers={"Origin": "http://testserver", "X-CSRF-Token": csrf_token(alice), **alice_context},
        json={"symbol": "000001.SZ"},
    )
    assert added.status_code == 201, added.text
    assert added.json()["symbol"] == "000001.SZ"
    assert [item["symbol"] for item in alice.get("/api/watchlist", headers=alice_context).json()["items"]] == ["000001.SZ"]
    assert bob.get("/api/watchlist", headers=bob_context).json()["items"] == []

    cannot_delete = bob.delete(
        "/api/watchlist/000001.SZ",
        headers={"Origin": "http://testserver", "X-CSRF-Token": csrf_token(bob), **bob_context},
    )
    assert cannot_delete.status_code == 404
    assert len(alice.get("/api/watchlist", headers=alice_context).json()["items"]) == 1

    removed = alice.delete(
        "/api/watchlist/000001.SZ",
        headers={"Origin": "http://testserver", "X-CSRF-Token": csrf_token(alice), **alice_context},
    )
    assert removed.status_code == 204
    assert alice.get("/api/watchlist", headers=alice_context).json()["items"] == []


def test_stale_page_context_cannot_read_or_mutate_the_new_cookie_owner(auth_runtime) -> None:
    service, _, _ = auth_runtime
    switched = new_client()
    assert register(switched, "context.alice").status_code == 201
    alice_context = session_context_headers(switched)

    # Simulate another tab replacing the shared cookies before its broadcast arrives.
    assert register(switched, "context.bob").status_code == 201
    bob_context = session_context_headers(switched)
    assert alice_context != bob_context

    missing_context = switched.get("/api/watchlist")
    assert missing_context.status_code == 409
    assert missing_context.json()["detail"]["code"] == "session_context_changed"

    stale_read = switched.get("/api/watchlist", headers=alice_context)
    assert stale_read.status_code == 409
    assert stale_read.json()["detail"]["code"] == "session_context_changed"

    stale_write = switched.post(
        "/api/watchlist",
        headers={
            "Origin": "http://testserver",
            "X-CSRF-Token": csrf_token(switched),
            **alice_context,
        },
        json={"symbol": "000001.SZ"},
    )
    assert stale_write.status_code == 409
    assert stale_write.json()["detail"]["code"] == "session_context_changed"
    assert switched.get("/api/watchlist", headers=bob_context).json()["items"] == []
    assert "session_context_mismatch" in {event["event_type"] for event in service.recent_audit(100)}


def test_same_user_old_session_generation_is_rejected_and_is_not_a_bearer(auth_runtime) -> None:
    service, _, _ = auth_runtime
    old_session = new_client()
    assert register(old_session, "generation.user").status_code == 201
    old_context = session_context_headers(old_session)

    current_session = new_client()
    assert login(current_session, "generation.user", "UserSecure!Pass2026").status_code == 200
    current_context = session_context_headers(current_session)
    assert old_context["X-Expected-User-Id"] == current_context["X-Expected-User-Id"]
    assert old_context["X-Expected-Session-Generation"] != current_context["X-Expected-Session-Generation"]

    mutation_headers = {
        "Origin": "http://testserver",
        "X-CSRF-Token": csrf_token(current_session),
        **current_context,
    }
    assert current_session.post(
        "/api/watchlist",
        headers=mutation_headers,
        json={"symbol": "000001.SZ"},
    ).status_code == 201

    stale_read = current_session.get("/api/watchlist", headers=old_context)
    stale_add = current_session.post(
        "/api/watchlist",
        headers={
            "Origin": "http://testserver",
            "X-CSRF-Token": csrf_token(current_session),
            **old_context,
        },
        json={"symbol": "000002.SZ"},
    )
    stale_delete = current_session.delete(
        "/api/watchlist/000001.SZ",
        headers={
            "Origin": "http://testserver",
            "X-CSRF-Token": csrf_token(current_session),
            **old_context,
        },
    )
    for response in (stale_read, stale_add, stale_delete):
        assert response.status_code == 409
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["detail"]["code"] == "session_context_changed"

    items = current_session.get("/api/watchlist", headers=current_context).json()["items"]
    assert [item["symbol"] for item in items] == ["000001.SZ"]

    anonymous = new_client()
    assert anonymous.get("/api/watchlist", headers=current_context).status_code == 401
    assert anonymous.post(
        "/api/watchlist",
        headers={"Origin": "http://testserver", "X-CSRF-Token": csrf_token(current_session), **current_context},
        json={"symbol": "000002.SZ"},
    ).status_code == 401
    assert anonymous.delete(
        "/api/watchlist/000001.SZ",
        headers={"Origin": "http://testserver", "X-CSRF-Token": csrf_token(current_session), **current_context},
    ).status_code == 401
    assert sum(event["event_type"] == "session_context_mismatch" for event in service.recent_audit(100)) >= 3


def test_each_watchlist_context_header_is_required_before_service_access(auth_runtime, monkeypatch) -> None:
    service, _, _ = auth_runtime
    client = new_client()
    assert register(client, "context.headers").status_code == 201
    context = session_context_headers(client)
    only_user = {"X-Expected-User-Id": context["X-Expected-User-Id"]}
    only_generation = {
        "X-Expected-Session-Generation": context["X-Expected-Session-Generation"],
    }
    calls = {"list": 0, "add": 0, "remove": 0}

    def tracked_list(*_args, **_kwargs):
        calls["list"] += 1
        return []

    def tracked_add(*_args, **_kwargs):
        calls["add"] += 1
        return {"symbol": "000001.SZ"}

    def tracked_remove(*_args, **_kwargs):
        calls["remove"] += 1
        return True

    monkeypatch.setattr(service, "list_watchlist", tracked_list)
    monkeypatch.setattr(service, "add_watchlist", tracked_add)
    monkeypatch.setattr(service, "remove_watchlist", tracked_remove)

    for partial_context in (only_user, only_generation):
        get_response = client.get("/api/watchlist", headers=partial_context)
        post_response = client.post(
            "/api/watchlist",
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": csrf_token(client),
                **partial_context,
            },
            json={"symbol": "000001.SZ"},
        )
        delete_response = client.delete(
            "/api/watchlist/000001.SZ",
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": csrf_token(client),
                **partial_context,
            },
        )
        for response in (get_response, post_response, delete_response):
            assert response.status_code == 409
            assert response.json()["detail"]["code"] == "session_context_changed"

    assert calls == {"list": 0, "add": 0, "remove": 0}
    assert sum(event["event_type"] == "session_context_mismatch" for event in service.recent_audit(100)) >= 6


def test_admin_rbac_user_management_and_deactivation_revokes_user_sessions(auth_runtime) -> None:
    service, _, secret_dir = auth_runtime
    anonymous = new_client()
    user_client = new_client()
    admin_client = new_client()
    user_auth = register(user_client, "alice").json()
    admin_auth, _ = setup_admin(admin_client, secret_dir)
    admin_data = admin_auth.json()

    assert anonymous.get("/api/admin/users").status_code == 401
    assert user_client.get("/api/admin/users").status_code == 403
    user_admin_html = user_client.get("/admin", follow_redirects=False)
    assert user_admin_html.status_code == 403

    users = admin_client.get("/api/admin/users")
    assert users.status_code == 200
    alice = next(item for item in users.json()["users"] if item["username"] == "alice")
    assert alice["role"] == "user"

    disabled = admin_client.patch(
        f"/api/admin/users/{alice['id']}",
        headers={"Origin": "http://testserver", "X-CSRF-Token": csrf_token(admin_client)},
        json={"is_active": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False
    assert user_client.get("/api/auth/session").status_code == 401
    assert login(new_client(), "alice", "UserSecure!Pass2026").status_code == 401
    assert user_auth["user"]["role"] == "user"

    cannot_disable_self = admin_client.patch(
        f"/api/admin/users/{admin_data['user']['id']}",
        headers={"Origin": "http://testserver", "X-CSRF-Token": csrf_token(admin_client)},
        json={"is_active": False},
    )
    assert cannot_disable_self.status_code == 400
    assert cannot_disable_self.json()["detail"]["code"] == "cannot_disable_self"
    assert admin_client.get("/api/auth/session").status_code == 200
    event_types = {event["event_type"] for event in service.recent_audit(200)}
    assert "authentication_required" in event_types
    assert "admin_access_denied" in event_types
    assert "admin_user_status_denied" in event_types


def test_admin_backend_and_internal_apis_are_protected_but_public_market_is_open(auth_runtime) -> None:
    _, _, secret_dir = auth_runtime
    anonymous = new_client()
    user = new_client()
    admin = new_client()
    register(user, "alice")
    setup_admin(admin, secret_dir)

    assert anonymous.get("/api/market").status_code == 200
    assert anonymous.get("/api/admin/overview").status_code == 401
    assert anonymous.get("/api/data-quality").status_code == 401
    redirect = anonymous.get("/admin", follow_redirects=False)
    assert redirect.status_code in {302, 307}
    assert redirect.headers["location"] == "/login?next=/backend-admin"
    assert redirect.headers["cache-control"] == "no-store"

    assert user.get("/api/admin/overview").status_code == 403
    assert user.get("/api/data-quality").status_code == 403
    admin_overview = admin.get("/api/admin/overview")
    assert admin_overview.status_code == 200
    assert admin_overview.headers["cache-control"] == "no-store"
    internal = admin.get("/api/data-quality")
    assert internal.status_code == 200
    assert internal.headers["cache-control"] == "no-store"
    assert admin.get("/admin").status_code == 200


def test_login_lockout_errors_are_generic_and_logout_requires_csrf(auth_runtime) -> None:
    _, clock, _ = auth_runtime
    registered = new_client()
    register(registered, "alice")
    assert registered.post("/api/auth/logout", headers={"Origin": "http://testserver"}).status_code == 403
    assert registered.post(
        "/api/auth/logout",
        headers={"Origin": "http://testserver", "X-CSRF-Token": csrf_token(registered)},
    ).status_code == 204

    probe = new_client()
    unknown = login(probe, "missing", "WrongSecure!Pass2026")
    assert unknown.status_code == 401
    generic = unknown.json()
    for _ in range(5):
        failed = login(probe, "alice", "WrongSecure!Pass2026")
        assert failed.status_code == 401
        assert failed.json() == generic
    assert login(probe, "alice", "UserSecure!Pass2026").status_code == 401
    clock.advance(minutes=15)
    probe = new_client()
    assert login(probe, "alice", "UserSecure!Pass2026").status_code == 200


def test_parallel_failed_logins_are_counted_atomically_and_locked_paths_still_hash(auth_runtime, monkeypatch) -> None:
    service, _, secret_dir = auth_runtime
    client = new_client()
    assert register(client, "parallel.user").status_code == 201

    def fail_login(_: int) -> str:
        try:
            service.login(
                "parallel.user",
                "WrongSecure!Pass2026",
                client_key="parallel-client",
            )
        except AuthError as error:
            return error.code
        return "unexpected_success"

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(fail_login, range(5)))

    assert results == ["invalid_credentials"] * 5
    with sqlite3.connect(secret_dir / "auth.db") as connection:
        failed_attempts, locked_until = connection.execute(
            "SELECT failed_attempts, locked_until FROM auth_users WHERE username_normalized = ?",
            ("parallel.user",),
        ).fetchone()
    assert failed_attempts == 5
    assert locked_until is not None

    calls = 0
    original_verify = service.verify_password

    def counted_verify(password: str, salt: bytes, expected: bytes) -> bool:
        nonlocal calls
        calls += 1
        return original_verify(password, salt, expected)

    monkeypatch.setattr(service, "verify_password", counted_verify)
    with pytest.raises(AuthError):
        service.login("parallel.user", "UserSecure!Pass2026", client_key="locked-probe")
    assert calls == 1

    with sqlite3.connect(secret_dir / "auth.db") as connection:
        connection.execute(
            "UPDATE auth_users SET is_active = 0, locked_until = NULL WHERE username_normalized = ?",
            ("parallel.user",),
        )
        connection.commit()
    with pytest.raises(AuthError):
        service.login("parallel.user", "UserSecure!Pass2026", client_key="disabled-probe")
    assert calls == 2

    with pytest.raises(AuthError):
        service.login("missing.user", "WrongSecure!Pass2026", client_key="missing-probe")
    assert calls == 3


def test_auth_rate_limit_blocks_expensive_login_bursts_and_recovers(auth_runtime, monkeypatch) -> None:
    _, clock, _ = auth_runtime
    monkeypatch.setattr(auth_service_module, "LOGIN_RATE_LIMIT", 2)
    client = new_client()
    assert register(client, "rate.user").status_code == 201

    assert login(client, "rate.user", "UserSecure!Pass2026").status_code == 200
    assert login(client, "rate.user", "UserSecure!Pass2026").status_code == 200
    limited = login(client, "rate.user", "UserSecure!Pass2026")
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "300"
    assert limited.headers["cache-control"] == "no-store"
    assert limited.json()["detail"]["code"] == "rate_limited"

    clock.advance(minutes=5)
    assert login(client, "rate.user", "UserSecure!Pass2026").status_code == 200


def test_origin_csrf_idle_and_absolute_session_limits_are_enforced(auth_runtime) -> None:
    service, clock, _ = auth_runtime
    idle_client = new_client()
    assert register(idle_client, "idle.user").status_code == 201

    missing_origin = idle_client.post(
        "/api/watchlist",
        headers={"X-CSRF-Token": csrf_token(idle_client)},
        json={"symbol": "000001.SZ"},
    )
    assert missing_origin.status_code == 403
    wrong_origin = idle_client.post(
        "/api/watchlist",
        headers={"Origin": "https://attacker.invalid", "X-CSRF-Token": csrf_token(idle_client)},
        json={"symbol": "000001.SZ"},
    )
    assert wrong_origin.status_code == 403
    wrong_csrf = idle_client.post(
        "/api/watchlist",
        headers={"Origin": "http://testserver", "X-CSRF-Token": "wrong-token"},
        json={"symbol": "000001.SZ"},
    )
    assert wrong_csrf.status_code == 403
    event_types = {event["event_type"] for event in service.recent_audit(200)}
    assert "origin_denied" in event_types
    assert "csrf_denied" in event_types

    clock.advance(minutes=31)
    assert service.auth_summary()["active_sessions"] == 0
    idle_user = next(user for user in service.list_users() if user["username"] == "idle.user")
    assert idle_user["active_sessions"] == 0
    idle_expired = idle_client.get("/api/auth/session")
    assert idle_expired.status_code == 401
    assert idle_expired.headers["cache-control"] == "no-store"

    absolute_client = new_client()
    assert register(absolute_client, "absolute.user").status_code == 201
    for _ in range(16):
        clock.advance(minutes=29)
        assert absolute_client.get("/api/auth/session").status_code == 200
    clock.advance(minutes=17)
    absolute_expired = absolute_client.get("/api/auth/session")
    assert absolute_expired.status_code == 401
    assert absolute_expired.headers["cache-control"] == "no-store"


def test_audit_database_never_contains_submitted_secrets(auth_runtime) -> None:
    _, _, secret_dir = auth_runtime
    admin = new_client()
    admin_response, raw_token = setup_admin(admin, secret_dir)
    password = "AdminSecure!Pass2026"
    login(new_client(), "platform.admin", "WrongSecure!Pass2026")

    with sqlite3.connect(secret_dir / "auth.db") as connection:
        audit_text = "\n".join(
            str(value)
            for row in connection.execute(
                "SELECT event_type, username, detail FROM auth_audit_log ORDER BY id"
            ).fetchall()
            for value in row
            if value is not None
        )
    for secret in (raw_token, password, "WrongSecure!Pass2026", csrf_token(admin)):
        assert secret not in audit_text
