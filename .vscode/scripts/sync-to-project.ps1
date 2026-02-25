# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# sync-to-project.ps1 - Copia arquivos universais do template para um projeto derivado
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Copia pastas e arquivos que sao identicos em todos os projetos:
#   - .vscode\          - Scripts de automacao e configuracao do VSCode (pasta inteira)
#   - .claude\          - Skills e configuracao do Claude Code (pasta inteira)
#                         Inclui: migrate-analyze, migrate-infra, migrate-domain, migrate-api,
#                                 migrate-tests, audit-project, audit-pair + skills-feedback/
#   - CLAUDE.md         - Instrucoes raiz do projeto
#   - src\CLAUDE.md     - Instrucoes de arquitetura
#   - scripts\CLAUDE.md - Instrucoes de scripts pontuais
#   - tests\CLAUDE.md   - Instrucoes de testes
#   - utils\CLAUDE.md   - Instrucoes de utilitarios
#   - utils\*.py        - Todos os utilitarios portaveis (exception_setup, logger_setup, etc.)
#
# NAO copia (customizados por projeto):
#   - src\api\main.py      - Routers e lifespan especificos do projeto
#   - src\config\          - Settings e providers especificos do projeto
#   - .env.example         - Variaveis especificas do projeto
#   - pyproject.toml       - Dependencias especificas do projeto
#   - tests\test_smoke.py      - Testa endpoints e comportamentos especificos do projeto
#   - tests\test_e2e.py        - Fluxo completo especifico do projeto
#   - src\tasks\arq_worker.py  - Tasks customizadas por projeto (nao sobrescrever)
#
# Arquivos raiz copiados individualmente (alem dos CLAUDEs):
#   - start-services.bat        - Launcher para iniciar FastAPI e ARQ Worker (Redis Cloud via .env)
#   - tests\conftest.py         - Fixtures universais: require_redis (Redis Cloud), isolated_test_dirs, env vars
#
# USO:
#   .\.vscode\scripts\sync-to-project.ps1 -ProjectPath "c:\Numen\AI Innovation Hub\Projects\MeuProjeto"
#   .\.vscode\scripts\sync-to-project.ps1 -ProjectPath "c:\Numen\AI Innovation Hub\Projects\MeuProjeto" -DryRun
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectPath,

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Carregar funcoes compartilhadas
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

. "$PSScriptRoot\lib\common.ps1"

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Configuracao
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

$PREFIX = "sync-to-project"
$TEMPLATE_PATH = $PSScriptRoot | Split-Path | Split-Path  # sobe 2 niveis: scripts/ -> .vscode/ -> raiz

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Validacoes iniciais
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

Write-Header "sync-to-project | Template → Projeto"

if ($DryRun) {
    Write-Step -Prefix $PREFIX -Message "MODO DRY-RUN: nenhum arquivo sera copiado"
}

if (-not (Test-Path $ProjectPath)) {
    Write-Failure -Prefix $PREFIX -Message "Projeto nao encontrado: $ProjectPath"
    exit 1
}

if (-not (Test-Path (Join-Path $ProjectPath ".git"))) {
    Write-Failure -Prefix $PREFIX -Message "Pasta nao e um repositorio Git: $ProjectPath"
    exit 1
}

$ProjectName = Split-Path $ProjectPath -Leaf
Write-Step -Prefix $PREFIX -Message "Template : $TEMPLATE_PATH"
Write-Step -Prefix $PREFIX -Message "Destino  : $ProjectPath ($ProjectName)"

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Funcao auxiliar de copia
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

$script:CopiedCount = 0
$script:SkippedCount = 0

function Copy-TemplateFile {
    param(
        [string]$RelativePath
    )

    $src = Join-Path $TEMPLATE_PATH $RelativePath
    $dst = Join-Path $ProjectPath $RelativePath

    if (-not (Test-Path $src)) {
        Write-Warning -Prefix $PREFIX -Message "Arquivo nao encontrado no template: $RelativePath"
        return
    }

    $dstDir = Split-Path $dst -Parent
    if (-not (Test-Path $dstDir)) {
        if (-not $DryRun) {
            New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
        }
        Write-Step -Prefix $PREFIX -Message "  [CRIAR DIR] $($dstDir.Replace($ProjectPath, ''))"
    }

    $action = if (Test-Path $dst) { "ATUALIZAR" } else { "CRIAR" }
    Write-Step -Prefix $PREFIX -Message "  [$action] $RelativePath"

    if (-not $DryRun) {
        Copy-Item $src $dst -Force
    }

    $script:CopiedCount++
}

