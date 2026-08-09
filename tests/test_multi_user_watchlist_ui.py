from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = PROJECT_ROOT / "frontend" / "src"


def read(relative: str) -> str:
    return (FRONTEND / relative).read_text(encoding="utf-8")


def test_multi_user_login_watchlist_and_session_navigation_are_real_api_backed() -> None:
    login_page = read("app/login/page.tsx")
    login_panel = read("components/LoginPanel.tsx")
    layout = read("app/layout.tsx")
    application_shell = read("components/ApplicationShell.tsx")
    auth_nav = read("components/AuthNav.tsx")
    watchlist_page = read("app/watchlist/page.tsx")
    watchlist_board = read("components/WatchlistBoard.tsx")
    market = read("components/MarketOverviewBoard.tsx")
    auth_lib = read("lib/auth.ts")
    combined = "\n".join([login_page, login_panel, layout, application_shell, auth_nav, watchlist_page, watchlist_board, market, auth_lib])

    assert "LoginPanel" in login_page
    assert "/api/auth/login" in login_panel
    assert "/api/auth/register" in login_panel
    assert "/api/auth/setup-admin" in login_panel
    assert "普通用户与管理员使用同一安全入口" in login_panel
    assert "ApplicationShell" in layout
    assert "AuthNav" in application_shell and "我的自选" in application_shell
    assert "isAdminRoute" in application_shell and "admin-application-shell" in application_shell
    assert "getSessionStatus" in auth_nav
    assert "/api/auth/logout" in auth_nav
    assert "WatchlistBoard" in watchlist_page
    assert "/api/watchlist" in watchlist_board
    assert "X-CSRF-Token" in watchlist_board
    assert "toggleFavorite" in market and "/api/watchlist" in market
    assert "localStorage" not in combined
    assert "sessionStorage" not in combined
    assert "password" not in auth_lib.lower()


def test_auth_status_requests_and_role_aware_return_paths_are_reliable() -> None:
    login_panel = read("components/LoginPanel.tsx")
    auth_nav = read("components/AuthNav.tsx")
    watchlist_board = read("components/WatchlistBoard.tsx")
    market = read("components/MarketOverviewBoard.tsx")
    auth_lib = read("lib/auth.ts")
    combined = "\n".join([login_panel, auth_nav, watchlist_board, market, auth_lib])

    # Layout-level clients share one in-flight status lookup instead of issuing
    # duplicate requests on the login, home, and watchlist routes.
    assert "getSessionStatus" in auth_lib
    assert combined.count("fetch('/api/auth/status'") == 1
    assert all("getSessionStatus" in source for source in (login_panel, auth_nav, watchlist_board, market))
    assert "request.then(releaseRequest, releaseRequest)" in auth_lib
    assert "SESSION_INVALIDATED_EVENT" in auth_lib
    assert "BroadcastChannel" in auth_lib
    assert "sourceTabId" in auth_lib
    assert "SessionInvalidationReason" in auth_lib
    assert "authorization-failed" in auth_lib
    assert "seenSessionEvents" in auth_lib
    assert all(
        "subscribeSessionInvalidation" in source
        for source in (login_panel, auth_nav, watchlist_board, market)
    )

    # A normal user must never be returned to the administrator-only rewrite.
    assert "allowBackendAdmin" in auth_lib
    assert "result.user.role === 'admin'" in login_panel
    assert "invalidateSessionStatus" in login_panel

    # Status and mutation failures stay distinguishable and recoverable.
    assert "重试" in login_panel and "重试" in auth_nav
    assert "response.status === 401" in watchlist_board
    assert "response.status === 401" in market
    assert watchlist_board.count("setItems([])") >= 3
    assert watchlist_board.count("requestSequence.current !== sequence") >= 3
    assert market.count("favoritesRequestSequence.current !== sequence") >= 3
    assert "favoritesLoading" in market
    assert "favoritesOwnerId" in market
    assert "favoritesSessionGeneration" in market
    assert "favoritesCsrfToken" in market
    assert "csrfToken" in auth_lib
    assert "X-Expected-Session-Generation" in combined
    assert "X-Expected-User-Id" in combined
    assert "readCsrfToken() !== context.csrfToken" in watchlist_board
    assert "readCsrfToken() !== context.csrfToken" in market
    assert all("shouldReloadPrivateSession(message)" in source for source in (watchlist_board, market))
    assert "if (sessionStatusRequest) return sessionStatusRequest" in auth_lib
    assert "authenticated === null || favoritesLoading || watchlistError" in market
    assert "Boolean(watchlistError)" in market
    assert "responseError(response)" in auth_nav
    assert "actionSequence" in login_panel
    assert "actionSequence" in auth_nav
    assert "mounted" in login_panel
    assert "mounted" in auth_nav


