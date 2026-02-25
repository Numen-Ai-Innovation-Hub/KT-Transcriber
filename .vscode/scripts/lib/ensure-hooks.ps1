# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# ensure-hooks.ps1 - Garante pre-commit hooks instalados
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

$PREFIX = "ensure-hooks"
$venv = Get-VenvPaths -RepoPath $RepoPath

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Execucao
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

try {
    Write-Host "Etapa 3: Configuracao pre-commit hooks" -ForegroundColor Cyan
    Write-Host ""

    # Verificar se e repositorio git
    if (-not (Test-IsGitRepo -RepoPath $RepoPath)) {
        Write-Skip -Prefix $PREFIX -Message "Nao e um repositorio git"
        Write-Host ""
        exit 0
    }

    # Verificar se hooks ja existem
    if (Test-PreCommitHookExists -RepoPath $RepoPath) {
        Write-Skip -Prefix $PREFIX -Message "Pre-commit hooks ja estao instalados"
        Write-Host ""
        exit 0
    }

    # Verificar ambiente virtual
    if (-not (Test-VenvExists -RepoPath $RepoPath)) {
        Write-Failure -Prefix $PREFIX -Message "Ambiente virtual nao encontrado em $($venv.VenvPath)"
        exit 1
    }

    # Instalar hooks
    Write-Step -Prefix $PREFIX -Message "Instalando pre-commit hooks"
    & $venv.VenvPython -m pre_commit install --hook-type pre-commit
    if ($LASTEXITCODE -ne 0) {
        Write-Failure -Prefix $PREFIX -Message "Falha ao instalar pre-commit hooks"
        exit $LASTEXITCODE
    }
    Write-Success -Prefix $PREFIX -Message "Pre-commit hooks instalados"

    Write-Host ""
    exit 0
}
catch {
    Write-Failure -Prefix $PREFIX -Message $_.Exception.Message
    exit 1
}