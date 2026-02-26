# Where Was I — KT-Transcriber

Guia de retomada de trabalho. Para qualquer pessoa ou IA que precise continuar o desenvolvimento
após uma pausa. Atualizado em: 2026-02-26.

Veja também: [STRUCTURE.md](STRUCTURE.md) | [FLOW.md](FLOW.md) | [REFERENCE.md](REFERENCE.md)

---

## Estado Atual do Projeto

### O que está implementado e estável

| Componente | Status | Observações |
|-----------|--------|-------------|
| **Domínio kt_ingestion** | ✅ Estável | TLDVClient + SmartProcessor + JSONConsolidator funcionando |
| **Domínio kt_indexing** | ✅ Estável | Slug semântico, LLM metadata, ChromaDB sem None |
| **Domínio kt_search** | ✅ Estável | Pipeline RAG 5 estágios, validated E2E |
| **API FastAPI** | ✅ Estável | 5 routers registrados, lifespan com ARQ pool |
| **Pipeline assíncrono RAG** | ✅ Estável | 6 tasks ARQ + polling com early-exit |
| **Pipeline Seletivo** | ✅ Implementado | `kt_pipeline_router` + `kt_selective_pipeline_task` criados |
| **UI Streamlit** | ✅ Estável | Aba Consulta + aba Pipeline Seletivo funcionando |
| **Testes unitários** | ✅ 360 passando | 0 falhas, ruff 0 erros, mypy 0 erros (57 source files) |
| **Base ChromaDB piloto** | ✅ Funcional | 20 chunks do KT "Ajuste no PO de frete" (DEXCO) |

### Piloto em andamento

O sistema está em piloto para o cliente **DEXCO**. Apenas vídeos DEXCO são indexados.
Regra de `client_name`: bracket `[DEXCO]` → `"DEXCO"`, sem bracket → fallback `"DEXCO"`.

### Pendências conhecidas

| Item | Prioridade | Localização |
|------|-----------|-------------|
| Smoke tests (8 testes) | Média | `tests/test_smoke.py` — requerem Redis Cloud no `.env` |
| E2E tests (5 testes) | Média | `tests/test_e2e.py` — requerem stack completa rodando |
| Cobertura `search_engine.py` (46%) | Baixa | Limitada estruturalmente (ChromaDB+OpenAI em `__init__`) |
| Cobertura `insights_agent.py` (15%) | Baixa | Limitada estruturalmente (mesmo motivo) |
| Cobertura `chromadb_search_executor.py` (4%) | Baixa | Limitada estruturalmente |
| Decomposição `query_classifier.py` (~1321 linhas) | Baixa | Candidato a decomposição futura |
| Testes unitários: QueryClassifier, QueryEnricher, ChunkSelector, DynamicClientManager | Baixa | Sem cobertura unitária dedicada |
| DeprecationWarning E2E: `HTTP_422_UNPROCESSABLE_ENTITY` | Muito baixa | Renomear para `HTTP_422_UNPROCESSABLE_CONTENT` |

---

## Entry Points

### Aplicação completa (modo produção/desenvolvimento)

```bash
# 1. API FastAPI (porta 8000)
uvicorn src.api.main:app --reload

# 2. ARQ Worker (processa tasks da fila Redis)
arq src.tasks.arq_worker.WorkerSettings

# 3. UI Streamlit (porta 8501) — consome API em localhost:8000
streamlit run scripts/app.py
```

Os três processos devem estar rodando simultaneamente para a UI funcionar completamente.

### Scripts CLI (execução pontual)

```bash
# Pipeline completo: ingestion + indexação + validação
uv run python scripts/run_full_pipeline.py

# Pipeline completo com limpeza prévia
uv run python scripts/run_full_pipeline.py --force-clean

# Pipeline seletivo interativo: escolhe reuniões por índice
uv run python scripts/run_select_pipeline.py

# Busca RAG direta (sem API/Streamlit)
uv run python -c "
from src.config.startup import initialize_application
from src.kt_search.search_cli import run_single_search
initialize_application()
run_single_search('quais problemas foram encontrados no KT de EWM?')
"
```

---

## Como Rodar e Testar

### Sincronizar dependências

```bash
uv sync --group dev
```

### Rodar a aplicação em desenvolvimento

```bash
uvicorn src.api.main:app --reload
arq src.tasks.arq_worker.WorkerSettings
streamlit run scripts/app.py
```

### Testes

```bash
# Unit tests (rápidos, zero infra externa)
uv run python -m pytest tests/ -m "not smoke and not e2e"

# Smoke tests (requer Redis Cloud no .env)
uv run python -m pytest tests/ -m smoke

# E2E tests (requer FastAPI + Redis + ARQ Worker rodando)
uv run python -m pytest tests/ -m e2e

# Coverage report
uv run python -m pytest tests/ -m "not smoke and not e2e" --cov=src --cov-branch --cov-report=term-missing
```

### Qualidade de código

