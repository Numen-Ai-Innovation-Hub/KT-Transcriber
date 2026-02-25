"""Testes unitários para as 6 tasks ARQ do pipeline RAG de busca KT.

Cobre: kt_search_enrich_task, kt_search_classify_task, kt_search_chromadb_task,
kt_search_discover_task, kt_search_select_task, kt_search_insights_task.

Estratégia de mock:
- ctx["redis"] — AsyncMock com .get()/.set() configurados via side_effect
- get_kt_search_service — patched em src.services.kt_search_service para retornar
  um serviço com components mockados
- Tipos de domínio (EnrichmentResult, ClassificationResult, etc.) — instâncias reais
  construídas com dados mínimos válidos
"""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ════════════════════════════════════════════════════════════════════════════
# HELPERS DE FIXTURES
# ════════════════════════════════════════════════════════════════════════════


def _run(coro: Any) -> Any:
    """Executa coroutine de forma síncrona nos testes."""
    return asyncio.run(coro)


def _make_redis(data: dict[str, Any] | None = None) -> AsyncMock:
    """Cria mock do aioredis.Redis com get/set/exists configurados.

    Args:
        data: Dicionário de chave → valor (str ou bytes) para simular o Redis.

    Returns:
        AsyncMock com comportamento de Redis em memória.
    """
    store: dict[str, str] = {}
    if data:
        for k, v in data.items():
            store[k] = v if isinstance(v, str) else json.dumps(v)

    redis = AsyncMock()

    async def _get(key: str) -> bytes | None:
        val = store.get(key)
        return val.encode() if val is not None else None

    async def _set(key: str, value: str, ex: int = 3600) -> None:
        store[key] = value

    async def _exists(key: str) -> int:
        return 1 if key in store else 0

    redis.get.side_effect = _get
    redis.set.side_effect = _set
    redis.exists.side_effect = _exists
    return redis


def _make_ctx(redis: AsyncMock | None = None) -> dict[str, Any]:
    return {"redis": redis or _make_redis()}


def _make_enrichment_dict(
    original_query: str = "quais módulos SAP foram discutidos?",
    confidence: float = 0.85,
) -> dict[str, Any]:
    return {
        "original_query": original_query,
        "cleaned_query": original_query,
        "enriched_query": original_query + " (enriquecido)",
        "entities": {"client": "DEXCO", "modules": ["SD"]},
        "context": {
            "query_complexity": "medium",
            "has_specific_client": True,
            "has_technical_terms": True,
            "has_temporal": False,
            "is_listing_request": False,
            "is_comparison_request": False,
            "is_broad_request": False,
            "detected_client": "DEXCO",
        },
        "confidence": confidence,
        "processing_time": 0.05,
    }


def _make_classify_dict(query_type: str = "SEMANTIC") -> dict[str, Any]:
    return {
        "query_type": query_type,
        "confidence": 0.90,
        "strategy": {"primary": "similarity"},
        "reasoning": "Query semântica detectada",
        "fallback_types": ["ENTITY"],
        "processing_time": 0.03,
        "query_analysis": {
            "query_complexity": "medium",
            "has_specific_client": True,
            "has_technical_terms": True,
            "has_temporal": False,
            "is_listing_request": False,
            "is_comparison_request": False,
            "is_broad_request": False,
            "detected_client": "DEXCO",
            "entity_count": 2,
            "enrichment_confidence": 0.85,
            "classification_confidence": 0.90,
            "original_query": "quais módulos SAP foram discutidos?",
        },
    }


def _make_raw_results(n: int = 2) -> list[dict[str, Any]]:
    return [
        {
            "id": f"chunk-{i}",
            "document": f"Conteúdo do chunk {i} sobre módulos SAP e processos de negócio.",
            "metadata": {
                "client_name": "DEXCO",
                "video_name": "KT SD 20251020",
                "sap_modules_title": "SD",
                "speaker": "Apresentador",
                "start_time": float(i * 60),
            },
            "distance": 0.1 + 0.05 * i,
        }
        for i in range(n)
    ]


def _make_select_dict(n: int = 2) -> dict[str, Any]:
    chunks = _make_raw_results(n)
    return {
        "selected_chunks": chunks,
        "chunk_scores": [
            {
                "chunk_id": f"chunk-{i}",
                "quality_score": 0.8,
                "diversity_score": 0.7,
                "combined_score": 0.75,
                "selection_reason": "qualidade alta",
            }
            for i in range(n)
        ],
        "total_candidates": n + 1,
        "selection_strategy": "quality_similarity_diversity",
        "processing_time": 0.02,
        "quality_threshold_met": True,
    }


