"""Constantes do domínio kt_search — busca semântica RAG em transcrições KT.

Define thresholds, estratégias e templates para o sistema RAG avançado
com suporte a 5 tipos de query semântica em transcrições KT.
"""

import os
from typing import Any

# ════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DE BUSCA
# ════════════════════════════════════════════════════════════════════════════

SEARCH_CONFIG: dict[str, Any] = {
    # Processamento de query
    "max_query_length": 500,
    "min_query_length": 5,
    "default_top_k": 10,
    # Thresholds de qualidade
    "similarity_threshold": 0.2,
    "quality_threshold": 0.3,
    "relevance_threshold": 0.25,
    # Restrições de performance
    "max_processing_time": 2.0,
    "max_embedding_calls": 1,
    "cache_embeddings": True,
    # Tratamento de erros
    "fail_fast": True,
    "enable_fallbacks": False,
}

# ════════════════════════════════════════════════════════════════════════════
# ESTRATÉGIA TOP_K POR TIPO DE QUERY
# ════════════════════════════════════════════════════════════════════════════

TOP_K_STRATEGY = {
    "SEMANTIC": {
        "base": 8,
        "with_client": 12,
        "technical_query": 6,
        "broad_query": 15,
        "max_limit": 20,
    },
    "METADATA": {
        "base": 20,
        "client_list": 100,
        "video_list": 500,
        "summary_view": 30,
        "max_limit": 500,
    },
    "ENTITY": {
        "base": 10,
        "participants": 15,
        "client_focused": 8,
        "cross_client": 12,
        "max_limit": 25,
    },
    "TEMPORAL": {
        "base": 12,
        "recent_focused": 8,
        "date_range": 20,
        "trend_analysis": 15,
        "max_limit": 30,
    },
    "CONTENT": {
        "base": 15,
        "exact_match": 20,
        "partial_match": 10,
        "quoted_search": 25,
        "max_limit": 30,
    },
}

# ════════════════════════════════════════════════════════════════════════════
# PERFORMANCE E PRECISÃO
# ════════════════════════════════════════════════════════════════════════════

PERFORMANCE_CONFIG = {
    "quality_threshold": 0.3,
    "similarity_threshold": 0.2,
    "relevance_threshold": 0.25,
    "max_processing_time": 2.0,
    "max_embedding_calls": 1,
    "cache_embeddings": True,
    "fast_mode": {
        "enabled_for": ["METADATA", "ENTITY"],
        "skip_embedding": True,
        "reduced_top_k_factor": 0.7,
        "quick_filters": True,
    },
    "comprehensive_mode": {
        "enabled_for": ["SEMANTIC"],
        "enhanced_embedding": True,
        "increased_top_k_factor": 1.2,
        "deep_analysis": True,
    },
    "adaptive_mode": {
        "enabled_for": ["TEMPORAL", "CONTENT"],
        "dynamic_top_k": True,
        "smart_filtering": True,
        "result_optimization": True,
    },
}

# ════════════════════════════════════════════════════════════════════════════
# PADRÕES DE CLASSIFICAÇÃO DE QUERIES
# ════════════════════════════════════════════════════════════════════════════

QUERY_PATTERNS = {
    "SEMANTIC": [
        "o que temos",
        "principais pontos",
        "informações sobre",
        "como funciona",
        "qual o objetivo",
        "resumo",
        "resuma",
        "me traga",
        "principais",
        "informação",
        "processo",
        "como foram",
        "o que sabemos",
        "sabemos sobre",
        "temos de informação",
        "discutidos",
        "pontos discutidos",
        "foram discutidos",
    ],
    "METADATA": [
        "liste",
        "quais",
        "quantos",
        "disponíveis",
        "base de conhecimento",
        "vídeos",
        "kts",
        "reuniões",
        "clientes",
        "projetos",
        "mostre",
        "exiba",
    ],
    "ENTITY": [
        "quem participou",
        "participantes",
        "de qual cliente",
        "informações do cliente",
        "pessoas envolvidas",
        "quem estava",
        "equipe",
    ],
    "TEMPORAL": ["últimos", "dias", "mês", "ano", "recentes", "setembro", "outubro", "2024", "2025", "ontem", "semana"],
    "CONTENT": [
        "onde mencionaram",
        "menção",
        "literal",
        "exata",
        "procurar",
        "chunk:",
        "busca literal",
        "encontre",
        "texto",
        "transação",
        "tcode",
        "código",
        "zewm",
        "f110",
        "específica sobre",
    ],
}

