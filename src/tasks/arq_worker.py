"""
ARQ Worker - Processa jobs assíncronos.

Configuração:
- Redis URL via settings
- Max 4 jobs simultâneos (ajustar se necessário)
- Job timeout: 1 hora (ajustar conforme necessário)

Tasks:
- TODO: Adicionar tasks customizadas (ex: process_data, send_email, etc.)
"""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from arq.connections import RedisSettings

from src.config.settings import REDIS_DB, REDIS_HOST, REDIS_PASSWORD, REDIS_PORT
from utils.logger_setup import LoggerManager, get_logger

if TYPE_CHECKING:
    from arq.typing import WorkerSettingsType

# Logger criado ANTES de configurar LOG_DIR (fallback tolerante permite isso)
logger = get_logger(__name__)

# LOG_DIR para configuração no startup callback
LOG_DIR = Path(__file__).parent.parent.parent / "logs"


# ════════════════════════════════════════════════════════════════════════════
# TASKS (Funções assíncronas processadas pelo worker)
# ════════════════════════════════════════════════════════════════════════════


async def exemplo_task(ctx: dict, mensagem: str = "ping") -> dict[str, Any]:
    """
    Task de exemplo — substitua por tasks reais do projeto.

    Args:
        ctx: Contexto ARQ (contém redis pool, job_id, etc.)
        mensagem: Mensagem de teste

    Returns:
        Resultado com status e mensagem
    """
    logger.info(f"exemplo_task executada: mensagem={mensagem}")
    return {"status": "ok", "mensagem": mensagem}


# TODO: Adicionar tasks customizadas do projeto aqui e registrá-las em WorkerSettings.functions


# ════════════════════════════════════════════════════════════════════════════
# CALLBACKS
# ════════════════════════════════════════════════════════════════════════════


async def startup(ctx: dict) -> None:
    """Callback executado ao iniciar worker."""
    # Configurar LOG_DIR para ativar file logging
    LoggerManager.set_default_log_dir(LOG_DIR)
    logger.info("ARQ Worker iniciado com file logging ativado")
    logger.info(f"Redis: {REDIS_HOST}:{REDIS_PORT} (db={REDIS_DB})")
    logger.info(f"Redis Auth: {'Sim' if REDIS_PASSWORD else 'Não'}")
    logger.info("Max jobs: 4")


async def shutdown(ctx: dict) -> None:
    """Callback executado ao encerrar worker."""
    logger.info("ARQ Worker encerrado")


# ════════════════════════════════════════════════════════════════════════════
# ARQ WORKER SETTINGS
# ════════════════════════════════════════════════════════════════════════════


class WorkerSettings:
    """
    Configurações do ARQ worker.

    Documentação: https://arq-docs.helpmanual.io/
    """

    # Funções (tasks) disponíveis para enfileirar
    # TODO: Substituir exemplo_task pelas tasks reais do projeto
    functions: list[Callable[..., Any]] = [exemplo_task]

    # Configuração Redis
    redis_settings = RedisSettings(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD if REDIS_PASSWORD else None,
        database=REDIS_DB,
    )

    # Worker config
    max_jobs = 4  # Máximo de jobs simultâneos (ajustar conforme necessário)
    job_timeout = 3600  # 1 hora (ajustar conforme necessário)
    keep_result = 3600  # Mantém resultado por 1 hora no Redis

    # Logging
    on_startup = startup
    on_shutdown = shutdown


# ════════════════════════════════════════════════════════════════════════════
# MAIN (opcional - para executar worker standalone)
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import asyncio
    from typing import cast

    from arq import run_worker

    # run_worker retorna Worker, que precisa ser executado com async_run()
    # Cast para satisfazer mypy (WorkerSettings é um duck-type válido)
    worker = run_worker(cast("WorkerSettingsType", WorkerSettings))
    asyncio.run(worker.async_run())