def _make_meta_dict(query: str = "quais módulos SAP foram discutidos?") -> dict[str, Any]:
    import time

    return {"query": query, "created_at": time.time(), "stages_completed": ["enrich"]}


def _make_service_mock(components: dict[str, Any]) -> MagicMock:
    """Cria mock do KTSearchService com components configurados."""
    service = MagicMock()
    service.components = components
    return service


# ════════════════════════════════════════════════════════════════════════════
# ENRICH TASK
# ════════════════════════════════════════════════════════════════════════════


class TestKtSearchEnrichTask:
    """Testa kt_search_enrich_task."""

    def test_happy_path_retorna_stage_complete(self) -> None:
        """Task conclui com sucesso e persiste resultado no Redis."""
        from src.kt_search.query_enricher import EnrichmentResult
        from src.tasks.kt_search_task import kt_search_enrich_task

        real_enrichment = EnrichmentResult(
            original_query="query teste",
            cleaned_query="query teste",
            enriched_query="query teste expandida",
            entities={},
            context={},
            confidence=0.85,
            processing_time=0.05,
        )

        enricher_mock = MagicMock()
        enricher_mock.enrich_query_universal.return_value = real_enrichment

        service_mock = _make_service_mock({"query_enricher": enricher_mock})

        redis = _make_redis()
        ctx = _make_ctx(redis)

        with patch("src.services.kt_search_service.get_kt_search_service", return_value=service_mock):
            result = _run(kt_search_enrich_task(ctx, "query teste", "sess-001"))

        assert result["session_id"] == "sess-001"
        assert result["stage"] == "enrich"
        assert result["status"] == "complete"
        assert result["processing_time"] > 0
        enricher_mock.enrich_query_universal.assert_called_once_with("query teste")

    def test_baixa_confidence_levanta_application_error(self) -> None:
        """Task levanta ApplicationError quando confidence < 0.1."""
        from src.tasks.kt_search_task import kt_search_enrich_task
        from utils.exception_setup import ApplicationError

        mock_enrichment = MagicMock()
        mock_enrichment.confidence = 0.05

        enricher_mock = MagicMock()
        enricher_mock.enrich_query_universal.return_value = mock_enrichment

        service_mock = _make_service_mock({"query_enricher": enricher_mock})
        ctx = _make_ctx()

        with patch("src.services.kt_search_service.get_kt_search_service", return_value=service_mock):
            with pytest.raises(ApplicationError) as exc_info:
                _run(kt_search_enrich_task(ctx, "x", "sess-002"))

        assert exc_info.value.error_code == "SERVICE_UNAVAILABLE"


# ════════════════════════════════════════════════════════════════════════════
# CLASSIFY TASK
# ════════════════════════════════════════════════════════════════════════════


class TestKtSearchClassifyTask:
    """Testa kt_search_classify_task."""

    def test_happy_path_serializa_enums(self) -> None:
        """Task classifica query e serializa QueryType como string (value)."""
        from src.tasks.kt_search_task import kt_search_classify_task

        enrich_data = _make_enrichment_dict()
        redis = _make_redis({"kt_search:sess-003:stage:enrich": json.dumps(enrich_data)})

        mock_classification = MagicMock()
        mock_classification.query_type = MagicMock(value="SEMANTIC")
        mock_classification.confidence = 0.90
        mock_classification.strategy = {}
        mock_classification.reasoning = "ok"
        mock_classification.fallback_types = []
        mock_classification.processing_time = 0.03

        classifier_mock = MagicMock()
        classifier_mock.classify_query_with_context.return_value = mock_classification

        response_builder_mock = MagicMock()
        response_builder_mock.analyze_query_complexity.return_value = {"query_complexity": "medium"}

        service_mock = _make_service_mock(
            {"query_classifier": classifier_mock, "response_builder": response_builder_mock}
        )

        with patch("src.services.kt_search_service.get_kt_search_service", return_value=service_mock):
            result = _run(kt_search_classify_task(_make_ctx(redis), "sess-003"))

        assert result["stage"] == "classify"
        assert result["status"] == "complete"
        classifier_mock.classify_query_with_context.assert_called_once()

    def test_chave_redis_ausente_levanta_application_error(self) -> None:
        """Task levanta ApplicationError se stage:enrich não existir no Redis."""
        from src.tasks.kt_search_task import kt_search_classify_task
        from utils.exception_setup import ApplicationError

        ctx = _make_ctx(_make_redis())  # Redis vazio

        with patch("src.services.kt_search_service.get_kt_search_service", return_value=MagicMock()):
            with pytest.raises(ApplicationError) as exc_info:
                _run(kt_search_classify_task(ctx, "sess-004"))

        assert exc_info.value.error_code == "SERVICE_UNAVAILABLE"


