"""Application Startup Configuration"""

import logging
from datetime import datetime

from src.config.settings import BASE_DIR, DIRECTORY_PATHS, LOG_DIR, LOG_LEVEL
from utils.logger_setup import LoggerManager


def ensure_directories_exist() -> None:
    """
    Garante que todos os diretórios necessários existem.
    Cria pastas base (logs, data, cache, etc.) se não existirem.
    """
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    for path in DIRECTORY_PATHS.values():
        path.mkdir(parents=True, exist_ok=True)


def setup_logging() -> logging.Logger:
    """
    Configura sistema de logging da aplicação.

    Returns:
        logging.Logger: Logger principal configurado

    Side Effects:
        - Cria arquivo de log em LOG_DIR/application_YYYYMMDD.log
        - Configura níveis de log para bibliotecas externas
        - Registra informações de startup
    """
    log_file = LOG_DIR / f"application_{datetime.now().strftime('%Y%m%d')}.log"

    LoggerManager.setup_logging(
        log_file=str(log_file),
        level=LOG_LEVEL,
        console=True,
        enable_file=True,
    )

    logger = LoggerManager.get_logger("config")

    # Silence verbose external libraries
    for lib in ["urllib3", "httpx", "requests", "httpcore", "chromadb", "openai", "streamlit"]:
        logging.getLogger(lib).setLevel(logging.WARNING)

    logger.info(f"Log file: {log_file}")

    return logger


def initialize_application() -> logging.Logger:
    """
    Inicializa aplicação completa.

    IMPORTANTE: load_dotenv() ocorre automaticamente via settings.py (importado antes
    deste módulo em qualquer contexto: uvicorn, arq CLI, pytest).

    Executa:
        1. Criação de diretórios necessários
        2. Setup de logging

    Returns:
        logging.Logger: Logger principal configurado
    """
    ensure_directories_exist()
    return setup_logging()