function Sync-TemplateFolder {
    param(
        [string]$RelativeFolder
    )

    $srcFolder = Join-Path $TEMPLATE_PATH $RelativeFolder
    $dstFolder = Join-Path $ProjectPath $RelativeFolder

    if (-not (Test-Path $srcFolder)) {
        Write-Warning -Prefix $PREFIX -Message "Pasta nao encontrada no template: $RelativeFolder (ignorado)"
        return
    }

    if (Test-Path $dstFolder) {
        Write-Step -Prefix $PREFIX -Message "  [REMOVER] $RelativeFolder\"
        if (-not $DryRun) {
            Remove-Item $dstFolder -Recurse -Force
        }
    }

    Write-Step -Prefix $PREFIX -Message "  [COPIAR]  $RelativeFolder\"
    if (-not $DryRun) {
        Copy-Item $srcFolder $ProjectPath -Recurse -Force
    }

    $fileCount = (Get-ChildItem $srcFolder -Recurse -File).Count
    $script:CopiedCount += $fileCount
}

function Sync-TemplateFile {
    param(
        [string]$RelativePath
    )

    $src = Join-Path $TEMPLATE_PATH $RelativePath
    $dst = Join-Path $ProjectPath $RelativePath

    if (-not (Test-Path $src)) {
        Write-Warning -Prefix $PREFIX -Message "Arquivo nao encontrado no template: $RelativePath (ignorado)"
        return
    }

    if (Test-Path $dst) {
        Write-Step -Prefix $PREFIX -Message "  [REMOVER] $RelativePath"
        if (-not $DryRun) {
            Remove-Item $dst -Force
        }
    }

    $dstDir = Split-Path $dst -Parent
    if (-not (Test-Path $dstDir)) {
        if (-not $DryRun) {
            New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
        }
    }

    Write-Step -Prefix $PREFIX -Message "  [COPIAR]  $RelativePath"
    if (-not $DryRun) {
        Copy-Item $src $dst -Force
    }

    $script:CopiedCount++
}

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Etapa 1: Pasta .vscode (configuracao VSCode + scripts de automacao)
# Remove pasta do destino e copia do template integralmente
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

Write-Subheader "Etapa 1/4 | Configuracao VSCode (.vscode\)"
Sync-TemplateFolder -RelativeFolder ".vscode"

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Etapa 2: Pasta .claude (skills e configuracao do Claude Code)
# Remove pasta do destino e copia do template integralmente
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

Write-Subheader "Etapa 2/4 | Claude Code (.claude\)"
Sync-TemplateFolder -RelativeFolder ".claude"

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Etapa 3: CLAUDEs (raiz + camadas) — cada arquivo removido e copiado individualmente
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

Write-Subheader "Etapa 3/5 | CLAUDEs e arquivos raiz"
Sync-TemplateFile -RelativePath "CLAUDE.md"
Sync-TemplateFile -RelativePath "src\CLAUDE.md"
Sync-TemplateFile -RelativePath "scripts\CLAUDE.md"
Sync-TemplateFile -RelativePath "tests\CLAUDE.md"
Sync-TemplateFile -RelativePath "utils\CLAUDE.md"
Sync-TemplateFile -RelativePath "start-services.bat"

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Etapa 4: Fixtures de teste universais (tests/conftest.py)
# Contem: require_redis (Redis Cloud), isolated_test_dirs, test_env_vars, set_test_env_vars
# NAO contem logica especifica de projeto (temp_dirs e _reset_all_singletons sao TODOs a adaptar)
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

Write-Subheader "Etapa 4/5 | Fixtures de teste universais (tests\conftest.py)"
Sync-TemplateFile -RelativePath "tests\conftest.py"

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Etapa 5: Utilitarios portaveis (utils/*.py — todos)
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

Write-Subheader "Etapa 5/5 | Utilitarios portaveis (utils\*.py)"
$utilFiles = Get-ChildItem (Join-Path $TEMPLATE_PATH "utils") -Filter "*.py" -File
foreach ($f in $utilFiles) {
    Copy-TemplateFile -RelativePath "utils\$($f.Name)"
}

# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Sumario
# ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host ("═" * $script:DELIMITER_WIDTH) -ForegroundColor Green

if ($DryRun) {
    Write-Host "DRY-RUN concluido: $($script:CopiedCount) arquivo(s) seriam copiados (nenhum alterado)" -ForegroundColor Yellow
} else {
    Write-Success -Prefix $PREFIX -Message "$($script:CopiedCount) arquivo(s) copiados para $ProjectName"
    Write-Host ""
    Write-Step -Prefix $PREFIX -Message "Proximos passos:"
    Write-Step -Prefix $PREFIX -Message "  1. Revisar alteracoes: git diff"
    Write-Step -Prefix $PREFIX -Message "  2. Commitar: git add -A && git commit -m 'chore: sync arquivos universais do template'"
}

Write-Host ("═" * $script:DELIMITER_WIDTH) -ForegroundColor Green