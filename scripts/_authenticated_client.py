from __future__ import annotations

import secrets
import tempfile
import weakref
from pathlib import Path
from threading import RLock
from typing import Any

from fastapi.testclient import TestClient

from backend.app.services.auth_service import AuthRuntime, AuthService


_AUTH_STATE_LOCK = RLock()
_MISSING = object()


class _IsolatedAcceptanceClient(TestClient):
    def __init__(self, app, service: AuthService, temporary, **kwargs: Any) -> None:
        self._target_app = app
        self._isolated_auth_service = service
        self._temporary_finalizer = weakref.finalize(self, temporary.cleanup)
        super().__init__(app, **kwargs)

    def request(self, method: str, url, **kwargs: Any):
        with _AUTH_STATE_LOCK:
            previous = getattr(self._target_app.state, "auth_service", _MISSING)
            self._target_app.state.auth_service = self._isolated_auth_service
            try:
                return super().request(method, url, **kwargs)
            finally:
                if previous is _MISSING:
                    delattr(self._target_app.state, "auth_service")
                else:
                    self._target_app.state.auth_service = previous

    def close(self) -> None:
        try:
            super().close()
        finally:
            self._temporary_finalizer()


def acceptance_admin_client(app) -> TestClient:
    temporary = tempfile.TemporaryDirectory(prefix="stock-good-acceptance-auth-")
    secret_dir = Path(temporary.name)
    service = AuthService(
        AuthRuntime(
            db_path=secret_dir / "auth.db",
            bootstrap_token_path=secret_dir / "admin-bootstrap-token.txt",
            allowed_origins=("http://testserver",),
            secure_cookie=False,
        )
    )
    client = _IsolatedAcceptanceClient(app, service, temporary, base_url="http://testserver")
    token = (secret_dir / "admin-bootstrap-token.txt").read_text(encoding="utf-8").strip()
    password = f"{secrets.token_urlsafe(24)}Aa1!"
    response = client.post(
        "/api/auth/setup-admin",
        headers={"Origin": "http://testserver"},
        json={
            "bootstrap_token": token,
            "username": "acceptance.root",
            "display_name": "验收管理员",
            "password": password,
            "password_confirm": password,
        },
    )
    if response.status_code != 201:
        client.close()
        raise RuntimeError("Could not initialize isolated acceptance admin")
    return client
