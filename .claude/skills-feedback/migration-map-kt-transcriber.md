# Migration Map: KT Transcriber

| Arquivo original | Função/Classe | Destino no template | Status |
|-----------------|---------------|---------------------|--------|
| `config/config.py` | Settings, TLDVConfig, OpenAIConfig, RedisConfig, ARQConfig, ChromaDBConfig, ProcessingConfig, ServerConfig, CacheConfig, LoggingConfig | `src/config/settings.py` | ❌ |
| `dashboard.py` | Dashboard Streamlit (frontend) | Raiz (manter) | ❌ |
| `create_user_db.py` | Script criação de usuários | `scripts/create_user_db.py` | ❌ |
| `utils/exception_setup.py` | ApplicationError + subclasses de domínio | `utils/exception_setup.py` (template) + subclasses → `src/<domínio>/` | ❌ |
| `utils/logger_setup.py` | KTLogger, PerformanceTracker, get_logger(), setup_logging() | Substituir por `utils/logger_setup.py` (template — LoggerManager) | ❌ |
| `utils/string_helpers.py` | normalize_unicode(), slugify(), clean_filename(), truncate(), count_words(), normalize_whitespace(), sanitize_metadata_value() | `utils/string_helpers.py` | ❌ |
| `utils/string_helpers.py` | build_meeting_key(), build_job_key(), extract_video_name_from_path(), mask_api_key() | `src/helpers/kt_helpers.py` | ❌ |
| `utils/rag_templates.py` | RAGPipelineTemplates | `src/kt_search/kt_search_constants.py` | ❌ |
| `src/api/main.py` | FastAPI app, lifespan, global handlers | `src/api/main.py` (atualizar) | ❌ |
| `src/api/exceptions.py` | KTAPIError | Remover — usar ApplicationError diretamente | ❌ |
| `src/api/routers/health.py` | Health router | `src/api/routers/health.py` (manter/atualizar) | ❌ |
| `src/api/routers/jobs.py` | get_job_status() | `src/api/routers/jobs.py` (atualizar imports) | ❌ |
| `src/api/routers/meetings.py` | Meetings endpoints | `src/api/routers/meetings.py` (atualizar) | ❌ |
| `src/api/routers/search.py` | Search endpoints | `src/api/routers/search.py` (atualizar) | ❌ |
| `src/api/schemas/job.py` | JobStatusResponse | `src/api/schemas/job.py` (manter) | ❌ |
| `src/api/schemas/meeting.py` | Meeting schemas | `src/api/schemas/meeting.py` (manter) | ❌ |
| `src/api/schemas/search.py` | Search schemas | `src/api/schemas/search.py` (manter) | ❌ |
| `src/core/infrastructure/arq_worker.py` | WorkerSettings, 9 ARQ tasks (transcription, indexing, full_pipeline, enrich, classify, chromadb, discovery, selection, insights) | `src/tasks/arq_worker.py` | ❌ |
| `src/core/infrastructure/redis_client.py` | RedisClient singleton, job tracking, phase results | `src/services/redis_service.py` | ❌ |
| `src/core/indexing/chromadb_manager.py` | ChromaDBManager | `src/kt_indexing/store.py` (unificado com embedding_generator) | ❌ |
| `src/core/indexing/embedding_generator.py` | EmbeddingGenerator, pickle cache | Integrado em `src/kt_indexing/store.py` — usar OpenAIEmbeddingFunction; eliminar pickle | ❌ |
| `src/core/indexing/config.py` | CHROMADB_CONFIG, EMBEDDING_CONFIG | Remover — paths → `src/config/settings.py`; constantes → `src/kt_indexing/kt_indexing_constants.py` | ❌ |
| `src/core/indexing/utils.py` | Utilitários de indexação | Avaliar em /migrate-domain → `src/kt_indexing/` ou `src/helpers/` | ❌ |
| `src/core/processing/chunk_processor.py` | ChunkProcessor (pipeline principal) | `src/kt_indexing/chunking_engine.py` | ❌ |
| `src/core/processing/text_chunker.py` | TextChunker, ChunkPart, chunk_text() | `src/kt_indexing/text_chunker.py` | ❌ |
| `src/core/processing/video_normalizer.py` | VideoNormalizer | `src/kt_indexing/video_normalizer.py` | ❌ |
| `src/core/processing/llm_metadata_extractor.py` | LLMMetadataExtractor | `src/kt_indexing/llm_metadata_extractor.py` | ❌ |
| `src/core/processing/file_generator.py` | FileGenerator | `src/kt_indexing/file_generator.py` | ❌ |
| `src/core/processing/config.py` | CHUNK_CONFIG, SENTENCE_PATTERNS, prompts, validation rules | Remover — paths → `src/config/settings.py`; constantes → `src/kt_indexing/kt_indexing_constants.py` | ❌ |
| `src/core/processing/utils.py` | Utilitários de processamento | Avaliar em /migrate-domain → `src/kt_indexing/` ou `src/helpers/` | ❌ |
| `src/core/rag/search_engine.py` | SearchEngine | `src/kt_search/search_engine.py` | ❌ |
| `src/core/rag/query_enrichment.py` | QueryEnricher | `src/kt_search/query_enricher.py` | ❌ |
| `src/core/rag/query_classifier.py` | QueryClassifier | `src/kt_search/query_classifier.py` | ❌ |
| `src/core/rag/chunk_selector.py` | ChunkSelector | `src/kt_search/chunk_selector.py` | ❌ |
| `src/core/rag/dynamic_client_manager.py` | DynamicClientManager, ClientInfo | `src/kt_search/dynamic_client_manager.py` | ❌ |
| `src/core/rag/insights_agent.py` | InsightsAgent | `src/kt_search/insights_agent.py` | ❌ |
| `src/core/rag/search_utils.py` | Utilitários de search | Avaliar em /migrate-domain → `src/kt_search/search_utils.py` ou `src/helpers/` | ❌ |
| `src/core/rag/config.py` | DYNAMIC_CONFIG, paths hardcoded (WSL absoluto!) | Remover — paths → `src/config/settings.py`; constantes → `src/kt_search/kt_search_constants.py` | ❌ |
| `src/core/transcription/tldv_client.py` | TLDVClient | `src/kt_ingestion/tldv_client.py` | ❌ |
| `src/core/transcription/json_consolidator.py` | JSONConsolidator | `src/kt_ingestion/json_consolidator.py` | ❌ |
| `src/core/transcription/smart_processor.py` | SmartMeetingProcessor | `src/kt_ingestion/smart_processor.py` | ❌ |
| — | (novo) LLM service re-export | `src/services/llm_service.py` | ❌ |
| — | (novo) kt_ingestion __init__ + constants | `src/kt_ingestion/kt_ingestion_constants.py` | ❌ |
| — | (novo) kt_indexing __init__ + constants | `src/kt_indexing/kt_indexing_constants.py` | ❌ |
| — | (novo) kt_search __init__ + constants | `src/kt_search/kt_search_constants.py` | ❌ |
| — | (novo) kt_helpers | `src/helpers/kt_helpers.py` | ❌ |

Status: `✅` correto | `⚠️` local não-padrão | `❌` pendente/não migrado
