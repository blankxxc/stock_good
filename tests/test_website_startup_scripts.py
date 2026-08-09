from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_website_launcher_completes_incremental_update_before_starting_services() -> None:
    script = (ROOT / "scripts" / "start_website.ps1").read_text(encoding="utf-8")

    assert "backend.app.main:app" in script
    assert "node_modules\\next\\dist\\bin\\next" in script
    assert "Get-Command -Name 'node.exe'" in script
    assert "Wait-HttpReady" in script
    assert "$handler.UseProxy = $false" in script
    assert "$client.GetAsync($Url)" in script
    assert "Invoke-WebRequest" not in script
    assert "run_daily_data_update.ps1" in script
    assert "completed_before_service_start" in script
    assert "[switch]$SkipStartupUpdate" in script
    assert "[switch]$FetchNews" in script
    assert "-WindowStyle Hidden" in script
    assert "-Wait" in script
    assert script.index("$startupUpdateProcess = Start-Process") < script.index("backend.app.main:app")
    assert "Startup data freshness check or incremental refresh failed" in script


def test_daily_task_installer_is_idempotent_and_uses_full_pipeline() -> None:
    script = (ROOT / "scripts" / "install_daily_update_task.ps1").read_text(encoding="utf-8")

    assert "StockGoodDailyData" in script
    assert "run_daily_data_update.ps1" in script
    assert "MON,TUE,WED,THU,FRI" in script
    assert "[string]$At = '16:40'" in script
    assert "'/F'" in script
    assert "fetch_real_csi300_daily.py" not in script


def test_daily_update_runner_does_not_treat_python_warnings_as_failures() -> None:
    script = (ROOT / "scripts" / "run_daily_data_update.ps1").read_text(encoding="utf-8")

    assert "$previousErrorActionPreference = $ErrorActionPreference" in script
    assert "$ErrorActionPreference = 'Continue'" in script
    assert "$exitCode = $LASTEXITCODE" in script
    assert "$ErrorActionPreference = $previousErrorActionPreference" in script
