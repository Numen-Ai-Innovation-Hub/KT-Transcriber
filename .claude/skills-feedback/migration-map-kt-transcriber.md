# Migration Map: KT Transcriber

> **Status final:** Migração concluída em 2026-02-25. Todos os itens abaixo estão ✅.
> Legenda: `✅` migrado e validado | `➖` descartado (não necessário) | `🔀` consolidado em outro destino

| Arquivo original | Função/Classe | Destino no template | Status |
|-----------------|---------------|---------------------|--------|
| `config/config.py` | Settings, TLDVConfig, OpenAIConfig, RedisConfig, ARQConfig, ChromaDBConfig, ProcessingConfig, ServerConfig, CacheConfig, LoggingConfig | `src/config/settings.py` | ✅ |
| `dashboard.py` | Dashboard Streamlit (frontend) | Raiz (mantido) | ✅ |
| `create_user_db.py` | Script criação de usuários | `scripts/` | ✅ |
| `utils/exception_setup.py` | ApplicationError | `utils/exception_setup.py` (template) | ✅ |
| `utils/logger_setup.py` | KTLogger customizado | Substituído por `utils/logger_setup.py` (LoggerManager do template) | ✅ |
| `utils/string_helpers.py` | Helpers genéricos (normalize, slugify, etc.) | `utils/string_helpers.py` | ✅ |
| `utils/string_helpers.py` | Helpers de domínio KT (build_meeting_key, etc.) | `src/helpers/kt_helpers.py` | ✅ |
| `utils/rag_templates.py` | RAGPipelineTemplates | `src/kt_search/kt_search_constants.py` | ✅ |
| `src/api/main.py` | FastAPI app, lifespan, global handlers | `src/api/main.py` (atualizado com ARQ pool + routers KT) | ✅ |
| `src/api/exceptions.py` | KTAPIError | ➖ Removido — usar `ApplicationError` diretamente | ✅ |
| `src/api/routers/health.py` | Health router | `src/api/routers/health.py` | ✅ |
| `src/api/routers/jobs.py` | get_job_status() | 🔀 Integrado nos routers de domínio (status por job_id) | ✅ |
| `src/api/routers/meetings.py` | Meetings endpoints | 🔀 `src/api/routers/kt_ingestion_router.py` | ✅ |
| `src/api/routers/search.py` | Search endpoints | 🔀 `src/api/routers/kt_search_router.py` | ✅ |
| `src/api/schemas/` | Job, Meeting, Search schemas | 🔀 `src/api/schemas/kt_schemas.py` (5 modelos Pydantic v2) | ✅ |
| `src/core/infrastructure/arq_worker.py` | WorkerSettings, 9 ARQ tasks | `src/tasks/arq_worker.py` (2 tasks: kt_ingestion + kt_indexing) | ✅ |
| `src/core/infrastructure/redis_client.py` | RedisClient singleton | ➖ Substituído por ARQ pool no lifespan do FastAPI | ✅ |
| `src/core/indexing/chromadb_manager.py` | ChromaDBManager | `src/kt_indexing/chromadb_store.py` (unificado com EmbeddingGenerator) | ✅ |
| `src/core/indexing/embedding_generator.py` | EmbeddingGenerator + pickle cache | 🔀 Integrado em `src/kt_indexing/chromadb_store.py` — pickle eliminado | ✅ |
| `src/core/indexing/config.py` | CHROMADB_CONFIG, EMBEDDING_CONFIG | ➖ Paths → `settings.py`; constantes → `src/kt_indexing/kt_indexing_constants.py` | ✅ |
| `src/core/indexing/utils.py` | Utilitários de indexação | `src/kt_indexing/kt_indexing_utils.py` | ✅ |
| `src/core/processing/chunk_processor.py` | ChunkProcessor (pipeline principal) | `src/kt_indexing/indexing_engine.py` | ✅ |
| `src/core/processing/text_chunker.py` | TextChunker, ChunkPart, chunk_text() | `src/kt_indexing/text_chunker.py` | ✅ |
| `src/core/processing/video_normalizer.py` | VideoNormalizer | `src/kt_indexing/video_normalizer.py` | ✅ |
| `src/core/processing/llm_metadata_extractor.py` | LLMMetadataExtractor | `src/kt_indexing/llm_metadata_extractor.py` | ✅ |
| `src/core/processing/file_generator.py` | FileGenerator | `src/kt_indexing/file_generator.py` | ✅ |
| `src/core/processing/config.py` | CHUNK_CONFIG, SENTENCE_PATTERNS, prompts | ➖ Paths → `settings.py`; constantes → `src/kt_indexing/kt_indexing_constants.py` | ✅ |
| `src/core/processing/utils.py` | Utilitários de processamento | 🔀 `src/kt_indexing/kt_indexing_utils.py` | ✅ |
| `src/core/rag/search_engine.py` | SearchEngine (5-stage pipeline) | `src/kt_search/search_engine.py` | ✅ |
| `src/core/rag/query_enrichment.py` | QueryEnricher | `src/kt_search/query_enricher.py` | ✅ |
| `src/core/rag/query_classifier.py` | QueryClassifier | `src/kt_search/query_classifier.py` | ✅ |
| `src/core/rag/chunk_selector.py` | ChunkSelector | `src/kt_search/chunk_selector.py` | ✅ |
| `src/core/rag/dynamic_client_manager.py` | DynamicClientManager | `src/kt_search/dynamic_client_manager.py` | ✅ |
| `src/core/rag/insights_agent.py` | InsightsAgent | `src/kt_search/insights_agent.py` | ✅ |
| `src/core/rag/search_utils.py` | Utilitários de search | `src/kt_search/search_utils.py` | ✅ |
| `src/core/rag/config.py` | DYNAMIC_CONFIG + paths hardcoded WSL | ➖ Paths → `settings.py`; constantes → `src/kt_search/kt_search_constants.py` | ✅ |
| `src/core/transcription/tldv_client.py` | TLDVClient | `src/kt_ingestion/tldv_client.py` | ✅ |
| `src/core/transcription/json_consolidator.py` | JSONConsolidator | `src/kt_ingestion/json_consolidator.py` | ✅ |
| `src/core/transcription/smart_processor.py` | SmartMeetingProcessor | `src/kt_ingestion/smart_processor.py` | ✅ |
| — | (novo) LLM service re-export | `src/services/llm_service.py` | ✅ |
| — | (novo) KTIngestionService singleton | `src/services/kt_ingestion_service.py` | ✅ |
| — | (novo) KTIndexingService singleton | `src/services/kt_indexing_service.py` | ✅ |
| — | (novo) KTSearchService singleton | `src/services/kt_search_service.py` | ✅ |
| — | (novo) constants por domínio | `src/kt_ingestion/kt_ingestion_constants.py`, `src/kt_indexing/kt_indexing_constants.py`, `src/kt_search/kt_search_constants.py` | ✅ |
| — | (novo) kt_helpers | `src/helpers/kt_helpers.py` | ✅ |
| — | (novo) ARQ tasks dedicadas | `src/tasks/kt_ingestion_task.py`, `src/tasks/kt_indexing_task.py` | ✅ |
| — | (novo) Schemas Pydantic unificados | `src/api/schemas/kt_schemas.py` | ✅ |
| — | (novo) Script pipeline completo | `scripts/run_full_pipeline.py` | ✅ |
| — | (novo) Suite de testes | `tests/test_kt_ingestion.py`, `tests/test_kt_indexing.py`, `tests/test_kt_search.py`, `tests/test_smoke.py`, `tests/test_e2e.py` | ✅ |

## Decisões arquiteturais aplicadas

| Decisão | Resultado |
|---------|-----------|
| chromadb 0.5.20 → 1.5.1 | ✅ API migrada para strings (`include=["documents", ...]`), sem `IncludeEnum` |
| `src/core/` → `src/<domínio>/` | ✅ Reestruturado em `kt_ingestion/`, `kt_indexing/`, `kt_search/` |
| 4× `config.py` com paths hardcoded | ✅ Consolidados em `settings.py` + `_constants.py` por domínio |
| `KTLogger` + `logging.basicConfig` | ✅ Substituídos por `LoggerManager.get_logger(__name__)` |
| `openai.OpenAI()` direto | ✅ Via `src/services/llm_service.py` → `utils/llm_manager.py` |
| Pickle cache de embeddings | ✅ Eliminado — ChromaDB PersistentClient gerencia persistência |
| `providers.py` + `active.py` | ➖ Não criados — projeto usa só OpenAI sem troca de provider via UI |
| `KTAPIError` paralelo | ➖ Removido — usa `ApplicationError` diretamente |
| `redis_client.py` ad-hoc | ➖ Substituído por ARQ pool no lifespan |
