# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# VALIDATE PROJECT STRUCTURE - Pre-commit Hook
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Valida estrutura obrigatória de pastas e arquivos do template.
# Impede commit se algum elemento obrigatório estiver faltando.
#
# Uso: powershell -ExecutionPolicy Bypass -File validate-structure.ps1
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

param(
    [switch]$Verbose = $false
)

$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"
$PROJECT_ROOT = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# DEFINIÇÃO DE ESTRUTURA OBRIGATÓRIA
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

$REQUIRED_STRUCTURE = @{
    # Pastas raiz obrigatórias
    Directories = @(
        "data",
        "docs",
        "logs",
        "scripts",
        "src",
        "tests",
        "utils"
    )

    # Arquivos raiz obrigatórios
    Files = @(
        ".env.example",
        ".gitignore",
        ".pre-commit-config.yaml",
        "pyproject.toml",
        "CLAUDE.md"
    )

    # Subpastas src/ obrigatórias
    SrcDirectories = @(
        "src\api",
        "src\api\routers",
        "src\config",
        "src\db",
        "src\helpers",
        "src\services",
        "src\tasks"
    )

    # Arquivos src/config/ obrigatórios
    # providers.py e active.py são OPCIONAIS — apenas se o projeto precisar de troca de provider LLM em runtime via UI
    ConfigFiles = @(
        "src\config\settings.py",
        "src\config\startup.py"
    )

    # CLAUDEs obrigatórios (estrutura consolidada)
    ClaudeFiles = @(
        "src\CLAUDE.md",
        "scripts\CLAUDE.md",
        "tests\CLAUDE.md",
        "utils\CLAUDE.md"
    )
}

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host ("═" * 120) -ForegroundColor Cyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host ("═" * 120) -ForegroundColor Cyan
}

function Write-Subheader {
    param([string]$Message)
    Write-Host ""
    Write-Host ("─" * 120) -ForegroundColor Gray
    Write-Host $Message -ForegroundColor White
    Write-Host ("─" * 120) -ForegroundColor Gray
}

function Test-PathExists {
    param(
        [string]$Path,
        [string]$Type  # "Directory" ou "File"
    )

    $FullPath = Join-Path $PROJECT_ROOT $Path
    $Exists = Test-Path $FullPath -PathType $Type

    if ($Verbose) {
        $Status = if ($Exists) { "✓" } else { "✗" }
        $Color = if ($Exists) { "Green" } else { "Red" }
        Write-Host "  $Status $Path" -ForegroundColor $Color
    }

    return $Exists
}

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# VALIDAÇÃO PRINCIPAL
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

Write-Header "VALIDAÇÃO DE ESTRUTURA DO PROJETO"
Write-Host "Projeto: $PROJECT_ROOT" -ForegroundColor Gray

$MissingItems = @()

# Validar pastas raiz
Write-Subheader "Validando pastas raiz obrigatórias"
foreach ($Dir in $REQUIRED_STRUCTURE.Directories) {
    if (-not (Test-PathExists -Path $Dir -Type "Container")) {
        $MissingItems += "Pasta: $Dir"
    }
}

# Validar arquivos raiz
Write-Subheader "Validando arquivos raiz obrigatórios"
foreach ($File in $REQUIRED_STRUCTURE.Files) {
    if (-not (Test-PathExists -Path $File -Type "Leaf")) {
        $MissingItems += "Arquivo: $File"
    }
}

# Validar subpastas src/
Write-Subheader "Validando subpastas src/ obrigatórias"
foreach ($Dir in $REQUIRED_STRUCTURE.SrcDirectories) {
    if (-not (Test-PathExists -Path $Dir -Type "Container")) {
        $MissingItems += "Pasta: $Dir"
    }
}

# Validar arquivos src/config/
Write-Subheader "Validando arquivos src/config/ obrigatórios"
foreach ($File in $REQUIRED_STRUCTURE.ConfigFiles) {
    if (-not (Test-PathExists -Path $File -Type "Leaf")) {
        $MissingItems += "Arquivo: $File"
    }
}

# Validar CLAUDEs específicos
Write-Subheader "Validando CLAUDEs específicos obrigatórios"
foreach ($File in $REQUIRED_STRUCTURE.ClaudeFiles) {
    if (-not (Test-PathExists -Path $File -Type "Leaf")) {
        $MissingItems += "Arquivo: $File"
    }
}

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# RESULTADO
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

Write-Host ""
Write-Host ("═" * 120) -ForegroundColor Cyan

if ($MissingItems.Count -eq 0) {
    Write-Host "✓ ESTRUTURA VÁLIDA - Todos os elementos obrigatórios estão presentes" -ForegroundColor Green
    Write-Host ("═" * 120) -ForegroundColor Cyan
    exit 0
}
else {
    Write-Host "✗ ESTRUTURA INVÁLIDA - Faltando $($MissingItems.Count) elemento(s) obrigatório(s)" -ForegroundColor Red
    Write-Host ("═" * 120) -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Elementos faltando:" -ForegroundColor Yellow
    foreach ($Item in $MissingItems) {
        Write-Host "  - $Item" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "AÇÃO NECESSÁRIA:" -ForegroundColor Yellow
    Write-Host "  1. Adicione os elementos faltando antes de fazer commit" -ForegroundColor White
    Write-Host "  2. Consulte CLAUDE.md raiz para ver estrutura completa obrigatória" -ForegroundColor White
    Write-Host "  3. Execute novamente: pre-commit run validate-structure" -ForegroundColor White
    Write-Host ""
    exit 1
}