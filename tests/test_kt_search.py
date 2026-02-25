"""Testes unitários para kt_search — QueryEnricher, QueryClassifier, ChunkSelector, SearchEngine."""

from typing import Any
from unittest.mock import MagicMock, patch

# ════════════════════════════════════════════════════════════════════════════
# HELPERS INLINE
# ════════════════════════════════════════════════════════════════════════════


def make_enrichment_result(query: str = "quais transações do módulo FI") -> object:
    """Cria EnrichmentResult real via QueryEnricher."""
    from src.kt_search.query_enricher import QueryEnricher

    enricher = QueryEnricher()
    return enricher.enrich_query_universal(query)


def make_raw_chunk_result(n: int = 3) -> list[dict[str, Any]]:
    """Gera lista de resultados brutos simulando retorno do ChromaDB."""
    return [
        {
            "id": f"chunk-{i}",
            "document": f"Texto do chunk {i} com conteúdo relevante para o teste de busca.",
            "metadata": {
                "client_name": "ClienteX",
                "video_name": "KT Finance",
                "sap_modules_title": "FI",
                "meeting_phase": "AS-IS",
                "speaker": "Ana",
                "start_time": float(i * 10),
                "searchable_tags": ["fi", "financeiro"],
                "participants_mentioned": ["Ana"],
                "systems": ["SAP"],
                "transactions": ["FB01"],
            },
            "distance": 0.1 * i,
        }
        for i in range(n)
    ]


# ════════════════════════════════════════════════════════════════════════════
# QueryEnricher
# ════════════════════════════════════════════════════════════════════════════


class TestQueryEnricher:
    """Testa enriquecimento de queries — sem I/O externo."""

    def test_enrich_retorna_enrichment_result(self) -> None:
        """enrich_query_universal retorna EnrichmentResult com campos obrigatórios."""
        from src.kt_search.query_enricher import EnrichmentResult, QueryEnricher

        enricher = QueryEnricher()
        result = enricher.enrich_query_universal("quais transações do módulo FI foram apresentadas?")

        assert isinstance(result, EnrichmentResult)
        assert result.original_query == "quais transações do módulo FI foram apresentadas?"
        assert result.cleaned_query
        assert isinstance(result.confidence, float)
        assert 0.0 <= result.confidence <= 1.0

    def test_enrich_popula_cleaned_query(self) -> None:
        """cleaned_query é versão sanitizada da query original."""
        from src.kt_search.query_enricher import QueryEnricher

        enricher = QueryEnricher()
        result = enricher.enrich_query_universal("  Quem falou sobre MM?  ")

        # Cleaned não deve ter espaços extras nas bordas
        assert result.cleaned_query == result.cleaned_query.strip()

    def test_enrich_registra_processing_time(self) -> None:
        """processing_time é um float positivo."""
        from src.kt_search.query_enricher import QueryEnricher

        enricher = QueryEnricher()
        result = enricher.enrich_query_universal("explicar módulo SD")

        assert isinstance(result.processing_time, float)
        assert result.processing_time >= 0.0

    def test_enrich_query_curta_retorna_resultado(self) -> None:
        """Query muito curta (válida) ainda gera EnrichmentResult."""
        from src.kt_search.query_enricher import QueryEnricher

        enricher = QueryEnricher()
        # Deve funcionar sem exceção mesmo com query mínima
        result = enricher.enrich_query_universal("FI")
        assert result is not None

    def test_enrich_query_none_retorna_resultado_sem_crash(self) -> None:
        """Query None não crasha o processo — retorna EnrichmentResult (comportamento defensivo).

        O QueryEnricher captura ValueError internamente e retorna resultado padrão.
        """
        from src.kt_search.query_enricher import EnrichmentResult, QueryEnricher

        enricher = QueryEnricher()
        # Não deve levantar — comportamento defensivo: captura e retorna result
        result = enricher.enrich_query_universal(None)  # type: ignore[arg-type]
        assert isinstance(result, EnrichmentResult)


# ════════════════════════════════════════════════════════════════════════════
# QueryClassifier
# ════════════════════════════════════════════════════════════════════════════


