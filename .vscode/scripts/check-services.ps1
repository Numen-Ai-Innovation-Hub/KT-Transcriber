# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# check-services.ps1 - Verifica estado da stack (nao-interativo, para Claude Code)
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Verifica FastAPI (HTTP) e existencia dos logs de servico.
# Redis Cloud e verificado indiretamente via ARQ Worker (se worker subiu, Redis esta ok).
# Sem Read-Host, sem janelas, sem Windows Terminal — invocavel pelo Claude Code.
# Retorna exit 0 se stack OK, exit 1 se algum servico indisponivel.
#
# USO pelo Claude Code (via Bash):
#   powershell -ExecutionPolicy Bypass -File ".vscode/scripts/check-services.ps1"
#
# USO humano (verificar apos start-services.ps1):
#   .\.vscode\scripts\check-services.ps1
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

param(
    [string]$RepoPath,
    [int]$FastApiPort = 8000
)

$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "SilentlyContinue"

if (-not $RepoPath) {
    $RepoPath = (Resolve-Path "$PSScriptRoot\..\..").Path
}

$allOk = $true

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# 1. .env
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

$EnvFile = Join-Path $RepoPath ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Output "ENV: ERRO - .env nao encontrado em $RepoPath"
    $allOk = $false
} else {
    Write-Output "ENV: OK - .env encontrado"
}

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# 2. FastAPI (HTTP health check)
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

$fastapiOk = $false
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:$FastApiPort/v1/health" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
    if ($resp.StatusCode -eq 200) {
        $fastapiOk = $true
    }
} catch {
    $fastapiOk = $false
}

if ($fastapiOk) {
    Write-Output "FASTAPI: OK - respondendo em http://localhost:$FastApiPort"
} else {
    Write-Output "FASTAPI: ERRO - nao responde em http://localhost:$FastApiPort/v1/health"
    $allOk = $false
}

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# 3. Logs de servico
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

$logFastApi = Join-Path $RepoPath "logs/fastapi.log"
$logArq     = Join-Path $RepoPath "logs/arq.log"

if (Test-Path $logFastApi) {
    $lines = (Get-Content $logFastApi -ErrorAction SilentlyContinue).Count
    Write-Output "LOG_FASTAPI: OK - $lines linhas em logs/fastapi.log"
} else {
    Write-Output "LOG_FASTAPI: AVISO - logs/fastapi.log nao existe (start-services.ps1 ainda nao foi executado?)"
}

if (Test-Path $logArq) {
    $lines = (Get-Content $logArq -ErrorAction SilentlyContinue).Count
    Write-Output "LOG_ARQ: OK - $lines linhas em logs/arq.log"
} else {
    Write-Output "LOG_ARQ: AVISO - logs/arq.log nao existe (start-services.ps1 ainda nao foi executado?)"
}

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# 4. Resultado
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

Write-Output ""
if ($allOk) {
    Write-Output "RESULTADO: OK - stack disponivel para testes smoke e e2e"
    exit 0
} else {
    Write-Output "RESULTADO: ERRO - servico(s) indisponivel(is) — execute start-services.ps1 no terminal"
    exit 1
}