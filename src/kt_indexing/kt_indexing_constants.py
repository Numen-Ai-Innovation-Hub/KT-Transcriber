"""Constantes do domínio kt_indexing — Transcrição de KT.

Consolida configurações de chunking, metadados e indexação ChromaDB.
Unifica src/core/processing/config.py + src/core/indexing/config.py do projeto legado.
"""

from src.config.settings import CHROMA_COLLECTION_NAME, DIRECTORY_PATHS, OPENAI_EMBEDDING_MODEL, OPENAI_MODEL

# ════════════════════════════════════════════════════════════════════════════
# CHUNK CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════

CHUNK_CONFIG = {
    "max_chars": 1000,
    "overlap_chars": 200,
    "min_chars": 50,
}

# Padrões de separação de sentenças para chunking inteligente
SENTENCE_PATTERNS = [
    r"(?<=[.!?])\s+",
    r"(?<=\n)\s*",
    r"(?<=,)\s+(?=[A-ZÁÉÍÓÚÃÕÂÊÎÔÛÀÈÌÒÙ])",
]

# ════════════════════════════════════════════════════════════════════════════
# LLM CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════

LLM_CONFIG = {
    "model": OPENAI_MODEL,
    "max_retries": 3,
    "max_tokens": 1000,
    "temperature": 0.1,
}

# Prompt para extração de metadados via LLM
ENHANCED_METADATA_EXTRACTION_PROMPT = """Analise o seguinte trecho de transcrição de uma reunião de KT (Knowledge Transfer) SAP e extraia metadados estruturados.

TRECHO DA TRANSCRIÇÃO:
{chunk_text}

CONTEXTO DO VÍDEO:
- Nome do vídeo: {video_name}
- Cliente: {client_name}

Extraia os seguintes metadados no formato Python de variáveis:

meeting_phase = "apresentacao|demo|discussao|qa|encerramento"  # Fase da reunião
kt_type = "sustentacao|implementacao|treinamento|migracao|integracao|outro"  # Tipo de KT
sap_modules = ["lista", "de", "modulos"]  # Módulos SAP mencionados (ex: MM, SD, FI, CO, EWM)
transactions = ["lista", "de", "transacoes"]  # Transações SAP mencionadas (ex: F110, ME21N)
technical_terms = ["lista", "de", "termos"]  # Termos técnicos relevantes
participants_mentioned = ["lista", "de", "participantes"]  # Nomes mencionados no trecho
systems = ["lista", "de", "sistemas"]  # Sistemas mencionados (ex: CPI, Fiori, BTP)
decisions = "texto descrevendo decisões tomadas no trecho"  # Decisões importantes
problems = "texto descrevendo problemas mencionados"  # Problemas/issues mencionados
searchable_tags = ["lista", "de", "tags"]  # Tags para busca semântica

Responda APENAS com as variáveis Python acima, sem explicações extras."""

# ════════════════════════════════════════════════════════════════════════════
# CHROMADB CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════

CHROMADB_CONFIG = {
    "persist_directory": str(DIRECTORY_PATHS["vector_db"]),
    "collection_name": CHROMA_COLLECTION_NAME,
    "embedding_dimensions": 1536,
    "max_batch_size": 100,
    "anonymized_telemetry": False,
    "allow_reset": False,
}

# ════════════════════════════════════════════════════════════════════════════
# OPENAI EMBEDDING CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════

OPENAI_CONFIG = {
    "model": OPENAI_EMBEDDING_MODEL,
    "dimensions": 1536,
    "max_retries": 3,
    "max_tokens": 8192,
    "rate_limit_delay": 0.1,
}

# ════════════════════════════════════════════════════════════════════════════
# FILE GENERATION CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════

FILE_CONFIG = {
    "encoding": "utf-8",
    "extension": ".txt",
    "max_filename_length": 200,
    "separator": "─" * 80,
}

# ════════════════════════════════════════════════════════════════════════════
# VALIDATION RULES
# ════════════════════════════════════════════════════════════════════════════

VALIDATION_RULES = {
    "min_content_length": 10,
    "max_content_length": 10000,
    "required_sections": ["TLDV", "CUSTOMIZADOS", "CHUNK"],
    "required_tldv_fields": [
        "video_name",
        "meeting_id",
        "original_url",
        "video_folder",
        "speaker",
        "start_time_formatted",
        "end_time_formatted",
        "processing_date",
        "client_name",
        "sap_modules_title",
        "participants_list",
        "highlights_summary",
        "decisions_summary",
    ],
    "required_customized_fields": [
        "sap_modules",
        "systems",
        "transactions",
        "integrations",
        "technical_terms",
        "participants_mentioned",
        "speaker_role",
        "meeting_phase",
        "meeting_date",
        "topics",
        "content_type",
        "business_impact",
        "knowledge_area",
        "key_decisions",
        "client_variations",
        "searchable_tags",
    ],
    "min_chunk_length": 50,
    "max_chunk_length": 1000,
}

METADATA_LIMITS = {
    "max_list_items": 20,
    "max_string_length": 500,
    "max_tags": 15,
}

VALID_ENUMS = {
    "meeting_phase": ["apresentacao", "demo", "discussao", "qa", "encerramento", "unknown"],
    "kt_type": ["sustentacao", "implementacao", "treinamento", "migracao", "integracao", "outro", "unknown"],
}

METADATA_DEFAULTS = {
    "meeting_phase": "unknown",
    "kt_type": "unknown",
    "sap_modules": [],
    "transactions": [],
    "technical_terms": [],
    "participants_mentioned": [],
    "systems": [],
    "decisions": "",
    "problems": "",
    "searchable_tags": [],
}

# ════════════════════════════════════════════════════════════════════════════
# NORMALIZAÇÃO E PADRÕES
# ════════════════════════════════════════════════════════════════════════════

# Substituições de caracteres para normalização
CHAR_REPLACEMENTS = {
    "\u2019": "'",  # Right single quotation mark
    "\u2018": "'",  # Left single quotation mark
    "\u201c": '"',  # Left double quotation mark
    "\u201d": '"',  # Right double quotation mark
    "\u2013": "-",  # En dash
    "\u2014": "-",  # Em dash
    "\u00e2\u0080\u0099": "'",  # UTF-8 encoding issue
    "\u00c2\u00b4": "'",  # Acute accent encoding issue
}

# Padrões para detectar clientes em nomes de vídeo
CLIENT_PATTERNS: dict[str, list[str]] = {}

# Padrões para detectar tipo de KT
KT_TYPE_PATTERNS: dict[str, list[str]] = {
    "sustentacao": ["sustentação", "sustentacao", "suporte", "support"],
    "implementacao": ["implementação", "implementacao", "implantação", "implantacao", "go-live", "go live"],
    "treinamento": ["treinamento", "treino", "training", "capacitação", "capacitacao"],
    "migracao": ["migração", "migracao", "migration", "migrar"],
    "integracao": ["integração", "integracao", "integration", "integrar", "cpi", "iflow"],
}

# ════════════════════════════════════════════════════════════════════════════
# PERFORMANCE CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════

PERFORMANCE_CONFIG = {
    "batch_size": 10,
    "rate_limit_delay": 0.1,
    "max_concurrent_requests": 5,
}

ERROR_CONFIG = {
    "max_retries": 3,
    "retry_delay": 1.0,
    "fail_fast": False,
}