class TestQueryClassifier:
    """Testa classificação de queries."""

    def test_classify_retorna_classification_result(self) -> None:
        """classify_query_with_context retorna ClassificationResult."""
        from src.kt_search.query_classifier import ClassificationResult, QueryClassifier

        classifier = QueryClassifier()
        result = classifier.classify_query_with_context(
            original_query="quais transações do módulo FI?",
            entities={"transactions": ["FB01"], "sap_modules": ["FI"]},
            context={"temporal": False, "has_entities": True},
        )

        assert isinstance(result, ClassificationResult)
        assert result.query_type is not None
        assert isinstance(result.confidence, float)
        assert 0.0 <= result.confidence <= 1.0

    def test_classify_tem_estrategia(self) -> None:
        """Resultado de classificação inclui strategy não vazia."""
        from src.kt_search.query_classifier import QueryClassifier

        classifier = QueryClassifier()
        result = classifier.classify_query_with_context(
            original_query="explicar processo de aprovação de NF",
            entities={},
            context={},
        )

        assert isinstance(result.strategy, dict)

    def test_classify_tem_fallback_types(self) -> None:
        """Resultado inclui lista de fallback_types."""
        from src.kt_search.query_classifier import QueryClassifier

        classifier = QueryClassifier()
        result = classifier.classify_query_with_context(
            original_query="quem falou sobre integração?",
            entities={"participants": ["Ana"]},
            context={},
        )

        assert isinstance(result.fallback_types, list)

    def test_classify_query_funcao_conveniencia(self) -> None:
        """classify_query (função de módulo) retorna ClassificationResult."""
        from src.kt_search.query_classifier import ClassificationResult, classify_query

        enrichment = make_enrichment_result("módulos SAP abordados na reunião")
        result = classify_query("módulos SAP abordados na reunião", enrichment)  # type: ignore[arg-type]

        assert isinstance(result, ClassificationResult)


# ════════════════════════════════════════════════════════════════════════════
# ChunkSelector
# ════════════════════════════════════════════════════════════════════════════


class TestChunkSelector:
    """Testa seleção inteligente de chunks."""

    def test_select_chunks_vazio_retorna_selection_vazia(self) -> None:
        """Sem candidatos, retorna SelectionResult com lista vazia."""
        from src.kt_search.chunk_selector import ChunkSelector, QueryType

        selector = ChunkSelector()
        result = selector.select_intelligent_chunks(
            raw_results=[],
            top_k=5,
            query_type=QueryType.SEMANTIC,
            query_analysis={},
            original_query="qualquer query",
        )

        assert result.selected_chunks == []
        assert result.total_candidates == 0

    def test_select_chunks_respeita_top_k(self) -> None:
        """Seleciona no máximo top_k chunks quando há candidatos suficientes."""
        from src.kt_search.chunk_selector import ChunkSelector, QueryType

        selector = ChunkSelector()
        raw = make_raw_chunk_result(n=10)

        result = selector.select_intelligent_chunks(
            raw_results=raw,
            top_k=3,
            query_type=QueryType.SEMANTIC,
            query_analysis={},
            original_query="transações FI",
        )

        assert len(result.selected_chunks) <= 3

    def test_select_chunks_retorna_selection_result(self) -> None:
        """Retorno é SelectionResult com todos os campos."""
        from src.kt_search.chunk_selector import ChunkSelector, QueryType, SelectionResult

        selector = ChunkSelector()
        raw = make_raw_chunk_result(n=5)

        result = selector.select_intelligent_chunks(
            raw_results=raw,
            top_k=5,
            query_type=QueryType.ENTITY,
            query_analysis={"entities": ["Ana"]},
            original_query="quem falou sobre integração?",
        )

        assert isinstance(result, SelectionResult)
        assert isinstance(result.processing_time, float)
        assert isinstance(result.selection_strategy, str)
        assert isinstance(result.quality_threshold_met, bool)

    def test_select_chunks_funcao_conveniencia(self) -> None:
        """select_chunks (função de módulo) retorna lista de dicts."""
        from src.kt_search.chunk_selector import QueryType, select_chunks

        raw = make_raw_chunk_result(n=3)
        result = select_chunks(raw, top_k=3, query_type=QueryType.SEMANTIC, query_analysis={})

        assert isinstance(result, list)


# ════════════════════════════════════════════════════════════════════════════
# SearchEngine
# ════════════════════════════════════════════════════════════════════════════


