"""Tasks ARQ para o pipeline RAG de busca KT — 6 estágios sequenciais.

Cada task lê o resultado do estágio anterior via Redis, executa um componente
do SearchEngine e persiste o resultado serializado para o próximo estágio.

Chaves Redis:
- kt_search:{session_id}:meta         — query + created_at + stages_completed
- kt_search:{session_id}:stage:enrich   — EnrichmentResult serializado
- kt_search:{session_id}:stage:classify — ClassificationResult + query_analysis
- kt_search:{session_id}:stage:chromadb — list[dict] raw results
- kt_search:{session_id}:stage:discover — list[dict] enriched results + skipped flag
- kt_search:{session_id}:stage:select   — SelectionResult serializado
- kt_search:{session_id}:stage:insights — DirectInsightResult serializado
- kt_search:{session_id}:final          — KTSearchResponse como dict
"""

import json
import time
from dataclasses import asdict
from typing import Any

from utils.exception_setup import ApplicationError
from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)

_KEY_PREFIX = "kt_search"
_TTL = 3600  # 1 hora


# ════════════════════════════════════════════════════════════════════════════
# HELPERS DE REDIS
# ════════════════════════════════════════════════════════════════════════════


def _stage_key(session_id: str, stage: str) -> str:
    return f"{_KEY_PREFIX}:{session_id}:stage:{stage}"


def _meta_key(session_id: str) -> str:
    return f"{_KEY_PREFIX}:{session_id}:meta"


def _final_key(session_id: str) -> str:
    return f"{_KEY_PREFIX}:{session_id}:final"


async def _redis_get_json(redis: Any, key: str) -> Any:
    """Lê e desserializa JSON do Redis. Levanta ApplicationError se chave ausente."""
    raw = await redis.get(key)
    if raw is None:
        raise ApplicationError(
            message=f"Dados do estágio ausentes no Redis: {key}",
            status_code=503,
            error_code="SERVICE_UNAVAILABLE",
        )
    return json.loads(raw)


# ════════════════════════════════════════════════════════════════════════════
# HELPERS DE (DE)SERIALIZAÇÃO
# ════════════════════════════════════════════════════════════════════════════


def _serialize_classification(classification_result: Any, query_analysis: dict[str, Any]) -> dict[str, Any]:
    """Serializa ClassificationResult + query_analysis para JSON (Enums → values)."""
    return {
        "query_type": classification_result.query_type.value,
        "confidence": classification_result.confidence,
        "strategy": classification_result.strategy,
        "reasoning": classification_result.reasoning,
        "fallback_types": [ft.value for ft in classification_result.fallback_types],
        "processing_time": classification_result.processing_time,
        "query_analysis": query_analysis,
    }


def _deserialize_classification(data: dict[str, Any]) -> Any:
    """Reconstrói ClassificationResult a partir de dict (values → Enums)."""
    from src.kt_search.query_classifier import ClassificationResult, QueryType

    return ClassificationResult(
        query_type=QueryType(data["query_type"]),
        confidence=data["confidence"],
        strategy=data["strategy"],
        reasoning=data["reasoning"],
        fallback_types=[QueryType(ft) for ft in data["fallback_types"]],
        processing_time=data["processing_time"],
    )


def _deserialize_selection(data: dict[str, Any]) -> Any:
    """Reconstrói SelectionResult a partir de dict."""
    from src.kt_search.chunk_selector import ChunkScore, SelectionResult

    return SelectionResult(
        selected_chunks=data["selected_chunks"],
        chunk_scores=[ChunkScore(**cs) for cs in data["chunk_scores"]],
        total_candidates=data["total_candidates"],
        selection_strategy=data["selection_strategy"],
        processing_time=data["processing_time"],
        quality_threshold_met=data["quality_threshold_met"],
    )


def _search_response_to_dict(response: Any, created_at: float) -> dict[str, Any]:
    """Converte SearchResponse para dict compatível com KTSearchResponse."""
    return {
        "answer": response.intelligent_response.get("answer", ""),
        "contexts": response.contexts,
        "query_type": response.query_type,
        "processing_time": time.time() - created_at,
        "success": response.success,
    }


