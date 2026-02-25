# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# ensure-node.ps1 - Garante Node.js e npm instalados
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

$PREFIX = "ensure-node"

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Execucao
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

try {
    Write-Host "Etapa 7: Verificacao Node.js e npm" -ForegroundColor Cyan
    Write-Host ""

    # Adicionar Node.js ao PATH do usuario (se necessario)
    Write-Step -Prefix $PREFIX -Message "Verificando PATH do usuario"
    $pathAdded = Add-ToUserPath -PathToAdd $script:NODE_INSTALL_PATH
    if ($pathAdded) {
        Write-Success -Prefix $PREFIX -Message "Node.js adicionado ao PATH: $($script:NODE_INSTALL_PATH)"
    } else {
        Write-Skip -Prefix $PREFIX -Message "Node.js ja esta no PATH"
    }

    # Verificar Node.js
    Write-Step -Prefix $PREFIX -Message "Verificando Node.js"
    $nodeExe = Get-ToolPath -CommandName "node" -FallbackPath (Join-Path $script:NODE_INSTALL_PATH "node.exe")

    if (-not $nodeExe) {
        Write-Warning-Message -Prefix $PREFIX -Message "Node.js nao encontrado"
        Write-Step -Prefix $PREFIX -Message "Tentando instalar via winget"
        Write-Host ""

        # Verificar se winget esta disponivel
        $wingetCmd = Get-Command winget -ErrorAction SilentlyContinue
        if (-not $wingetCmd) {
            Write-Failure -Prefix $PREFIX -Message "winget nao encontrado (requer Windows 10 1809+ ou Windows 11)"
            Write-Host ""
            Write-Host "Instale manualmente: https://nodejs.org/" -ForegroundColor Yellow
            Write-Host "Apos instalar, feche e reabra o VSCode" -ForegroundColor Yellow
            Write-Host ""
            exit 1
        }

        # Instalar Node.js LTS via winget
        Write-Step -Prefix $PREFIX -Message "Instalando Node.js LTS"
        winget install --id OpenJS.NodeJS.LTS --silent --accept-source-agreements --accept-package-agreements

        if ($LASTEXITCODE -eq 0) {
            Write-Success -Prefix $PREFIX -Message "Node.js instalado com sucesso!"
            Write-Host ""
            Write-Host "IMPORTANTE: Feche e reabra o VSCode para aplicar as mudancas no PATH" -ForegroundColor Cyan
            Write-Host ""
            exit 0
        } else {
            Write-Failure -Prefix $PREFIX -Message "Falha na instalacao automatica via winget"
            Write-Host ""
            Write-Host "Instale manualmente: https://nodejs.org/" -ForegroundColor Yellow
            Write-Host "Apos instalar, feche e reabra o VSCode" -ForegroundColor Yellow
            Write-Host ""
            exit 1
        }
    }

    $nodeVersion = & node --version
    Write-Success -Prefix $PREFIX -Message "Node.js instalado: $nodeVersion"

    # Verificar npm
    Write-Step -Prefix $PREFIX -Message "Verificando npm"
    $npmCmd = Get-Command npm -ErrorAction SilentlyContinue

    if (-not $npmCmd) {
        Write-Failure -Prefix $PREFIX -Message "npm nao encontrado (deveria vir com Node.js)"
        exit 1
    }

    $npmVersion = & npm --version
    Write-Success -Prefix $PREFIX -Message "npm instalado: v$npmVersion"

    # Verificar package.json do frontend
    Write-Step -Prefix $PREFIX -Message "Verificando projeto frontend Lovable"
    $packageJson = Join-Path $script:FRONTEND_PATH "package.json"

    if (-not (Test-Path $packageJson)) {
        Write-Warning-Message -Prefix $PREFIX -Message "Frontend Lovable nao encontrado em: $($script:FRONTEND_PATH)"
        Write-Warning-Message -Prefix $PREFIX -Message "start_services.bat pode falhar ao iniciar o frontend"
        Write-Host ""
        exit 0
    }

    Write-Success -Prefix $PREFIX -Message "Frontend Lovable encontrado: $($script:FRONTEND_PATH)"

    # Verificar node_modules instalados
    $nodeModules = Join-Path $script:FRONTEND_PATH "node_modules"
    if (-not (Test-Path $nodeModules)) {
        Write-Warning-Message -Prefix $PREFIX -Message "Dependencias do frontend nao instaladas"
        Write-Warning-Message -Prefix $PREFIX -Message "Execute: cd '$($script:FRONTEND_PATH)' && npm install"
        Write-Host ""
        exit 0
    }

    Write-Success -Prefix $PREFIX -Message "Dependencias do frontend instaladas"

    Write-Host ""
    exit 0
}
catch {
    Write-Failure -Prefix $PREFIX -Message $_.Exception.Message
    exit 1
}