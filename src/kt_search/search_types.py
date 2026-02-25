"""
Search Types - Tipos compartilhados do pacote kt_search.

Centraliza o dataclass SearchResponse para evitar imports circulares
entre search_engine.py e search_response_builder.py.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class SearchResponse:
    """Resposta final do SearchEngine."""

    intelligent_response: dict[str, Any]
    contexts: list[dict[str, Any]]
    summary_stats: dict[str, Any]
    query_type: str
    processing_time: float
    success: bool
    error_message: str | None = None
