# src/ - Código Fonte Principal

Duas categorias de pastas: **infraestrutura** (obrigatórias, validadas no pre-commit) e **domínio** (criadas por projeto, nomeadas pela funcionalidade de negócio). Nunca misture responsabilidades entre camadas.

## Pastas de Infraestrutura

### api/ — Camada HTTP (FastAPI)

Recebe requests, valida entrada via Pydantic, delega para services, retorna responses.

- Endpoints com `APIRouter(prefix="/v1/...", tags=[...])`
- Schemas Pydantic como request/response em `api/schemas/`
- Raise `ApplicationError` para erros de domínio
- NEVER capture Exception genérica — global handlers em `api/main.py` tratam
- NEVER faz `logger.exception()` — exclusivo dos global handlers
- NEVER implementa lógica de negócio — delegar para `src/services/`

Global Exception Handlers (somente `api/main.py`): `ApplicationError` → JSON com error_code/message/context, `RequestValidationError` → 422, `Exception` → 500 genérico.

**Lifespan pattern** (`api/main.py`): ALWAYS chamar `initialize_application()` de `src.config.startup` no startup. Depois descomentar `get_<nome>_service().warm_up()` para services com modelos pesados. ARQ pool em `app.state.arq_pool` se usar tasks assíncronas.

### config/ — Configuração Centralizada

| Arquivo | Responsabilidade | Quando |
|---------|-----------------|--------|
| `settings.py` | Constantes, paths, valores do `.env` — ZERO lógica, `load_dotenv()` no topo | Sempre |
| `startup.py` | ÚNICO com side effects: cria diretórios, configura logging — silencia loggers barulhentos (httpx, httpcore, etc.) | Sempre |
| `providers.py` | `@dataclass(frozen=True)` para providers — validação fail-fast | Opcional* |
| `active.py` | `ACTIVE_LLM_PROVIDER` e `ACTIVE_ENVIRONMENT` (mutável por UI) | Opcional* |

*`providers.py` e `active.py` apenas se o projeto precisar de troca de provider LLM em runtime via UI. Projetos com credenciais fixas não os criam.

- `settings.py` usa `Path(__file__).resolve().parent.parent.parent` para `BASE_DIR`
- Credenciais faltando → raise `ApplicationError` imediatamente (fail-fast)
- `settings.py` NÃO cria diretórios nem valida arquivos (isso é `startup.py`)

#### DIRECTORY_PATHS — Entradas por Stack

`DIRECTORY_PATHS` em `settings.py` deve conter apenas as pastas efetivamente usadas pelo projeto. Entradas por stack:

| Stack | Entradas obrigatórias | Entradas a remover |
|-------|-----------------------|--------------------|
| PKL/arquivos físicos | `hashed`, `processed`, `chunked`, `sqlite_db` | — |
| ChromaDB | `vector_db`, `sqlite_db` | `hashed`, `processed`, `chunked` |
| ChromaDB + auditoria | `vector_db`, `sqlite_db`, `extracted` | `hashed`, `processed`, `chunked` |

`sqlite_db` é obrigatório em qualquer projeto que use `hash_manager.py` — o HashManager persiste hashes em `data/sqlite_db/hashes.db`.
Qualquer outro banco SQLite do projeto também vai para `data/sqlite_db/`.

NEVER manter entradas não usadas — `startup.py` cria as pastas em disco, entradas fantasma criam pastas desnecessárias.

### helpers/ — Funções de Suporte Transversais

Funções auxiliares de formatação, parsing, conversão, validações reutilizáveis. NÃO é onde vai lógica core de domínio.

- Funções de formatação/parsing/conversão (ex: `format_cpf`, `sanitize_filename`)
- Validações reutilizáveis entre múltiplos domínios
- Funções puras quando possível
- NEVER contém lógica core de negócio — isso vai em pastas de domínio
- NEVER orquestra fluxo — isso é `src/services/`

### services/ — Orquestração de Negócio

Coordena domínios, helpers, repositories e APIs externas. Thread-safe singletons obrigatórios.

- Padrão singleton com `threading.Lock()` — instância única por processo
- `src/services/__init__.py` exporta TODOS os getters: `from .x_service import XService, get_x_service` + `__all__`
- Raise `ApplicationError` para erros de domínio
- Log sem stacktrace: `logger.warning()` ou `logger.error()`
- NEVER retorna dict com erro — always raise exception
- NEVER usa `logger.exception()` — exclusivo dos global handlers
- NEVER importa de `src/api/`

