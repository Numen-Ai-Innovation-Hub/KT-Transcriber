"""Task ARQ para pipeline seletivo KT (ingestion + indexação).

Executa em sequência:
1. force_clean opcional — apaga transcriptions/, vector_db/ e chunks/
2. Ingestion seletiva — baixa apenas os meeting_ids fornecidos
3. Indexação incremental — indexa novos JSONs no ChromaDB

As operações síncronas pesadas (HTTP TL:DV, OpenAI embeddings/LLM) rodam via
run_in_executor para não bloquear o event loop do ARQ. Isso mantém o polling
Redis ativo e evita TimeoutError por idle em conexões Redis Cloud.

Entry point via enqueue_job("kt_selective_pipeline_task", meeting_ids=[...], session_id="...", force_clean=False)
"""

import asyncio
from typing import Any

from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)


async def kt_selective_pipeline_task(
    ctx: dict[str, Any],
    meeting_ids: list[str],
    session_id: str,
    force_clean: bool = False,
) -> dict[str, Any]:
    """Task ARQ para pipeline seletivo: ingestion seletiva + indexação incremental.

    Args:
        ctx: Contexto ARQ (injetado automaticamente — contém redis, job_id, etc.).
        meeting_ids: IDs das reuniões TL:DV a baixar e indexar.
        session_id: ID da sessão para rastreamento no cliente.
        force_clean: Se True, apaga todos os dados existentes antes de iniciar.

    Returns:
        Dicionário com stats de ingestion, indexação e metadados da sessão.
    """
    from src.services.kt_indexing_service import get_kt_indexing_service
    from src.services.kt_ingestion_service import get_kt_ingestion_service

    logger.info(
        f"[selective_pipeline] Iniciando — session={session_id}, "
        f"meetings={len(meeting_ids)}, force_clean={force_clean}"
    )

    ingestion_svc = get_kt_ingestion_service()
    indexing_svc = get_kt_indexing_service()
    loop = asyncio.get_running_loop()

    if force_clean:
        logger.warning("[selective_pipeline] Force clean ativado — apagando dados existentes")
        await loop.run_in_executor(None, ingestion_svc.force_clean)
        await loop.run_in_executor(None, indexing_svc.force_clean)

    logger.info(f"[selective_pipeline] Fase 1/2: ingestion seletiva de {len(meeting_ids)} reunião(ões)")
    ingestion_stats: dict[str, Any] = await loop.run_in_executor(
        None, ingestion_svc.run_selective_ingestion, meeting_ids
    )

    logger.info("[selective_pipeline] Fase 2/2: indexação incremental no ChromaDB")
    indexing_stats: dict[str, Any] = await loop.run_in_executor(None, indexing_svc.run_indexing)

    result: dict[str, Any] = {
        "session_id": session_id,
        "ingestion": ingestion_stats,
        "indexing": indexing_stats,
        "total_meetings_selected": len(meeting_ids),
        "status": "complete",
    }

    logger.info(
        f"[selective_pipeline] Concluído — session={session_id} | "
        f"baixadas: {ingestion_stats.get('meetings_downloaded', 0)}, "
        f"chunks: {indexing_stats.get('chunks_indexed', 0)}, "
        f"falhas: {ingestion_stats.get('meetings_failed', 0)}"
    )
    return result
