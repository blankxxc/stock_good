from __future__ import annotations

import hmac
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.app.services.auth_service import AuthError, AuthPrincipal, AuthService
from backend.app.services.research_loop_catalog import market_overview_payload

SESSION_COOKIE = "oa_session"
CSRF_COOKIE = "oa_csrf"
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"
router = APIRouter()


class RegisterBody(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    display_name: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=12, max_length=128)
    password_confirm: str = Field(min_length=12, max_length=128)


class AdminSetupBody(RegisterBody):
    bootstrap_token: str = Field(min_length=20, max_length=256)


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class WatchlistBody(BaseModel):
    symbol: str = Field(min_length=9, max_length=16)


class UserStatusBody(BaseModel):
    is_active: bool


@lru_cache(maxsize=1)
def default_auth_service() -> AuthService:
    return AuthService()


def get_auth_service(request: Request) -> AuthService:
    return getattr(request.app.state, "auth_service", None) or default_auth_service()


def client_key(request: Request) -> str:
    host = request.client.host if request.client else "unknown"
    return host


def _raise_auth(error: AuthError) -> None:
    raise HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": error.message},
        headers={"Retry-After": "300"} if error.status_code == 429 else None,
    ) from error


def enforce_origin(request: Request, service: AuthService) -> None:
    origin = request.headers.get("origin")
    allowed = {value.rstrip("/") for value in service.runtime.allowed_origins}
    if not origin or origin.rstrip("/") not in allowed:
        service.record_security_event("origin_denied", client_key=client_key(request))
        raise HTTPException(
            status_code=403,
            detail={"code": "origin_denied", "message": "请求来源校验失败。"},
        )


def optional_principal(request: Request) -> AuthPrincipal | None:
    service = get_auth_service(request)
    return service.authenticate(request.cookies.get(SESSION_COOKIE))


def require_user(request: Request) -> AuthPrincipal:
    service = get_auth_service(request)
    principal = service.authenticate(request.cookies.get(SESSION_COOKIE))
    if principal is None:
        service.record_security_event("authentication_required", client_key=client_key(request))
        raise HTTPException(
            status_code=401,
            detail={"code": "authentication_required", "message": "请先登录。"},
        )
    return principal


def require_admin(request: Request) -> AuthPrincipal:
    principal = require_user(request)
    if principal.role != "admin":
        get_auth_service(request).record_security_event(
            "admin_access_denied",
            principal=principal,
            client_key=client_key(request),
        )
        raise HTTPException(
            status_code=403,
            detail={"code": "admin_required", "message": "仅管理员可访问该后台资源。"},
        )
    return principal


def enforce_csrf(
    request: Request,
    principal: AuthPrincipal,
    service: AuthService,
    csrf_token: str | None,
) -> None:
    enforce_origin(request, service)
    try:
        service.require_csrf(principal, csrf_token)
    except AuthError as error:
        service.record_security_event(
            "csrf_denied",
            principal=principal,
            client_key=client_key(request),
        )
        _raise_auth(error)


def enforce_session_context(
    request: Request,
    principal: AuthPrincipal,
    expected_user_id: int | None,
    expected_generation: str | None,
) -> None:
    generation_matches = (
        bool(expected_generation)
        and len(expected_generation) <= 128
        and hmac.compare_digest(principal.session_generation, expected_generation)
    )
    if expected_user_id == principal.id and generation_matches:
        return
    get_auth_service(request).record_security_event(
        "session_context_mismatch",
        principal=principal,
        detail="watchlist_precondition",
        client_key=client_key(request),
    )
    raise HTTPException(
        status_code=409,
        detail={
            "code": "session_context_changed",
            "message": "登录账号已变化，请刷新账户状态后重试。",
        },
    )


def _no_store(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


def _session_response(result: dict[str, object], service: AuthService, status_code: int) -> JSONResponse:
    token = str(result.pop("session_token"))
    csrf = str(result.pop("csrf_token"))
    response = JSONResponse(result, status_code=status_code)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=8 * 60 * 60,
        path="/",
        secure=service.runtime.secure_cookie,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=8 * 60 * 60,
        path="/",
        secure=service.runtime.secure_cookie,
        httponly=False,
        samesite="lax",
    )
    return _no_store(response)  # type: ignore[return-value]


def _watchlist_with_market(items: list[dict[str, object]]) -> list[dict[str, object]]:
    market = market_overview_payload(RESEARCH_BOUNDARY)
    stock_map = {
        str(stock.get("symbol", "")).upper(): stock
        for stock in market.get("stocks", [])
        if stock.get("symbol")
    }
    return [
        {
            **item,
            "stock": stock_map.get(str(item["symbol"]).upper()),
        }
        for item in items
    ]


@router.get("/api/auth/status")
def auth_status(request: Request) -> Response:
    service = get_auth_service(request)
    principal = service.authenticate(request.cookies.get(SESSION_COOKIE))
    payload: dict[str, object] = {
        "setup_required": service.setup_required(),
        "registration_open": service.runtime.registration_open,
        "authenticated": principal is not None,
    }
    if principal:
        payload["user"] = principal.public_user()
        payload["expires_at"] = principal.expires_at
        payload["session_generation"] = principal.session_generation
    return _no_store(JSONResponse(payload))


@router.post("/api/auth/register", status_code=201)
def register_user(body: RegisterBody, request: Request) -> Response:
    service = get_auth_service(request)
    enforce_origin(request, service)
    try:
        result = service.register(
            body.username,
            body.display_name,
            body.password,
            body.password_confirm,
            client_key=client_key(request),
        )
    except AuthError as error:
        _raise_auth(error)
    return _session_response(result, service, 201)


