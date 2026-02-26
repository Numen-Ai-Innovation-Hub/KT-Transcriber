# Estrutura do Projeto — KT-Transcriber

Documentação da estrutura de pastas e arquivos do projeto. Gerado por `/document-project`.

---

## `src/` — Código-fonte principal

### `src/api/` — Camada HTTP: routers, schemas e aplicação FastAPI

- **`main.py`** — Aplicação FastAPI: lifespan (startup/shutdown), registro de routers, handlers globais de exceção (ApplicationError, RequestValidationError, Exception), configuração de CORS e ARQ pool
- **`routers/`** — Endpoints HTTP organizados por domínio
  - **`health.py`** — `GET /v1/health` — retorna status da API e versão
  - **`kt_ingestion_router.py`** — `POST /v1/kt-ingestion/run` (enfileira task) e `GET /v1/kt-ingestion/status/{job_id}` (polling)
  - **`kt_indexing_router.py`** — `POST /v1/kt-indexing/run` (enfileira task), `GET /v1/kt-indexing/status` (info ChromaDB), `GET /v1/kt-indexing/status/{job_id}` (polling)
  - **`kt_search_router.py`** — `POST /v1/kt-search/` (busca síncrona) e pipeline assíncrono de 6 estágios (`/pipeline/start`, `/pipeline/{session_id}/classify`, `/pipeline/{session_id}/chromadb`, `/pipeline/{session_id}/discover`, `/pipeline/{session_id}/select`, `/pipeline/{session_id}/insights`, `/pipeline/status/{job_id}`, `/pipeline/{session_id}/result`)
  - **`kt_pipeline_router.py`** — `GET /v1/kt-pipeline/meetings` (lista reuniões TL:DV com badge `already_indexed`), `POST /v1/kt-pipeline/start` (enfileira pipeline seletivo), `GET /v1/kt-pipeline/status/{job_id}` (polling)
- **`schemas/`** — Schemas Pydantic para toda a API
  - **`kt_schemas.py`** — Todos os schemas de request/response: `KTSearchRequest`, `KTSearchResponse`, `AsyncJobResponse`, `JobStatusResponse`, `KTIndexingStatusResponse`, `PipelineStartRequest`, `PipelineStartResponse`, `StageJobResponse`, `StageStatusResponse`, `MeetingItemResponse`, `MeetingListResponse`, `SelectivePipelineRequest`, `SelectivePipelineStartResponse`

### `src/config/` — Configuração da aplicação

- **`settings.py`** — Única fonte de verdade para paths e variáveis de ambiente: `DIRECTORY_PATHS` (sqlite_db, vector_db, transcriptions), `FILE_PATHS` (hashes_db), constantes de formatação (`DELIMITER_LINE`, `DELIMITER_SECTION`), variáveis lidas do `.env` (Redis, TL:DV, OpenAI, ChromaDB, app)
- **`startup.py`** — Side effects de inicialização: `initialize_application()` (orquestra diretórios + logging), `ensure_directories_exist()` (cria `data/` e subpastas), `setup_logging()` (arquivo rotativo diário + console, silencia libs verbosas)

### `src/helpers/` — Funções auxiliares transversais ao projeto

- **`kt_helpers.py`** — `build_meeting_key()`, `build_job_key()`, `extract_video_name_from_path()` — constroem chaves padronizadas para Redis e extraem nomes limpos de caminhos

### `src/kt_ingestion/` — Domínio: download e consolidação de transcrições do TL:DV

- **`tldv_client.py`** — `TLDVClient`: comunicação com API TL:DV — lista reuniões, obtém transcrição com polling, retorna `MeetingData` estruturado; dataclasses: `MeetingData`, `TranscriptSegment`, `Highlight`; enum: `MeetingStatus`
- **`smart_processor.py`** — `SmartMeetingProcessor`: processa reunião em duas fases (dados imediatos + completude em background thread); flag `is_complete` para validação antes de salvar
- **`json_consolidator.py`** — `JSONConsolidator`: cria JSON consolidado no formato aninhado (`metadata` + `transcript.segments` + `highlights`) e salva em `data/transcriptions/`
- **`kt_ingestion_constants.py`** — Constantes: endpoints TL:DV (`TLDV_MEETINGS_ENDPOINT`, `TLDV_IMPORTS_ENDPOINT`), timeouts (`TLDV_MAX_WAIT_SECONDS=300`, `TLDV_POLL_INTERVAL_SECONDS=10`), limites de threads (`MAX_BACKGROUND_THREADS=5`)

