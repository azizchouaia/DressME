<#
.SYNOPSIS
  TEMPORARY: runs M1 in real mode WITHOUT Docker, on an embedded PostgreSQL + pgvector (pgserver).

.DESCRIPTION
  Use run_real.ps1 (Docker, infra/docker-compose.yml) as soon as Docker Desktop is installed.

  1. Creates a small venv (Python 3.12 or 3.11) in m01_wardrobe/.pgdev with `pgserver`
     (PostgreSQL 16 + pgvector, no admin rights needed). Done once.
  2. Starts the database; its data lives in m01_wardrobe/data/pgdata (git-ignored, kept between runs).
  3. Sets DATABASE_URL to it and M01_USE_MOCKS=false (only M1 goes real).
  4. Starts uvicorn (or runs the tests with -Test). The database is stopped when you quit (Ctrl+C).

.EXAMPLE
  .\backend\modules\m01_wardrobe\scripts\run_real_local.ps1                # http://localhost:8000/m01/ui
  .\backend\modules\m01_wardrobe\scripts\run_real_local.ps1 -Test          # pgvector + real-model tests
  .\backend\modules\m01_wardrobe\scripts\run_real_local.ps1 -Stop          # stop a database left running
  .\backend\modules\m01_wardrobe\scripts\run_real_local.ps1 -Reset         # delete the local database
#>
param(
    [int]$Port = 8000,
    [string]$Device = "cpu",
    [switch]$InstallDeps,
    [switch]$Test,
    [switch]$Stop,
    [switch]$Reset
)
# Native tools (py, pip, docker) write progress to stderr: with "Stop", Windows PowerShell 5.1 would
# turn that into fatal errors. Every native call is checked through $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"

$module = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backend = (Resolve-Path (Join-Path $module "..\..")).Path
$venv = Join-Path $module ".pgdev\venv"
$venvPy = Join-Path $venv "Scripts\python.exe"
$pgdata = Join-Path $module "data\pgdata"
$pgDev = Join-Path $PSScriptRoot "pg_dev.py"

function Invoke-PgDev([string]$action) {
    $out = & $venvPy $pgDev $action $pgdata
    if ($LASTEXITCODE -ne 0) { throw "pg_dev.py $action a echoue (log : $pgdata\log)." }
    return ($out | Select-Object -Last 1)
}

if ($Stop -or $Reset) {
    if (Test-Path $venvPy) { Invoke-PgDev "stop" | Out-Null; Write-Host "Base locale arretee." -ForegroundColor Green }
    if ($Reset -and (Test-Path $pgdata)) { Remove-Item -Recurse -Force $pgdata; Write-Host "Base locale supprimee." -ForegroundColor Yellow }
    return
}

# 1. venv with pgserver (once)
if (-not (Test-Path $venvPy)) {
    $pyVersion = $null
    foreach ($v in "3.12", "3.11", "3.10") {
        & py "-$v" -c "import sys" 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { $pyVersion = $v; break }
    }
    if (-not $pyVersion) { throw "pgserver demande Python 3.10-3.12 (introuvable via 'py'). Installe Python 3.12 ou utilise Docker." }
    Write-Host "Creation du venv pgserver (Python $pyVersion)..." -ForegroundColor Cyan
    & py "-$pyVersion" -m venv $venv
    & $venvPy -m pip install -q --disable-pip-version-check pgserver
    if ($LASTEXITCODE -ne 0) { throw "pip install pgserver a echoue." }
}

if ($InstallDeps) {
    python -m pip install -r (Join-Path $module "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "pip install a echoue." }
}

# 2. database
Write-Host "Demarrage de PostgreSQL + pgvector (embarque)..." -ForegroundColor Cyan
$uri = Invoke-PgDev "start"
if ($uri -notmatch "^postgresql://") { throw "URI inattendue : $uri" }
$env:DATABASE_URL = $uri -replace "^postgresql://", "postgresql+asyncpg://"
Write-Host "PostgreSQL pret : $($env:DATABASE_URL)" -ForegroundColor Green

# 3. M1 real mode only
$env:M01_USE_MOCKS = "false"
$env:M01_DEVICE = $Device

Push-Location $backend
try {
    if ($Test) {
        $env:M01_TEST_DATABASE_URL = $env:DATABASE_URL
        $env:M01_RUN_SLOW = "1"
        python -m pytest modules/m01_wardrobe -q
    } else {
        Write-Host "M1 en mode reel -> http://localhost:$Port/m01/ui  (1er ajout ~15 s : chargement des modeles)" -ForegroundColor Green
        Write-Host "Ctrl+C pour arreter (la base locale est arretee aussi, les donnees sont conservees)." -ForegroundColor DarkGray
        python -m uvicorn api.main:app --reload --port $Port
    }
} finally {
    Pop-Location
    Invoke-PgDev "stop" | Out-Null
    Write-Host "Base locale arretee." -ForegroundColor DarkGray
}
