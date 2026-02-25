"""Task ARQ para ingestion de reuniões KT.

Executa em background — não bloqueia o servidor HTTP.
ApplicationError propagada automaticamente → ARQ registra job como failed.
"""

from typing import Any

from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)


async def kt_ingestion_task(ctx: dict[str, Any]) -> dict[str, Any]:
    """Task ARQ para ingestion incremental de reuniões TL:DV.

    Args:
        ctx: Contexto ARQ (injetado automaticamente pelo worker).

    Returns:
        Estatísticas da execução (meetings_found, meetings_downloaded, etc.).

    Raises:
        ApplicationError: Propagada para o ARQ framework registrar job como failed.
    """
    logger.info("Iniciando task de ingestion KT")
    from src.services.kt_ingestion_service import get_kt_ingestion_service

    service = get_kt_ingestion_service()
    stats = service.run_ingestion()
    logger.info(
        f"Task de ingestion concluída — "
        f"baixadas: {stats.get('meetings_downloaded', 0)}, "
        f"falhas: {stats.get('meetings_failed', 0)}"
    )
    return stats