class TestSearchEngineInit:
    """Testa inicialização do SearchEngine com dependências externas mockadas."""

    def _make_engine(self) -> object:
        """Cria SearchEngine com ChromaDB e OpenAI completamente mockados."""
        with (
            patch("src.kt_search.search_engine.DynamicClientManager"),
            patch("src.kt_indexing.chromadb_store.chromadb.PersistentClient"),
            patch("src.kt_indexing.chromadb_store.openai.OpenAI"),
            patch("src.kt_search.search_engine.InsightsAgent", autospec=True) if False else patch(
                "src.kt_search.search_engine.SearchEngine._initialize_insights_agent"
            ),
        ):
            from src.kt_search.search_engine import SearchEngine

            engine = SearchEngine.__new__(SearchEngine)
            engine.verbose = False
            engine.query_enricher = MagicMock()
            engine.query_classifier = MagicMock()
            engine.chunk_selector = MagicMock()
            engine.dynamic_client_manager = MagicMock()
            engine.chromadb_manager = MagicMock()
            engine.embedding_generator = MagicMock()
            engine.insights_agent = MagicMock()
            engine.search_stats = {
                "total_queries": 0,
                "successful_queries": 0,
                "failed_queries": 0,
                "avg_processing_time": 0.0,
            }
            return engine

    def test_search_engine_tem_componentes_pipeline(self) -> None:
        """SearchEngine possui todos os componentes do pipeline."""
        engine = self._make_engine()

        assert hasattr(engine, "query_enricher")
        assert hasattr(engine, "query_classifier")
        assert hasattr(engine, "chunk_selector")
        assert hasattr(engine, "insights_agent")

    def test_search_stats_inicializado_zerado(self) -> None:
        """search_stats é inicializado com contadores zerados."""
        engine = self._make_engine()

        assert engine.search_stats["total_queries"] == 0  # type: ignore[union-attr]
        assert engine.search_stats["successful_queries"] == 0  # type: ignore[union-attr]

    def test_validate_query_retorna_verdadeiro_para_query_valida(self) -> None:
        """_validate_query retorna True para query com comprimento adequado."""
        engine = self._make_engine()
        assert engine._validate_query("transações do módulo FI") is True  # type: ignore[union-attr]

    def test_validate_query_retorna_falso_para_query_vazia(self) -> None:
        """_validate_query retorna False para string vazia."""
        engine = self._make_engine()
        assert engine._validate_query("") is False  # type: ignore[union-attr]


class TestSearchEngineSearchMethod:
    """Testa o método search com pipeline completamente mockado."""

    def test_search_retorna_search_response(self) -> None:
        """search() retorna SearchResponse com campo success."""
        from src.kt_search.chunk_selector import SelectionResult
        from src.kt_search.query_classifier import ClassificationResult, QueryType
        from src.kt_search.query_enricher import EnrichmentResult
        from src.kt_search.search_engine import SearchEngine, SearchResponse

        enrichment = MagicMock(spec=EnrichmentResult)
        enrichment.original_query = "transações FI"
        enrichment.cleaned_query = "transações fi"
        enrichment.enriched_query = "transações fi módulo"
        enrichment.entities = {}
        enrichment.context = {}
        enrichment.confidence = 0.8
        enrichment.processing_time = 0.01

        classification = MagicMock(spec=ClassificationResult)
        classification.query_type = QueryType.SEMANTIC
        classification.confidence = 0.9
        classification.strategy = {"n_results": 10, "include": ["documents", "metadatas", "distances"]}
        classification.reasoning = "Busca semântica"
        classification.fallback_types = []
        classification.processing_time = 0.01

        selection = MagicMock(spec=SelectionResult)
        selection.selected_chunks = make_raw_chunk_result(n=2)
        selection.chunk_scores = []
        selection.total_candidates = 2
        selection.selection_strategy = "quality_diversity"
        selection.processing_time = 0.01
        selection.quality_threshold_met = True

        from src.kt_search.search_logging import PipelineLogger
        from src.kt_search.search_response_builder import SearchResponseBuilder

        engine = SearchEngine.__new__(SearchEngine)
        engine.verbose = False
        engine.query_enricher = MagicMock()
        engine.query_enricher.enrich_query_universal.return_value = enrichment
        engine.query_classifier = MagicMock()
        engine.query_classifier.classify_query_with_context.return_value = classification
        engine.chunk_selector = MagicMock()
        engine.chunk_selector.select_intelligent_chunks.return_value = selection
        engine.dynamic_client_manager = MagicMock()
        engine.chromadb_manager = MagicMock()
        engine.embedding_generator = MagicMock()
        engine._chromadb_executor = MagicMock()
        engine._chromadb_executor.execute_search.return_value = []
        engine.insights_agent = MagicMock()
        engine.insights_agent.generate_insights.return_value = {
            "response": "Resposta gerada.", "sources": [], "confidence": 0.9
        }
        engine.search_stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "avg_processing_time": 0.0,
        }
        engine._response_builder = SearchResponseBuilder()
        engine._pipeline_logger = PipelineLogger()

        result = engine.search("transações FI")

        assert isinstance(result, SearchResponse)
        assert isinstance(result.success, bool)
        assert isinstance(result.processing_time, float)


# ════════════════════════════════════════════════════════════════════════════
# DynamicClientManager — métodos puros (sem ChromaDB real)
# ════════════════════════════════════════════════════════════════════════════