### `src/kt_indexing/` — Domínio: chunking, embedding e indexação no ChromaDB

- **`indexing_engine.py`** — `IndexingEngine`: orquestra o processamento completo de um JSON — normalização de nome, chunking por segmento, extração de metadados via LLM e geração de embeddings — com suporte a processamento em lote de todos os JSONs novos
- **`chromadb_store.py`** — `ChromaDBStore`: persistência e busca vetorial via ChromaDB PersistentClient; `EmbeddingGenerator`: gera embeddings híbridos via OpenAI (80% conteúdo + 20% metadados)
- **`video_normalizer.py`** — `EnhancedVideoNormalizer`: normaliza nome de reunião e gera slug semântico no formato `{cliente}_{modulo_ou_keyword}_{data}` (ex: `dexco_ewm_20250822`); usa LLM como fallback
- **`text_chunker.py`** — `TextChunker`: divide segmentos de transcrição em chunks de até 1000 chars com sobreposição de 200 chars; dataclass `ChunkPart` (text, char_start, char_end, part_index, total_parts)
- **`llm_metadata_extractor.py`** — `LLMMetadataExtractor`: extrai via GPT-4o-mini metadados estruturados de cada chunk: `meeting_phase`, `kt_type`, `sap_modules`, `transactions`, `technical_terms`, `participants_mentioned`, `systems`, `decisions`, `problems`, `searchable_tags`
- **`file_generator.py`** — `FileGenerator`: cria arquivos TXT de auditoria em `data/transcriptions/chunks/` com metadados TL:DV, metadados LLM e conteúdo do chunk
- **`kt_indexing_utils.py`** — Funções utilitárias: `load_and_validate_json()`, `extract_client_name_smart()` (prioridade: `[BRACKET]` → client_patterns → fallback `"DEXCO"`), `extract_sap_modules_from_title()`, `extract_enriched_tldv_fields()`, `normalize_client_name()`
- **`kt_indexing_constants.py`** — Constantes: `CHUNK_CONFIG` (max_chars, overlap, min), `LLM_CONFIG` (modelo, retries, temperatura), `CHROMADB_CONFIG` (collection, dimensões), `KT_TYPE_PATTERNS` (sustentacao, implementacao, treinamento...), `METADATA_LIMITS`

### `src/kt_search/` — Domínio: pipeline RAG de 5 estágios para busca semântica

- **`search_engine.py`** — `SearchEngine`: orquestra pipeline RAG completo em modo síncrono (instancia todos os 7 componentes; método `search()` executa estágios em sequência)
- **`query_enricher.py`** — `QueryEnricher`: detecta entidades (clientes, transações SAP, módulos, participantes, temporal), normaliza e expande query; retorna `EnrichmentResult`
- **`query_classifier.py`** — `QueryClassifier`: classifica tipo de busca RAG em `SEMANTIC | METADATA | ENTITY | TEMPORAL | CONTENT` com confidence e fallbacks; retorna `ClassificationResult`
- **`query_type_detector.py`** — `QueryTypeDetector`: detecta (sem LLM/ChromaDB) se query é análise de KT específico (`detect_specific_kt_analysis()`) ou listagem genérica (fast-track)
- **`chromadb_search_executor.py`** — `ChromaDBSearchExecutor`: executa 5 estratégias de busca no ChromaDB (SEMANTIC, METADATA, ENTITY, TEMPORAL, CONTENT) com early-exit para cliente inexistente
- **`dynamic_client_manager.py`** — `DynamicClientManager`: descobre clientes únicos presentes no ChromaDB com contagem; filtra resultados por cliente relevante à query
- **`chunk_selector.py`** — `ChunkSelector`: scoring de qualidade + diversidade para seleção de TOP-K chunks adaptativos ao tipo de query; dataclasses `ChunkScore`, `SelectionResult`
- **`insights_agent.py`** — `InsightsAgent`: gera resposta final via GPT analisando múltiplos contextos selecionados; consolida insights acionáveis; retorna `DirectInsightResult`
- **`insights_prompts.py`** — Funções para construção de prompts: `get_insights_extraction_prompt()`, `get_final_answer_prompt()`, `get_summary_prompt()`
- **`insight_processors.py`** — Processadores de insights pós-geração: consolidação, deduplicação e ranqueamento de insights extraídos
- **`search_response_builder.py`** — `SearchResponseBuilder`: monta `SearchResponse` final com metadados; detecta cliente inexistente (`should_stop_for_nonexistent_client()`); analisa complexidade da query
- **`search_types.py`** — Tipos do domínio de busca: `SearchResponse` (intelligent_response, contexts, summary_stats, query_type, processing_time, success, error_message); `QueryType` enum
- **`search_formatters.py`** — Formatação de resultados para console: `print_results()`, `format_contexts()`, `format_summary_stats()`
- **`search_cli.py`** — CLI de busca: `run_interactive_search()` (loop REPL), `run_single_search(query)` (busca única com saída)
- **`search_logging.py`** — `PipelineLogger`: log estruturado de cada estágio do pipeline (nome, status, duração, detalhes)
- **`search_utils.py`** — Utilitários: `normalize_query()`, `calculate_relevance_score()`, `extract_top_entities()`
- **`kt_search_constants.py`** — Constantes: `ENTITY_PATTERNS` (regex para clientes/transações/módulos), `QUERY_PATTERNS` (detecção de tipo RAG), `QUALITY_WEIGHTS`, `DIVERSITY_CONFIG`, `TOP_K_STRATEGY` (adaptativo por tipo)

