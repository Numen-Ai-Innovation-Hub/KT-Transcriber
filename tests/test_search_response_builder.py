"""
Testes unitários para SearchResponseBuilder.

Cobre: format_final_response, extract_additional_details, format_contexts_for_display,
format_metadata_listing_display, extract_unique_clients, create_error_response,
create_client_not_found_response, analyze_query_complexity, should_stop_for_nonexistent_client.
"""

import time
from typing import Any
from unittest.mock import MagicMock

import pytest


def _make_chunk(
    content: str = "conteúdo teste",
    client_name: str = "DEXCO",
    video_name: str = "KT_DEXCO_01",
    speaker: str = "Palestrante",
    quality_score: float = 0.8,
    similarity_score: float | None = None,
    original_url: str = "",
) -> dict[str, Any]:
    chunk: dict[str, Any] = {
        "content": content,
        "metadata": {
            "client_name": client_name,
            "video_name": video_name,
            "speaker": speaker,
            "start_time_formatted": "00:01",
            "end_time_formatted": "00:05",
            "original_url": original_url,
        },
        "quality_score": quality_score,
    }
    if similarity_score is not None:
        chunk["similarity_score"] = similarity_score
    return chunk


def _make_selection_result(chunks: list[dict[str, Any]], total_candidates: int = 10) -> Any:
    sel = MagicMock()
    sel.selected_chunks = chunks
    sel.total_candidates = total_candidates
    sel.selection_strategy = "quality_diversity"
    sel.quality_threshold_met = True
    return sel


def _make_classification_result(query_type_value: str = "SEMANTIC") -> Any:
    from src.kt_search.query_classifier import QueryType

    clf = MagicMock()
    clf.query_type = QueryType(query_type_value)
    clf.confidence = 0.9
    return clf


def _make_insights_result(insight: str = "Insight gerado", confidence: float = 0.85) -> Any:
    ins = MagicMock()
    ins.insight = insight
    ins.confidence = confidence
    ins.processing_time = 0.5
    return ins


# ════════════════════════════════════════════════════════════════════════════
# SearchResponseBuilder — testes
# ════════════════════════════════════════════════════════════════════════════


class TestSearchResponseBuilderFormatFinalResponse:
    """Testa format_final_response."""

    def _make_builder(self) -> Any:
        from src.kt_search.search_response_builder import SearchResponseBuilder

        return SearchResponseBuilder()

    def test_retorna_search_response_com_success_true(self) -> None:
        """format_final_response retorna SearchResponse com success=True."""
        from src.kt_search.search_types import SearchResponse

        builder = self._make_builder()
        chunks = [_make_chunk()]
        result = builder.format_final_response(
            original_query="query teste",
            insights_result=_make_insights_result(),
            selection_result=_make_selection_result(chunks),
            classification_result=_make_classification_result(),
            start_time=time.time(),
        )
        assert isinstance(result, SearchResponse)
        assert result.success is True

    def test_intelligent_response_contem_answer(self) -> None:
        """intelligent_response contém a chave 'answer' com o insight."""
        builder = self._make_builder()
        chunks = [_make_chunk()]
        result = builder.format_final_response(
            original_query="query",
            insights_result=_make_insights_result(insight="Resposta esperada"),
            selection_result=_make_selection_result(chunks),
            classification_result=_make_classification_result(),
            start_time=time.time(),
        )
        assert result.intelligent_response["answer"] == "Resposta esperada"
        assert result.intelligent_response["confidence"] == pytest.approx(0.85)

    def test_summary_stats_inclui_query_type(self) -> None:
        """summary_stats registra query_type da classification."""
        builder = self._make_builder()
        result = builder.format_final_response(
            original_query="query",
            insights_result=_make_insights_result(),
            selection_result=_make_selection_result([_make_chunk()]),
            classification_result=_make_classification_result("SEMANTIC"),
            start_time=time.time(),
        )
        assert result.summary_stats["query_type"] == "SEMANTIC"
        assert result.query_type == "SEMANTIC"

    def test_processing_time_eh_positivo(self) -> None:
        """processing_time é um float positivo."""
        builder = self._make_builder()
        result = builder.format_final_response(
            original_query="query",
            insights_result=_make_insights_result(),
            selection_result=_make_selection_result([]),
            classification_result=_make_classification_result(),
            start_time=time.time() - 0.1,
        )
        assert result.processing_time > 0


