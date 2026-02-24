# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# ensure-uv.ps1 - Garante uv instalado, PATH configurado e dependencias sincronizadas
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

$PREFIX = "ensure-uv"
$venv = Get-VenvPaths -RepoPath $RepoPath
$lockFile = Join-Path $RepoPath "uv.lock"
$uvUserPath = Join-Path $script:PYTHON_SCRIPTS_PATH "uv.exe"

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Execucao
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

try {
    Write-Host "Etapa 2: Configuracao uv e dependencias" -ForegroundColor Cyan
    Write-Host ""

    # Adicionar Python Scripts ao PATH
    Write-Step -Prefix $PREFIX -Message "Verificando PATH do usuario"
    $pathAdded = Add-ToUserPath -PathToAdd $script:PYTHON_SCRIPTS_PATH
    if ($pathAdded) {
        Write-Success -Prefix $PREFIX -Message "Python Scripts adicionado ao PATH: $($script:PYTHON_SCRIPTS_PATH)"
    } else {
        Write-Skip -Prefix $PREFIX -Message "Python Scripts ja esta no PATH"
    }

    # Atualizar pip
    Write-Step -Prefix $PREFIX -Message "Atualizando pip"
    python.exe -m pip install --upgrade pip --quiet --no-warn-script-location
    if ($LASTEXITCODE -ne 0) {
        Write-Failure -Prefix $PREFIX -Message "Falha ao atualizar pip"
        exit 1
    }
    Write-Success -Prefix $PREFIX -Message "pip atualizado"

    # Instalar uv
    $uvExe = Get-ToolPath -CommandName "uv" -FallbackPath $uvUserPath
    if (-not $uvExe) {
        Write-Step -Prefix $PREFIX -Message "Instalando uv via pip"
        pip install uv --quiet --no-warn-script-location
        if ($LASTEXITCODE -ne 0) {
            Write-Failure -Prefix $PREFIX -Message "Falha ao instalar uv"
            exit 1
        }
        $uvExe = Get-ToolPath -CommandName "uv" -FallbackPath $uvUserPath
        if (-not $uvExe) {
            Write-Failure -Prefix $PREFIX -Message "uv instalado mas nao encontrado"
            exit 1
        }
        Write-Success -Prefix $PREFIX -Message "uv instalado"
    } else {
        Write-Skip -Prefix $PREFIX -Message "uv ja esta instalado"
    }

    # Criar .venv
    if (-not (Test-Path $venv.VenvPath)) {
        Write-Step -Prefix $PREFIX -Message "Criando ambiente virtual"
        Push-Location $RepoPath
        & $uvExe venv .venv
        $exitCode = $LASTEXITCODE
        Pop-Location
        if ($exitCode -ne 0) {
            Write-Failure -Prefix $PREFIX -Message "Falha ao criar ambiente virtual"
            exit 1
        }
        Write-Success -Prefix $PREFIX -Message "Ambiente virtual criado"
    } else {
        Write-Skip -Prefix $PREFIX -Message "Ambiente virtual ja existe"
    }

    # Sincronizar dependencias
    if (Test-Path $lockFile) {
        Write-Step -Prefix $PREFIX -Message "Sincronizando dependencias"
        Push-Location $RepoPath
        & $uvExe sync --group dev
        $exitCode = $LASTEXITCODE
        Pop-Location
        if ($exitCode -ne 0) {
            Write-Failure -Prefix $PREFIX -Message "Falha ao sincronizar dependencias"
            exit 1
        }
        Write-Success -Prefix $PREFIX -Message "Dependencias sincronizadas"
    } else {
        Write-Skip -Prefix $PREFIX -Message "Arquivo uv.lock nao encontrado"
    }

    Write-Host ""
    exit 0
}
catch {
    Write-Failure -Prefix $PREFIX -Message $_.Exception.Message
    exit 1
}