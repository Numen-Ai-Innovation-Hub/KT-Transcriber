# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# ensure-winget.ps1 - Valida que winget esteja instalado (pre-requisito do sistema)
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

$PREFIX = "ensure-winget"
$windowsAppsPath = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps"
$wingetExePath = Join-Path $windowsAppsPath "winget.exe"

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Execucao
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

try {
    Write-Host "Etapa 1: Verificacao winget (App Installer)" -ForegroundColor Cyan
    Write-Host ""

    # 1. Validar que App Installer esta instalado (pre-requisito)
    $appInstaller = Get-AppxPackage -Name Microsoft.DesktopAppInstaller -ErrorAction SilentlyContinue
    if (-not $appInstaller) {
        Write-Failure -Prefix $PREFIX -Message "winget nao esta instalado (pre-requisito obrigatorio)"
        Write-Host ""
        Write-Host "Para instalar winget:" -ForegroundColor Yellow
        Write-Host "  1. Abra Microsoft Store" -ForegroundColor Yellow
        Write-Host "  2. Procure por 'App Installer'" -ForegroundColor Yellow
        Write-Host "  3. Clique em 'Instalar'" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Ou instale via PowerShell (como Administrador):" -ForegroundColor Yellow
        Write-Host "  Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Ou baixe: https://github.com/microsoft/winget-cli/releases" -ForegroundColor Cyan
        Write-Host ""
        exit 1
    }

    Write-Success -Prefix $PREFIX -Message "App Installer detectado (versao $($appInstaller.Version))"

    # 2. Verificar se winget esta acessivel no PATH
    $wingetCmd = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $wingetCmd) {
        Write-Failure -Prefix $PREFIX -Message "winget nao esta acessivel no PATH (pre-requisito obrigatorio)"
        Write-Host ""
        Write-Host "WindowsApps nao esta no PATH do sistema." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Solucao: Adicionar manualmente ao PATH:" -ForegroundColor Yellow
        Write-Host "  1. Abra 'Configuracoes do Sistema' (Win + Pause)" -ForegroundColor Yellow
        Write-Host "  2. Clique em 'Configuracoes avancadas do sistema'" -ForegroundColor Yellow
        Write-Host "  3. Clique em 'Variaveis de Ambiente'" -ForegroundColor Yellow
        Write-Host "  4. Em 'Variaveis do usuario', selecione 'Path' e clique em 'Editar'" -ForegroundColor Yellow
        Write-Host "  5. Clique em 'Novo' e adicione: $windowsAppsPath" -ForegroundColor Cyan
        Write-Host "  6. Clique em 'OK' e REINICIE o computador" -ForegroundColor Yellow
        Write-Host ""
        exit 1
    }

    Write-Success -Prefix $PREFIX -Message "winget detectado no PATH: $($wingetCmd.Source)"

    # 3. Testar winget
    $wingetVersion = winget --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success -Prefix $PREFIX -Message "winget funcional: $wingetVersion"
    } else {
        Write-Failure -Prefix $PREFIX -Message "winget no PATH mas nao funcional (Exit Code: $LASTEXITCODE)"
        Write-Host ""
        Write-Host "Reinstale o App Installer via Microsoft Store" -ForegroundColor Yellow
        Write-Host ""
        exit 1
    }

    Write-Host ""
    exit 0
}
catch {
    Write-Failure -Prefix $PREFIX -Message $_.Exception.Message
    exit 1
}