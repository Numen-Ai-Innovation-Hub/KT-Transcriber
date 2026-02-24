# Project: Python FastAPI Template

Template base para projetos Python + FastAPI + ARQ + Redis da AI Innovation Hub.

## Stack

- **FastAPI** (web async) + **ARQ** (filas Redis) + **Pydantic** (schemas) + **SQLAlchemy** (ORM)
- **Pre-commit hooks**: Ruff (lint/format), mypy (type check), validate-structure (pastas obrigatórias), auto-init (__init__.py)
- **Playwright**: Browser automation (Chromium)
- **Utilitários do time** (`utils/`): `logger_setup.py` (logging), `exception_setup.py` (erros), `hash_manager.py` (hashes/cache SQLite), `pdfplumber_extractor.py` (PDFs), `dpt2_extractor.py` (OCR avançado via Landing.AI), `wordcom_toolkit.py` (.docx) — futuramente pacote instalável via uv

## Configuração Multi-Provider (active.py)

Arquivo `src/config/active.py` define provider/environment ativo. UI pode alterar via `update_active_config()` + `reload_active_config()`.

```python
ACTIVE_LLM_PROVIDER = "openai"      # openai | gemini | anthropic | ollama
ACTIVE_ENVIRONMENT = "development"  # development | staging | production
```

Ideal para apps desktop/single-user. NÃO usar em multi-tenant ou microserviços stateless.

## Estrutura do Projeto

```
python-fastapi-template/
├── .vscode/scripts/        # Scripts PowerShell de setup e validação
├── data/                   # Cache, outputs, temp
├── docs/                   # Documentação adicional
├── logs/                   # Logs (criado automaticamente)
├── scripts/                # Scripts Python utilitários (ver scripts/CLAUDE.md)
├── src/                    # Código fonte (ver src/CLAUDE.md)
│   ├── api/                # INFRA: FastAPI routers e endpoints
│   ├── config/             # INFRA: active.py, providers.py, settings.py, startup.py
│   ├── db/                 # INFRA: Modelos SQLAlchemy e repositórios
│   ├── helpers/            # INFRA: Funções de suporte transversais
│   ├── services/           # INFRA: Orquestração (singletons thread-safe)
│   ├── tasks/              # INFRA: ARQ tasks assíncronas
│   └── <domínio>/          # DOMÍNIO: pastas por funcionalidade de negócio
├── tests/                  # Testes pytest (ver tests/CLAUDE.md)
├── utils/                  # Utilitários portáveis (ver utils/CLAUDE.md)
├── .env.example            # Template de credenciais
├── pyproject.toml          # Dependências e config de ferramentas
└── CLAUDE.md               # Este arquivo
```

## Pastas Obrigatórias (validadas no pre-commit)

- **Raiz:** `data/`, `docs/`, `logs/`, `scripts/`, `src/`, `tests/`, `utils/`, `.env.example`, `.gitignore`, `.pre-commit-config.yaml`, `pyproject.toml`, `CLAUDE.md`
- **src/:** `api/`, `config/`, `db/`, `helpers/`, `services/`, `tasks/`
- **src/config/:** `settings.py`, `startup.py` (obrigatórios) — `providers.py` e `active.py` opcionais (apenas se o projeto tiver seleção de provider LLM em runtime via UI)
- **Pastas de domínio** em `src/` são livres por projeto (ex: `data_pipeline/`, `analytics/`)

## Filosofia Arquitetural

- **Big-Bang Refactoring:** NEVER use temporary solutions, phased migrations, compatibility layers ou fallback logic. ALWAYS refactor completo em um step.
- **Schema-First:** ALWAYS use Pydantic schemas como source of truth. NEVER parse strings — use objetos tipados.
- **Fail-Fast:** NEVER use defaults para parâmetros obrigatórios — raise ValueError/ApplicationError. NEVER catch exceptions silently. NEVER return None/False para indicar erro.
- **File Naming:** settings.py é SOLE source of truth para paths. NEVER hardcode paths — use DIRECTORY_PATHS/FILE_PATHS.
- **DRY Validation:** Validação em 2+ lugares MUST ser centralizada em função dedicada que raises ApplicationError.
- **KISS:** NEVER add conditional logic para "descobrir" o que fazer — caller passa exatamente o necessário. Utilities são "dumb".

## Exception Handling

- **Router:** Raise ApplicationError para erros de domínio. NEVER capture Exception genérica. NEVER log errors.
- **Service:** Raise ApplicationError. Log sem stacktrace (logger.warning/error). NEVER return dict com erro.
- **Client/Integration:** Translate exceptions to ApplicationError com `raise ... from e`.
- **Global Handlers (src/api/main.py):** ONLY place para logger.exception(). Handle ApplicationError, RequestValidationError, Exception.

```python
ApplicationError(message="Msg", status_code=422, error_code="VALIDATION_ERROR", context={"field": "value"})
```

Error codes: `VALIDATION_ERROR` (422), `NOT_FOUND` (404), `SERVICE_UNAVAILABLE` (503), `QUOTA_EXCEEDED` (429), `INTERNAL_ERROR` (500)

