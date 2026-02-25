# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# ensure-playwright.ps1 - Garante Chromium instalado para Playwright
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

param(
    [string]$RepoPath
)

$ErrorActionPreference = "Stop"

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Carregar funcoes compartilhadas
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

. "$PSScriptRoot\common.ps1"

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Configuracao
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

$PREFIX = "ensure-playwright"
$venv = Get-VenvPaths -RepoPath $RepoPath

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Execucao
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

try {
    Write-Host "Etapa 6: Configuracao Playwright - Chromium" -ForegroundColor Cyan
    Write-Host ""

    # Verificar ambiente virtual
    if (-not (Test-VenvExists -RepoPath $RepoPath)) {
        Write-Failure -Prefix $PREFIX -Message "Ambiente virtual nao encontrado em $($venv.VenvPath)"
        exit 1
    }

    # Verificar se Playwright esta instalado
    $playwrightCheck = & $venv.VenvPython -c "import importlib.util; print('OK' if importlib.util.find_spec('playwright') else 'NO')" 2>$null
    if ($LASTEXITCODE -ne 0 -or $playwrightCheck -notmatch "OK") {
        Write-Skip -Prefix $PREFIX -Message "Playwright nao esta instalado no ambiente virtual"
        Write-Host ""
        exit 0
    }

    # Verificar se Chromium esta instalado
    $chromiumCheck = & $venv.VenvPython -c "import os; from playwright.sync_api import sync_playwright; p = sync_playwright().start(); path = p.chromium.executable_path; print('OK' if path and os.path.exists(path) else 'NO'); p.stop()" 2>$null
    if ($LASTEXITCODE -eq 0 -and $chromiumCheck -match "OK") {
        Write-Skip -Prefix $PREFIX -Message "Chromium ja esta instalado"
        Write-Host ""
        exit 0
    }

    # Instalar Chromium
    Write-Step -Prefix $PREFIX -Message "Instalando Chromium para Playwright"
    & $venv.VenvPython -m playwright install chromium
    if ($LASTEXITCODE -ne 0) {
        Write-Failure -Prefix $PREFIX -Message "Falha ao instalar Chromium"
        exit $LASTEXITCODE
    }
    Write-Success -Prefix $PREFIX -Message "Chromium instalado"

    Write-Host ""
    exit 0
}
catch {
    Write-Failure -Prefix $PREFIX -Message $_.Exception.Message
    exit 1
}