### `src/services/` — Singletons thread-safe de orquestração

- **`kt_ingestion_service.py`** — `KTIngestionService`: singleton que orquestra TLDVClient + SmartMeetingProcessor + JSONConsolidator; métodos: `force_clean()`, `run_ingestion()`, `list_meetings_with_status()`, `run_selective_ingestion(meeting_ids)`
- **`kt_indexing_service.py`** — `KTIndexingService`: singleton que orquestra IndexingEngine + ChromaDBStore; métodos: `force_clean()` (apaga ChromaDB + chunks/), `run_indexing()`, `get_status()`
- **`kt_search_service.py`** — `KTSearchService`: singleton que orquestra SearchEngine; método `search(query)` e propriedade `components` (expõe os 7 componentes individuais para tasks ARQ)
- **`llm_service.py`** — Ponto único de re-export do `utils/llm_manager.py`: `LLMUsageTrackingCallback`, `get_structured_output_method`, `llm_client_manager`, `llm_monitor`

### `src/tasks/` — Tasks ARQ assíncronas

- **`arq_worker.py`** — `WorkerSettings`: `max_jobs=6`, `job_timeout=7200`, `keep_result=3600`, `poll_delay=0.5`; lista de 10 functions registradas; callbacks `startup()` e `shutdown()`
- **`kt_ingestion_task.py`** — `kt_ingestion_task(ctx)`: download incremental de reuniões TL:DV; lazy import de `get_kt_ingestion_service()`
- **`kt_indexing_task.py`** — `kt_indexing_task(ctx)`: indexação incremental de JSONs no ChromaDB; lazy import de `get_kt_indexing_service()`
- **`kt_selective_pipeline_task.py`** — `kt_selective_pipeline_task(ctx, meeting_ids, session_id, force_clean)`: pipeline completo seletivo — `force_clean` opcional + ingestion seletiva + indexação
- **`kt_search_task.py`** — 6 tasks do pipeline RAG assíncrono, cada uma lê/escreve estado no Redis via `ctx["redis"]`: `kt_search_enrich_task`, `kt_search_classify_task`, `kt_search_chromadb_task`, `kt_search_discover_task`, `kt_search_select_task`, `kt_search_insights_task`

---

## `utils/` — Utilitários portáveis (zero dependências de `src/`)

- **`exception_setup.py`** — `ApplicationError(Exception)`: exception padrão do time com `message`, `status_code`, `error_code` (VALIDATION_ERROR, NOT_FOUND, SERVICE_UNAVAILABLE, QUOTA_EXCEEDED, INTERNAL_ERROR), `context` (dict para debug) e `timestamp` (UTC)
- **`logger_setup.py`** — `LoggerManager`: `get_logger(name)`, `setup_logging()`, `set_default_log_dir()`; formato `TIMESTAMP [logger_name] [LEVEL] message`; idempotente (não duplica handlers); silencia libs verbosas
- **`hash_manager.py`** — `HashManager`: cache de hashes por conteúdo em SQLite (`data/sqlite_db/hashes.db`); métodos: `generate_file_hash()`, `should_reprocess()`, `update_cache_hash()`, `load_hash_metadata()`
- **`llm_manager.py`** — `LLMManager`: cliente LLM multi-provider (OpenAI, Gemini, Anthropic, Ollama) com tracking de uso (`LLMUsageTrackingCallback`), retries e timeout; `llm_client_manager` (singleton), `llm_monitor`
- **`string_helpers.py`** — `sanitize_string()`, `truncate_string()`, `normalize_whitespace()` — manipulação genérica de strings
- **`pdfplumber_extractor.py`** — `PDFPlumberExtractor`: `extract_text(pdf_path)`, `extract_tables(pdf_path)` — extração simples de texto e tabelas de PDFs
- **`dpt2_extractor.py`** — `DPT2Extractor`: `extract_text_from_image()`, `extract_with_layout()` — OCR avançado via Landing.AI DPT-2 para documentos complexos
- **`wordcom_toolkit.py`** — `WordcomToolkit`: `open_docx()`, `extract_text()`, `extract_tables()` — manipulação de `.docx` via COM (Windows/pywin32)