```bash
# Lint (src, utils, scripts, tests)
.venv\Scripts\ruff.exe check src utils scripts tests

# Format
.venv\Scripts\ruff.exe format src utils scripts tests

# Type check (NÃO inclui tests/)
.venv\Scripts\mypy.exe --config-file=pyproject.toml src utils scripts

# Todos os pre-commit hooks
pre-commit run --all-files
```

### Adicionar dependências

```bash
uv add <pkg>==<ver>         # dependência de produção
uv add --dev <pkg>==<ver>   # dependência de desenvolvimento
uv lock --upgrade           # upgrade de todas as deps
```

---

## Onde Está Cada Tipo de Lógica

### API e endpoints HTTP
→ `src/api/routers/` — 5 routers: health, kt_ingestion, kt_indexing, kt_search, kt_pipeline
→ `src/api/main.py` — FastAPI app, lifespan, global handlers
→ `src/api/schemas/kt_schemas.py` — todos os schemas Pydantic

### Lógica de negócio (domínios)
→ `src/kt_ingestion/` — download e consolidação de transcrições TL:DV
→ `src/kt_indexing/` — chunking, embedding e indexação no ChromaDB
→ `src/kt_search/` — pipeline RAG de busca semântica (5 estágios + 7 componentes)

### Orquestração (singletons)
→ `src/services/kt_ingestion_service.py` — facade para kt_ingestion
→ `src/services/kt_indexing_service.py` — facade para kt_indexing
→ `src/services/kt_search_service.py` — facade para kt_search (expõe `components` para tasks ARQ)
→ `src/services/llm_service.py` — re-export do llm_manager (único ponto de import no projeto)

### Tasks assíncronas (filas Redis)
→ `src/tasks/arq_worker.py` — WorkerSettings + 10 functions registradas
→ `src/tasks/kt_ingestion_task.py` — download via ARQ
→ `src/tasks/kt_indexing_task.py` — indexação via ARQ
→ `src/tasks/kt_selective_pipeline_task.py` — pipeline seletivo completo via ARQ
→ `src/tasks/kt_search_task.py` — 6 estágios do pipeline RAG assíncrono

### Configuração
→ `src/config/settings.py` — DIRECTORY_PATHS, FILE_PATHS, variáveis de ambiente (fonte de verdade)
→ `src/config/startup.py` — side effects de inicialização (diretórios, logging)
→ `.env` — credenciais e configurações de ambiente (não versionado)

### Utilitários transversais
→ `src/helpers/kt_helpers.py` — funções auxiliares usadas em 2+ domínios do projeto
→ `utils/exception_setup.py` — ApplicationError (padrão do time)
→ `utils/logger_setup.py` — LoggerManager (padrão do time)
→ `utils/hash_manager.py` — cache por hash de conteúdo em SQLite
→ `utils/llm_manager.py` — cliente LLM multi-provider

### UI e scripts de execução pontual
→ `scripts/app.py` — UI Streamlit (Consulta + Pipeline Seletivo)
→ `scripts/run_full_pipeline.py` — pipeline completo CLI
→ `scripts/run_select_pipeline.py` — pipeline seletivo CLI

### Testes
→ `tests/` — flat: unit tests (`test_*.py`), smoke (`test_smoke.py`), E2E (`test_e2e.py`)
→ `tests/conftest.py` — fixtures globais (require_redis, tmp dirs)

---

## Configuração de Ambiente

Arquivo `.env` obrigatório na raiz. Variáveis essenciais:

```bash
# Redis Cloud (obrigatório para ARQ + testes smoke/e2e)
REDIS_HOST=<host>
REDIS_PORT=6380
REDIS_PASSWORD=<senha>
REDIS_DB=0

# OpenAI (obrigatório para indexação e busca)
OPENAI_API_KEY=<chave>
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# TL:DV (obrigatório para ingestion)
TLDV_API_KEY=<chave>
TLDV_BASE_URL=pasta.tldv.io

# ChromaDB
CHROMA_COLLECTION_NAME=kt_transcriptions
```

Consulte `.env.example` para a lista completa com instruções por variável.

---

## Decisões Arquiteturais Relevantes

| Decisão | Razão |
|---------|-------|
| ChromaDB `PersistentClient` (nunca HttpClient) | Padrão do time — sem servidor separado |
| Embedding híbrido 80%/20% | Melhora recall para queries de metadados (módulo SAP, cliente) |
| Pipeline RAG em 6 tasks ARQ separadas | Permite progress bar em tempo real na UI |
| `ctx["redis"]` para estado entre estágios | Tasks ARQ são stateless — Redis é o mecanismo de passagem de dados |
| Slug semântico `{cliente}_{modulo}_{data}` | Unicidade + legibilidade nos chunks indexados |
| `_clean_metadata` remove `None` antes de inserir | ChromaDB rejeita `None` como MetadataValue (bug descoberto em produção) |
| `force_clean()` limpa `vector_db/` **e** `chunks/` | Chunks obsoletos em disco causam confusão na auditoria |
| Lazy import do service dentro das tasks ARQ | Evita inicialização de ChromaDB/OpenAI no processo do worker antes de precisar |
| `poll_delay=0.5` explícito no WorkerSettings | Default do ARQ pode variar entre versões |
