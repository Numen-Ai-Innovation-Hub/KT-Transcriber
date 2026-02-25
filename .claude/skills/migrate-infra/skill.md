# SKILL: /migrate-infra

**Propósito:** Montar a fundação do projeto — tudo que precisa existir antes de qualquer
código de negócio ser criado. Opera no projeto atual, consumindo o plano gerado pelo
`/migrate-analyze`.

**Argumento:** sem argumento

**Pré-requisito:** `/migrate-analyze` executado e `migration-plan-<projeto>.md` salvo em
`.claude/skills-feedback/`.

---

## Definições de Plataforma

Padrões obrigatórios — não negociáveis:

| Categoria | Definição | Proibido |
|-----------|-----------|---------|
| Gestão de deps | `uv add <pkg>==<ver>` (versões exatas) | `pip install`, `poetry add` |
| Redis | Redis Cloud via .env | Docker Redis, Redis local/WSL2 |
| Containerização | Nenhuma | Docker, docker-compose |
| `.gitignore` | `data/**/*` (padrão global) | entradas por subpasta |

---

## Procedimento

### FASE 1 — Ler Plano

1. Ler `.claude/skills-feedback/migration-plan-<projeto>.md`
2. Identificar: dependências a adicionar, config necessária, subpastas `data/`, decisões arquiteturais obrigatórias
3. Para cada decisão arquitetural obrigatória do plano, verificar se há ação a executar nesta fase:
   - "embeddings em PKL → ChromaDB" → adicionar `chromadb` como dependência na FASE 2
   - "main.py na raiz como entry point" → remover `main.py` na FASE 1b abaixo
   - "requirements.txt presente" → remover após migrar deps para `pyproject.toml`

### FASE 1b — Remover Artefatos do Legado

Antes de qualquer outra ação, remover arquivos que não têm lugar no template:

1. **`main.py` na raiz** — se existir e o projeto usa FastAPI:
   - Entry point é exclusivamente `uvicorn src.api.main:app`
   - Remover o arquivo — não adaptar, não mover
   - Exceção: projetos CLI puro (Typer sem FastAPI) podem ter `main.py` na raiz

2. **`requirements.txt`** — se existir:
   - Deps já foram migradas para `pyproject.toml` nesta fase
   - Remover após confirmação que todas as deps estão no `pyproject.toml`

3. **Arquivos de ambiente de legado** (`setup.py`, `setup.cfg`, `Pipfile`, `Pipfile.lock`):
   - Remover — `pyproject.toml` é a única fonte de verdade

### FASE 2 — Dependências

1. Ler `pyproject.toml` do projeto atual e do legado (`requirements.txt`, `setup.py`, ou `pyproject.toml`)
2. Para cada dependência do legado ausente no projeto atual:
   - Verificar versão compatível com o stack (FastAPI, ARQ, Pydantic v2)
   - Adicionar via `uv add <pkg>==<ver>` (NUNCA `pip`)
   - Versões exatas, não ranges
3. Rodar `uv sync` e verificar sem erros

**Dependências obrigatórias por decisão arquitetural:**
- Plano tem "embeddings em PKL/numpy → ChromaDB" → adicionar `chromadb` (versão atual estável)
- Plano tem "Celery → ARQ" → verificar que `arq` e `redis` estão presentes
- Plano tem frontend Streamlit → adicionar `streamlit`; atenção: Streamlit tem loop de eventos
  próprio — services com singletons devem usar `threading.Lock()` (já é o padrão do template)

**Incompatibilidades comuns:**
- LangChain < 0.3.0 → incompatível com tenacity >= 9.x → usar `langchain>=0.3.0`
- Pydantic v1 → migrar para Pydantic v2 (modelos mudam de `BaseModel.parse_obj` para `model_validate`)
- Celery → ARQ: tasks Celery recebem `self` (bound); ARQ tasks recebem `ctx: dict[str, Any]` — assinatura diferente
- Streamlit + FastAPI no mesmo processo: não misturar — Streamlit é frontend que consome a API HTTP

### FASE 3 — Configuração

Distribuir configurações nos arquivos corretos:

**`src/config/settings.py`** (sempre existente — apenas editar):
- APENAS constantes, paths, `DIRECTORY_PATHS`, vars lidas do `.env` com `os.getenv()`
- Zero lógica, zero imports de `src/`
- Adicionar variáveis de ambiente identificadas no legado
- Redis já configurado por padrão: `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DB`