---

## `scripts/` — Scripts utilitários e UI (execução pontual ou contínua)

- **`app.py`** — UI Streamlit (porta 8501): aba "🔍 Consulta" (busca RAG via pipeline assíncrono de 6 estágios com progress bar) e aba "📥 Pipeline Seletivo" (lista reuniões TL:DV, multiselect, toggle force_clean, polling de job); consome FastAPI em `localhost:8000`
- **`run_full_pipeline.py`** — Pipeline completo via CLI: ingestion TL:DV → indexação ChromaDB → validação; flags `--force-clean`, `--skip-ingestion`, `--skip-indexing`; relatório final com estatísticas
- **`run_select_pipeline.py`** — Pipeline seletivo via CLI: listagem interativa de reuniões → seleção por índice/lista/intervalo → ingestion → indexação → relatório; flag `--force-clean`
- **`auto_init.py`** — Auto-geração de `__init__.py` em `src/` (hook de pre-commit do template — não modificar)

---

## `data/` — Dados persistidos (excluído do controle de versão via `.gitignore`)

- **`sqlite_db/`** — Banco SQLite `hashes.db` gerado pelo `hash_manager`: rastreia arquivos já processados por hash de conteúdo
- **`vector_db/`** — Base ChromaDB persistida: embeddings e metadados dos chunks de transcrições KT indexadas
- **`transcriptions/`** — JSONs consolidados de reuniões TL:DV no formato aninhado (`metadata` + `transcript` + `highlights`); subpasta **`chunks/`** com TXTs de auditoria por chunk indexado

---

## `tests/` — Testes automatizados

- **`conftest.py`** — Fixtures globais: `require_redis` (skip automático se Redis indisponível), diretórios temporários para isolamento de testes
- **`test_kt_ingestion.py`** — Testes unitários do domínio kt_ingestion: TLDVClient, SmartMeetingProcessor, JSONConsolidator
- **`test_kt_indexing.py`** — Testes unitários do domínio kt_indexing: IndexingEngine, ChromaDBStore, utils e normalização de slugs
- **`test_kt_search.py`** — Testes unitários do domínio kt_search: SearchEngine e componentes individuais do pipeline RAG
- **`test_kt_search_pipeline.py`** — Testes de integração do pipeline RAG completo (estágios encadeados)
- **`test_search_response_builder.py`** — 35 testes do SearchResponseBuilder (including available_clients dinâmico)
- **`test_search_formatters.py`** — 32 testes dos formatadores de busca (92% cobertura)
- **`test_search_cli.py`** — 25 testes da search CLI (94% cobertura)
- **`test_search_logging.py`** — Testes do PipelineLogger
- **`test_query_type_detector.py`** — 37 testes do QueryTypeDetector (detect_specific_kt_analysis)
- **`test_insight_processors.py`** — Testes dos processadores de insights
- **`test_insights_prompts.py`** — 21 testes dos insights prompts (100% cobertura)
- **`test_smoke.py`** — Smoke tests (`@pytest.mark.smoke`): FastAPI importa, Redis conecta, ARQ worker configurado, health endpoint responde 200
- **`test_e2e.py`** — E2E tests (`@pytest.mark.e2e`): fluxos completos de busca e indexação com stack real

---

## Raiz do projeto

- **`pyproject.toml`** — Dependências (uv), configuração de ruff (lint/format), mypy (type check estrito), pytest (`pythonpath=["."]`, markers `smoke` e `e2e`, coverage em `src/`)
- **`.env.example`** — Template de variáveis de ambiente com instruções para cada chave (REDIS_HOST, OPENAI_API_KEY, TLDV_API_KEY, etc.)
- **`.pre-commit-config.yaml`** — Hooks: auto-init (`__init__.py`), validate-structure (pastas obrigatórias), ruff check, ruff format, mypy
- **`CLAUDE.md`** — Instruções do projeto para Claude Code: arquitetura, padrões de código, exception handling, comandos e CLAUDEs especializados