#### llm_service.py — Obrigatório em projetos com LLM

Quando `ACTIVE_LLM_PROVIDER` estiver configurado, criar `src/services/llm_service.py` como ponto único de re-export do `utils/llm_manager.py` para o projeto:

```python
# src/services/llm_service.py
from utils.llm_manager import (
    LLMUsageTrackingCallback,
    get_structured_output_method,
    llm_client_manager,
    llm_monitor,
)

__all__ = [
    "LLMUsageTrackingCallback",
    "get_structured_output_method",
    "llm_client_manager",
    "llm_monitor",
]
```

Services de domínio importam de `src.services.llm_service` — NEVER importam `utils.llm_manager` diretamente.

### tasks/ — ARQ Tasks Assíncronas

Jobs de longa duração processados em background via Redis/ARQ.

- Funções `async def` com parâmetros serializáveis (str, int, dict, list)
- Registradas em `WorkerSettings.functions` no `arq_worker.py`
- Delegam lógica para `src/services/`
- NEVER usa `asyncio.run()` — tasks já são async

## Pastas de Domínio (Criadas por Projeto)

Contêm a **lógica core** do sistema — engines, processors, agents, integrações especializadas. Nomeadas pela funcionalidade de negócio (ex: `data_pipeline/`, `analytics/`, `integration/`, `reporting/`).

- Nomeadas pela **funcionalidade**, nunca por tipo técnico
- Podem ter subpasta `schemas/` com Pydantic models específicos
- São importadas por `src/services/` para orquestração
- NEVER importam de `src/api/` ou `src/services/` (fluxo unidirecional)
- NEVER expõem endpoints HTTP diretamente
- Não são validadas pelo pre-commit (são livres por projeto)

### Convenção de Nomes de Arquivos em src/<domínio>/

- Padrão: **`<função>_<tipo>.py`** (2 palavras, snake_case)
- Exemplos corretos: `extraction_service.py`, `chunking_engine.py`, `embedding_engine.py`, `rag_constants.py`
- NEVER usar nomes de uma palavra: `extractor.py`, `chunker.py`, `constants.py`
- Arquivos `constants.py` → renomear para `<domínio>_constants.py`
- Dois providers da mesma interface (ex: pdfplumber + DPT-2) ficam num **único arquivo** com duas classes — separar apenas se > 300-400 linhas
- Orquestrador LLM do domínio pertence a `src/services/<domínio>_service.py`, NEVER dentro da pasta de domínio

### Estrutura de Referência: src/rag/

Exemplo canônico de estrutura de domínio RAG:

```
src/rag/
├── extraction_service.py   # Extratores de PDF (pdfplumber + DPT-2 na mesma classe base)
├── chunking_engine.py      # Motor de chunking com estratégias configuráveis
├── embedding_engine.py     # EmbeddingEngine + get_embedding_engine() singleton
├── rag_constants.py        # Constantes de domínio (chunk_size, overlap, etc.)
└── __init__.py
```

O `RAGService` (orquestrador que chama LLM) fica em `src/services/rag_service.py`.

### ChromaDB — Versão e API

Ao adicionar ChromaDB, **não fixar versão** no `pyproject.toml`. Motivo:

- `chromadb==0.5.x` exige `tokenizers<=0.20.3`
- `sentence-transformers>=5.0` exige `tokenizers>=0.22.0`
- Conflito irresolvível → deixar `uv` resolver (resulta em `chromadb>=1.0`)

Diferença de API entre versões (breaking change):

```python
# chromadb 0.5.x (DEPRECATED)
include=[IncludeEnum.documents, IncludeEnum.metadatas, IncludeEnum.distances]

# chromadb 1.x (CORRETO)
include=["documents", "metadatas", "distances"]  # IncludeEnum removido
```

### Quando Criar Domínio vs helpers/

- Pipeline com múltiplos estágios, regras de negócio complexas, integração profunda com sistema externo → **pasta de domínio**
- Função de formatação/parsing usada por vários domínios, uma função auxiliar simples → **helpers/**
- Orquestração que coordena múltiplos domínios → **services/**

## Fluxo de Camadas

```
Request HTTP → src/api/routers/ → src/services/ → src/<domínio>/ + src/helpers/ + src/config/
```

Camadas superiores importam das inferiores. **Nunca o contrário.**