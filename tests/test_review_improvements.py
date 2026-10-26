from pathlib import Path
import shutil
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not shutil.which("powershell.exe"), reason="Windows launcher")
@pytest.mark.parametrize("status", [200, 404, 503])
def test_readiness_requires_success_and_fails_after_retries(tmp_path, status):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    source = (ROOT / "scripts/start_website.ps1").read_text(encoding="utf-8")
    function = source[source.index("function Wait-HttpReady {"):source.index("$timestamp = Get-Date")]
    script = tmp_path / "readiness.ps1"
    script.write_text("$ErrorActionPreference = 'Stop'\n" + function
                      + f"\nWait-HttpReady -Url 'http://127.0.0.1:{server.server_port}/' -Attempts 1\n",
                      encoding="utf-8-sig")
    try:
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(script)],
                                capture_output=True, text=True, timeout=15)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    assert (result.returncode == 0) is (status == 200)
    if status != 200:
        assert f"HTTP {status}" in result.stderr


def test_stock_detail_filters_parquet_and_reports_price_basis(tmp_path, monkeypatch):
    from backend.app.services import research_loop_catalog as catalog

    path = tmp_path / "data/real/csi300_daily/part-000.parquet"
    path.parent.mkdir(parents=True)
    daily = pd.DataFrame({
        "symbol": ["600519.SH", "000001.SZ"], "stock_name": ["贵州茅台", "平安银行"],
        "trade_date": ["2026-10-16"] * 2, "close": [2000.0, 1468.123212],
        "turnover_rate": [0.1, 0.57], "adjustment_mode": ["hfq"] * 2,
    })
    daily.to_parquet(path, index=False)
    monkeypatch.setattr(catalog, "project_root", lambda: tmp_path)
    original = pd.read_parquet
    reads = []

    def read(source, **kwargs):
        if Path(source) == path:
            reads.append(kwargs)
        return original(source, **kwargs)

    monkeypatch.setattr(catalog.pd, "read_parquet", read)
    payload = catalog.stock_detail_payload("600519-sh", "test")
    assert reads == [{"filters": [("symbol", "=", "600519.SH")]}]
    assert payload["symbol"] == "600519.SH"
    assert len(payload["price_series"]) == 1
    assert payload["price_basis"]["mode"] == "hfq"
    assert payload["price_basis"]["label"] == "后复权收盘价"
    assert "不是当日实际成交报价" in payload["price_basis"]["description"]
    assert catalog.stock_detail_payload("999999.SH", "test")["status"] == "stock_detail_not_found"


def test_missing_daily_data_returns_not_found(tmp_path, monkeypatch):
    from backend.app.services import research_loop_catalog as catalog

    monkeypatch.setattr(catalog, "project_root", lambda: tmp_path)
    assert catalog.stock_detail_payload("600519.SH", "test")["status"] == "stock_detail_not_found"
