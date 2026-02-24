# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# common.ps1 - Funcoes e constantes compartilhadas para scripts de automacao
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Este arquivo deve ser dot-sourced no inicio de cada script:
#   . "$PSScriptRoot\common.ps1"  (para scripts em lib/)
#   . "$PSScriptRoot\lib\common.ps1"  (para scripts na raiz de scripts/)
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Encoding UTF-8 — garante que caracteres especiais (═, ─, │) sejam exibidos corretamente
# em qualquer terminal (VSCode, Claude Code, Windows Terminal)
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Constantes compartilhadas
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

$script:DELIMITER_WIDTH = 120
$script:PYTHON_SCRIPTS_PATH = Join-Path $env:APPDATA "Python\Python312\Scripts"
$script:FRONTEND_PATH = "C:\Numen\AI Innovation Hub\Portals\ai-i9-portal"
$script:PLAYWRIGHT_BROWSERS_PATH = Join-Path $env:LOCALAPPDATA "ms-playwright"
$script:NODE_INSTALL_PATH = Join-Path $env:ProgramFiles "nodejs"

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Funcoes de output padronizadas
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host ("═" * $script:DELIMITER_WIDTH) -ForegroundColor Green
    Write-Host $Text -ForegroundColor Green
    Write-Host ("═" * $script:DELIMITER_WIDTH) -ForegroundColor Green
    Write-Host ""
}

function Write-Subheader {
    param([string]$Text)
    Write-Host ""
    Write-Host ("─" * $script:DELIMITER_WIDTH) -ForegroundColor Yellow
    Write-Host $Text -ForegroundColor Yellow
    Write-Host ("─" * $script:DELIMITER_WIDTH) -ForegroundColor Yellow
    Write-Host ""
}

function Write-Step {
    param(
        [string]$Prefix,
        [string]$Message
    )
    Write-Host "[$Prefix] $Message"
}

function Write-Success {
    param(
        [string]$Prefix,
        [string]$Message
    )
    Write-Host "[$Prefix] OK: $Message" -ForegroundColor Green
}

function Write-Failure {
    param(
        [string]$Prefix,
        [string]$Message
    )
    Write-Host "[$Prefix] ERRO: $Message" -ForegroundColor Red
}

function Write-Skip {
    param(
        [string]$Prefix,
        [string]$Message
    )
    Write-Host "[$Prefix] SKIP: $Message" -ForegroundColor Yellow
}

function Write-Warning-Message {
    param(
        [string]$Prefix,
        [string]$Message
    )
    Write-Host "[$Prefix] AVISO: $Message" -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Text)
    Write-Host "  -> $Text" -ForegroundColor Cyan
}

function Write-Error-Message {
    param([string]$Text)
    Write-Host "  X $Text" -ForegroundColor Red
}

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Funcoes utilitarias
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function Add-ToUserPath {
    param([string]$PathToAdd)
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentPath -notlike "*$PathToAdd*") {
        [Environment]::SetEnvironmentVariable("Path", "$currentPath;$PathToAdd", "User")
        return $true
    }
    return $false
}

function Remove-FromUserPath {
    param([string]$PathToRemove)
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentPath -like "*$PathToRemove*") {
        $newPath = $currentPath -replace ";$([regex]::Escape($PathToRemove))", ""
        $newPath = $newPath -replace "$([regex]::Escape($PathToRemove));", ""
        $newPath = $newPath -replace "$([regex]::Escape($PathToRemove))", ""
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        return $true
    }
    return $false
}

function Get-ToolPath {
    param(
        [string]$CommandName,
        [string]$FallbackPath
    )
    $cmd = Get-Command $CommandName -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    if ($FallbackPath -and (Test-Path $FallbackPath)) { return $FallbackPath }
    return $null
}

function Get-VenvPaths {
    param([string]$RepoPath)
    return @{
        VenvPath = Join-Path $RepoPath ".venv"
        VenvPython = Join-Path $RepoPath ".venv\Scripts\python.exe"
        VenvActivate = Join-Path $RepoPath ".venv\Scripts\Activate.ps1"
    }
}

function Test-VenvExists {
    param([string]$RepoPath)
    $paths = Get-VenvPaths -RepoPath $RepoPath
    return Test-Path $paths.VenvPython
}

function Test-IsGitRepo {
    param([string]$RepoPath)
    return Test-Path (Join-Path $RepoPath ".git")
}

function Test-PreCommitHookExists {
    param([string]$RepoPath)
    return Test-Path (Join-Path $RepoPath ".git\hooks\pre-commit")
}