@router.post("/api/auth/setup-admin", status_code=201)
def setup_admin(body: AdminSetupBody, request: Request) -> Response:
    service = get_auth_service(request)
    enforce_origin(request, service)
    try:
        result = service.setup_admin(
            body.bootstrap_token,
            body.username,
            body.display_name,
            body.password,
            body.password_confirm,
            client_key=client_key(request),
        )
    except AuthError as error:
        _raise_auth(error)
    return _session_response(result, service, 201)


@router.post("/api/auth/login")
def login(body: LoginBody, request: Request) -> Response:
    service = get_auth_service(request)
    enforce_origin(request, service)
    try:
        result = service.login(
            body.username,
            body.password,
            client_key=client_key(request),
        )
    except AuthError as error:
        _raise_auth(error)
    return _session_response(result, service, 200)


@router.get("/api/auth/session")
def session(request: Request, principal: Annotated[AuthPrincipal, Depends(require_user)]) -> Response:
    return _no_store(
        JSONResponse({
            "authenticated": True,
            "user": principal.public_user(),
            "expires_at": principal.expires_at,
            "session_generation": principal.session_generation,
        })
    )


@router.post("/api/auth/logout", status_code=204)
def logout(
    request: Request,
    principal: Annotated[AuthPrincipal, Depends(require_user)],
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> Response:
    service = get_auth_service(request)
    enforce_csrf(request, principal, service, x_csrf_token)
    service.logout(principal, client_key=client_key(request))
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return _no_store(response)


@router.get("/api/watchlist")
def get_watchlist(
    principal: Annotated[AuthPrincipal, Depends(require_user)],
    request: Request,
    x_expected_user_id: Annotated[int | None, Header()] = None,
    x_expected_session_generation: Annotated[str | None, Header()] = None,
) -> Response:
    service = get_auth_service(request)
    enforce_session_context(
        request,
        principal,
        x_expected_user_id,
        x_expected_session_generation,
    )
    items = _watchlist_with_market(service.list_watchlist(principal.id))
    return _no_store(JSONResponse({
        "items": items,
        "count": len(items),
        "owner_user_id": principal.id,
        "session_generation": principal.session_generation,
    }))


@router.post("/api/watchlist", status_code=201)
def add_watchlist(
    body: WatchlistBody,
    request: Request,
    principal: Annotated[AuthPrincipal, Depends(require_user)],
    x_csrf_token: Annotated[str | None, Header()] = None,
    x_expected_user_id: Annotated[int | None, Header()] = None,
    x_expected_session_generation: Annotated[str | None, Header()] = None,
) -> Response:
    service = get_auth_service(request)
    enforce_csrf(request, principal, service, x_csrf_token)
    enforce_session_context(
        request,
        principal,
        x_expected_user_id,
        x_expected_session_generation,
    )
    try:
        item = service.add_watchlist(principal.id, body.symbol)
    except AuthError as error:
        _raise_auth(error)
    return _no_store(JSONResponse(_watchlist_with_market([item])[0], status_code=201))


@router.delete("/api/watchlist/{symbol}", status_code=204)
def delete_watchlist(
    symbol: str,
    request: Request,
    principal: Annotated[AuthPrincipal, Depends(require_user)],
    x_csrf_token: Annotated[str | None, Header()] = None,
    x_expected_user_id: Annotated[int | None, Header()] = None,
    x_expected_session_generation: Annotated[str | None, Header()] = None,
) -> Response:
    service = get_auth_service(request)
    enforce_csrf(request, principal, service, x_csrf_token)
    enforce_session_context(
        request,
        principal,
        x_expected_user_id,
        x_expected_session_generation,
    )
    try:
        removed = service.remove_watchlist(principal.id, symbol)
    except AuthError as error:
        _raise_auth(error)
    if not removed:
        raise HTTPException(
            status_code=404,
            detail={"code": "watchlist_item_not_found", "message": "该股票不在当前账号的自选列表中。"},
        )
    return _no_store(Response(status_code=204))


@router.get("/api/admin/users")
def admin_users(
    request: Request,
    _: Annotated[AuthPrincipal, Depends(require_admin)],
) -> Response:
    service = get_auth_service(request)
    users = service.list_users()
    return _no_store(JSONResponse({"users": users, "count": len(users)}))


@router.patch("/api/admin/users/{user_id}")
def update_user_status(
    user_id: int,
    body: UserStatusBody,
    request: Request,
    principal: Annotated[AuthPrincipal, Depends(require_admin)],
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> Response:
    service = get_auth_service(request)
    enforce_csrf(request, principal, service, x_csrf_token)
    try:
        user = service.set_user_active(
            principal,
            user_id,
            body.is_active,
            client_key=client_key(request),
        )
    except AuthError as error:
        _raise_auth(error)
    return _no_store(JSONResponse(user))


@router.get("/api/admin/audit")
def admin_audit(
    request: Request,
    _: Annotated[AuthPrincipal, Depends(require_admin)],
    limit: int = 100,
) -> Response:
    service = get_auth_service(request)
    events = service.recent_audit(limit)
    return _no_store(JSONResponse({"events": events, "count": len(events)}))


@router.get("/api/admin/security-summary")
def admin_security_summary(
    request: Request,
    _: Annotated[AuthPrincipal, Depends(require_admin)],
) -> Response:
    service = get_auth_service(request)
    return _no_store(JSONResponse(service.auth_summary()))
