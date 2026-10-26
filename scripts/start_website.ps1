[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$FrontendPort = 3000,
    [ValidateRange(1, 65535)]
    [int]$BackendPort = 8000,
    [switch]$SkipStartupUpdate,
    [switch]$FetchNews,
    [switch]$InstallDailyTask,
    [switch]$Dev,
    [switch]$OpenBrowser
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $projectRoot 'frontend'
$pythonExecutable = Join-Path $projectRoot '.venv\Scripts\python.exe'
$nodeExecutable = (Get-Command -Name 'node.exe' -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$nextEntrypoint = Join-Path $frontendRoot 'node_modules\next\dist\bin\next'
$dailyUpdateRunner = Join-Path $PSScriptRoot 'run_daily_data_update.ps1'
$taskInstaller = Join-Path $PSScriptRoot 'install_daily_update_task.ps1'
$runtimeLogDirectory = Join-Path $projectRoot 'reports\runtime\website'

foreach ($requiredPath in @($pythonExecutable, $nodeExecutable, $nextEntrypoint, $dailyUpdateRunner, $taskInstaller)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required website runtime file was not found: $requiredPath"
    }
}

New-Item -ItemType Directory -Force -Path $runtimeLogDirectory | Out-Null

function Test-TcpPort {
    param(
        [Parameter(Mandatory)]
        [string]$HostName,
        [Parameter(Mandatory)]
        [int]$Port,
        [int]$TimeoutMilliseconds = 500
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.ConnectAsync($HostName, $Port)
        if (-not $connect.Wait($TimeoutMilliseconds)) {
            return $false
        }
        return $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Wait-HttpReady {
    param(
        [Parameter(Mandatory)]
        [string]$Url,
        [ValidateRange(1, 120)]
        [int]$Attempts = 60
    )

    Add-Type -AssemblyName System.Net.Http
    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.UseProxy = $false
    $client = [System.Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromSeconds(3)
    $lastFailure = 'No successful response'
    try {
        for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
            try {
                $response = $client.GetAsync($Url).GetAwaiter().GetResult()
                try {
                    $statusCode = [int]$response.StatusCode
                    if ($statusCode -ge 200 -and $statusCode -lt 300) {
                        return
                    }
                    $lastFailure = "HTTP $statusCode"
                }
                finally {
                    $response.Dispose()
                }
            }
            catch {
                $lastFailure = $_.Exception.Message
            }
            if ($attempt -lt $Attempts) { Start-Sleep -Milliseconds 500 }
        }
        throw "Website endpoint did not become ready: $Url ($lastFailure)"
    }
    finally {
        $client.Dispose()
    }
}

$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$startedProcesses = @()
$startupUpdateStatus = 'skipped'
$startupUpdateExitCode = $null

# Complete the freshness gate before either service is exposed.  The daily
# runner performs an incremental overlap fetch and turns into a no-op when the
# local watermark and all derived checkpoints already match the latest
# completed China A-share trading day.
if (-not $SkipStartupUpdate) {
    $startupUpdateArguments = @(
        '-NoProfile',
        '-ExecutionPolicy', 'RemoteSigned',
        '-File', "`"$dailyUpdateRunner`"",
        '-RetryCount', '1'
    )
    if ($FetchNews) {
        $startupUpdateArguments += '-FetchNews'
    }

    $startupUpdateProcess = Start-Process `
        -FilePath 'powershell.exe' `
        -ArgumentList $startupUpdateArguments `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -Wait `
        -PassThru
    $startupUpdateExitCode = $startupUpdateProcess.ExitCode
    if ($startupUpdateExitCode -ne 0) {
        throw "Startup data freshness check or incremental refresh failed with exit code $startupUpdateExitCode. See reports\daily_update\logs; use -SkipStartupUpdate only for explicit offline debugging."
    }
    $startupUpdateStatus = 'completed_before_service_start'
}

if (-not (Test-TcpPort -HostName '127.0.0.1' -Port $BackendPort)) {
    $backendProcess = Start-Process `
        -FilePath $pythonExecutable `
        -ArgumentList @(
            '-m', 'uvicorn', 'backend.app.main:app',
            '--host', '127.0.0.1',
            '--port', [string]$BackendPort
        ) `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $runtimeLogDirectory "backend_${timestamp}.stdout.log") `
        -RedirectStandardError (Join-Path $runtimeLogDirectory "backend_${timestamp}.stderr.log") `
        -PassThru
    $startedProcesses += [pscustomobject]@{ Service = 'backend'; ProcessId = $backendProcess.Id }
}

if (-not (Test-TcpPort -HostName '127.0.0.1' -Port $FrontendPort)) {
    $previousBackendOrigin = $env:BACKEND_INTERNAL_ORIGIN
    $previousHostname = $env:HOSTNAME
    $previousPort = $env:PORT
    try {
        $env:BACKEND_INTERNAL_ORIGIN = "http://127.0.0.1:${BackendPort}"
        $env:HOSTNAME = '0.0.0.0'
        $env:PORT = [string]$FrontendPort
        if ($Dev) {
            $frontendArguments = @("`"$nextEntrypoint`"", 'dev', '-H', '0.0.0.0', '-p', [string]$FrontendPort)
        }
        else {
            Push-Location $frontendRoot
            try {
                & $nodeExecutable (Join-Path $frontendRoot 'scripts\validate_routes.mjs')
                if ($LASTEXITCODE -ne 0) { throw 'Frontend route validation failed.' }
                & $nodeExecutable $nextEntrypoint build
                if ($LASTEXITCODE -ne 0) { throw 'Frontend production build failed. See the build output above.' }
            }
            finally { Pop-Location }
            $frontendArguments = @("`"$(Join-Path $frontendRoot 'scripts\start_standalone.mjs')`"")
        }
        $frontendProcess = Start-Process `
            -FilePath $nodeExecutable `
            -ArgumentList $frontendArguments `
            -WorkingDirectory $frontendRoot `
            -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $runtimeLogDirectory "frontend_${timestamp}.stdout.log") `
            -RedirectStandardError (Join-Path $runtimeLogDirectory "frontend_${timestamp}.stderr.log") `
            -PassThru
        $startedProcesses += [pscustomobject]@{ Service = 'frontend'; ProcessId = $frontendProcess.Id }
    }
    finally {
        $env:BACKEND_INTERNAL_ORIGIN = $previousBackendOrigin
        $env:HOSTNAME = $previousHostname
        $env:PORT = $previousPort
    }
}

Wait-HttpReady -Url "http://127.0.0.1:${BackendPort}/health"
Wait-HttpReady -Url "http://127.0.0.1:${FrontendPort}/"

if ($InstallDailyTask) {
    & $taskInstaller
}

$result = [ordered]@{
    status = 'ok'
    website_url = "http://127.0.0.1:${FrontendPort}/"
    backend_health_url = "http://127.0.0.1:${BackendPort}/health"
    services_started = $startedProcesses
    requested_frontend_mode = $(if ($Dev) { 'development' } else { 'production' })
    startup_incremental_update = $startupUpdateStatus
    startup_update_exit_code = $startupUpdateExitCode
    startup_news_refresh_requested = [bool]$FetchNews
    daily_task_install_requested = [bool]$InstallDailyTask
    runtime_log_directory = $runtimeLogDirectory
}
$result | ConvertTo-Json -Depth 4

if ($OpenBrowser) {
    Start-Process "http://127.0.0.1:${FrontendPort}/"
}