# ════════════════════════════════════════════════════════════════════════════
# TASKS ARQ
# ════════════════════════════════════════════════════════════════════════════


async def kt_search_enrich_task(ctx: dict[str, Any], query: str, session_id: str) -> dict[str, Any]:
    """Task ARQ — Fase 1: enriquecimento universal da query.

    Args:
        ctx: Contexto ARQ com redis.
        query: Query original do usuário.
        session_id: Identificador único da sessão de pipeline.

    Returns:
        Dicionário com session_id, stage, status e processing_time.

    Raises:
        ApplicationError: Se o enriquecimento falhar (confidence < 0.1).
    """
    start = time.time()
    logger.info(f"[enrich] Iniciando — session={session_id}")

    from src.services.kt_search_service import get_kt_search_service

    comps = get_kt_search_service().components
    enrichment_result = comps["query_enricher"].enrich_query_universal(query)

    if enrichment_result.confidence < 0.1:
        raise ApplicationError(
            message="Enriquecimento da query falhou (confidence abaixo do mínimo)",
            status_code=503,
            error_code="SERVICE_UNAVAILABLE",
        )

    redis = ctx["redis"]
    created_at = time.time()

    await redis.set(_stage_key(session_id, "enrich"), json.dumps(asdict(enrichment_result)), ex=_TTL)
    await redis.set(
        _meta_key(session_id),
        json.dumps({"query": query, "created_at": created_at, "stages_completed": ["enrich"]}),
        ex=_TTL,
    )

    elapsed = time.time() - start
    logger.info(f"[enrich] Concluído em {elapsed:.3f}s — session={session_id}")
    return {"session_id": session_id, "stage": "enrich", "status": "complete", "processing_time": elapsed}


async def kt_search_classify_task(ctx: dict[str, Any], session_id: str) -> dict[str, Any]:
    """Task ARQ — Fase 2: classificação contextual do tipo RAG.

    Args:
        ctx: Contexto ARQ com redis.
        session_id: Identificador único da sessão de pipeline.

    Returns:
        Dicionário com session_id, stage, status e processing_time.

    Raises:
        ApplicationError: Se dados do estágio anterior estiverem ausentes no Redis.
    """
    start = time.time()
    logger.info(f"[classify] Iniciando — session={session_id}")

    from src.kt_search.query_enricher import EnrichmentResult
    from src.services.kt_search_service import get_kt_search_service

    redis = ctx["redis"]
    enrich_data = await _redis_get_json(redis, _stage_key(session_id, "enrich"))
    enrichment_result = EnrichmentResult(**enrich_data)

    comps = get_kt_search_service().components
    classification_result = comps["query_classifier"].classify_query_with_context(
        enrichment_result.cleaned_query,
        enrichment_result.entities,
        enrichment_result.context,
    )

    query_analysis: dict[str, Any] = comps["response_builder"].analyze_query_complexity(
        enrichment_result, classification_result, enrichment_result.original_query
    )

    payload = _serialize_classification(classification_result, query_analysis)
    await redis.set(_stage_key(session_id, "classify"), json.dumps(payload), ex=_TTL)

    elapsed = time.time() - start
    logger.info(
        f"[classify] {classification_result.query_type.value} "
        f"(conf={classification_result.confidence:.2f}) em {elapsed:.3f}s — session={session_id}"
    )
    return {"session_id": session_id, "stage": "classify", "status": "complete", "processing_time": elapsed}