**`src/config/startup.py`** (sempre existente — apenas editar):
- ÚNICO arquivo com side effects: `mkdir`, logging, validação fail-fast de credenciais
- Atualizar `ensure_directories_exist()` se novas subpastas `data/` forem adicionadas
- `initialize_application()` chama `get_active_app_config()` apenas se `providers.py` existir

**`src/config/providers.py`** (OPCIONAL — criar apenas se necessário):
- Criar SOMENTE se o projeto precisar de **troca de provider LLM em runtime via UI**
- Conteúdo: `LLMConfig`, `EnvironmentConfig`, `AppConfig` como `@dataclass(frozen=True)`
- Factory `from_env()` com fail-fast para credenciais obrigatórias
- `get_active_app_config()`, `update_active_config()`, `reload_active_config()`
- Se NÃO necessário: credenciais ficam direto em `settings.py` como `os.getenv()`

**`src/config/active.py`** (OPCIONAL — criar apenas se `providers.py` for criado):
- `ACTIVE_LLM_PROVIDER = "openai"` — provider padrão
- `ACTIVE_ENVIRONMENT = "development"` — environment padrão
- Modificado em runtime via `update_active_config()` + `reload_active_config()`

**Pergunta guiada ao utilizador:** "O projeto precisa trocar de provider LLM em runtime via UI sem reiniciar? (sim/não)"
- Sim → criar `providers.py` + `active.py`
- Não → credenciais direto em `settings.py`, não criar os opcionais

### FASE 4 — Estrutura de Dados

1. Identificar subpastas `data/` que o projeto precisa (baseado no plano)
2. Declarar em `DIRECTORY_PATHS` em `settings.py` apenas as pastas efetivamente usadas:
   ```python
   DIRECTORY_PATHS = {
       "sqlite_db":  DATA_DIR / "sqlite_db",   # SQLite — obrigatório se usar hash_manager ou qualquer banco SQLite
       "vector_db":  DATA_DIR / "vector_db",   # ChromaDB — incluir apenas se o projeto usa embeddings
       "extracted":  DATA_DIR / "extracted",   # Auditoria de extração — incluir apenas se necessário
       # Adicionar entradas específicas do projeto aqui
       # NEVER incluir: "hashed", "processed", "chunked" (PKL legado), "hashes" (JSON legado)
   }
   ```
   Se o projeto usa `hash_manager.py`, adicionar também em `FILE_PATHS`:
   ```python
   FILE_PATHS = {
       "hashes_db": DIRECTORY_PATHS["sqlite_db"] / "hashes.db",
   }
   ```
3. Verificar que `startup.py` itera sobre `DIRECTORY_PATHS.values()` com `mkdir(exist_ok=True)`
4. Criar as subpastas físicas se não existirem

### FASE 5 — Arquivos de Ambiente

**`.gitignore`** — verificar presença de:
```
data/**/*
logs/
*.log
.env
```
Usar padrão global `data/**/*` (NUNCA por subpasta como `data/cache/`, `data/databases/`)

**`.env.example`** — sincronizar com todas as variáveis usadas em `settings.py`:
- Cada variável com comentário explicando o valor esperado
- Variáveis obrigatórias (sem default) marcadas com `# OBRIGATÓRIO`
- Variáveis com default documentam o default: `# Padrão: localhost`
- Redis obrigatório:
  ```
  REDIS_HOST=localhost
  REDIS_PORT=6379
  REDIS_PASSWORD=
  REDIS_DB=0
  ```

**`.env`** — verificar se existe. Se não existir, criar a partir de `.env.example` com valores de dev funcionais.

### FASE 6 — Validação

Executar na ordem:
1. `uv sync` — zero erros
2. `python -c "from src.config.settings import *"` — import sem crash
3. `python -c "from src.config.startup import initialize_application"` — import sem crash
4. Verificar que `src/config/` tem exatamente os arquivos corretos:
   - Obrigatórios: `settings.py`, `startup.py`, `__init__.py`
   - Opcionais (conforme decisão): `providers.py`, `active.py`

---

## FASE FINAL — Registro de Feedback

Ao concluir, registrar entrada em `.claude/skills-feedback/migrate-infra.md`:

```markdown
## [YYYY-MM-DD] Projeto: <nome>

**Dependências adicionadas:** <N>
**providers.py criado:** sim/não (motivo)
**Subpastas data/ criadas:** <lista>

**O que funcionou bem:**
- <ponto positivo>

**O que foi difícil:**
- <ponto de atrito>

**Sugestão de melhoria para esta SKILL:**
- <proposta>
```