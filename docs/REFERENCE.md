# Referência de Funções e Classes — KT-Transcriber

Documentação das interfaces públicas de `src/`, `utils/` e `scripts/`. Gerado por `/document-project`.

---

## `src/config/`

### `settings.py`

| Símbolo | Tipo | Descrição |
|---------|------|-----------|
| `DIRECTORY_PATHS` | `dict[str, Path]` | Paths de dados: `sqlite_db`, `vector_db`, `transcriptions` |
| `FILE_PATHS` | `dict[str, Path]` | Paths de arquivos: `hashes_db` → `data/sqlite_db/hashes.db` |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DB` | `str / int` | Conexão Redis Cloud (lido do `.env`) |
| `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL` | `str` | Configuração OpenAI (lido do `.env`) |
| `TLDV_API_KEY`, `TLDV_BASE_URL`, `TLDV_TIMEOUT` | `str / int` | Configuração TL:DV API (lido do `.env`) |
| `CHROMA_COLLECTION_NAME` | `str` | Nome da coleção ChromaDB (lido do `.env`) |
| `DELIMITER_LINE`, `DELIMITER_SECTION`, `DELIMITER_POPUP_LINE` | `str` | Delimitadores visuais para formatação de saída no console |

### `startup.py`

| Função | Assinatura | Descrição |
|--------|-----------|-----------|
| `initialize_application` | `() -> logging.Logger` | Orquestra inicialização completa: cria diretórios e configura logging. Ponto de entrada obrigatório em `main.py` e scripts. |
| `ensure_directories_exist` | `() -> None` | Cria `BASE_DIR`, `LOG_DIR` e todas as pastas em `DIRECTORY_PATHS` via `mkdir(exist_ok=True)`. |
| `setup_logging` | `(log_file: str \| None, level: str, console: bool, enable_file: bool) -> logging.Logger` | Configura logger raiz com arquivo rotativo diário e console. Silencia libs verbosas (urllib3, httpx, chromadb, openai). |

---

## `src/api/schemas/kt_schemas.py`

Todos os schemas Pydantic v2 da API.

| Schema | Campos principais | Uso |
|--------|------------------|-----|
| `KTSearchRequest` | `query: str` (mín. 3 chars) | Request de busca síncrona e início de pipeline |
| `KTSearchResponse` | `answer, contexts, query_type, processing_time, success` | Resposta final de busca RAG |
| `AsyncJobResponse` | `job_id, status, message` | Retorno de enfileiramento de task ARQ |
| `JobStatusResponse` | `job_id, status, result, error` | Status + resultado de job ARQ |
| `KTIndexingStatusResponse` | `total_documents, collection_name, unique_clients, embedding_dimensions` | Info do ChromaDB |
| `PipelineStartRequest` | `query: str` | Inicia pipeline assíncrono de busca |
| `PipelineStartResponse` | `session_id, job_id, message` | Confirma início — session_id usado nos estágios seguintes |
| `StageJobResponse` | `job_id, stage, session_id` | Retorno ao enfileirar cada estágio do pipeline |
| `StageStatusResponse` | `job_id, stage, status, result, early_exit` | Status de estágio com flag de early-exit |
| `MeetingItemResponse` | `id, name, status, duration, already_indexed` | Item de reunião TL:DV com badge de indexação |
| `MeetingListResponse` | `meetings: list[MeetingItemResponse], total` | Lista de reuniões |
| `SelectivePipelineRequest` | `meeting_ids: list[str], force_clean: bool` | Inicia pipeline seletivo |
| `SelectivePipelineStartResponse` | `job_id, session_id, total_meetings` | Confirma enfileiramento do pipeline seletivo |

---

## `src/api/routers/`

### `health.py`
- **`GET /v1/health`** → `{"status": "healthy", "version": "1.0.0"}` — Verificação de saúde da API.

### `kt_ingestion_router.py`
- **`POST /v1/kt-ingestion/run`** → `AsyncJobResponse` — Enfileira `kt_ingestion_task` no ARQ. Retorna `job_id` para polling.
- **`GET /v1/kt-ingestion/status/{job_id}`** → `JobStatusResponse` — Consulta status e resultado de job de ingestion.

### `kt_indexing_router.py`
- **`POST /v1/kt-indexing/run`** → `AsyncJobResponse` — Enfileira `kt_indexing_task` no ARQ.
- **`GET /v1/kt-indexing/status`** → `KTIndexingStatusResponse` — Retorna info atual do ChromaDB (documentos, clientes únicos, dimensões).
- **`GET /v1/kt-indexing/status/{job_id}`** → `JobStatusResponse` — Consulta status de job de indexação.

### `kt_search_router.py`
- **`POST /v1/kt-search/`** → `KTSearchResponse` — Busca RAG síncrona completa.
- **`POST /v1/kt-search/pipeline/start`** → `PipelineStartResponse` — Inicia estágio 1 do pipeline assíncrono (enrich).
- **`POST /v1/kt-search/pipeline/{session_id}/classify`** → `StageJobResponse` — Enfileira estágio 2.
- **`POST /v1/kt-search/pipeline/{session_id}/chromadb`** → `StageJobResponse` — Enfileira estágio 3.
- **`POST /v1/kt-search/pipeline/{session_id}/discover`** → `StageJobResponse` — Enfileira estágio 4.
- **`POST /v1/kt-search/pipeline/{session_id}/select`** → `StageJobResponse` — Enfileira estágio 5.
- **`POST /v1/kt-search/pipeline/{session_id}/insights`** → `StageJobResponse` — Enfileira estágio 6.
- **`GET /v1/kt-search/pipeline/status/{job_id}`** → `StageStatusResponse` — Polling com flag `early_exit`.
- **`GET /v1/kt-search/pipeline/{session_id}/result`** → `KTSearchResponse` — Resultado final (404 se ainda não disponível).

### `kt_pipeline_router.py`
- **`GET /v1/kt-pipeline/meetings`** → `MeetingListResponse` — Lista reuniões TL:DV com `already_indexed` por meeting_id.
- **`POST /v1/kt-pipeline/start`** → `SelectivePipelineStartResponse` — Enfileira `kt_selective_pipeline_task`.
- **`GET /v1/kt-pipeline/status/{job_id}`** → `JobStatusResponse` — Polling do pipeline seletivo.

---

## `src/helpers/kt_helpers.py`

| Função | Assinatura | Descrição |
|--------|-----------|-----------|
| `build_meeting_key` | `(meeting_id: str, suffix: str = "") -> str` | Constrói chave Redis padronizada `meeting:{id}:{suffix}`. |
| `build_job_key` | `(job_id: str, field: str = "") -> str` | Constrói chave Redis padronizada `job:{id}:{field}`. |
| `extract_video_name_from_path` | `(path: str \| Path) -> str` | Extrai nome limpo de vídeo a partir de caminho de arquivo (remove extensão e underscores extras). |

---

## `src/kt_ingestion/`

### `tldv_client.py`

**Dataclasses e Enums:**

| Tipo | Campos | Descrição |
|------|--------|-----------|
| `MeetingStatus` | `PROCESSING, COMPLETED, FAILED, PENDING` | Enum de status de reunião no TL:DV |
| `TranscriptSegment` | `speaker, text, start_time, end_time` | Segmento de transcrição |
| `Highlight` | `text, start_time, source, topic` | Highlight de reunião |
| `MeetingData` | `id, name, happened_at, url, duration, status, organizer, invitees, template` | Dados completos de uma reunião |

**Classe `TLDVClient`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `__init__` | `(api_key: str)` | Inicializa com headers de autenticação e session HTTP. |
| `list_meetings` | `() -> list[MeetingData]` | Lista todas as reuniões do workspace TL:DV. |
| `get_meeting_status` | `(meeting_id: str) -> MeetingData` | Retorna dados e status atual de uma reunião. |
| `get_transcript` | `(meeting_id: str, wait_for_complete: bool = False) -> dict \| None` | Retorna transcrição; se `wait_for_complete=True` faz polling por até `TLDV_MAX_WAIT_SECONDS`. |
| `get_complete_meeting_data` | `(meeting_id: str) -> dict` | Dados completos: metadata + transcript + highlights. |
| `import_meeting` | `(video_url: str, meeting_name: str, happened_at: str) -> str` | Importa vídeo externo; retorna `job_id` (não `meeting_id`). |

### `smart_processor.py`

**Classe `SmartMeetingProcessor`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `__init__` | `(tldv_client: TLDVClient, consolidator: JSONConsolidator \| None = None)` | Inicializa com cliente TL:DV e consolidador opcional. |
| `process_meeting_smart` | `(meeting_id: str, client_name: str, video_name: str, wait_for_complete: bool = False) -> dict` | Processa reunião em dois tempos: dados imediatos (fase 1) + completude em background thread (fase 2). Flag `is_complete` indica se transcrição está completa. |
| `shutdown_background_threads` | `() -> None` | Aguarda conclusão de todas as threads de background pendentes. |

### `json_consolidator.py`

**Classe `JSONConsolidator`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `__init__` | `(output_dir: Path \| None = None)` | Usa `DIRECTORY_PATHS["transcriptions"]` por padrão. |
| `create_consolidated_json` | `(meeting_data: dict, client_name: str, video_name: str) -> dict` | Cria dict no formato aninhado (`metadata` + `transcript` + `highlights`). |
| `save_consolidated_json` | `(consolidated_data: dict, filename: str \| None = None) -> Path` | Salva JSON em disco; gera nome automaticamente se não fornecido. |
| `process_from_tldv_data` | `(meeting_data: dict, client_name: str, video_name: str, save: bool = True) -> dict` | Cria + salva JSON em uma operação. |
| `process_from_chunked_data` | `(chunked_data: dict, client_name: str, save: bool = True) -> dict` | Processa dados já fragmentados pelo SmartProcessor. |

---

## `src/kt_indexing/`

### `indexing_engine.py`

**Classe `IndexingEngine`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `__init__` | `(input_dir: Path \| None, output_dir: Path \| None, enable_chromadb: bool = True, generate_txt_files: bool = True)` | Inicializa com componentes: Normalizer, Chunker, LLMExtractor, EmbeddingGenerator, ChromaDBStore, FileGenerator. |
| `process_single_video` | `(json_file: Path) -> dict` | Processa 1 JSON: normalização → chunking por segmento → LLM metadata → embedding → ChromaDB. Retorna `{parts_created, segments_processed, errors, video_slug}`. |
| `process_all_videos` | `(validate: bool = True) -> dict` | Processa todos os JSONs em `input_dir` não ainda indexados no ChromaDB. Retorna stats por vídeo. |

### `chromadb_store.py`

**Classe `EmbeddingGenerator`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `__init__` | `(config: dict \| None = None)` | Inicializa cliente OpenAI para embeddings. |
| `generate_chunk_embedding` | `(chunk_text: str, metadata: dict) -> list[float]` | Gera embedding híbrido 1536D: 80% conteúdo + 20% contexto de metadados concatenado. |

**Classe `ChromaDBStore`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `__init__` | `()` | Conecta ao `PersistentClient` em `DIRECTORY_PATHS["vector_db"]` com coleção `CHROMA_COLLECTION_NAME`. |
| `add_chunk` | `(chunk_text: str, metadata: dict, embeddings: list[float], video_slug: str) -> str` | Indexa 1 chunk com metadados limpos (None removido por `_clean_metadata`). Retorna ID gerado. |
| `search_chunks` | `(query: str, limit: int, filters: dict \| None) -> list[dict]` | Busca semântica por texto; suporta filtros de metadados. |
| `delete_by_meeting_id` | `(meeting_id: str) -> int` | Remove todos os chunks de uma reunião específica. Retorna contagem deletada. |
| `get_collection_info` | `() -> dict` | Info da coleção: `total_documents`, `unique_clients`, `embedding_dimensions`, `collection_name`. |
| `get_distinct_values` | `(metadata_field: str) -> list[str]` | Retorna valores únicos de um campo de metadado (ex.: `client_name`). |

### `video_normalizer.py`

**Classe `EnhancedVideoNormalizer`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `__init__` | `(use_llm: bool = True)` | Usa OpenAI como fallback para extração de slug quando regras não cobrem. |
| `normalize` | `(video_name: str, meeting_id: str = "") -> dict` | Retorna `{normalized_name, slug, modules, description, original_name}`. Slug: `{cliente}_{modulo}_{data}` (ex: `dexco_ewm_20250822`). |

**Regras do Slug**: `[BRACKET]` → lowercase do bracket; sem bracket → `"dexco"`. Módulo: regex SAP (EWM, SD, FI...) → keyword map (ICMS→icms, FRETE→frete...) → fallback LLM. Data: YYYYMMDD extraído do nome original.

### `text_chunker.py`

**Classe `TextChunker`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `__init__` | `(config: dict \| None = None)` | `max_chars=1000`, `overlap_chars=200`, `min_chars=50` (via `CHUNK_CONFIG`). |
| `split_segment_into_parts` | `(text: str) -> list[ChunkPart]` | Divide texto em chunks com sobreposição. Chunks abaixo de `min_chars` são ignorados. |

**Dataclass `ChunkPart`**: `text`, `char_start`, `char_end`, `part_index`, `total_parts`.

### `llm_metadata_extractor.py`

**Classe `LLMMetadataExtractor`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `__init__` | `(config: dict \| None = None)` | GPT-4o-mini, temperatura 0.1, max 3 retries. |
| `extract_metadata_for_chunk` | `(chunk_text: str, video_name: str, client_name: str) -> dict` | Retorna dict com: `meeting_phase`, `kt_type`, `sap_modules`, `transactions`, `technical_terms`, `participants_mentioned`, `systems`, `decisions`, `problems`, `searchable_tags`. |

### `kt_indexing_utils.py`

| Função | Assinatura | Descrição |
|--------|-----------|-----------|
| `load_and_validate_json` | `(file_path: Path) -> dict` | Carrega JSON e valida formato aninhado obrigatório (`metadata` + `transcript.segments`). Levanta `ApplicationError` se inválido. |
| `extract_client_name_smart` | `(video_name: str, client_patterns: list[str] \| None = None) -> str` | Extrai cliente: Prioridade 1=`[BRACKET]`, 2=`client_patterns`, fallback=`"DEXCO"`. |
| `normalize_client_name` | `(client_name: str) -> str` | Normaliza para UPPER_SNAKE_CASE sem acentos. |
| `extract_sap_modules_from_title` | `(title: str) -> list[str]` | Extrai módulos SAP via regex (MM, SD, FI, EWM, WM, PP, QM, PM, CO, FI, HR, PS). |
| `extract_enriched_tldv_fields` | `(video_data: dict) -> dict` | Compatível com formato aninhado — extrai campos de `video_data["metadata"]`. |
| `format_datetime` | `(dt_str: str) -> str` | Formata datetime ISO para exibição. |
| `calculate_estimated_processing_time` | `(total_chars: int) -> float` | Estimativa de tempo de processamento em segundos. |
| `handle_processing_error` | `(error: Exception, context: dict) -> None` | Log padronizado de erro de processamento (não levanta exception). |
| `create_client_variations` | `(client_name: str) -> list[str]` | Gera variações de nome de cliente para busca (maiúsculas, lowercase, sem acento). |

### `file_generator.py`

**Classe `FileGenerator`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `create_chunk_txt_file` | `(filename: str, output_dir: Path, tldv_metadata: dict, customized_metadata: dict, chunk_text: str) -> Path` | Cria TXT de auditoria com 3 seções: metadados TL:DV, metadados LLM e conteúdo do chunk. |

---

## `src/kt_search/`

### `search_engine.py`

**Classe `SearchEngine`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `__init__` | `(verbose: bool = False)` | Instancia os 7 componentes do pipeline: QueryEnricher, QueryClassifier, ChromaDBSearchExecutor, DynamicClientManager, ChunkSelector, InsightsAgent, SearchResponseBuilder. |
| `search` | `(query: str) -> SearchResponse` | Executa pipeline RAG completo em modo síncrono (5 estágios encadeados). |

### `query_enricher.py`

**Classe `QueryEnricher`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `enrich_query_universal` | `(query: str) -> EnrichmentResult` | Detecta entidades (clientes, transações, módulos, participantes, temporal), normaliza e constrói contexto semântico. |

**Dataclass `EnrichmentResult`**: `original_query`, `cleaned_query`, `enriched_query`, `entities`, `context`, `confidence`, `processing_time`.

### `query_classifier.py`

**Classe `QueryClassifier`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `classify_query_with_context` | `(cleaned_query: str, entities: dict, context: dict) -> ClassificationResult` | Classifica tipo RAG com base em contexto enriquecido; fornece fallbacks para queries híbridas. |

**Dataclass `ClassificationResult`**: `query_type: QueryType`, `confidence: float`, `strategy: str`, `reasoning: str`, `fallback_types: list[QueryType]`, `processing_time: float`.

**Enum `QueryType`**: `SEMANTIC | METADATA | ENTITY | TEMPORAL | CONTENT`.

### `query_type_detector.py`

**Classe `QueryTypeDetector`** (métodos estáticos — zero deps externas):

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `detect_specific_kt_analysis` | `(query_lower: str) -> bool` | `True` se query é análise de KT específico (ex.: "quais foram os problemas no KT de EWM?"). `False` se é listagem genérica (pode usar fast-track). |

### `chromadb_search_executor.py`

**Classe `ChromaDBSearchExecutor`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `execute_search` | `(enrichment_result: EnrichmentResult, classification_result: ClassificationResult, query: str) -> list[dict]` | Executa 5 estratégias de busca (SEMANTIC, METADATA, ENTITY, TEMPORAL, CONTENT). Early-exit se cliente mencionado na query não existe no ChromaDB. |

### `dynamic_client_manager.py`

**Classe `DynamicClientManager`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `discover_clients` | `() -> dict[str, int]` | Retorna clientes únicos presentes no ChromaDB com contagem de chunks por cliente. |
| `filter_results_by_client` | `(results: list[dict], discovered_clients: dict, query: str) -> list[dict]` | Filtra resultados de busca pelo cliente mais relevante à query. |

### `chunk_selector.py`

**Classe `ChunkSelector`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `select_chunks` | `(search_results: list[dict], query_type: QueryType, desired_count: int) -> SelectionResult` | Aplica quality scoring + diversity scoring; seleciona TOP-K adaptativo ao tipo de query. |

**Dataclass `ChunkScore`**: `chunk_id`, `quality_score`, `diversity_score`, `combined_score`, `selection_reason`.

**Dataclass `SelectionResult`**: `selected_chunks`, `chunk_scores`, `total_candidates`, `selection_strategy`, `processing_time`, `quality_threshold_met`.

### `insights_agent.py`

**Classe `InsightsAgent`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `__init__` | `(openai_client: OpenAI \| None = None)` | Cliente OpenAI injetável (para testes com mock). |
| `extract_insights` | `(contexts: list[dict], query: str, classification_result: ClassificationResult) -> DirectInsightResult` | Analisa chunks selecionados via GPT, consolida e gera resposta acionável. |

**Dataclass `DirectInsightResult`**: `insight`, `confidence`, `sources_used`, `processing_time`, `fallback_used`.

### `insights_prompts.py`

| Função | Assinatura | Descrição |
|--------|-----------|-----------|
| `get_insights_extraction_prompt` | `(contexts: list[dict], query: str) -> str` | Constrói prompt para extração de insights de múltiplos contextos. |
| `get_final_answer_prompt` | `(insights: list[str], query: str) -> str` | Constrói prompt para consolidação de insights em resposta final. |
| `get_summary_prompt` | `(contexts: list[dict]) -> str` | Constrói prompt para sumarização de contextos. |

### `search_response_builder.py`

**Classe `SearchResponseBuilder`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `build_final_response` | `(insights: DirectInsightResult, selected_chunks: SelectionResult, query_type: QueryType, processing_time: float) -> SearchResponse` | Monta `SearchResponse` final com todos os campos. |
| `should_stop_for_nonexistent_client` | `(query: str) -> bool` | Detecta se query menciona cliente inexistente no ChromaDB (para early-exit). |
| `create_client_not_found_response` | `(query: str, created_at: datetime, discovered_clients: dict) -> SearchResponse` | Cria resposta de "cliente não encontrado" com lista de clientes disponíveis. |
| `analyze_query_complexity` | `(enrichment_result: EnrichmentResult, classification_result: ClassificationResult, original_query: str) -> dict` | Analisa complexidade da query para ajuste de estratégia. |

### `search_types.py`

**Dataclass `SearchResponse`**: `intelligent_response: str`, `contexts: list[dict]`, `summary_stats: dict`, `query_type: str`, `processing_time: float`, `success: bool`, `error_message: str | None`.

### `search_formatters.py`

| Função | Assinatura | Descrição |
|--------|-----------|-----------|
| `print_results` | `(response: SearchResponse) -> None` | Formata e imprime resultado completo no console com delimitadores visuais. |
| `format_contexts` | `(contexts: list[dict]) -> str` | Formata lista de contextos como string legível. |
| `format_summary_stats` | `(stats: dict) -> str` | Formata estatísticas de resumo como string. |

### `search_cli.py`

| Função | Assinatura | Descrição |
|--------|-----------|-----------|
| `run_interactive_search` | `() -> None` | Loop REPL de buscas: lê query do stdin, exibe resultado, aguarda próxima query. Encerra com `q` ou Ctrl+C. |
| `run_single_search` | `(query: str) -> None` | Executa uma busca única, imprime resultado e encerra. |

### `search_logging.py`

**Classe `PipelineLogger`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `log_stage` | `(stage_name: str, status: str, duration: float, details: dict) -> None` | Registra entrada estruturada de estágio do pipeline com nome, status, duração e detalhes. |

### `search_utils.py`

| Função | Assinatura | Descrição |
|--------|-----------|-----------|
| `normalize_query` | `(query: str) -> str` | Normaliza query: lowercase, remove pontuação excessiva, strip. |
| `calculate_relevance_score` | `(chunk: dict, query: str) -> float` | Calcula score de relevância de um chunk em relação à query. |
| `extract_top_entities` | `(contexts: list[dict]) -> list[str]` | Extrai entidades mais frequentes de uma lista de contextos. |

---

## `src/services/`

### `kt_ingestion_service.py`

**Classe `KTIngestionService`** (singleton thread-safe):

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `get_instance` | `() -> KTIngestionService` | Retorna instância singleton (double-checked locking). |
| `force_clean` | `() -> None` | Remove todos os JSONs em `data/transcriptions/` (exceto subpastas). |
| `run_ingestion` | `() -> dict` | Download incremental: pula reuniões já salvas. Retorna: `meetings_found`, `meetings_downloaded`, `meetings_already_downloaded`, `meetings_skipped_incomplete`, `meetings_failed`, `errors`. |
| `list_meetings_with_status` | `() -> list[dict]` | Lista reuniões TL:DV com `already_indexed` boolean por meeting_id. |
| `run_selective_ingestion` | `(meeting_ids: list[str]) -> dict` | Download seletivo dos IDs especificados. |

**Factory**: `get_kt_ingestion_service() -> KTIngestionService`

### `kt_indexing_service.py`

**Classe `KTIndexingService`** (singleton thread-safe):

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `get_instance` | `() -> KTIndexingService` | Retorna instância singleton. |
| `force_clean` | `() -> None` | Apaga coleção ChromaDB (recria vazia) e limpa `data/transcriptions/chunks/`. |
| `run_indexing` | `() -> dict` | Indexação incremental: pula meeting_ids já presentes no ChromaDB. Retorna: `videos_already_indexed`, `videos_indexed`, `chunks_indexed`, `videos_failed`, `errors`. |
| `get_status` | `() -> dict` | Info do ChromaDB: `total_documents`, `collection_name`, `unique_clients`, `embedding_dimensions`. |

**Factory**: `get_kt_indexing_service() -> KTIndexingService`

### `kt_search_service.py`

**Classe `KTSearchService`** (singleton thread-safe):

| Membro | Tipo | Descrição |
|--------|------|-----------|
| `components` | `dict` | Expõe `query_enricher`, `query_classifier`, `chromadb_executor`, `dynamic_client_manager`, `chunk_selector`, `insights_agent`, `response_builder` para uso direto em tasks ARQ. |
| `search` | `(query: str) -> dict` | Executa pipeline RAG completo síncrono. Retorna dict com `answer`, `contexts`, `query_type`, `processing_time`, `success`. |

**Factory**: `get_kt_search_service() -> KTSearchService`

### `llm_service.py`

Re-export centralizado do `utils/llm_manager.py` — importar sempre daqui, nunca diretamente de `utils/`:

| Símbolo | Descrição |
|---------|-----------|
| `LLMUsageTrackingCallback` | Callback para rastreamento de uso de tokens |
| `get_structured_output_method` | Retorna método de output estruturado por provider |
| `llm_client_manager` | Singleton do cliente LLM multi-provider |
| `llm_monitor` | Monitor de uso e quota de LLM |

---

## `src/tasks/`

### `arq_worker.py`

**Classe `WorkerSettings`:**

| Atributo | Valor | Descrição |
|----------|-------|-----------|
| `max_jobs` | `6` | Máximo de jobs simultâneos (I/O bound: 6 estágios de busca RAG) |
| `job_timeout` | `7200` | Timeout por job em segundos (2 horas) |
| `keep_result` | `3600` | Duração do resultado no Redis (1 hora) |
| `poll_delay` | `0.5` | Intervalo de polling do worker em segundos |
| `functions` | `list` | 10 tasks registradas: kt_ingestion_task, kt_indexing_task, kt_selective_pipeline_task + 6 tasks de busca RAG |
| `on_startup` | `startup` | Inicializa logging no startup do worker |
| `on_shutdown` | `shutdown` | Log de encerramento |

**Entry point**: `arq src.tasks.arq_worker.WorkerSettings` — nunca via `if __name__ == "__main__"`.

### Tasks individuais

| Task | Assinatura | Descrição |
|------|-----------|-----------|
| `kt_ingestion_task` | `(ctx: dict) -> dict` | Download incremental de reuniões TL:DV via `KTIngestionService`. |
| `kt_indexing_task` | `(ctx: dict) -> dict` | Indexação incremental de JSONs no ChromaDB via `KTIndexingService`. |
| `kt_selective_pipeline_task` | `(ctx: dict, meeting_ids: list[str], session_id: str, force_clean: bool) -> dict` | Pipeline seletivo: force_clean opcional → ingestion seletiva → indexação. |
| `kt_search_enrich_task` | `(ctx: dict, query: str, session_id: str) -> dict` | Estágio 1: enriquecimento. Persiste `EnrichmentResult` no Redis. |
| `kt_search_classify_task` | `(ctx: dict, session_id: str) -> dict` | Estágio 2: classificação do tipo RAG. |
| `kt_search_chromadb_task` | `(ctx: dict, session_id: str) -> dict` | Estágio 3: busca ChromaDB com 5 estratégias. |
| `kt_search_discover_task` | `(ctx: dict, session_id: str) -> dict` | Estágio 4: descoberta de clientes. |
| `kt_search_select_task` | `(ctx: dict, session_id: str) -> dict` | Estágio 5: seleção de TOP-K chunks. |
| `kt_search_insights_task` | `(ctx: dict, session_id: str) -> dict` | Estágio 6: geração de insights via GPT. Escreve resultado final no Redis. |

---

## `utils/`

### `exception_setup.py`

**Classe `ApplicationError(Exception)`:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `message` | `str` | Mensagem client-safe (exibida ao usuário) |
| `status_code` | `int` | HTTP status code sugerido (default: 500) |
| `error_code` | `str` | Código estável: `VALIDATION_ERROR` (422), `NOT_FOUND` (404), `SERVICE_UNAVAILABLE` (503), `QUOTA_EXCEEDED` (429), `INTERNAL_ERROR` (500) |
| `context` | `dict[str, Any]` | Metadados de debug — NÃO expostos ao cliente |
| `timestamp` | `datetime` | UTC timezone-aware |

### `logger_setup.py`

**Classe `LoggerManager`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `get_logger` | `(name: str) -> logging.Logger` | Retorna logger nomeado. Usar: `logger = LoggerManager.get_logger(__name__)`. |
| `setup_logging` | `(log_file: str, level: str, console: bool, enable_file: bool) -> None` | Configura handlers (arquivo + console). Idempotente. |
| `set_default_log_dir` | `(log_dir: Path) -> None` | Define diretório padrão para arquivos de log. |

### `hash_manager.py`

**Classe `HashManager`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `__init__` | `(db_path: Path)` | SQLite em `FILE_PATHS["hashes_db"]` — `data/sqlite_db/hashes.db`. |
| `generate_file_hash` | `(file_path: Path) -> str` | Hash MD5 ou SHA256 do conteúdo do arquivo. |
| `should_reprocess` | `(source_file: Path, current_hash: str) -> bool` | `True` se o arquivo mudou desde o último processamento. |
| `update_cache_hash` | `(source_file: Path, content_hash: str, metadata: dict) -> None` | Armazena hash e metadados (INSERT OR REPLACE atômico). |
| `load_hash_metadata` | `(source_file: Path) -> dict \| None` | Carrega metadados do último processamento; `None` se inédito. |

**Factory**: `get_hash_manager() -> HashManager`

### `llm_manager.py`

**Funções e Objetos:**

| Símbolo | Descrição |
|---------|-----------|
| `LLMUsageTrackingCallback` | Classe callback para rastrear tokens consumidos por chamada |
| `get_structured_output_method(provider: str) -> str` | Retorna método de output estruturado pelo provider (json_mode, tool_use, etc.) |
| `llm_client_manager` | Singleton que gerencia clientes por provider (OpenAI, Gemini, Anthropic, Ollama) |
| `llm_monitor` | Monitor de uso e quota de LLM |

### `string_helpers.py`

| Função | Assinatura | Descrição |
|--------|-----------|-----------|
| `sanitize_string` | `(s: str, allowed_chars: str \| None = None) -> str` | Remove ou substitui caracteres não permitidos. |
| `truncate_string` | `(s: str, max_length: int) -> str` | Trunca string com reticências se necessário. |
| `normalize_whitespace` | `(s: str) -> str` | Colapsa espaços múltiplos e remove espaços de borda. |

### `pdfplumber_extractor.py`

**Classe `PDFPlumberExtractor`:**

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `extract_text` | `(pdf_path: Path) -> str` | Extrai texto completo do PDF. |
| `extract_tables` | `(pdf_path: Path) -> list[pd.DataFrame]` | Extrai tabelas do PDF como DataFrames. |

### `dpt2_extractor.py`

**Classe `DPT2Extractor`** (Landing.AI OCR avançado):

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `extract_text_from_image` | `(image_path: Path) -> str` | OCR de imagem via API Landing.AI DPT-2. |
| `extract_with_layout` | `(image_path: Path) -> dict` | OCR com preservação de layout (posição, blocos). |

### `wordcom_toolkit.py`

**Classe `WordcomToolkit`** (requer Windows + pywin32):

| Método | Assinatura | Descrição |
|--------|-----------|-----------|
| `open_docx` | `(file_path: Path) -> Document` | Abre arquivo `.docx` via COM. |
| `extract_text` | `(docx: Document) -> str` | Extrai texto completo do documento. |
| `extract_tables` | `(docx: Document) -> list[list[str]]` | Extrai tabelas como listas de listas de strings. |

---

## `scripts/`

### `app.py` — UI Streamlit

**Configuração:**
- `FASTAPI_URL`: `os.getenv("FASTAPI_URL", "http://localhost:8000")`
- `_POLL_INTERVAL_S`: `0.5` segundos
- `_POLL_TIMEOUT_S`: `120.0` segundos

**Abas disponíveis:**
- **🔍 Consulta** — Busca RAG com pipeline assíncrono de 6 estágios. Exibe progress bar por estágio e resultado final com contextos e resposta do GPT.
- **📥 Pipeline Seletivo** — Lista reuniões TL:DV com badge `already_indexed`, multiselect de reuniões, toggle `force_clean`, enfileira `kt_selective_pipeline_task` e faz polling de resultado.

**Execução**: `streamlit run scripts/app.py` (porta 8501)

### `run_full_pipeline.py` — Pipeline Completo CLI

**Fluxo**: ingestion TL:DV → indexação ChromaDB → validação com relatório.

**Flags**:
- `--force-clean` — Limpa dados existentes antes de iniciar
- `--skip-ingestion` — Apenas indexação (usa JSONs já existentes)
- `--skip-indexing` — Apenas ingestion (baixa sem indexar)

**Execução**: `uv run python scripts/run_full_pipeline.py [--force-clean] [--skip-ingestion] [--skip-indexing]`

### `run_select_pipeline.py` — Pipeline Seletivo CLI

**Fluxo interativo**: listagem de reuniões → seleção por índice/lista/intervalo → confirmação → ingestion seletiva → indexação → relatório.

**Flags**: `--force-clean` — Limpa dados antes de iniciar.

**Formatos de seleção**: número único (`3`), lista (`1,3,5`), intervalo (`1-20`), combinação (`1,3-7,10`).

**Execução**: `uv run python scripts/run_select_pipeline.py [--force-clean]`