async def kt_search_chromadb_task(ctx: dict[str, Any], session_id: str) -> dict[str, Any]:
    """Task ARQ — Fase 3: busca ChromaDB com early-exit para clientes inexistentes.

    Args:
        ctx: Contexto ARQ com redis.
        session_id: Identificador único da sessão de pipeline.

    Returns:
        Dicionário com session_id, stage, status, processing_time e early_exit flag.

    Raises:
        ApplicationError: Se dados de estágios anteriores estiverem ausentes no Redis.
    """
    start = time.time()
    logger.info(f"[chromadb] Iniciando — session={session_id}")

    from src.kt_search.query_enricher import EnrichmentResult
    from src.services.kt_search_service import get_kt_search_service

    redis = ctx["redis"]
    enrich_data = await _redis_get_json(redis, _stage_key(session_id, "enrich"))
    classify_data = await _redis_get_json(redis, _stage_key(session_id, "classify"))
    meta_data = await _redis_get_json(redis, _meta_key(session_id))

    enrichment_result = EnrichmentResult(**enrich_data)
    classification_result = _deserialize_classification(classify_data)
    query: str = meta_data["query"]
    created_at: float = meta_data["created_at"]

    comps = get_kt_search_service().components

    # Early-exit: cliente obviamente inexistente — evita busca ChromaDB desnecessária
    if comps["response_builder"].should_stop_for_nonexistent_client(query):
        logger.info(f"[chromadb] Early-exit: cliente inexistente detectado — session={session_id}")
        discovered_clients: list[str] = []
        try:
            discovery = comps["dynamic_client_manager"].discover_clients()
            discovered_clients = list(discovery.keys())
        except Exception as e:
            logger.warning(f"[chromadb] Não foi possível descobrir clientes: {e}")

        response = comps["response_builder"].create_client_not_found_response(query, created_at, discovered_clients)
        await redis.set(_final_key(session_id), json.dumps(_search_response_to_dict(response, created_at)), ex=_TTL)

        elapsed = time.time() - start
        return {
            "session_id": session_id,
            "stage": "chromadb",
            "status": "complete",
            "early_exit": True,
            "processing_time": elapsed,
        }

    raw_results: list[dict[str, Any]] = comps["chromadb_executor"].execute_search(
        enrichment_result, classification_result, query
    )

    await redis.set(_stage_key(session_id, "chromadb"), json.dumps(raw_results), ex=_TTL)

    elapsed = time.time() - start
    logger.info(f"[chromadb] {len(raw_results)} resultados em {elapsed:.3f}s — session={session_id}")
    return {
        "session_id": session_id,
        "stage": "chromadb",
        "status": "complete",
        "early_exit": False,
        "processing_time": elapsed,
    }


async def kt_search_discover_task(ctx: dict[str, Any], session_id: str) -> dict[str, Any]:
    """Task ARQ — Fase 4: descoberta dinâmica de clientes (apenas ENTITY e METADATA).

    Args:
        ctx: Contexto ARQ com redis.
        session_id: Identificador único da sessão de pipeline.

    Returns:
        Dicionário com session_id, stage, status, skipped flag e processing_time.

    Raises:
        ApplicationError: Se dados de estágios anteriores estiverem ausentes no Redis.
    """
    start = time.time()
    logger.info(f"[discover] Iniciando — session={session_id}")

    from src.kt_search.query_classifier import QueryType
    from src.services.kt_search_service import get_kt_search_service

    redis = ctx["redis"]
    classify_data = await _redis_get_json(redis, _stage_key(session_id, "classify"))
    chromadb_data = await _redis_get_json(redis, _stage_key(session_id, "chromadb"))
    enrich_data = await _redis_get_json(redis, _stage_key(session_id, "enrich"))

    query_type = QueryType(classify_data["query_type"])
    raw_results: list[dict[str, Any]] = chromadb_data
    entities: dict[str, Any] = enrich_data["entities"]

    comps = get_kt_search_service().components

    if query_type in (QueryType.ENTITY, QueryType.METADATA):
        enriched_results = comps["dynamic_client_manager"].enrich_with_client_discovery(raw_results, entities)
        skipped = False
    else:
        enriched_results = raw_results
        skipped = True

    await redis.set(
        _stage_key(session_id, "discover"),
        json.dumps({"results": enriched_results, "skipped": skipped}),
        ex=_TTL,
    )

    elapsed = time.time() - start
    logger.info(f"[discover] skipped={skipped} em {elapsed:.3f}s — session={session_id}")
    return {
        "session_id": session_id,
        "stage": "discover",
        "status": "complete",
        "skipped": skipped,
        "processing_time": elapsed,
    }


