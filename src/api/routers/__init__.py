"""routers package."""

# Health
from .health import health_check

# Kt Indexing Router
from .kt_indexing_router import (
    get_indexing_job_status,
    get_indexing_status,
    run_indexing,
)

# Kt Ingestion Router
from .kt_ingestion_router import (
    get_ingestion_status,
    run_ingestion,
)

# Kt Search Router
from .kt_search_router import (
    pipeline_chromadb,
    pipeline_classify,
    pipeline_discover,
    pipeline_insights,
    pipeline_result,
    pipeline_select,
    pipeline_start,
    pipeline_status,
    search_kt,
)

__all__ = [
    "get_indexing_job_status",
    "get_indexing_status",
    "get_ingestion_status",
    "health_check",
    "pipeline_chromadb",
    "pipeline_classify",
    "pipeline_discover",
    "pipeline_insights",
    "pipeline_result",
    "pipeline_select",
    "pipeline_start",
    "pipeline_status",
    "run_indexing",
    "run_ingestion",
    "search_kt",
]
