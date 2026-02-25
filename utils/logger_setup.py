"""
Centralized logging configuration - Portável e reutilizável.

Fornece setup de logging thread-safe e idempotente.
Feature ETAPA: adiciona linha em branco ao trocar contexto para legibilidade.

Princípios:
- Não limpar handlers existentes (seguro para frameworks)
- File logging configurável
- Estado do formatter por instância (thread-safe)
- Configuração de loggers externos
- Idempotente: múltiplas chamadas não duplicam handlers
"""

import logging
import sys
from pathlib import Path
from typing import Any


class EnhancedFormatter(logging.Formatter):
    """
    Formatter com linha em branco ao trocar contexto (feature ETAPA).

    Formato: TIMESTAMP [logger_name] [LEVEL] message
    Exemplo: 2025-12-10 15:07:25 [rag_processor] [INFO] Cache validado

    Feature ETAPA:
    - Adiciona linha em branco ao trocar de logger (módulo diferente)
    - Adiciona linha em branco antes de delimitadores ETAPA (═════)
    - Estado mantido por instância (thread-safe)
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._last_logger_name: str = ""
        self._last_had_content: bool = False
        self._in_etapa_block: bool = False

    def format(self, record: logging.LogRecord) -> str:
        """Formata log com linha em branco ao trocar contexto."""
        timestamp = self.formatTime(record, self.datefmt)
        level = record.levelname
        name = record.name
        msg = record.getMessage()

        prefix = ""
        if self._last_logger_name and self._last_logger_name != name:
            prefix = "\n"
            self._last_had_content = False
            self._in_etapa_block = False

        is_delimiter = "═" in msg and len(msg.strip()) > 50 and msg.strip().replace("═", "") == ""
        is_etapa_title = msg.strip().startswith("ETAPA") and ":" in msg
        is_etapa_start = is_delimiter and not self._in_etapa_block

        if is_etapa_start and self._last_had_content and not prefix:
            prefix = "\n"
            self._last_had_content = False

        if is_etapa_title:
            self._in_etapa_block = True
        elif is_delimiter and self._in_etapa_block:
            self._in_etapa_block = False

        self._last_logger_name = name
        formatted = f"{prefix}{timestamp} [{name}] [{level}] {msg}"

        if not prefix:
            self._last_had_content = True

        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)

        return formatted


class LoggerManager:
    """
    Gerenciador de logging thread-safe com dependency injection.

    Dependency Injection:
    - Chame set_default_log_dir(log_dir) ANTES de qualquer get_logger()
    - Se log_dir foi definido → auto-config com console+file
    - Senão → auto-config com console apenas

    Configuração uma vez, reutilização em todo o projeto.
    Múltiplas chamadas a setup_logging() não duplicam handlers.
    """

    _initialized = False
    _log_file: Path | None = None
    _created_handlers: list[logging.Handler] = []
    _default_log_dir: Path | None = None  # Diretório injetado para auto-config file logging

    @classmethod
    def set_default_log_dir(cls, log_dir: Path | str) -> None:
        """
        Define diretório padrão para logs (dependency injection).

        Deve ser chamado ANTES de qualquer get_logger() para ativar file logging automático.
        Se não chamado, get_logger() inicializa apenas com console.

        Args:
            log_dir: Diretório onde arquivos de log serão criados (ex: Path("logs/"))

        Example:
            from src.config.settings import LOG_DIR
            LoggerManager.set_default_log_dir(LOG_DIR)
        """
        cls._default_log_dir = Path(log_dir) if isinstance(log_dir, str) else log_dir

    @classmethod
    def setup_logging(
        cls,
        log_file: str | Path | None = None,
        level: str = "INFO",
        console: bool = True,
        enable_file: bool = False,
    ) -> None:
        """
        Configura logging para a aplicação.

        Args:
            log_file: Caminho para arquivo de log (requerido se enable_file=True)
            level: Nível de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            console: Habilita console logging
            enable_file: Habilita file logging

        Raises:
            ValueError: Se enable_file=True mas log_file não foi informado
        """
        if cls._initialized:
            return

        if enable_file and not log_file:
            raise ValueError("enable_file=True requer log_file especificado")

        numeric_level = getattr(logging, level.upper(), logging.INFO)
        formatter = EnhancedFormatter(datefmt="%Y-%m-%d %H:%M:%S")

        root_logger = logging.getLogger()
        root_logger.setLevel(numeric_level)

        if console:
            has_console = any(
                isinstance(h, logging.StreamHandler) and h.stream == sys.stdout for h in root_logger.handlers
            )
            if not has_console:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setLevel(numeric_level)
                console_handler.setFormatter(formatter)
                root_logger.addHandler(console_handler)
                cls._created_handlers.append(console_handler)

        if enable_file and log_file:
            log_path = Path(log_file) if isinstance(log_file, str) else log_file
            log_path.parent.mkdir(parents=True, exist_ok=True)

            has_file = any(
                isinstance(h, logging.FileHandler) and Path(h.baseFilename) == log_path for h in root_logger.handlers
            )
            if not has_file:
                file_handler = logging.FileHandler(log_path, encoding="utf-8")
                file_handler.setLevel(numeric_level)
                file_handler.setFormatter(formatter)
                root_logger.addHandler(file_handler)
                cls._created_handlers.append(file_handler)
                cls._log_file = log_path

        # Suprime loggers verbosos de bibliotecas externas
        logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("openai").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("langchain_google_genai._function_utils").setLevel(logging.ERROR)
        logging.getLogger("google_genai._api_client").setLevel(logging.WARNING)
        logging.getLogger("google_genai.models").setLevel(logging.WARNING)

        cls._initialized = True

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        Retorna logger para um módulo.

        Auto-inicializa na primeira chamada:
        - Se default_log_dir foi definido → cria arquivo em default_log_dir/application_YYYYMMDD.log + console
        - Senão → console apenas (fallback tolerante para import-time antes de LOG_DIR configurado)

        IMPORTANTE: Fallback permite imports antes de LOG_DIR estar configurado (ex: uvicorn subprocess).
        Quando LOG_DIR for configurado via set_default_log_dir(), próxima chamada a get_logger()
        irá reconfigurar com file logging via setup_logging().

        Args:
            name: Nome do módulo (geralmente __name__)

        Returns:
            Logger configurado (console+file se LOG_DIR definido, console-only caso contrário)
        """
        if not cls._initialized:
            if cls._default_log_dir is None:
                # FALLBACK TOLERANTE: Console-only para permitir imports antes de LOG_DIR configurado
                # Cenário: uvicorn --reload subprocess importa módulos antes de lifespan configurar LOG_DIR
                cls.setup_logging(
                    log_file=None,  # Sem arquivo ainda
                    level="INFO",
                    console=True,
                    enable_file=False,  # Apenas console
                )
            else:
                # LOG_DIR configurado → habilita file logging
                from datetime import datetime

                cls._default_log_dir.mkdir(parents=True, exist_ok=True)
                log_file_path = cls._default_log_dir / f"application_{datetime.now().strftime('%Y%m%d')}.log"

                cls.setup_logging(
                    log_file=str(log_file_path),
                    level="INFO",
                    console=True,
                    enable_file=True,
                )

        return logging.getLogger(name)


def get_logger(name: str) -> logging.Logger:
    """
    Função de conveniência para obter logger.

    Args:
        name: Nome do módulo (geralmente __name__)

    Returns:
        Logger configurado
    """
    return LoggerManager.get_logger(name)