# ════════════════════════════════════════════════════════════════════════════
# CHROMADB TASK
# ════════════════════════════════════════════════════════════════════════════


class TestKtSearchChromadbTask:
    """Testa kt_search_chromadb_task."""

    def _make_redis_with_enrich_and_classify(self, session_id: str = "sess-005") -> AsyncMock:
        return _make_redis(
            {
                f"kt_search:{session_id}:stage:enrich": json.dumps(_make_enrichment_dict()),
                f"kt_search:{session_id}:stage:classify": json.dumps(_make_classify_dict()),
                f"kt_search:{session_id}:meta": json.dumps(_make_meta_dict()),
            }
        )

    def test_happy_path_executa_busca_e_persiste(self) -> None:
        """Task executa busca ChromaDB e grava resultados no Redis."""
        from src.tasks.kt_search_task import kt_search_chromadb_task

        session_id = "sess-005"
        redis = self._make_redis_with_enrich_and_classify(session_id)

        raw_results = _make_raw_results(3)
        chromadb_executor_mock = MagicMock()
        chromadb_executor_mock.execute_search.return_value = raw_results

        response_builder_mock = MagicMock()
        response_builder_mock.should_stop_for_nonexistent_client.return_value = False

        service_mock = _make_service_mock(
            {
                "chromadb_executor": chromadb_executor_mock,
                "response_builder": response_builder_mock,
                "dynamic_client_manager": MagicMock(),
            }
        )

        with patch("src.services.kt_search_service.get_kt_search_service", return_value=service_mock):
            result = _run(kt_search_chromadb_task(_make_ctx(redis), session_id))

        assert result["stage"] == "chromadb"
        assert result["status"] == "complete"
        assert result.get("early_exit") is False
        chromadb_executor_mock.execute_search.assert_called_once()

    def test_early_exit_cliente_inexistente(self) -> None:
        """Task grava resultado final e retorna early_exit=True para cliente inexistente."""
        from src.tasks.kt_search_task import kt_search_chromadb_task

        session_id = "sess-006"
        redis = self._make_redis_with_enrich_and_classify(session_id)

        response_builder_mock = MagicMock()
        response_builder_mock.should_stop_for_nonexistent_client.return_value = True
        mock_response = MagicMock()
        mock_response.intelligent_response = {"answer": "Cliente não encontrado."}
        mock_response.contexts = []
        mock_response.query_type = "EARLY_EXIT"
        mock_response.success = True
        response_builder_mock.create_client_not_found_response.return_value = mock_response

        dynamic_client_mock = MagicMock()
        dynamic_client_mock.discover_clients.return_value = {"DEXCO": {}}

        service_mock = _make_service_mock(
            {
                "chromadb_executor": MagicMock(),
                "response_builder": response_builder_mock,
                "dynamic_client_manager": dynamic_client_mock,
            }
        )

        with patch("src.services.kt_search_service.get_kt_search_service", return_value=service_mock):
            result = _run(kt_search_chromadb_task(_make_ctx(redis), session_id))

        assert result["early_exit"] is True
        response_builder_mock.create_client_not_found_response.assert_called_once()


# ════════════════════════════════════════════════════════════════════════════
# DISCOVER TASK
# ════════════════════════════════════════════════════════════════════════════