# ════════════════════════════════════════════════════════════════════════════
# PADRÕES DE ENTIDADES
# ════════════════════════════════════════════════════════════════════════════

ENTITY_PATTERNS: dict[str, dict[str, Any]] = {
    "clients": {
        "patterns": [r"\b(víssimo|vissimo|arco|dexco|gran cru|pc\s*factory|pc_factory)\b"],
        "normalization": {
            "víssimo": "VÍSSIMO",
            "vissimo": "VÍSSIMO",
            "pc factory": "PC_FACTORY",
            "pc_factory": "PC_FACTORY",
        },
        "target_column": "client_variations",
    },
    "transactions": {
        "patterns": [r"\b([A-Z]{1,2}\d{2,3}|ZEWM\d{4})\b"],
        "examples": ["F110", "VA01", "ME21N", "ZEWM0008"],
        "target_column": "transactions",
    },
    "sap_modules": {"patterns": [r"\b(SD|MM|FI|CO|PP|HR|EWM|BTP)\b"], "target_column": "sap_modules"},
    "participants": {
        "patterns": [r"\b([A-Z][a-z]+)\b"],
        "common_names": ["Sebas", "Frampton", "Thiago", "Bernard"],
        "target_column": "participants_mentioned",
    },
    "temporal": {
        "patterns": [
            r"últimos?\s+(\d+)\s+(dias?|semanas?|meses?)",
            r"(janeiro|fevereiro|março|setembro|outubro|novembro|dezembro)\s+(\d{4})",
            r"recentes?|ontem|hoje|semana|mês",
        ],
        "target_column": "meeting_date",
    },
}

# ════════════════════════════════════════════════════════════════════════════
# PESOS DE QUALIDADE PARA SELEÇÃO DE CHUNKS
# ════════════════════════════════════════════════════════════════════════════

QUALITY_WEIGHTS = {
    # Fatores positivos (bônus)
    "rich_content": 0.2,
    "client_match": 0.3,
    "technical_rich": 0.15,
    "highlights_available": 0.1,
    "relevant_phase": 0.1,
    "high_impact": 0.15,
    "defined_speaker": 0.05,
    "query_match": 0.1,
    # Fatores negativos (penalidades)
    "small_content": -0.3,
    "intro_only": -0.2,
    "unknown_speaker": -0.1,
    "low_impact": -0.1,
    "incomplete_metadata": -0.15,
}

# ════════════════════════════════════════════════════════════════════════════
# DIVERSIDADE DE SELEÇÃO
# ════════════════════════════════════════════════════════════════════════════

DIVERSITY_CONFIG = {
    "max_results_per_segment": 2,
    "max_results_per_speaker": 3,
    "max_results_per_phase": 4,
    "quality_threshold": 0.3,
    "diversity_weight": 0.4,
    "quality_weight": 0.6,
}

# ════════════════════════════════════════════════════════════════════════════
# DESCOBERTA DINÂMICA DE CLIENTES
# ════════════════════════════════════════════════════════════════════════════

DYNAMIC_CONFIG = {
    "auto_discovery": {
        "clients": True,
        "cache_ttl": 3600,
        "min_chunks_per_client": 5,
    },
    "adaptive_thresholds": {
        "recalculate_interval": 1800,
        "volume_based_adjustment": True,
        "performance_based_tuning": True,
    },
    "client_variations": {
        "auto_generate": True,
        "max_variations": 6,
        "include_lowercase": True,
        "include_camelcase": True,
        "include_no_accents": True,
    },
}

