[CmdletBinding()]
param(
    [ValidateNotNullOrEmpty()]
    [string]$TaskName = 'StockGoodDailyData',
    [ValidatePattern('^(?:[01]\d|2[0-3]):[0-5]\d$')]
    [string]$At = '16:40',
    [ValidateRange(1, 10)]
    [int]$RetryCount = 3,
    [ValidateRange(1, 86400)]
    [int]$RetryDelaySeconds = 1800,
    [switch]$RunNow
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $PSScriptRoot 'run_daily_data_update.ps1'

if (-not (Test-Path -LiteralPath $runner)) {
    throw "Daily update runner was not found: $runner"
}

$taskCommand = @(
    'powershell.exe',
    '-NoProfile',
    '-ExecutionPolicy', 'RemoteSigned',
    '-File', "`"$runner`"",
    '-RetryCount', [string]$RetryCount,
    '-RetryDelaySeconds', [string]$RetryDelaySeconds
) -join ' '

$createArguments = @(
    '/Create',
    '/TN', $TaskName,
    '/SC', 'WEEKLY',
    '/D', 'MON,TUE,WED,THU,FRI',
    '/ST', $At,
    '/TR', $taskCommand,
    '/F'
)
& schtasks.exe @createArguments
if ($LASTEXITCODE -ne 0) {
    throw "Unable to create scheduled task '$TaskName' (exit code $LASTEXITCODE)."
}

if ($RunNow) {
    $runArguments = @('/Run', '/TN', $TaskName)
    & schtasks.exe @runArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Scheduled task '$TaskName' was created but could not be started."
    }
}

[ordered]@{
    status = 'ok'
    task_name = $TaskName
    schedule = "MON-FRI $At"
    command = $taskCommand
    project_root = $projectRoot
    run_now = [bool]$RunNow
} | ConvertTo-Json -Depth 3