class TestKtSearchDiscoverTask:
    """Testa kt_search_discover_task."""

    def _make_redis_for_discover(self, query_type: str, session_id: str = "sess-007") -> AsyncMock:
        classify = _make_classify_dict(query_type)
        return _make_redis(
            {
                f"kt_search:{session_id}:stage:classify": json.dumps(classify),
                f"kt_search:{session_id}:stage:chromadb": json.dumps(_make_raw_results(2)),
                f"kt_search:{session_id}:stage:enrich": json.dumps(_make_enrichment_dict()),
            }
        )

    def test_entity_type_chama_enrich_with_client_discovery(self) -> None:
        """Para ENTITY, chama enrich_with_client_discovery e persiste com skipped=False."""
        from src.tasks.kt_search_task import kt_search_discover_task

        session_id = "sess-007"
        redis = self._make_redis_for_discover("ENTITY", session_id)

        enriched = _make_raw_results(2)
        dynamic_client_mock = MagicMock()
        dynamic_client_mock.enrich_with_client_discovery.return_value = enriched

        service_mock = _make_service_mock({"dynamic_client_manager": dynamic_client_mock})

        with patch("src.services.kt_search_service.get_kt_search_service", return_value=service_mock):
            result = _run(kt_search_discover_task(_make_ctx(redis), session_id))

        assert result["skipped"] is False
        assert result["status"] == "complete"
        dynamic_client_mock.enrich_with_client_discovery.assert_called_once()

    def test_semantic_type_nao_chama_discovery(self) -> None:
        """Para SEMANTIC, passa resultados adiante sem chamar enrich_with_client_discovery."""
        from src.tasks.kt_search_task import kt_search_discover_task

        session_id = "sess-008"
        redis = self._make_redis_for_discover("SEMANTIC", session_id)

        dynamic_client_mock = MagicMock()
        service_mock = _make_service_mock({"dynamic_client_manager": dynamic_client_mock})

        with patch("src.services.kt_search_service.get_kt_search_service", return_value=service_mock):
            result = _run(kt_search_discover_task(_make_ctx(redis), session_id))

        assert result["skipped"] is True
        dynamic_client_mock.enrich_with_client_discovery.assert_not_called()

    def test_metadata_type_chama_enrich_with_client_discovery(self) -> None:
        """Para METADATA, também chama enrich_with_client_discovery."""
        from src.tasks.kt_search_task import kt_search_discover_task

        session_id = "sess-009"
        redis = self._make_redis_for_discover("METADATA", session_id)

        dynamic_client_mock = MagicMock()
        dynamic_client_mock.enrich_with_client_discovery.return_value = _make_raw_results(1)

        service_mock = _make_service_mock({"dynamic_client_manager": dynamic_client_mock})

        with patch("src.services.kt_search_service.get_kt_search_service", return_value=service_mock):
            result = _run(kt_search_discover_task(_make_ctx(redis), session_id))

        assert result["skipped"] is False
        dynamic_client_mock.enrich_with_client_discovery.assert_called_once()


# ════════════════════════════════════════════════════════════════════════════
# SELECT TASK
# ════════════════════════════════════════════════════════════════════════════


class TestKtSearchSelectTask:
    """Testa kt_search_select_task."""

    def test_happy_path_serializa_selection_result(self) -> None:
        """Task seleciona chunks e persiste SelectionResult serializado."""
        from src.tasks.kt_search_task import kt_search_select_task

        session_id = "sess-010"
        redis = _make_redis(
            {
                f"kt_search:{session_id}:stage:classify": json.dumps(_make_classify_dict()),
                f"kt_search:{session_id}:stage:discover": json.dumps(
                    {"results": _make_raw_results(3), "skipped": False}
                ),
                f"kt_search:{session_id}:stage:enrich": json.dumps(_make_enrichment_dict()),
            }
        )

        mock_selection = MagicMock()
        mock_selection.selected_chunks = _make_raw_results(2)
        mock_selection.chunk_scores = []
        mock_selection.total_candidates = 3
        mock_selection.selection_strategy = "quality_similarity_diversity"
        mock_selection.processing_time = 0.02
        mock_selection.quality_threshold_met = True

        chunk_selector_mock = MagicMock()
        chunk_selector_mock.calculate_adaptive_top_k.return_value = 5
        chunk_selector_mock.select_intelligent_chunks.return_value = mock_selection

        service_mock = _make_service_mock({"chunk_selector": chunk_selector_mock})

        with patch("src.services.kt_search_service.get_kt_search_service", return_value=service_mock):
            result = _run(kt_search_select_task(_make_ctx(redis), session_id))

        assert result["stage"] == "select"
        assert result["status"] == "complete"
        chunk_selector_mock.calculate_adaptive_top_k.assert_called_once()
        chunk_selector_mock.select_intelligent_chunks.assert_called_once()


# ════════════════════════════════════════════════════════════════════════════
# INSIGHTS TASK
# ════════════════════════════════════════════════════════════════════════════


