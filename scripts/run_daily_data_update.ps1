[CmdletBinding()]
param(
    [switch]$FetchOnly,
    [switch]$FullRefresh,
    [int]$OverlapDays = 7,
    [switch]$FetchNews,
    [ValidateRange(1, 10)]
    [int]$RetryCount = 1,
    [ValidateRange(1, 86400)]
    [int]$RetryDelaySeconds = 1800
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw "Project Python was not found: $pythonExecutable"
}

$entrypoint = if ($FetchOnly) {
    Join-Path $projectRoot 'scripts\fetch_real_csi300_daily.py'
} else {
    Join-Path $projectRoot 'scripts\update_daily_market_data.py'
}

$arguments = @($entrypoint, '--overlap-days', [string]$OverlapDays)
if ($FullRefresh) {
    $arguments += '--full-refresh'
}
if ($FetchNews) {
    $arguments += '--fetch-news'
}

Push-Location $projectRoot
try {
    $logDirectory = Join-Path $projectRoot 'reports\daily_update\logs'
    New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
    $exitCode = 1
    for ($attempt = 1; $attempt -le $RetryCount; $attempt++) {
        $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        $logPath = Join-Path $logDirectory ("daily_update_{0}_attempt{1}.log" -f $timestamp, $attempt)
        # Windows PowerShell converts a native process' stderr lines into error
        # records.  With the script-wide Stop preference, harmless Python
        # warnings would otherwise terminate this wrapper before LASTEXITCODE
        # can be inspected.  The Python process exit code remains authoritative.
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            & $pythonExecutable @arguments 2>&1 | Tee-Object -FilePath $logPath
            $exitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        if ($exitCode -eq 0) {
            break
        }
        if ($attempt -lt $RetryCount) {
            Start-Sleep -Seconds $RetryDelaySeconds
        }
    }
    exit $exitCode
}
finally {
    Pop-Location
}
