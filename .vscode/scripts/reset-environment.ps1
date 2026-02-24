# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# reset-environment.ps1 - Zera completamente o ambiente de desenvolvimento
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Remove: .venv, pre-commit hooks, Chromium (Playwright), Node.js, Python Scripts do PATH, uv
# NOTA: Redis Cloud nao e desinstalado — apenas credenciais no .env precisam ser removidas manualmente
#
# USO:
#   .\.vscode\scripts\reset-environment.ps1
#
# DEPOIS:
#   Feche e reabra o VSCode para recriar tudo automaticamente
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

$PREFIX = "reset"

if (-not $RepoPath) {
    $RepoPath = (Resolve-Path "$PSScriptRoot\..\..").Path
}

$venv = Get-VenvPaths -RepoPath $RepoPath
$preCommitHook = Join-Path $RepoPath ".git\hooks\pre-commit"

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Execucao
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

try {
    Write-Header "Zerando ambiente de desenvolvimento"

    # 1. Remover .venv
    if (Test-Path $venv.VenvPath) {
        Write-Step -Prefix $PREFIX -Message "Removendo .venv"
        Remove-Item -Recurse -Force $venv.VenvPath
        Write-Success -Prefix $PREFIX -Message ".venv removido"
    } else {
        Write-Skip -Prefix $PREFIX -Message ".venv nao encontrado"
    }

    # 2. Remover pre-commit hook
    if (Test-Path $preCommitHook) {
        Write-Step -Prefix $PREFIX -Message "Removendo pre-commit hook"
        Remove-Item -Force $preCommitHook
        Write-Success -Prefix $PREFIX -Message "Pre-commit hook removido"
    } else {
        Write-Skip -Prefix $PREFIX -Message "Pre-commit hook nao encontrado"
    }

    # 3. Remover Chromium (Playwright)
    if (Test-Path $script:PLAYWRIGHT_BROWSERS_PATH) {
        Write-Step -Prefix $PREFIX -Message "Removendo navegadores Playwright"
        Remove-Item -Recurse -Force $script:PLAYWRIGHT_BROWSERS_PATH
        Write-Success -Prefix $PREFIX -Message "Navegadores Playwright removidos"
    } else {
        Write-Skip -Prefix $PREFIX -Message "Navegadores Playwright nao encontrados"
    }

    # 4. Remover Node.js do PATH do usuario
    Write-Step -Prefix $PREFIX -Message "Verificando Node.js no PATH"
    $nodePathRemoved = Remove-FromUserPath -PathToRemove $script:NODE_INSTALL_PATH
    if ($nodePathRemoved) {
        Write-Success -Prefix $PREFIX -Message "Node.js removido do PATH"
    } else {
        Write-Skip -Prefix $PREFIX -Message "Node.js nao esta no PATH"
    }

    # 5. Desinstalar Node.js
    $nodeExe = Get-ToolPath -CommandName "node" -FallbackPath (Join-Path $script:NODE_INSTALL_PATH "node.exe")
    if ($nodeExe) {
        Write-Step -Prefix $PREFIX -Message "Removendo Node.js via winget"

        $wingetCmd = Get-Command "winget" -ErrorAction SilentlyContinue
        if (-not $wingetCmd) {
            Write-Failure -Prefix $PREFIX -Message "winget nao esta no PATH (pre-requisito obrigatorio para remover Node.js)"
            Write-Host ""
            Write-Host "Adicione WindowsApps ao PATH e REINICIE o computador:" -ForegroundColor Yellow
            Write-Host "  $($env:LOCALAPPDATA)\Microsoft\WindowsApps" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "Ou remova Node.js manualmente:" -ForegroundColor Yellow
            Write-Host "  Configuracoes > Aplicativos > Node.js > Desinstalar" -ForegroundColor Cyan
            Write-Host ""
            exit 1
        }

        # Descobrir qual ID do Node.js esta instalado (LTS ou Current)
        $nodeWingetId = $null
        $wingetList = winget list --name "Node.js" --accept-source-agreements 2>&1 | Out-String
        if ($wingetList -match "OpenJS\.NodeJS\.LTS") {
            $nodeWingetId = "OpenJS.NodeJS.LTS"
        } elseif ($wingetList -match "OpenJS\.NodeJS") {
            $nodeWingetId = "OpenJS.NodeJS"
        }

        if ($nodeWingetId) {
            Write-Step -Prefix $PREFIX -Message "Detectado $nodeWingetId - removendo (elevacao UAC)"
            $proc = Start-Process winget -ArgumentList "uninstall --id $nodeWingetId --source winget --accept-source-agreements --silent" -Verb RunAs -Wait -PassThru
            if ($proc.ExitCode -eq 0) {
                Write-Success -Prefix $PREFIX -Message "Node.js removido com sucesso"
            } else {
                Write-Failure -Prefix $PREFIX -Message "Falha ao remover Node.js via winget (Exit Code: $($proc.ExitCode))"
                exit 1
            }
        } else {
            Write-Warning-Message -Prefix $PREFIX -Message "Node.js encontrado no disco mas nao registrado no winget"
            Write-Host ""
            Write-Host "Remova manualmente:" -ForegroundColor Yellow
            Write-Host "  Configuracoes > Aplicativos > Node.js > Desinstalar" -ForegroundColor Cyan
            Write-Host ""
        }
    } else {
        Write-Skip -Prefix $PREFIX -Message "Node.js nao encontrado"
    }

    # 6. Remover Python Scripts do PATH do usuario
    Write-Step -Prefix $PREFIX -Message "Verificando Python Scripts no PATH"
    $pathRemoved = Remove-FromUserPath -PathToRemove $script:PYTHON_SCRIPTS_PATH
    if ($pathRemoved) {
        Write-Success -Prefix $PREFIX -Message "Python Scripts removido do PATH"
    } else {
        Write-Skip -Prefix $PREFIX -Message "Python Scripts nao esta no PATH"
    }

    # 7. Desinstalar uv
    $uvUserPath = Join-Path $script:PYTHON_SCRIPTS_PATH "uv.exe"
    $uvExe = Get-ToolPath -CommandName "uv" -FallbackPath $uvUserPath
    if ($uvExe) {
        Write-Step -Prefix $PREFIX -Message "Desinstalando uv"
        python.exe -m pip uninstall uv -y --quiet
        if ($LASTEXITCODE -eq 0) {
            Write-Success -Prefix $PREFIX -Message "uv desinstalado"
        } else {
            Write-Warning-Message -Prefix $PREFIX -Message "Falha ao desinstalar uv via pip"
        }
    } else {
        Write-Skip -Prefix $PREFIX -Message "uv nao esta instalado"
    }

    # Windows Terminal e winget sao pre-requisitos do sistema e nao sao removidos

    Write-Header "Ambiente zerado com sucesso!"
    Write-Host "Feche e reabra o VSCode para recriar tudo automaticamente" -ForegroundColor Cyan
    Write-Host ""

    exit 0
}
catch {
    Write-Failure -Prefix $PREFIX -Message $_.Exception.Message
    exit 1
}