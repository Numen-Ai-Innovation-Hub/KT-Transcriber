"""
Configuration Settings - Python FastAPI Template
────────────────────────────────────────────────────────────────────────────────

Central configuration module with environment-based settings.
Contains ONLY constants, paths, and dictionaries - NO logic or side effects.
"""

import os
from pathlib import Path

# CRITICAL: Carregar .env automaticamente quando settings.py é importado
# Necessário para todos os contextos: uvicorn, arq CLI, pytest (sem entry point dedicado)
from dotenv import load_dotenv

load_dotenv()

# ════════════════════════════════════════════════════════════════════════════
# FORMATTING CONSTANTS
# ════════════════════════════════════════════════════════════════════════════

MAX_LINE_LENGTH = 120  # PEP 8 standard, configured in pyproject.toml
TERMINAL_WIDTH = 120
DELIMITER_CHAR = "─"  # U+2500 Box Drawing Light Horizontal
DELIMITER_HEAVY = "═"  # U+2550 Box Drawing Double Horizontal
DELIMITER_POPUP = "━"  # U+2501 Box Drawing Heavy Horizontal
DELIMITER_LINE = DELIMITER_CHAR * MAX_LINE_LENGTH  # 120 chars
DELIMITER_SECTION = DELIMITER_HEAVY * MAX_LINE_LENGTH  # 120 chars
DELIMITER_POPUP_LINE = DELIMITER_POPUP * 50  # 50 chars (popup width optimization)


# ════════════════════════════════════════════════════════════════════════════
# DIRECTORY PATHS
# ════════════════════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # src/config -> src -> root
LOG_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

DIRECTORY_PATHS = {
    "sqlite_db": DATA_DIR / "sqlite_db",  # Bancos SQLite — hash_manager (hashes.db)
    "vector_db": DATA_DIR / "vector_db",  # ChromaDB PersistentClient
    "transcriptions": DATA_DIR / "transcriptions",  # JSONs de transcrição TL:DV
}

FILE_PATHS = {
    "hashes_db": DATA_DIR / "sqlite_db" / "hashes.db",  # Banco de hashes do hash_manager
}


# ════════════════════════════════════════════════════════════════════════════
# APPLICATION CONFIGURATION (Lidas do .env)
# ════════════════════════════════════════════════════════════════════════════

APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT", "development")  # development | staging | production
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Processing Configuration
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))  # Número de tentativas em caso de falha
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))  # Timeout em segundos para requests HTTP
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))  # Tamanho do lote para processamento em batch

# Redis Configuration (ARQ + Cache)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# TL:DV API
TLDV_API_KEY = os.getenv("TLDV_API_KEY", "")
TLDV_BASE_URL = os.getenv("TLDV_BASE_URL", "https://api.tldv.io/v1alpha1")
TLDV_TIMEOUT = int(os.getenv("TLDV_TIMEOUT", "60"))

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "4096"))
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

# ChromaDB
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "kt_transcriptions")
