# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# ensure-environment.ps1 - Configura ambiente de desenvolvimento completo
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PRE-REQUISITOS (devem estar instalados no sistema):
#   - Windows Terminal - Instale via Microsoft Store
#   - winget (App Installer) - Instale via Microsoft Store
#
# Orquestra a execucao sequencial dos scripts de configuracao:
#   1. lib/ensure-winget.ps1     - Valida winget (pre-requisito)
#   2. lib/ensure-uv.ps1         - uv, PATH, venv, dependencias
#   3. lib/ensure-hooks.ps1      - pre-commit hooks
#   4. lib/ensure-playwright.ps1 - Chromium para Playwright
#   5. lib/ensure-node.ps1       - Node.js/npm para frontend (via winget)
#   6. lib/ensure-wt.ps1         - Valida Windows Terminal (pre-requisito)
#
# NOTA: Redis Cloud e usado (configurado no .env) — nao e necessario instalar Redis localmente
#
# USO:
#   .\.vscode\scripts\ensure-environment.ps1
#   OU automaticamente ao abrir o VSCode (via tasks.json)
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

param(
    [string]$RepoPath
)

$ErrorActionPreference = "Stop"

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Carregar funcoes compartilhadas
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

. "$PSScriptRoot\lib\common.ps1"

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Configuracao
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

$PREFIX = "ensure-environment"

if (-not $RepoPath) {
    $RepoPath = (Resolve-Path "$PSScriptRoot\..\..").Path
}

$libPath = Join-Path $PSScriptRoot "lib"

# Lista de scripts a executar em ordem
$scripts = @(
    "ensure-winget.ps1",
    "ensure-uv.ps1",
    "ensure-hooks.ps1",
    "ensure-playwright.ps1",
    "ensure-node.ps1",
    "ensure-wt.ps1"
)

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Execucao
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

try {
    Write-Header "Configurando ambiente de desenvolvimento"

    foreach ($script in $scripts) {
        $scriptPath = Join-Path $libPath $script

        if (-not (Test-Path $scriptPath)) {
            Write-Failure -Prefix $PREFIX -Message "Script nao encontrado: $scriptPath"
            exit 1
        }

        & $scriptPath -RepoPath $RepoPath
        if ($LASTEXITCODE -ne 0) {
            Write-Failure -Prefix $PREFIX -Message "Falha ao executar $script"
            exit $LASTEXITCODE
        }
    }

    Write-Header "Ambiente configurado com sucesso!"

    exit 0
}
catch {
    Write-Failure -Prefix $PREFIX -Message $_.Exception.Message
    exit 1
}