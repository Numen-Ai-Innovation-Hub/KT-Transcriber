# Migration Plan: KT Transcriber

## Domínios identificados

- **kt_ingestion**: `tldv_client.py`, `json_consolidator.py`, `smart_processor.py`
  — Ingestão de reuniões via TL:DV API, consolidação de JSONs, processamento inteligente em duas fases
- **kt_indexing**: `chunk_processor.py`, `text_chunker.py`, `video_normalizer.py`,
  `llm_metadata_extractor.py`, `file_generator.py`, `chromadb_manager.py`, `embedding_generator.py`
  — Pipeline de chunking, normalização, extração de metadados via LLM, indexação no ChromaDB
- **kt_search**: `search_engine.py`, `query_enricher.py`, `query_classifier.py`,
  `chunk_selector.py`, `dynamic_client_manager.py`, `insights_agent.py`, `search_utils.py`
  — RAG pipeline: enrich → classify → chromadb → discovery → selection → insights

## Config necessária

- `settings.py`: Adicionar todas as variáveis do legado — `TLDV_API_KEY`, `OPENAI_API_KEY`,
  `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL`, `OPENAI_MAX_TOKENS`, `CHROMA_COLLECTION_NAME`,
  manter `REDIS_HOST/PORT/PASSWORD/DB` já existentes
- `providers.py` + `active.py`: **NÃO criar** — projeto usa só OpenAI sem troca de provider via UI em runtime
- `data/`: Criar subpastas `transcriptions/` (JSONs TL:DV), `vector_db/` (ChromaDB),
  `sqlite_db/` (hash_manager — já padrão do template)

## Dependências a adicionar

- `chromadb==1.0.0` (upgrade crítico de 0.5.20 — re-ingestão de dados obrigatória)
- Verificar versões atuais de: `openai`, `httpx`, `streamlit`, `arq`, `redis`
- Remover: `setuptools` como build backend (usar hatchling do template)

## Decisões arquiteturais obrigatórias

- **chromadb 0.5.20 → 1.x** (`/migrate-infra` adiciona dep; `/migrate-domain` reescreve `store.py`
  sem `IncludeEnum`; usar `include=["documents", "metadatas", "distances"]` como strings; re-ingestão obrigatória)
- **`src/core/` não-padrão → `src/<domínio>/`** (`/migrate-domain` reestrutura)
- **`config/config.py` raiz + 3 `config.py` de domínio com paths hardcoded** (incluindo path WSL absoluto
  em `rag/config.py`) → consolidar em `src/config/settings.py` + `<domínio>_constants.py` (`/migrate-infra`)
- **`logging.basicConfig()` + `KTLogger` customizado** → `LoggerManager.get_logger(__name__)` (`/migrate-domain`)
- **`openai.OpenAI()` direto para completions** (metadata extractor, query enricher, classifier, insights)
  → `utils/llm_manager.py` via `src/services/llm_service.py` (`/migrate-domain`)
- **`openai.Embeddings` + pickle cache** → `chromadb.utils.embedding_functions.OpenAIEmbeddingFunction`;
  ChromaDB PersistentClient gerencia; cache pickle eliminado (`/migrate-domain`)
- **`arq_worker.py` em `src/core/infrastructure/`** → `src/tasks/arq_worker.py` (`/migrate-api`)
- **`redis_client.py` ad-hoc** → `src/services/redis_service.py` singleton thread-safe (`/migrate-api`)
- **`utils/logger_setup.py` KT** → substituir pelo template (LoggerManager) (`/migrate-infra`)
- **`utils/exception_setup.py` KT** → template + mover subclasses para `src/<domínio>/` (`/migrate-domain`)
- **`src/api/exceptions.py` (KTAPIError)** → remover; usar `ApplicationError` diretamente (`/migrate-domain`)
- **`providers.py` + `active.py`** → remover do projeto destino (não necessários) (`/migrate-infra`)
- **`utils/string_helpers.py`** → split: genérico → `utils/`; domínio → `src/helpers/kt_helpers.py` (`/migrate-domain`)
- **`utils/rag_templates.py`** → `src/kt_search/kt_search_constants.py` (`/migrate-domain`)
- **`dashboard.py` Streamlit** → manter na raiz (padrão correto) (`/migrate-api`)
- **`pyproject.toml`** sem `pythonpath = ["."]` nem markers `smoke`/`e2e` → adicionar (`/migrate-infra`)
- **`create_user_db.py` na raiz** → `scripts/create_user_db.py` (`/migrate-infra`)

## Checklist de execução

- [ ] /migrate-infra
- [ ] /migrate-domain
- [ ] /migrate-api
- [ ] /migrate-tests
- [ ] /audit-project
