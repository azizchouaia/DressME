<#
.SYNOPSIS
  Runs M1 in real mode: PostgreSQL + pgvector (infra/docker-compose.yml), rembg + FashionCLIP, API.

.DESCRIPTION
  1. Checks that Docker Desktop is running.
  2. Creates infra/.env from infra/.env.example if it is missing (local file, ignored by git).
  3. Starts the `postgres` service only (pgvector/pgvector:pg16) and waits until it accepts connections.
  4. Sets M01_USE_MOCKS=false: only M1 goes real, the other modules keep their mocks.
  5. Starts uvicorn (or, with -Test, runs the M1 tests against this database and the real models).

.EXAMPLE
  .\backend\modules\m01_wardrobe\scripts\run_real.ps1                 # API on http://localhost:8000/m01/ui
  .\backend\modules\m01_wardrobe\scripts\run_real.ps1 -InstallDeps    # first time: pip install the M1 deps
  .\backend\modules\m01_wardrobe\scripts\run_real.ps1 -Test           # pgvector + real-model tests
  .\backend\modules\m01_wardrobe\scripts\run_real.ps1 -Device cuda    # FashionCLIP on the GPU
#>
param(
    [int]$Port = 8000,
    [string]$Device = "cpu",
    [switch]$InstallDeps,
    [switch]$Test
)
# Native tools (py, pip, docker) write progress to stderr: with "Stop", Windows PowerShell 5.1 would
# turn that into fatal errors. Every native call is checked through $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")).Path
$infra = Join-Path $root "infra"
$backend = Join-Path $root "backend"
$compose = Join-Path $infra "docker-compose.yml"
$envFile = Join-Path $infra ".env"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker est introuvable. Installe Docker Desktop puis rouvre le terminal."
}
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop n'est pas demarre (lance-le puis attends 'Engine running')." }

if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $infra ".env.example") $envFile
    Write-Host "infra/.env cree depuis .env.example (fichier local, ignore par git)." -ForegroundColor Yellow
}

function Get-EnvValue([string]$name) {
    $line = Select-String -Path $envFile -Pattern "^\s*$name\s*=" | Select-Object -First 1
    if (-not $line) { return $null }
    return ($line.Line -split "=", 2)[1].Split("#")[0].Trim()
}

Write-Host "Demarrage de PostgreSQL + pgvector..." -ForegroundColor Cyan
docker compose -f $compose up -d postgres
if ($LASTEXITCODE -ne 0) { throw "docker compose up a echoue." }

$pgUser = Get-EnvValue "POSTGRES_USER"
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    docker compose -f $compose exec -T postgres pg_isready -U $pgUser *> $null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ready) { throw "PostgreSQL ne repond pas apres 60 s (docker compose -f infra/docker-compose.yml logs postgres)." }
Write-Host "PostgreSQL pret." -ForegroundColor Green

if ($InstallDeps) {
    python -m pip install -r (Join-Path $backend "modules\m01_wardrobe\requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "pip install a echoue." }
}

$env:M01_USE_MOCKS = "false"
$env:M01_DEVICE = $Device

Push-Location $backend
try {
    if ($Test) {
        $env:M01_TEST_DATABASE_URL = Get-EnvValue "DATABASE_URL"
        $env:M01_RUN_SLOW = "1"
        python -m pytest modules/m01_wardrobe -q
    } else {
        Write-Host "M1 en mode reel -> http://localhost:$Port/m01/ui  (1er appel ~15 s : chargement des modeles)" -ForegroundColor Green
        python -m uvicorn api.main:app --reload --port $Port
    }
} finally {
    Pop-Location
}