def test_auth_and_watchlist_controls_expose_accessible_busy_and_scroll_contracts() -> None:
    login_panel = read("components/LoginPanel.tsx")
    auth_nav = read("components/AuthNav.tsx")
    watchlist_board = read("components/WatchlistBoard.tsx")
    market = read("components/MarketOverviewBoard.tsx")
    layout = read("app/layout.tsx")
    application_shell = read("components/ApplicationShell.tsx")
    css = read("app/globals.css")

    assert "ApplicationShell" in layout
    assert 'className="skip-link"' in application_shell
    assert 'aria-label="主导航"' in application_shell
    assert 'id="main-content"' in application_shell
    assert 'id="admin-main-content"' in application_shell
    assert 'tabIndex={-1}' in application_shell

    assert 'role="tab"' in login_panel
    assert "aria-selected" in login_panel
    assert 'role="tabpanel"' in login_panel
    assert "onKeyDown" in login_panel
    assert 'name="username"' in login_panel
    assert 'autoComplete="username"' in login_panel
    assert "两次输入的密码不一致" in login_panel
    assert "registration_open" in login_panel
    assert "aria-busy" in login_panel

    assert 'role="alert"' in auth_nav
    assert "aria-busy" in auth_nav
    assert 'aria-pressed' in market
    assert "aria-busy" in market
    assert 'aria-busy={favoritesLoading || Boolean(pendingSymbol)}' in market
    assert "aria-busy" in watchlist_board
    assert "window.confirm" in watchlist_board

    for table_source in (market, watchlist_board):
        assert "<caption" in table_source
        assert "tabIndex={0}" in table_source
        assert 'scope="col"' in table_source

    assert ".skip-link" in css
    assert ".stock-table-shell:focus-visible" in css
    assert ".watchlist-board {" in css and "min-width: 0" in css
    assert ":focus-visible" in css


def test_backend_admin_is_server_guarded_and_not_only_hidden_by_frontend() -> None:
    main = (PROJECT_ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    router = (PROJECT_ROOT / "backend" / "app" / "routers" / "auth.py").read_text(encoding="utf-8")
    service = (PROJECT_ROOT / "backend" / "app" / "services" / "auth_service.py").read_text(encoding="utf-8")
    next_config = (PROJECT_ROOT / "frontend" / "next.config.js").read_text(encoding="utf-8")
    proxy = (PROJECT_ROOT / "frontend" / "src" / "proxy.ts").read_text(encoding="utf-8")
    package = (PROJECT_ROOT / "frontend" / "package.json").read_text(encoding="utf-8")
    standalone_start = (PROJECT_ROOT / "frontend" / "scripts" / "start_standalone.mjs").read_text(encoding="utf-8")

    assert "Depends(require_admin)" in main
    assert '"/api/admin/users"' in router
    assert '"/api/admin/audit"' in router
    assert '"/api/watchlist"' in router
    assert "principal.id" in router
    assert "UNIQUE(user_id, symbol)" in service
    assert "role TEXT NOT NULL CHECK(role IN ('user', 'admin'))" in service
    assert "hashlib.scrypt" in service
    assert "password.encode()" not in main
    assert "source: '/backend-admin'" not in next_config
    assert "destination: `${apiBase}/admin`" not in next_config
    assert "new URL('/admin-console', publicOrigin)" in proxy
    assert "BACKEND_INTERNAL_ORIGIN" in next_config
    assert "NEXT_PUBLIC_API_BASE_URL" not in next_config
    assert "PUBLIC_SITE_ORIGINS" in proxy
    assert "trustedPublicOrigins.includes(request.nextUrl.origin)" in proxy
    assert "return NextResponse.redirect(redirectUrl, 307)" in proxy
    assert "NEXT_PUBLIC_BACKEND_ADMIN_URL" not in proxy
    assert '"start": "node scripts/start_standalone.mjs"' in package
    assert "path.join(frontendRoot, '.next', 'static')" in standalone_start
    assert "path.join(standaloneRoot, '.next', 'static')" in standalone_start