async def kt_search_select_task(ctx: dict[str, Any], session_id: str) -> dict[str, Any]:
    """Task ARQ — Fase 5: seleção inteligente de chunks por qualidade e diversidade.

    Args:
        ctx: Contexto ARQ com redis.
        session_id: Identificador único da sessão de pipeline.

    Returns:
        Dicionário com session_id, stage, status e processing_time.

    Raises:
        ApplicationError: Se dados de estágios anteriores estiverem ausentes no Redis.
    """
    start = time.time()
    logger.info(f"[select] Iniciando — session={session_id}")

    from src.services.kt_search_service import get_kt_search_service

    redis = ctx["redis"]
    classify_data = await _redis_get_json(redis, _stage_key(session_id, "classify"))
    discover_data = await _redis_get_json(redis, _stage_key(session_id, "discover"))
    enrich_data = await _redis_get_json(redis, _stage_key(session_id, "enrich"))

    classification_result = _deserialize_classification(classify_data)
    query_analysis: dict[str, Any] = classify_data["query_analysis"]
    results: list[dict[str, Any]] = discover_data["results"]
    original_query: str = enrich_data["original_query"]

    comps = get_kt_search_service().components
    top_k = comps["chunk_selector"].calculate_adaptive_top_k(classification_result.query_type, query_analysis)
    selection_result = comps["chunk_selector"].select_intelligent_chunks(
        results, top_k, classification_result.query_type, query_analysis, original_query
    )

    select_payload: dict[str, Any] = {
        "selected_chunks": selection_result.selected_chunks,
        "chunk_scores": [asdict(cs) for cs in selection_result.chunk_scores],
        "total_candidates": selection_result.total_candidates,
        "selection_strategy": selection_result.selection_strategy,
        "processing_time": selection_result.processing_time,
        "quality_threshold_met": selection_result.quality_threshold_met,
    }
    await redis.set(_stage_key(session_id, "select"), json.dumps(select_payload), ex=_TTL)

    elapsed = time.time() - start
    logger.info(
        f"[select] {len(selection_result.selected_chunks)} chunks selecionados em {elapsed:.3f}s — session={session_id}"
    )
    return {"session_id": session_id, "stage": "select", "status": "complete", "processing_time": elapsed}


async def kt_search_insights_task(ctx: dict[str, Any], session_id: str) -> dict[str, Any]:
    """Task ARQ — Fase 6: geração de insights LLM e construção da resposta final.

    Além de persistir o DirectInsightResult em stage:insights, constrói o
    KTSearchResponse final e o grava em kt_search:{session_id}:final para
    leitura direta pelo endpoint de resultado.

    Args:
        ctx: Contexto ARQ com redis.
        session_id: Identificador único da sessão de pipeline.

    Returns:
        Dicionário com session_id, stage, status e processing_time.

    Raises:
        ApplicationError: Se dados de estágios anteriores estiverem ausentes no Redis
            ou se a geração de insights retornar None.
    """
    start = time.time()
    logger.info(f"[insights] Iniciando — session={session_id}")

    from src.services.kt_search_service import get_kt_search_service

    redis = ctx["redis"]
    select_data = await _redis_get_json(redis, _stage_key(session_id, "select"))
    classify_data = await _redis_get_json(redis, _stage_key(session_id, "classify"))
    enrich_data = await _redis_get_json(redis, _stage_key(session_id, "enrich"))
    meta_data = await _redis_get_json(redis, _meta_key(session_id))

    original_query: str = enrich_data["original_query"]
    created_at: float = meta_data["created_at"]
    classification_result = _deserialize_classification(classify_data)
    selection_result = _deserialize_selection(select_data)

    comps = get_kt_search_service().components
    insights_result = comps["insights_agent"].generate_direct_insight(
        original_query=original_query,
        search_results=selection_result.selected_chunks,
    )

    if insights_result is None:
        raise ApplicationError(
            message="Geração de insights falhou (retornou None)",
            status_code=503,
            error_code="SERVICE_UNAVAILABLE",
        )

    await redis.set(_stage_key(session_id, "insights"), json.dumps(asdict(insights_result)), ex=_TTL)

    response = comps["response_builder"].format_final_response(
        original_query, insights_result, selection_result, classification_result, created_at
    )
    await redis.set(_final_key(session_id), json.dumps(_search_response_to_dict(response, created_at)), ex=_TTL)

    elapsed = time.time() - start
    logger.info(f"[insights] Concluído em {elapsed:.3f}s — session={session_id}")
    return {"session_id": session_id, "stage": "insights", "status": "complete", "processing_time": elapsed}
