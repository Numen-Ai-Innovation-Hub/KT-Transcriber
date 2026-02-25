# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# start-services.ps1 - Inicia os servicos do projeto
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Inicia FastAPI + ARQ Worker. Redis Cloud e usado (configurado no .env).
#
# PREREQUISITOS:
#   - uv instalado no sistema (pip install uv)
#   - .env configurado com credenciais Redis Cloud (REDIS_HOST, REDIS_PORT, REDIS_PASSWORD)
#   - .venv sera criado automaticamente com uv sync --group dev se nao existir
#
# USO:
#   .\.vscode\scripts\start-services.ps1
#
# APOS INICIAR, rodar os testes:
#   uv run python -m pytest tests/ -m smoke
#   uv run python -m pytest tests/ -m e2e
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

param(
    [string]$RepoPath
)

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Configurar UTF-8 IMEDIATAMENTE para corrigir acentuacao
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Carregar funcoes compartilhadas
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

. "$PSScriptRoot\lib\common.ps1"

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Configuracao
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

if (-not $RepoPath) {
    $RepoPath = (Resolve-Path "$PSScriptRoot\..\..").Path
}

$EnvFile = Join-Path $RepoPath ".env"
$venv = Get-VenvPaths -RepoPath $RepoPath

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Banner inicial
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

Clear-Host
Write-Header "Iniciando Servicos"

# Garantir que pasta logs/ existe (logs de servico para monitoramento pelo Claude Code)
$LogDir = Join-Path $RepoPath "logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}
$LogFastApi   = Join-Path $LogDir "fastapi.log"
$LogArq       = Join-Path $LogDir "arq.log"
$LogStreamlit = Join-Path $LogDir "streamlit.log"

# Limpar logs anteriores para facilitar leitura
"" | Set-Content $LogFastApi   -Encoding UTF8
"" | Set-Content $LogArq       -Encoding UTF8
"" | Set-Content $LogStreamlit -Encoding UTF8

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PRE-REQUISITOS
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

Write-Subheader "Verificando pre-requisitos"

# .env
if (-not (Test-Path $EnvFile)) {
    Write-Error-Message "Arquivo .env nao encontrado!"
    Write-Error-Message "Copie .env.example para .env e configure as credenciais Redis Cloud"
    Read-Host "Pressione ENTER para sair"
    exit 1
}
Write-Info "Arquivo .env encontrado"

# Ambiente virtual — cria automaticamente se nao existir
if (-not (Test-VenvExists -RepoPath $RepoPath)) {
    Write-Info "Ambiente virtual nao encontrado — criando com uv sync..."
    $uvExe = Get-ToolPath -CommandName "uv" -FallbackPath (Join-Path $env:APPDATA "Python\Python312\Scripts\uv.exe")
    if (-not $uvExe) {
        Write-Error-Message "uv nao encontrado! Instale com: pip install uv"
        Read-Host "Pressione ENTER para sair"
        exit 1
    }
    Push-Location $RepoPath
    & $uvExe sync --group dev
    $exitCode = $LASTEXITCODE
    Pop-Location
    if ($exitCode -ne 0) {
        Write-Error-Message "Falha ao criar ambiente virtual com uv sync --group dev"
        Read-Host "Pressione ENTER para sair"
        exit 1
    }
    Write-Info "Ambiente virtual criado com sucesso"
}
Write-Info "Ambiente virtual encontrado"

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# INICIAR SERVICOS
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

Write-Subheader "Iniciando FastAPI (porta 8000), ARQ Worker e Streamlit (porta 8501)"

$WtPath = Get-ToolPath -CommandName "wt" -FallbackPath "$env:LOCALAPPDATA\Microsoft\WindowsApps\wt.exe"

# Se WT existe E nao estamos dentro dele, relancar dentro do WT
if ($WtPath -and (-not $env:WT_SESSION)) {
    $currentScript = $PSCommandPath
    $argList = "-w new -p `"Windows PowerShell`" powershell -NoExit -File `"$currentScript`" -RepoPath `"$RepoPath`""
    Start-Process $WtPath -ArgumentList $argList
    [System.Environment]::Exit(0)
}

$utf8Cmd = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; `$env:PYTHONUTF8 = '1'; `$env:PYTHONIOENCODING = 'utf-8';"