class TestKtSearchInsightsTask:
    """Testa kt_search_insights_task."""

    def _make_redis_for_insights(self, session_id: str = "sess-011") -> AsyncMock:
        return _make_redis(
            {
                f"kt_search:{session_id}:stage:select": json.dumps(_make_select_dict()),
                f"kt_search:{session_id}:stage:classify": json.dumps(_make_classify_dict()),
                f"kt_search:{session_id}:stage:enrich": json.dumps(_make_enrichment_dict()),
                f"kt_search:{session_id}:meta": json.dumps(_make_meta_dict()),
            }
        )

    def test_happy_path_persiste_final(self) -> None:
        """Task gera insights, persiste stage:insights e kt_search:final."""
        from src.kt_search.insights_agent import DirectInsightResult
        from src.tasks.kt_search_task import kt_search_insights_task

        session_id = "sess-011"
        redis = self._make_redis_for_insights(session_id)

        real_insight = DirectInsightResult(
            insight="Resposta final gerada.",
            confidence=0.90,
            sources_used=2,
            processing_time=2.5,
            fallback_used=False,
        )

        insights_agent_mock = MagicMock()
        insights_agent_mock.generate_direct_insight.return_value = real_insight

        mock_response = MagicMock()
        mock_response.intelligent_response = {"answer": "Resposta final gerada."}
        mock_response.contexts = []
        mock_response.query_type = "SEMANTIC"
        mock_response.processing_time = 5.0
        mock_response.success = True

        response_builder_mock = MagicMock()
        response_builder_mock.format_final_response.return_value = mock_response

        service_mock = _make_service_mock(
            {"insights_agent": insights_agent_mock, "response_builder": response_builder_mock}
        )

        with patch("src.services.kt_search_service.get_kt_search_service", return_value=service_mock):
            result = _run(kt_search_insights_task(_make_ctx(redis), session_id))

        assert result["stage"] == "insights"
        assert result["status"] == "complete"
        insights_agent_mock.generate_direct_insight.assert_called_once()
        response_builder_mock.format_final_response.assert_called_once()

    def test_insights_none_levanta_application_error(self) -> None:
        """Task levanta ApplicationError quando generate_direct_insight retorna None."""
        from src.tasks.kt_search_task import kt_search_insights_task
        from utils.exception_setup import ApplicationError

        session_id = "sess-012"
        redis = self._make_redis_for_insights(session_id)

        insights_agent_mock = MagicMock()
        insights_agent_mock.generate_direct_insight.return_value = None

        service_mock = _make_service_mock({"insights_agent": insights_agent_mock, "response_builder": MagicMock()})

        with patch("src.services.kt_search_service.get_kt_search_service", return_value=service_mock):
            with pytest.raises(ApplicationError) as exc_info:
                _run(kt_search_insights_task(_make_ctx(redis), session_id))

        assert exc_info.value.error_code == "SERVICE_UNAVAILABLE"

    def test_redis_ausente_levanta_application_error(self) -> None:
        """Task levanta ApplicationError quando stage:select está ausente no Redis."""
        from src.tasks.kt_search_task import kt_search_insights_task
        from utils.exception_setup import ApplicationError

        ctx = _make_ctx(_make_redis())  # Redis vazio

        with patch("src.services.kt_search_service.get_kt_search_service", return_value=MagicMock()):
            with pytest.raises(ApplicationError) as exc_info:
                _run(kt_search_insights_task(ctx, "sess-013"))

        assert exc_info.value.error_code == "SERVICE_UNAVAILABLE"


# ════════════════════════════════════════════════════════════════════════════
# HELPERS DE SERIALIZAÇÃO
# ════════════════════════════════════════════════════════════════════════════


class TestSerializacaoDeserializacao:
    """Testa os helpers internos de (de)serialização dos tipos de domínio."""

    def test_deserialize_classification_reconstroi_enums(self) -> None:
        """_deserialize_classification reconstrói QueryType Enum corretamente."""
        from src.tasks.kt_search_task import _deserialize_classification

        data = _make_classify_dict("METADATA")
        result = _deserialize_classification(data)

        from src.kt_search.query_classifier import QueryType

        assert result.query_type == QueryType.METADATA
        assert result.fallback_types == [QueryType.ENTITY]
        assert result.confidence == 0.90

    def test_deserialize_selection_reconstroi_chunk_scores(self) -> None:
        """_deserialize_selection reconstrói ChunkScore corretamente."""
        from src.kt_search.chunk_selector import ChunkScore
        from src.tasks.kt_search_task import _deserialize_selection

        data = _make_select_dict(2)
        result = _deserialize_selection(data)

        assert len(result.chunk_scores) == 2
        assert isinstance(result.chunk_scores[0], ChunkScore)
        assert result.selection_strategy == "quality_similarity_diversity"
        assert result.quality_threshold_met is True
