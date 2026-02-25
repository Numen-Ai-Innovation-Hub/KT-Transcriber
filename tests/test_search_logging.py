"""
Testes unitários para PipelineLogger.

Cobre: log_enrichment_phase, log_classification_phase, log_chromadb_phase,
log_client_discovery_phase, log_selection_phase, log_insights_phase.

Os métodos de PipelineLogger são puramente de logging (retornam None).
Os testes verificam que:
1. Nenhuma exceção é levantada durante a execução.
2. Parâmetros inválidos são tolerados sem crash.
3. Caminhos show_details=True e show_details=False executam sem erros.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest


def _make_logger() -> Any:
    from src.kt_search.search_logging import PipelineLogger

    return PipelineLogger()


def _make_enrichment_result(
    original_query: str = "query teste",
    cleaned_query: str = "query teste",
    enriched_query: str = "query teste expandida",
    confidence: float = 0.85,
    entities: dict | None = None,
    context: dict | None = None,
) -> Any:
    r = MagicMock()
    r.original_query = original_query
    r.cleaned_query = cleaned_query
    r.enriched_query = enriched_query
    r.confidence = confidence
    r.entities = entities or {}
    r.context = context or {}
    return r


def _make_classification_result(query_type_value: str = "SEMANTIC") -> Any:
    from src.kt_search.query_classifier import QueryType

    r = MagicMock()
    r.query_type = QueryType(query_type_value)
    r.confidence = 0.9
    r.strategy = {"name": "semantic_strategy", "n_results": 20}
    r.reasoning = "Busca semântica padrão"
    r.fallback_types = []
    r.processing_time = 0.01
    return r


def _make_selection_result(n_chunks: int = 3) -> Any:
    r = MagicMock()
    r.selected_chunks = [{"content": f"chunk {i}", "quality_score": 0.8} for i in range(n_chunks)]
    r.total_candidates = n_chunks + 2
    r.selection_strategy = "quality_diversity"
    r.quality_threshold_met = True
    r.chunk_scores = []
    r.processing_time = 0.05
    return r


def _make_insights_result(
    insight: str = "Insight gerado com sucesso pelo modelo.",
    confidence: float = 0.88,
    processing_time: float = 1.5,
) -> Any:
    r = MagicMock()
    r.insight = insight
    r.confidence = confidence
    r.processing_time = processing_time
    return r


def _make_raw_results(n: int = 3) -> list[dict[str, Any]]:
    return [
        {"content": f"conteúdo {i}", "quality_score": 0.8, "metadata": {"video_name": f"KT_{i}"}}
        for i in range(n)
    ]


# ════════════════════════════════════════════════════════════════════════════
# Fase 1 — log_enrichment_phase
# ════════════════════════════════════════════════════════════════════════════


class TestPipelineLoggerEnrichmentPhase:
    """Testa log_enrichment_phase — fase 1 do pipeline."""

    def test_sem_show_details_nao_levanta_excecao(self) -> None:
        """log_enrichment_phase sem detalhes executa sem exceções."""
        pl = _make_logger()
        enrichment = _make_enrichment_result()
        pl.log_enrichment_phase("query original", enrichment, 0.123, show_details=False)

    def test_com_show_details_nao_levanta_excecao(self) -> None:
        """log_enrichment_phase com detalhes executa sem exceções."""
        pl = _make_logger()
        enrichment = _make_enrichment_result(
            entities={
                "clients": {"values": ["DEXCO"], "confidence": 0.9},
                "modules": {"values": [], "confidence": 0.0},
            },
            context={"has_specific_client": True, "detected_client": "DEXCO"},
        )
        pl.log_enrichment_phase("query original", enrichment, 0.05, show_details=True)

    def test_retorna_none(self) -> None:
        """Método retorna None."""
        pl = _make_logger()
        result = pl.log_enrichment_phase("q", _make_enrichment_result(), 0.1, False)
        assert result is None

    def test_com_entidades_vazias_nao_crasha(self) -> None:
        """Entidades sem valores não causam crash no show_details=True."""
        pl = _make_logger()
        enrichment = _make_enrichment_result(
            entities={"clients": {"values": [], "confidence": 0.0}}
        )
        pl.log_enrichment_phase("query", enrichment, 0.1, show_details=True)

    def test_query_muito_longa_nao_crasha(self) -> None:
        """Query de 500 chars não causa crash."""
        pl = _make_logger()
        longa = "palavra " * 60
        pl.log_enrichment_phase(longa, _make_enrichment_result(), 0.2, False)


# ════════════════════════════════════════════════════════════════════════════
# Fase 2 — log_classification_phase
# ════════════════════════════════════════════════════════════════════════════


class TestPipelineLoggerClassificationPhase:
    """Testa log_classification_phase — fase 2 do pipeline."""

    def test_sem_show_details_nao_levanta_excecao(self) -> None:
        """log_classification_phase sem detalhes executa sem exceções."""
        pl = _make_logger()
        pl.log_classification_phase(_make_classification_result(), 0.05, show_details=False)

    def test_com_show_details_nao_levanta_excecao(self) -> None:
        """log_classification_phase com detalhes executa sem exceções."""
        pl = _make_logger()
        clf = _make_classification_result("METADATA")
        clf.strategy = {
            "name": "metadata_strategy",
            "n_results": 20,
            "debug_scores": {"SEMANTIC": 0.3, "METADATA": 0.8},
        }
        pl.log_classification_phase(clf, 0.03, show_details=True)

    def test_retorna_none(self) -> None:
        """Método retorna None."""
        pl = _make_logger()
        result = pl.log_classification_phase(_make_classification_result(), 0.1, False)
        assert result is None

    @pytest.mark.parametrize("query_type", ["SEMANTIC", "METADATA", "ENTITY", "TEMPORAL", "CONTENT"])
    def test_todos_os_tipos_de_query_nao_crasham(self, query_type: str) -> None:
        """Todos os 5 tipos de query RAG executam sem erro."""
        pl = _make_logger()
        pl.log_classification_phase(_make_classification_result(query_type), 0.05, False)


# ════════════════════════════════════════════════════════════════════════════
# Fase 3 — log_chromadb_phase
# ════════════════════════════════════════════════════════════════════════════


class TestPipelineLoggerChromaDbPhase:
    """Testa log_chromadb_phase — fase 3 do pipeline."""

    def test_sem_show_details_nao_levanta_excecao(self) -> None:
        """log_chromadb_phase sem detalhes executa sem exceções."""
        pl = _make_logger()
        pl.log_chromadb_phase(
            raw_results=_make_raw_results(),
            chromadb_time=0.3,
            enrichment_result=_make_enrichment_result(),
            classification_result=_make_classification_result(),
            show_details=False,
        )

    def test_com_show_details_nao_levanta_excecao(self) -> None:
        """log_chromadb_phase com detalhes executa sem exceções."""
        pl = _make_logger()
        enrichment = _make_enrichment_result(
            entities={"clients": {"values": ["DEXCO"], "confidence": 0.9}}
        )
        pl.log_chromadb_phase(
            raw_results=_make_raw_results(5),
            chromadb_time=0.45,
            enrichment_result=enrichment,
            classification_result=_make_classification_result("ENTITY"),
            show_details=True,
        )

    def test_lista_vazia_nao_crasha(self) -> None:
        """Lista vazia de resultados não causa crash."""
        pl = _make_logger()
        pl.log_chromadb_phase([], 0.1, _make_enrichment_result(), _make_classification_result(), False)

    def test_retorna_none(self) -> None:
        """Método retorna None."""
        pl = _make_logger()
        result = pl.log_chromadb_phase([], 0.1, _make_enrichment_result(), _make_classification_result(), False)
        assert result is None


# ════════════════════════════════════════════════════════════════════════════
# Fase 4 — log_client_discovery_phase
# ════════════════════════════════════════════════════════════════════════════


class TestPipelineLoggerClientDiscoveryPhase:
    """Testa log_client_discovery_phase — fase 4 do pipeline."""

    def _make_dynamic_manager(self, clients: dict | None = None) -> Any:
        manager = MagicMock()
        if clients is None:
            clients = {
                "DEXCO": MagicMock(chunk_count=150),
                "ARCO": MagicMock(chunk_count=80),
            }
        manager.discover_clients.return_value = clients
        return manager

    def test_sem_show_details_nao_levanta_excecao(self) -> None:
        """log_client_discovery_phase sem detalhes executa sem exceções."""
        pl = _make_logger()
        manager = self._make_dynamic_manager()
        pl.log_client_discovery_phase(0.1, show_details=False, dynamic_client_manager=manager)

    def test_com_show_details_nao_levanta_excecao(self) -> None:
        """log_client_discovery_phase com detalhes executa sem exceções."""
        pl = _make_logger()
        manager = self._make_dynamic_manager()
        pl.log_client_discovery_phase(0.2, show_details=True, dynamic_client_manager=manager)

    def test_manager_com_erro_nao_crasha(self) -> None:
        """Se discover_clients levanta exceção, log não crasha."""
        pl = _make_logger()
        manager = MagicMock()
        manager.discover_clients.side_effect = Exception("Erro de conexão")
        pl.log_client_discovery_phase(0.1, show_details=True, dynamic_client_manager=manager)

    def test_retorna_none(self) -> None:
        """Método retorna None."""
        pl = _make_logger()
        result = pl.log_client_discovery_phase(0.1, False, self._make_dynamic_manager())
        assert result is None


# ════════════════════════════════════════════════════════════════════════════
# Fase 5 — log_selection_phase
# ════════════════════════════════════════════════════════════════════════════


class TestPipelineLoggerSelectionPhase:
    """Testa log_selection_phase — fase 5 do pipeline."""

    def test_sem_show_details_nao_levanta_excecao(self) -> None:
        """log_selection_phase sem detalhes executa sem exceções."""
        pl = _make_logger()
        pl.log_selection_phase(
            selection_result=_make_selection_result(),
            raw_results=_make_raw_results(),
            top_k=20,
            selection_time=0.05,
            show_details=False,
        )

    def test_com_show_details_nao_levanta_excecao(self) -> None:
        """log_selection_phase com detalhes executa sem exceções."""
        pl = _make_logger()
        pl.log_selection_phase(
            selection_result=_make_selection_result(5),
            raw_results=_make_raw_results(8),
            top_k=20,
            selection_time=0.08,
            show_details=True,
        )

    def test_sem_chunks_nao_crasha(self) -> None:
        """Seleção sem chunks não causa crash."""
        pl = _make_logger()
        sel = _make_selection_result(0)
        pl.log_selection_phase(sel, [], 20, 0.01, False)

    def test_retorna_none(self) -> None:
        """Método retorna None."""
        pl = _make_logger()
        result = pl.log_selection_phase(_make_selection_result(), [], 20, 0.01, False)
        assert result is None

    @pytest.mark.parametrize("strategy", ["all_candidates", "quality_filter", "top_k_limit", "diversity_selection"])
    def test_todas_estrategias_de_selecao(self, strategy: str) -> None:
        """Todas as estratégias de seleção conhecidas executam sem erro."""
        pl = _make_logger()
        sel = _make_selection_result()
        sel.selection_strategy = strategy
        pl.log_selection_phase(sel, _make_raw_results(), 20, 0.05, show_details=True)


# ════════════════════════════════════════════════════════════════════════════
# Fase 6 — log_insights_phase
# ════════════════════════════════════════════════════════════════════════════


class TestPipelineLoggerInsightsPhase:
    """Testa log_insights_phase — fase 6 do pipeline."""

    def test_sem_show_details_nao_levanta_excecao(self) -> None:
        """log_insights_phase sem detalhes executa sem exceções."""
        pl = _make_logger()
        pl.log_insights_phase(_make_insights_result(), 1.5, show_details=False)

    def test_com_show_details_nao_levanta_excecao(self) -> None:
        """log_insights_phase com detalhes executa sem exceções."""
        pl = _make_logger()
        pl.log_insights_phase(_make_insights_result(), 2.3, show_details=True)

    def test_fast_track_processing_time_baixo(self) -> None:
        """Insights com processing_time < 0.01 (fast-track) não causam crash."""
        pl = _make_logger()
        ins = _make_insights_result(processing_time=0.001)
        pl.log_insights_phase(ins, 0.001, show_details=True)

    def test_retorna_none(self) -> None:
        """Método retorna None."""
        pl = _make_logger()
        result = pl.log_insights_phase(_make_insights_result(), 1.0, False)
        assert result is None

    @pytest.mark.parametrize("confidence", [0.1, 0.5, 0.7, 0.9, 1.0])
    def test_niveis_de_confianca(self, confidence: float) -> None:
        """Todos os níveis de confiança são tratados sem erro."""
        pl = _make_logger()
        ins = _make_insights_result(confidence=confidence)
        pl.log_insights_phase(ins, 1.0, show_details=True)

    def test_insight_longo_nao_crasha(self) -> None:
        """Insight com texto longo (>500 chars) executa sem crash."""
        pl = _make_logger()
        ins = _make_insights_result(insight="palavra " * 100)
        pl.log_insights_phase(ins, 2.0, show_details=True)