if ($WtPath) {
    Write-Info "Windows Terminal detectado - iniciando servicos em abas"

    # FastAPI (porta 8000) — stderr vai direto ao terminal (uvicorn usa stderr para logs); stdout capturado em logs/fastapi.log
    $cmdFastApi = "$utf8Cmd cd '$RepoPath'; & '$($venv.VenvActivate)'; `$host.UI.RawUI.WindowTitle = 'FastAPI'; Write-Host 'Iniciando FastAPI (porta 8000) — log: logs/fastapi.log'; uvicorn src.api.main:app --reload --reload-exclude .venv --reload-exclude data --reload-exclude logs --host 0.0.0.0 --port 8000 | Tee-Object -FilePath '$LogFastApi'"
    $bytesFastApi = [System.Text.Encoding]::Unicode.GetBytes($cmdFastApi)
    $encFastApi = [Convert]::ToBase64String($bytesFastApi)

    # ARQ Worker — stderr vai direto ao terminal (ARQ usa stderr para logs); stdout capturado em logs/arq.log
    $cmdArq = "$utf8Cmd cd '$RepoPath'; & '$($venv.VenvActivate)'; `$host.UI.RawUI.WindowTitle = 'ARQ Worker'; Write-Host 'Iniciando ARQ Worker — log: logs/arq.log'; arq src.tasks.arq_worker.WorkerSettings | Tee-Object -FilePath '$LogArq'"
    $bytesArq = [System.Text.Encoding]::Unicode.GetBytes($cmdArq)
    $encArq = [Convert]::ToBase64String($bytesArq)

    # Streamlit (porta 8501) — UI de busca KT
    $cmdStreamlit = "$utf8Cmd cd '$RepoPath'; & '$($venv.VenvActivate)'; `$host.UI.RawUI.WindowTitle = 'Streamlit'; Write-Host 'Iniciando Streamlit (porta 8501) — log: logs/streamlit.log'; streamlit run scripts/app.py --server.port 8501 --server.headless true | Tee-Object -FilePath '$LogStreamlit'"
    $bytesStreamlit = [System.Text.Encoding]::Unicode.GetBytes($cmdStreamlit)
    $encStreamlit = [Convert]::ToBase64String($bytesStreamlit)

    $wtArgs = "-w 0 nt --title `"FastAPI`" powershell -NoExit -EncodedCommand $encFastApi ; nt --title `"ARQ Worker`" powershell -NoExit -EncodedCommand $encArq ; nt --title `"Streamlit`" powershell -NoExit -EncodedCommand $encStreamlit"
    Start-Process $WtPath -ArgumentList $wtArgs

    Write-Info "Abas de servico adicionadas ao Windows Terminal."
    Start-Sleep -Seconds 2

} else {
    Write-Info "Windows Terminal nao encontrado - iniciando em janelas separadas"

    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "cd '$RepoPath'; & '$($venv.VenvActivate)'; uvicorn src.api.main:app --reload --reload-exclude .venv --reload-exclude data --reload-exclude logs --host 0.0.0.0 --port 8000 | Tee-Object -FilePath '$LogFastApi'"
    ) -WindowStyle Normal
    Start-Sleep -Seconds 2

    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "cd '$RepoPath'; & '$($venv.VenvActivate)'; arq src.tasks.arq_worker.WorkerSettings | Tee-Object -FilePath '$LogArq'"
    ) -WindowStyle Normal
    Start-Sleep -Seconds 2

    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "cd '$RepoPath'; & '$($venv.VenvActivate)'; streamlit run scripts/app.py --server.port 8501 --server.headless true | Tee-Object -FilePath '$LogStreamlit'"
    ) -WindowStyle Normal
    Start-Sleep -Seconds 2
}

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Health check
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

Write-Info "Aguardando 5 segundos para servicos iniciarem..."
Start-Sleep -Seconds 5

Write-Subheader "Health Check"

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/v1/health" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
    Write-Info "FastAPI respondendo em http://localhost:8000"
} catch {
    Write-Info "FastAPI ainda nao esta respondendo (pode levar alguns segundos)"
    Write-Info "Verifique a aba FastAPI no Windows Terminal"
}

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Resumo final
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

Write-Header "Servicos prontos!"

Write-Host "Servicos rodando:" -ForegroundColor Yellow
Write-Host "  - Redis:       Redis Cloud (configurado no .env)"
Write-Host "  - FastAPI:     http://localhost:8000"
Write-Host "  - Swagger UI:  http://localhost:8000/docs"
Write-Host "  - ARQ Worker:  Processando jobs em background"
Write-Host "  - Streamlit:   http://localhost:8501"
Write-Host ""
Write-Host "Logs de servico (lidos pelo Claude Code):" -ForegroundColor Cyan
Write-Host "  - logs/fastapi.log    — output completo do uvicorn"
Write-Host "  - logs/arq.log        — output completo do ARQ Worker"
Write-Host "  - logs/streamlit.log  — output completo do Streamlit"
Write-Host ""
Write-Host "Para rodar os testes:" -ForegroundColor Yellow
Write-Host "  uv run python -m pytest tests/ -m smoke     # smoke: stack sobe e responde"
Write-Host "  uv run python -m pytest tests/ -m e2e       # e2e: fluxo completo"
Write-Host ""
Write-Host "Para rodar unit tests (sem infra):" -ForegroundColor Yellow
Write-Host "  uv run python -m pytest tests/ -m `"not smoke and not e2e`""
Write-Host ""

if ($env:WT_SESSION) {
    Read-Host "Pressione ENTER para fechar esta aba (os servicos continuarao rodando)"
    exit 0
}