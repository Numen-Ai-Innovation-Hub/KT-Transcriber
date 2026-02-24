"""Utilitários de busca — domínio kt_search.

Funções utilitárias compartilhadas pelos componentes do pipeline RAG.
"""

from typing import Any


def analyze_query_complexity(
    enrichment_context: dict[str, Any],
    enrichment_confidence: float,
    classification_confidence: float,
    original_query: str = "",
) -> dict[str, Any]:
    """Analisa complexidade de query para processamento adaptativo.

    Extrai indicadores do contexto de enriquecimento para uso pelos componentes
    do pipeline no cálculo de top_k adaptativo.

    Args:
        enrichment_context: Contexto retornado pelo QueryEnricher.
        enrichment_confidence: Confiança do enriquecimento (0.0–1.0).
        classification_confidence: Confiança da classificação (0.0–1.0).
        original_query: Query original para referência nos logs.

    Returns:
        Dict com indicadores de complexidade para o ChunkSelector.
    """
    return {
        "query_complexity": enrichment_context.get("query_complexity", "medium"),
        "has_specific_client": enrichment_context.get("has_specific_client", False),
        "has_technical_terms": enrichment_context.get("has_technical_terms", False),
        "has_temporal": enrichment_context.get("has_temporal", False),
        "is_listing_request": enrichment_context.get("is_listing_request", False),
        "is_comparison_request": enrichment_context.get("is_comparison_request", False),
        "is_broad_request": enrichment_context.get("is_broad_request", False),
        "detected_client": enrichment_context.get("detected_client"),
        "entity_count": enrichment_context.get("entity_count", 0),
        "enrichment_confidence": enrichment_confidence,
        "classification_confidence": classification_confidence,
        "original_query": original_query,
    }
