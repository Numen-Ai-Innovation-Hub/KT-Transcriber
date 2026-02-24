# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# ensure-wt.ps1 - Garante que o Windows Terminal esteja instalado
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

$PREFIX = "ensure-wt"
$WtPath = "$env:LOCALAPPDATA\Microsoft\WindowsApps\wt.exe"

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Execucao
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

try {
    Write-Host "Etapa 8: Verificacao Windows Terminal" -ForegroundColor Cyan
    Write-Host ""

    # Validar que Windows Terminal esta instalado (pre-requisito)
    $WtCmd = Get-Command "wt" -ErrorAction SilentlyContinue
    if ((Test-Path $WtPath) -or $WtCmd) {
        Write-Success -Prefix $PREFIX -Message "Windows Terminal detectado"
        Write-Host ""
        exit 0
    }

    # Windows Terminal ausente - falhar com instrucoes
    Write-Failure -Prefix $PREFIX -Message "Windows Terminal nao esta instalado (pre-requisito obrigatorio)"
    Write-Host ""
    Write-Host "Para instalar Windows Terminal:" -ForegroundColor Yellow
    Write-Host "  1. Abra a Microsoft Store" -ForegroundColor Yellow
    Write-Host "  2. Procure por 'Windows Terminal'" -ForegroundColor Yellow
    Write-Host "  3. Clique em 'Instalar'" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Ou instale via winget:" -ForegroundColor Yellow
    Write-Host "  winget install --id Microsoft.WindowsTerminal" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Link direto: https://aka.ms/terminal" -ForegroundColor Cyan
    Write-Host ""
    exit 1

    Write-Host ""
    exit 0
}
catch {
    Write-Failure -Prefix $PREFIX -Message $_.Exception.Message
    exit 1
}