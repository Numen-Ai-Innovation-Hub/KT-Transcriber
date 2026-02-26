"""kt_search package."""

# Chromadb Search Executor
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

# Insight Processors
from .insight_processors import InsightProcessors

# Insights Agent
from .insights_agent import (
    DirectInsightResult,
    InsightsAgent,
)

# Insights Prompts
from .insights_prompts import (
    BASE_PROMPT_TEMPLATE,
    DECISION_PROMPT_TEMPLATE,
    GENERAL_PROMPT_TEMPLATE,
    HIGHLIGHTS_SUMMARY_TEMPLATE,
    METADATA_LISTING_TEMPLATE,
    PARTICIPANTS_TEMPLATE,
    PROBLEM_PROMPT_TEMPLATE,
    PROJECT_LISTING_TEMPLATE,
    PROMPT_TEMPLATES,
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
    RAGPipelineTemplates,
    SEARCH_CONFIG,
    TOP_K_STRATEGY,
    VALIDATION_METRICS,
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

# Query Type Detector
from .query_type_detector import QueryTypeDetector

# Search Cli
from .search_cli import (
    interactive_mode,
    main,
    single_query_mode,
)

# Search Engine
from .search_engine import SearchEngine

# Search Formatters
from .search_formatters import (
    formatar_resultado_teams,
    main_teams,
    print_results,
    quick_search,
    search_kt_knowledge,
)

# Search Logging
from .search_logging import PipelineLogger

# Search Response Builder
from .search_response_builder import SearchResponseBuilder

# Search Types
from .search_types import SearchResponse

# Search Utils
from .search_utils import analyze_query_complexity

__all__ = [
    "BASE_PROMPT_TEMPLATE",
    "ChromaDBSearchExecutor",
    "ChunkScore",
    "ChunkSelector",
    "ClassificationResult",
    "ClientInfo",
    "DECISION_PROMPT_TEMPLATE",
    "DIVERSITY_CONFIG",
    "DYNAMIC_CONFIG",
    "DirectInsightResult",
    "DynamicClientManager",
    "ENTITY_PATTERNS",
    "ERROR_MESSAGES",
    "EnrichmentResult",
    "GENERAL_PROMPT_TEMPLATE",
    "HIGHLIGHTS_SUMMARY_TEMPLATE",
    "InsightProcessors",
    "InsightsAgent",
    "METADATA_LISTING_TEMPLATE",
    "PARTICIPANTS_TEMPLATE",
    "PERFORMANCE_CONFIG",
    "PROBLEM_PROMPT_TEMPLATE",
    "PROJECT_LISTING_TEMPLATE",
    "PROMPT_TEMPLATES",
    "PipelineLogger",
    "QUALITY_WEIGHTS",
    "QUERY_PATTERNS",
    "QueryClassifier",
    "QueryEnricher",
    "QueryType",
    "QueryTypeDetector",
    "RAGPipelineTemplates",
    "SEARCH_CONFIG",
    "SearchEngine",
    "SearchResponse",
    "SearchResponseBuilder",
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