class TestSearchResponseBuilderCreateErrorResponse:
    """Testa create_error_response."""

    def _make_builder(self) -> Any:
        from src.kt_search.search_response_builder import SearchResponseBuilder

        return SearchResponseBuilder()

    def test_retorna_success_false(self) -> None:
        """create_error_response retorna SearchResponse com success=False."""
        builder = self._make_builder()
        result = builder.create_error_response("Erro de conexão", "query", time.time())
        assert result.success is False

    def test_error_message_preenchida(self) -> None:
        """error_message contém a mensagem passada."""
        builder = self._make_builder()
        result = builder.create_error_response("Erro crítico", "query", time.time())
        assert result.error_message == "Erro crítico"

    def test_query_type_eh_error(self) -> None:
        """query_type é 'ERROR' na resposta de erro."""
        builder = self._make_builder()
        result = builder.create_error_response("erro", "query", time.time())
        assert result.query_type == "ERROR"

    def test_contextos_vazios(self) -> None:
        """Resposta de erro não contém contextos."""
        builder = self._make_builder()
        result = builder.create_error_response("erro", "query", time.time())
        assert result.contexts == []


class TestSearchResponseBuilderCreateClientNotFoundResponse:
    """Testa create_client_not_found_response."""

    def _make_builder(self) -> Any:
        from src.kt_search.search_response_builder import SearchResponseBuilder

        return SearchResponseBuilder()

    def test_retorna_success_true(self) -> None:
        """create_client_not_found_response retorna success=True (não é erro de sistema)."""
        builder = self._make_builder()
        result = builder.create_client_not_found_response("cliente XPTO", time.time())
        assert result.success is True

    def test_answer_menciona_cliente_nao_encontrado(self) -> None:
        """Resposta menciona que cliente não foi encontrado."""
        builder = self._make_builder()
        result = builder.create_client_not_found_response("query", time.time())
        assert "não encontrado" in result.intelligent_response["answer"].lower()

    def test_confidence_alta(self) -> None:
        """Confiança é alta porque o sistema tem certeza que o cliente não existe."""
        builder = self._make_builder()
        result = builder.create_client_not_found_response("query", time.time())
        assert result.intelligent_response["confidence"] >= 0.9

    def test_query_type_early_exit(self) -> None:
        """query_type indica saída antecipada."""
        builder = self._make_builder()
        result = builder.create_client_not_found_response("query", time.time())
        assert result.query_type == "EARLY_EXIT"


class TestSearchResponseBuilderFormatContexts:
    """Testa format_contexts_for_display e format_metadata_listing_display."""

    def _make_builder(self) -> Any:
        from src.kt_search.search_response_builder import SearchResponseBuilder

        return SearchResponseBuilder()

    def test_format_contexts_retorna_lista_com_rank(self) -> None:
        """Cada contexto formatado tem campo 'rank' incremental."""
        builder = self._make_builder()
        chunks = [_make_chunk(video_name="KT_01"), _make_chunk(video_name="KT_02")]
        result = builder.format_contexts_for_display(chunks)
        assert result[0]["rank"] == 1
        assert result[1]["rank"] == 2

    def test_content_truncado_em_300_chars(self) -> None:
        """Conteúdo maior que 300 chars é truncado."""
        builder = self._make_builder()
        longo = "x" * 400
        chunks = [_make_chunk(content=longo)]
        result = builder.format_contexts_for_display(chunks)
        assert len(result[0]["content"]) <= 303  # 300 + "..."

    def test_query_type_metadata_usa_listing(self) -> None:
        """query_type 'METADATA' direciona para format_metadata_listing_display."""
        builder = self._make_builder()
        chunks = [
            _make_chunk(video_name="KT_01", client_name="DEXCO"),
            _make_chunk(video_name="KT_01", client_name="DEXCO"),  # duplicado
        ]
        result = builder.format_contexts_for_display(chunks, query_type="METADATA")
        assert len(result) == 1  # deduplica por video_name

    def test_similarity_score_incluido_quando_presente(self) -> None:
        """similarity_score aparece no contexto quando fornecido no chunk."""
        builder = self._make_builder()
        chunks = [_make_chunk(similarity_score=0.92)]
        result = builder.format_contexts_for_display(chunks)
        assert "similarity_score" in result[0]
        assert result[0]["similarity_score"] == pytest.approx(0.92)

    def test_format_metadata_deduplica_por_video_name(self) -> None:
        """format_metadata_listing_display agrupa por video_name único."""
        builder = self._make_builder()
        chunks = [
            _make_chunk(video_name="VideoA", client_name="ARCO"),
            _make_chunk(video_name="VideoA", client_name="ARCO"),
            _make_chunk(video_name="VideoB", client_name="ARCO"),
        ]
        result = builder.format_metadata_listing_display(chunks)
        assert len(result) == 2
        video_names = [r["video_name"] for r in result]
        assert "VideoA" in video_names
        assert "VideoB" in video_names

    def test_format_contexts_lista_vazia(self) -> None:
        """format_contexts_for_display com lista vazia retorna lista vazia."""
        builder = self._make_builder()
        result = builder.format_contexts_for_display([])
        assert result == []


