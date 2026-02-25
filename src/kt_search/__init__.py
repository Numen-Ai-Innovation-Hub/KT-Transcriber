"""kt_search package."""

# ChromaDB Search Executor
from .chromadb_search_executor import ChromaDBSearchExecutor

# Chunk Selector
from .chunk_selector import (
    ChunkScore,
    ChunkSelector,
    SelectionResult,
    calculate_quality_score,
    select_chunks,
)

# Dynamic Client Manager
from .dynamic_client_manager import (
    ClientInfo,
    DynamicClientManager,
)

# Insights Agent
from .insights_agent import (
    DirectInsightResult,
    InsightsAgent,
)

# Kt Search Constants
from .kt_search_constants import (
    DIVERSITY_CONFIG,
    DYNAMIC_CONFIG,
    ENTITY_PATTERNS,
    ERROR_MESSAGES,
    PERFORMANCE_CONFIG,
    QUALITY_WEIGHTS,
    QUERY_PATTERNS,
    SEARCH_CONFIG,
    TOP_K_STRATEGY,
    VALIDATION_METRICS,
    RAGPipelineTemplates,
)

# Query Classifier
from .query_classifier import (
    ClassificationResult,
    QueryClassifier,
    QueryType,
    classify_query,
    get_query_type,
)

# Query Enricher
from .query_enricher import (
    EnrichmentResult,
    QueryEnricher,
    enrich_query,
    extract_entities,
)

# Search CLI
from .search_cli import (
    interactive_mode,
    main,
    single_query_mode,
)

# Search Engine
from .search_engine import (
    SearchEngine,
    SearchResponse,
)

# Search Formatters
from .search_formatters import (
    formatar_resultado_teams,
    main_teams,
    print_results,
    quick_search,
    search_kt_knowledge,
)

# Search Utils
from .search_utils import analyze_query_complexity

__all__ = [
    "ChromaDBSearchExecutor",
    "ChunkScore",
    "ChunkSelector",
    "ClassificationResult",
    "ClientInfo",
    "DIVERSITY_CONFIG",
    "DYNAMIC_CONFIG",
    "DirectInsightResult",
    "DynamicClientManager",
    "ENTITY_PATTERNS",
    "ERROR_MESSAGES",
    "EnrichmentResult",
    "InsightsAgent",
    "PERFORMANCE_CONFIG",
    "QUALITY_WEIGHTS",
    "QUERY_PATTERNS",
    "QueryClassifier",
    "QueryEnricher",
    "QueryType",
    "RAGPipelineTemplates",
    "SEARCH_CONFIG",
    "SearchEngine",
    "SearchResponse",
    "SelectionResult",
    "TOP_K_STRATEGY",
    "VALIDATION_METRICS",
    "analyze_query_complexity",
    "calculate_quality_score",
    "classify_query",
    "enrich_query",
    "extract_entities",
    "formatar_resultado_teams",
    "get_query_type",
    "interactive_mode",
    "main",
    "main_teams",
    "print_results",
    "quick_search",
    "search_kt_knowledge",
    "select_chunks",
    "single_query_mode",
]