# ════════════════════════════════════════════════════════════════════════════
# MÉTRICAS DE VALIDAÇÃO
# ════════════════════════════════════════════════════════════════════════════

VALIDATION_METRICS = {
    "recall_target": 0.85,
    "precision_target": 0.80,
    "latency_target": 0.5,
    "accuracy_target": 0.90,
    "quality_thresholds": {
        "minimum_chunks": 1,
        "optimal_chunks": 5,
        "maximum_chunks": 20,
    },
    "fuzzy_matching_accuracy": 0.95,
    "negative_test_accuracy": 1.0,
}

# ════════════════════════════════════════════════════════════════════════════
# MENSAGENS DE ERRO
# ════════════════════════════════════════════════════════════════════════════

ERROR_MESSAGES = {
    "no_results": "Não foram encontrados contextos relevantes para gerar insights sobre sua consulta.",
    "invalid_query": "Query inválida. Por favor, reformule sua consulta.",
    "chromadb_error": "Erro ao acessar a base de conhecimento. Tente novamente.",
    "timeout": "Timeout na consulta. A consulta foi muito complexa.",
    "embedding_error": "Erro ao processar a consulta. Verifique se a consulta é válida.",
    "insufficient_results": "Poucos resultados encontrados para gerar uma resposta completa.",
}

# ════════════════════════════════════════════════════════════════════════════
# TEMPLATES DE PIPELINE RAG
# ════════════════════════════════════════════════════════════════════════════


class RAGPipelineTemplates:
    """Templates padronizados para operações do Pipeline RAG."""

    # Geral
    PIPELINE_STARTED = "Pipeline RAG Corporativo iniciado - {total_phases} fases programadas"
    PIPELINE_COMPLETED = "Pipeline RAG concluído em {duration} - {success_rate}% sucesso"
    PIPELINE_FAILED = "Pipeline RAG falhou na {phase}: {error}"

    # Fases
    PHASE_STARTED = "Executando: {phase_name}"
    PHASE_COMPLETED = "{phase_name} concluída com sucesso"
    PHASE_FAILED = "{phase_name} falhou: {reason}"
    PHASE_PROGRESS = "{phase_name} [{progress_bar}] {current}/{total} {item_type}"

    # Busca e Query
    SEARCH_QUERY = "Busca: '{query}' → {results} resultados em {time}s"
    QUERY_TYPE_DETECTED = "Tipo de query detectado: {query_type}"
    SEMANTIC_SEARCH = "Busca semântica: {similarity_threshold}% similaridade mínima"

    # Performance
    PERFORMANCE_METRIC = "Performance: {metric} = {value}"

    @classmethod
    def get_template(cls, template_name: str) -> str:
        """Retorna template por nome."""
        return getattr(cls, template_name, f"Template não encontrado: {template_name}")

    @classmethod
    def format_progress_bar(cls, current: int, total: int, width: int = 10) -> str:
        """Gera barra de progresso visual."""
        if total == 0:
            return "□" * width
        progress = int((current / total) * width)
        return "■" * progress + "□" * (width - progress)

    @classmethod
    def format_duration(cls, seconds: float) -> str:
        """Formata duração em formato legível."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"


# ════════════════════════════════════════════════════════════════════════════
# OVERRIDES DE AMBIENTE
# ════════════════════════════════════════════════════════════════════════════


def _get_environment_config() -> dict[str, Any]:
    """Carrega overrides de configuração por ambiente."""
    config: dict[str, Any] = {}

    max_processing_time = os.getenv("SEARCH_MAX_PROCESSING_TIME")
    if max_processing_time:
        config["max_processing_time"] = float(max_processing_time)

    default_top_k = os.getenv("SEARCH_DEFAULT_TOP_K")
    if default_top_k:
        config["default_top_k"] = int(default_top_k)

    quality_threshold = os.getenv("SEARCH_QUALITY_THRESHOLD")
    if quality_threshold:
        config["quality_threshold"] = float(quality_threshold)

    return config


_ENV_CONFIG = _get_environment_config()
if _ENV_CONFIG:
    SEARCH_CONFIG.update(_ENV_CONFIG)