class TestSearchResponseBuilderExtract:
    """Testa extract_additional_details e extract_unique_clients."""

    def _make_builder(self) -> Any:
        from src.kt_search.search_response_builder import SearchResponseBuilder

        return SearchResponseBuilder()

    def test_extract_additional_details_sem_chunks(self) -> None:
        """Sem chunks retorna string vazia."""
        builder = self._make_builder()
        assert builder.extract_additional_details([]) == ""

    def test_extract_additional_details_um_chunk(self) -> None:
        """Com 1 chunk retorna string com contagem."""
        builder = self._make_builder()
        result = builder.extract_additional_details([_make_chunk()])
        assert "1" in result

    def test_extract_additional_details_multiplos_videos(self) -> None:
        """Com múltiplos vídeos menciona quantidade de reuniões."""
        builder = self._make_builder()
        chunks = [_make_chunk(video_name="KT_01"), _make_chunk(video_name="KT_02")]
        result = builder.extract_additional_details(chunks)
        assert "2" in result
        assert "reuniões" in result

    def test_extract_unique_clients_sem_duplicatas(self) -> None:
        """extract_unique_clients retorna lista sem duplicatas."""
        builder = self._make_builder()
        chunks = [
            _make_chunk(client_name="DEXCO"),
            _make_chunk(client_name="DEXCO"),
            _make_chunk(client_name="ARCO"),
        ]
        result = builder.extract_unique_clients(chunks)
        assert len(result) == 2
        assert "DEXCO" in result
        assert "ARCO" in result

    def test_extract_unique_clients_ignora_unknown(self) -> None:
        """'Unknown' não é incluído na lista de clientes."""
        builder = self._make_builder()
        chunks = [_make_chunk(client_name="Unknown"), _make_chunk(client_name="ARCO")]
        result = builder.extract_unique_clients(chunks)
        assert "Unknown" not in result

    def test_extract_unique_clients_lista_vazia(self) -> None:
        """Lista vazia de chunks retorna lista vazia."""
        builder = self._make_builder()
        assert builder.extract_unique_clients([]) == []


class TestSearchResponseBuilderAnalyzeComplexity:
    """Testa analyze_query_complexity."""

    def _make_builder(self) -> Any:
        from src.kt_search.search_response_builder import SearchResponseBuilder

        return SearchResponseBuilder()

    def test_retorna_dict_com_chaves_esperadas(self) -> None:
        """analyze_query_complexity retorna dict com todas as chaves esperadas."""
        builder = self._make_builder()
        enrichment = MagicMock()
        enrichment.context = {
            "query_complexity": "high",
            "has_specific_client": True,
            "has_technical_terms": False,
            "has_temporal": False,
            "is_listing_request": False,
            "is_comparison_request": False,
            "is_broad_request": False,
            "detected_client": "DEXCO",
        }
        enrichment.entities = {"clients": {"values": ["DEXCO"]}}
        enrichment.confidence = 0.9

        classification = _make_classification_result()
        result = builder.analyze_query_complexity(enrichment, classification, "query")

        assert result["query_complexity"] == "high"
        assert result["has_specific_client"] is True
        assert result["detected_client"] == "DEXCO"
        assert result["entity_count"] == 1
        assert result["original_query"] == "query"

    def test_original_query_preservada(self) -> None:
        """original_query é incluída no resultado."""
        builder = self._make_builder()
        enrichment = MagicMock()
        enrichment.context = {}
        enrichment.entities = {}
        enrichment.confidence = 0.5
        result = builder.analyze_query_complexity(enrichment, _make_classification_result(), "minha query")
        assert result["original_query"] == "minha query"


class TestSearchResponseBuilderShouldStop:
    """Testa should_stop_for_nonexistent_client."""

    def _make_builder(self) -> Any:
        from src.kt_search.search_response_builder import SearchResponseBuilder

        return SearchResponseBuilder()

    def test_retorna_false_sem_palavra_cliente(self) -> None:
        """Sem 'cliente' na query, não para o pipeline."""
        builder = self._make_builder()
        assert builder.should_stop_for_nonexistent_client("quais reuniões temos") is False

    def test_retorna_false_cliente_real(self) -> None:
        """Query com cliente real não para o pipeline."""
        builder = self._make_builder()
        assert builder.should_stop_for_nonexistent_client("informações do cliente DEXCO") is False

    def test_retorna_true_cliente_xpto(self) -> None:
        """Padrão 'xpto' como cliente dispara early-exit."""
        builder = self._make_builder()
        assert builder.should_stop_for_nonexistent_client("informações do cliente XPTO") is True

    def test_retorna_true_cliente_inexistente(self) -> None:
        """Padrão 'inexistente' como cliente dispara early-exit."""
        builder = self._make_builder()
        assert builder.should_stop_for_nonexistent_client("dados do cliente inexistente") is True

    def test_case_insensitive(self) -> None:
        """Detecção é case-insensitive."""
        builder = self._make_builder()
        assert builder.should_stop_for_nonexistent_client("cliente TESTE") is True
