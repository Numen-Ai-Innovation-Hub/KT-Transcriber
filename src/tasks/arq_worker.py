"""
ARQ Worker - Processa jobs assíncronos KT.

Configuração:
- Redis URL via settings
- Max 2 jobs simultâneos (ingestion e indexação são intensivos em I/O e API calls)
- Job timeout: 2 horas (ingestion de muitas reuniões pode ser demorado)

Tasks:
- kt_ingestion_task — Download incremental de reuniões TL:DV → JSONs em transcriptions/
- kt_indexing_task  — Indexação incremental de JSONs → ChromaDB (chunks + embeddings + LLM metadata)

Entry point exclusivo: arq src.tasks.arq_worker.WorkerSettings
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from arq.connections import RedisSettings

from src.config.settings import REDIS_DB, REDIS_HOST, REDIS_PASSWORD, REDIS_PORT
from src.tasks.kt_indexing_task import kt_indexing_task
from src.tasks.kt_ingestion_task import kt_ingestion_task
from utils.logger_setup import LoggerManager, get_logger

# Logger criado ANTES de configurar LOG_DIR (fallback tolerante permite isso)
logger = get_logger(__name__)

# LOG_DIR para configuração no startup callback
LOG_DIR = Path(__file__).parent.parent.parent / "logs"


# ════════════════════════════════════════════════════════════════════════════
# CALLBACKS
# ════════════════════════════════════════════════════════════════════════════


async def startup(ctx: dict[str, Any]) -> None:
    """Callback executado ao iniciar worker."""
    LoggerManager.set_default_log_dir(LOG_DIR)
    logger.info("ARQ Worker KT iniciado com file logging ativado")
    logger.info(f"Redis: {REDIS_HOST}:{REDIS_PORT} (db={REDIS_DB})")
    logger.info(f"Redis Auth: {'Sim' if REDIS_PASSWORD else 'Não'}")
    logger.info("Max jobs: 2 | Timeout: 7200s")


async def shutdown(ctx: dict[str, Any]) -> None:
    """Callback executado ao encerrar worker."""
    logger.info("ARQ Worker KT encerrado")


# ════════════════════════════════════════════════════════════════════════════
# ARQ WORKER SETTINGS
# ════════════════════════════════════════════════════════════════════════════


class WorkerSettings:
    """Configurações do ARQ worker KT.

    Documentação: https://arq-docs.helpmanual.io/
    """

    functions: list[Callable[..., Any]] = [kt_ingestion_task, kt_indexing_task]

    redis_settings = RedisSettings(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD if REDIS_PASSWORD else None,
        database=REDIS_DB,
    )

    max_jobs = 2  # Ingestion e indexação são operações pesadas — limitar concorrência
    job_timeout = 7200  # 2 horas (ingestion de muitas reuniões pode ser lento)
    keep_result = 3600  # Mantém resultado por 1 hora no Redis

    on_startup = startup
    on_shutdown = shutdown
