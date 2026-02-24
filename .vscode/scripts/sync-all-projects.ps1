# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# sync-all-projects.ps1 - Sincroniza arquivos universais do template para todos os projetos derivados
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Chama sync-to-project.ps1 sequencialmente para cada projeto listado em $PROJECTS.
# Para adicionar ou remover projetos: editar apenas a secao PROJETOS abaixo.
#
# USO:
#   .\.vscode\scripts\sync-all-projects.ps1
#   .\.vscode\scripts\sync-all-projects.ps1 -DryRun
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# PROJETOS — editar esta lista para adicionar ou remover projetos do sync
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

$BASE = "c:\Numen\AI Innovation Hub\Projects"

$PROJECTS = @(
    "$BASE\Document_Query"
    "$BASE\Learn_Assistant"
    "$BASE\NPV_Assistant"
)

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Execucao
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

$SYNC_SCRIPT = Join-Path $PSScriptRoot "sync-to-project.ps1"
$success = 0
$failed = @()

Write-Host ("═" * 120) -ForegroundColor Cyan
Write-Host "sync-all-projects | $($PROJECTS.Count) projeto(s)$(if ($DryRun) { ' | DRY-RUN' })" -ForegroundColor Cyan
Write-Host ("═" * 120) -ForegroundColor Cyan

foreach ($projectPath in $PROJECTS) {
    $projectName = Split-Path $projectPath -Leaf
    Write-Host ""
    Write-Host ("─" * 120) -ForegroundColor DarkGray
    Write-Host ">>> $projectName" -ForegroundColor Cyan
    Write-Host ("─" * 120) -ForegroundColor DarkGray

    try {
        if ($DryRun) {
            & $SYNC_SCRIPT -ProjectPath $projectPath -DryRun
        } else {
            & $SYNC_SCRIPT -ProjectPath $projectPath
        }
        $success++
    } catch {
        Write-Host "ERRO em ${projectName}: $_" -ForegroundColor Red
        $failed += $projectName
    }
}

Write-Host ""
Write-Host ("═" * 120) -ForegroundColor Cyan
$color = if ($failed.Count -eq 0) { "Green" } else { "Yellow" }
Write-Host "Concluido: $success/$($PROJECTS.Count) projeto(s) sincronizados" -ForegroundColor $color
if ($failed.Count -gt 0) {
    Write-Host "Falhas: $($failed -join ', ')" -ForegroundColor Red
}
Write-Host ("═" * 120) -ForegroundColor Cyan