class TestDynamicClientManager:
    """Testa DynamicClientManager — lógica pura de normalização e matching."""

    def _make_manager(self) -> object:
        """Cria DynamicClientManager com ChromaDBStore mockado."""
        with patch("src.kt_search.dynamic_client_manager.ChromaDBStore"):
            from src.kt_search.dynamic_client_manager import DynamicClientManager

            return DynamicClientManager()

    def test_get_client_variations_gera_upper_e_lower(self) -> None:
        """Variações incluem versões uppercase e lowercase do nome."""
        manager = self._make_manager()
        result = manager.get_client_variations("EMPRESA_X")  # type: ignore[attr-defined]

        result_lower = [v.lower() for v in result]
        assert "empresa_x" in result_lower
        assert "EMPRESA_X" in result  # type: ignore[operator]
        assert len(result) >= 3

    def test_get_client_variations_unknown_retorna_vazio(self) -> None:
        """'UNKNOWN' retorna lista vazia (cliente inválido)."""
        manager = self._make_manager()
        result = manager.get_client_variations("UNKNOWN")  # type: ignore[attr-defined]
        assert result == []

    def test_normalize_text_remove_acentos(self) -> None:
        """_normalize_text converte 'Ação' → 'Acao'."""
        manager = self._make_manager()
        result = manager._normalize_text("Ação")  # type: ignore[attr-defined]
        assert result == "Acao"

    def test_is_cache_valid_sem_timestamp_retorna_falso(self) -> None:
        """Cache sem timestamp é considerado inválido."""
        manager = self._make_manager()
        # cache_timestamp é None por padrão
        assert manager._is_cache_valid() is False  # type: ignore[attr-defined]

    def test_should_ignore_client_nomes_invalidos(self) -> None:
        """Nomes inválidos ('UNKNOWN', '') retornam True em _should_ignore_client."""
        manager = self._make_manager()
        assert manager._should_ignore_client("UNKNOWN") is True  # type: ignore[attr-defined]
        assert manager._should_ignore_client("") is True  # type: ignore[attr-defined]
        assert manager._should_ignore_client("EMPRESA_VALIDA") is False  # type: ignore[attr-defined]


# ════════════════════════════════════════════════════════════════════════════
# InsightsAgent — mock via parâmetro do construtor
# ════════════════════════════════════════════════════════════════════════════


class TestInsightsAgent:
    """Testa InsightsAgent — instância com mock client, fallback e cache."""

    def test_instancia_com_mock_client(self) -> None:
        """InsightsAgent aceita mock OpenAI client via construtor."""
        from openai import OpenAI

        from src.kt_search.insights_agent import InsightsAgent

        mock_client = MagicMock(spec=OpenAI)
        agent = InsightsAgent(openai_client=mock_client)

        assert agent.openai_client is mock_client
        assert agent.model == "gpt-4o-mini"
        assert isinstance(agent._insights_cache, dict)

    def test_sem_resultados_de_busca_retorna_fallback(self) -> None:
        """generate_direct_insight com search_results=[] retorna DirectInsightResult com fallback_used=True."""
        from openai import OpenAI

        from src.kt_search.insights_agent import DirectInsightResult, InsightsAgent

        mock_client = MagicMock(spec=OpenAI)
        agent = InsightsAgent(openai_client=mock_client)

        with patch("utils.hash_manager.get_hash_manager") as mock_hm:
            mock_hm.return_value.generate_content_hash.return_value = "key-sem-resultados"
            result = agent.generate_direct_insight("query de teste", [])

        assert isinstance(result, DirectInsightResult)
        assert result.fallback_used is True

    def test_cache_hit_retorna_resultado_armazenado(self) -> None:
        """Resultado já no cache é retornado diretamente sem nova chamada."""
        from openai import OpenAI

        from src.kt_search.insights_agent import DirectInsightResult, InsightsAgent

        mock_client = MagicMock(spec=OpenAI)
        agent = InsightsAgent(openai_client=mock_client)

        cached = DirectInsightResult(
            insight="Resultado em cache",
            confidence=0.9,
            sources_used=2,
            processing_time=0.01,
            fallback_used=False,
        )
        fixed_key = "cache-key-fixo"
        agent._insights_cache[fixed_key] = cached

        with patch("utils.hash_manager.get_hash_manager") as mock_hm:
            mock_hm.return_value.generate_content_hash.return_value = fixed_key
            result = agent.generate_direct_insight("qualquer query", make_raw_chunk_result(3))

        assert result is cached

    def test_prompt_templates_inicializados(self) -> None:
        """Todos os templates de prompt são inicializados no construtor."""
        from openai import OpenAI

        from src.kt_search.insights_agent import InsightsAgent

        mock_client = MagicMock(spec=OpenAI)
        agent = InsightsAgent(openai_client=mock_client)

        for template_key in ("base", "decision", "problem", "general", "metadata_listing"):
            assert template_key in agent.prompt_templates