Forbidden: `except Exception: pass`, `HTTPException` fora de routers, `logger.exception()` fora de global handlers, log duplicado entre camadas.

## Commands

**uv:** `uv sync --group dev` (sync deps), `uv add <pkg>==<ver>` (add dep), `uv add --dev <pkg>==<ver>` (add dev dep), `uv lock --upgrade` (upgrade all)
**App:** `uvicorn src.api.main:app --reload` (dev), `uvicorn src.api.main:app --host 0.0.0.0 --port 8000` (prod), `arq src.tasks.arq_worker.WorkerSettings` (worker)
**Dev:** `.venv\Scripts\ruff.exe check src utils scripts tests` (lint), `.venv\Scripts\ruff.exe format src utils scripts tests` (format), `.venv\Scripts\mypy.exe --config-file=pyproject.toml src utils scripts` (type check — NÃO inclui tests/), `uv run python -m pytest tests/ -m "not smoke and not e2e"` (unit tests), `pre-commit run --all-files` (hooks)

## Code Style

- **Naming:** `snake_case` (vars/funcs), `PascalCase` (classes), `UPPER_SNAKE_CASE` (constants), `_leading_underscore` (private)
- **Dictionary keys/JSON fields:** `snake_case` em inglês
- **Comments/Docstrings/Logs:** Português (pt-BR), Google-style
- **Class names/Technical terms:** Inglês
- **Type hints:** Python 3.10+ (`str | None`, `dict[str, Any]`, `list[str]`)
- **Imports:** (1) Standard library, (2) Third-party, (3) Local
- **Line length:** 120 chars max. Strings: f-strings exclusivamente. Quotes: double quotes.
- **NEVER** use `"..."` (ellipsis) em strings. **NEVER** use `# type: ignore` genérico — apenas `# type: ignore[import-untyped]` para libs sem stubs (ex: `langchain_*`, `win32com`).
- **Unicode:** UTF-8 enforced via `PYTHONUTF8=1` (.env) e `settings.json` ([powershell] utf8bom). Box-drawing chars permitidos (`═`, `─`, `│`). Delimiters: `"═" * 120` (títulos), `"─" * 120` (subtítulos).
- **PowerShell (.ps1):** MUST be saved com UTF-8 BOM encoding.

## Pre-commit Hooks

1. **auto-init:** Auto-generates `__init__.py` em `src/`
2. **validate-structure:** Valida pastas/arquivos obrigatórios (PowerShell)
3. **ruff check:** Linting com auto-fix (E, F, B, I, UP)
4. **ruff format:** Formatting (double quotes, 120 chars, LF)
5. **mypy:** Type checking strict (`disallow_untyped_defs`)

## Testing

- **Structure:** `tests/` (flat), `tests/fixtures/` (test data)
- **Run:** `uv run python -m pytest tests/ -m "not smoke and not e2e"` (unit, rápidos, sem infra). `uv run python -m pytest tests/ -m smoke` (stack deve estar rodando). `uv run python -m pytest tests/ -m e2e` (fluxo completo, requer stack).
- **NEVER** usar `--ignore` para excluir smoke/e2e — usar `-m "not smoke and not e2e"`. `--ignore` esconde arquivos do coverage e da descoberta.
- **Pré-requisitos smoke:** Redis Cloud configurado no `.env` (REDIS_HOST, REDIS_PORT, REDIS_PASSWORD)
- **Pré-requisitos e2e:** Redis Cloud no `.env` + `arq src.tasks.arq_worker.WorkerSettings` + `uvicorn src.api.main:app --reload`
- Se Redis não disponível: testes fazem `pytest.skip` automaticamente — não falham com erro de conexão
- **Coverage:** Always active (`--cov=src --cov-branch`), HTML em `htmlcov/`

## VSCode Integration

- Terminal auto-activates `.venv` on open
- Auto-task on folder open: `ensure-environment.ps1` orchestrates complete setup
- Pre-requisitos do sistema: Windows Terminal, winget (App Installer)

## CLAUDEs Especializados

- [src/CLAUDE.md](src/CLAUDE.md) — Infraestrutura + domínios (api/, config/, db/, helpers/, services/, tasks/)
- [scripts/CLAUDE.md](scripts/CLAUDE.md) — Scripts Python pontuais
- [tests/CLAUDE.md](tests/CLAUDE.md) — Testes pytest
- [utils/CLAUDE.md](utils/CLAUDE.md) — Utilitários portáveis

## Implementation Checklist

- [ ] Router does NOT capture Exception or log errors
- [ ] Service raises ApplicationError for domain errors
- [ ] Client uses `raise ... from e` always
- [ ] `logger.exception()` ONLY in global handler
- [ ] No `except Exception: pass`
- [ ] No `HTTPException` outside router
- [ ] Type hints on all functions (mypy strict)
- [ ] Docstrings in Portuguese (Google-style)
- [ ] Run `pre-commit run --all-files` before committing