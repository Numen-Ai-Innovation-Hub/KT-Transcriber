"""Task ARQ para indexação de JSONs KT no ChromaDB.

Executa em background — não bloqueia o servidor HTTP.
ApplicationError propagada automaticamente → ARQ registra job como failed.
"""

from typing import Any

from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)


async def kt_indexing_task(ctx: dict[str, Any]) -> dict[str, Any]:
    """Task ARQ para indexação incremental de JSONs no ChromaDB.

    Args:
        ctx: Contexto ARQ (injetado automaticamente pelo worker).

    Returns:
        Estatísticas da execução (videos_indexed, chunks_indexed, etc.).

    Raises:
        ApplicationError: Propagada para o ARQ framework registrar job como failed.
    """
    logger.info("Iniciando task de indexação KT")
    from src.services.kt_indexing_service import get_kt_indexing_service

    service = get_kt_indexing_service()
    stats = service.run_indexing()
    logger.info(
        f"Task de indexação concluída — "
        f"indexados: {stats.get('videos_indexed', 0)}, "
        f"chunks: {stats.get('chunks_indexed', 0)}, "
        f"falhas: {stats.get('videos_failed', 0)}"
    )
    return stats
