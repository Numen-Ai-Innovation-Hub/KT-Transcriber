"""Constantes do domínio kt_ingestion — Transcrição de KT.

Consolida configurações do cliente TL:DV e processamento de transcrições.
"""

# ════════════════════════════════════════════════════════════════════════════
# TLDV API
# ════════════════════════════════════════════════════════════════════════════

TLDV_MEETINGS_ENDPOINT = "meetings"
TLDV_IMPORTS_ENDPOINT = "imports"

# Status de processamento TL:DV
TLDV_STATUS_DONE = "done"
TLDV_STATUS_PROCESSING = "processing"
TLDV_STATUS_FAILED = "failed"
TLDV_STATUS_PENDING = "pending"

# Limites de polling
TLDV_MAX_WAIT_SECONDS = 300  # 5 minutos máximo de espera por reunião
TLDV_POLL_INTERVAL_SECONDS = 10  # Verificar a cada 10s

# ════════════════════════════════════════════════════════════════════════════
# CONSOLIDAÇÃO DE JSON
# ════════════════════════════════════════════════════════════════════════════

# Formato do arquivo JSON consolidado
JSON_OUTPUT_EXTENSION = ".json"

# Configuração de codificação
FILE_ENCODING = "utf-8"

# ════════════════════════════════════════════════════════════════════════════
# SMART PROCESSOR
# ════════════════════════════════════════════════════════════════════════════

# Timeout para threads de processamento em background
BACKGROUND_THREAD_TIMEOUT = 300  # 5 minutos

# Número máximo de threads de background simultâneas
MAX_BACKGROUND_THREADS = 5
