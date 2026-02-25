"""
Testes unitários para QueryTypeDetector.

Cobre: detect_specific_kt_analysis, detect_listing_query_refined,
determine_primary_theme, detect_query_type.
"""

import pytest

# ════════════════════════════════════════════════════════════════════════════
# QueryTypeDetector — testes
# ════════════════════════════════════════════════════════════════════════════


class TestQueryTypeDetectorDetectSpecificKtAnalysis:
    """Testa detect_specific_kt_analysis."""

    def _make_detector(self) -> object:
        from src.kt_search.query_type_detector import QueryTypeDetector

        return QueryTypeDetector()

    def test_listagem_generica_retorna_false(self) -> None:
        """Queries de listagem genérica de KTs retornam False."""
        detector = self._make_detector()
        assert detector.detect_specific_kt_analysis("liste todos os kts que temos") is False

    def test_quantos_kts_retorna_false(self) -> None:
        """'quantos kts temos' é listagem genérica — retorna False."""
        detector = self._make_detector()
        assert detector.detect_specific_kt_analysis("quantos kts temos na base") is False

    def test_quais_kts_disponiveis_retorna_false(self) -> None:
        """'quais kts disponíveis' retorna False."""
        detector = self._make_detector()
        assert detector.detect_specific_kt_analysis("quais kts estão disponíveis") is False

    def test_resuma_retorna_true(self) -> None:
        """Query com 'resuma' indica análise específica — retorna True."""
        detector = self._make_detector()
        assert detector.detect_specific_kt_analysis("resuma os pontos do kt iflow") is True

    def test_o_que_foi_abordado_retorna_true(self) -> None:
        """'o que foi abordado' indica análise específica."""
        detector = self._make_detector()
        assert detector.detect_specific_kt_analysis("o que foi abordado no kt de ontem") is True

    def test_kt_com_nome_especifico_retorna_true(self) -> None:
        """KT com nome técnico específico (iflow, estorno) indica análise."""
        detector = self._make_detector()
        assert detector.detect_specific_kt_analysis("qual o conteúdo do kt iflow pc factory") is True

    def test_temas_discutidos_retorna_true(self) -> None:
        """'temas discutidos' é padrão de análise específica."""
        detector = self._make_detector()
        assert detector.detect_specific_kt_analysis("quais os temas discutidos no kt") is True

    def test_analise_retorna_true(self) -> None:
        """Palavra 'analise' dispara detecção de análise específica."""
        detector = self._make_detector()
        assert detector.detect_specific_kt_analysis("analise o conteúdo do kt sustentação") is True

    def test_query_generica_sem_indicadores_retorna_false(self) -> None:
        """Query sem padrões específicos retorna False por padrão."""
        detector = self._make_detector()
        assert detector.detect_specific_kt_analysis("preciso de informações") is False


class TestQueryTypeDetectorDetectListingQueryRefined:
    """Testa detect_listing_query_refined."""

    def _make_detector(self) -> object:
        from src.kt_search.query_type_detector import QueryTypeDetector

        return QueryTypeDetector()

    def test_liste_retorna_true(self) -> None:
        """Query começando com 'liste' retorna True."""
        detector = self._make_detector()
        assert detector.detect_listing_query_refined("liste todos os kts disponíveis") is True

    def test_quais_kts_temos_retorna_true(self) -> None:
        """'quais kts temos' é listagem explícita."""
        detector = self._make_detector()
        assert detector.detect_listing_query_refined("quais kts temos") is True

    def test_todos_os_kts_retorna_true(self) -> None:
        """'todos os kts' indica listagem genérica."""
        detector = self._make_detector()
        assert detector.detect_listing_query_refined("mostre todos os kts") is True

    def test_kts_disponiveis_retorna_true(self) -> None:
        """'kts disponíveis' é padrão de listagem."""
        detector = self._make_detector()
        assert detector.detect_listing_query_refined("quais kts estão disponíveis") is True

    def test_query_especifica_retorna_false(self) -> None:
        """Query de análise específica retorna False."""
        detector = self._make_detector()
        assert detector.detect_listing_query_refined("explique o conteúdo do kt dexco") is False

    def test_query_generica_sem_padrao_retorna_false(self) -> None:
        """Query sem padrões explícitos de listagem retorna False."""
        detector = self._make_detector()
        assert detector.detect_listing_query_refined("quais problemas foram discutidos") is False


class TestQueryTypeDetectorDeterminePrimaryTheme:
    """Testa determine_primary_theme."""

    def _make_detector(self) -> object:
        from src.kt_search.query_type_detector import QueryTypeDetector

        return QueryTypeDetector()

    def test_cliente_dominante_com_reuniao(self) -> None:
        """Com cliente dominante e 'reunião' na query, tema é reunião_{cliente}."""
        detector = self._make_detector()
        result = detector.determine_primary_theme("reunião do cliente DEXCO", [], "DEXCO")
        assert result == "reunião_dexco"

    def test_cliente_dominante_sem_reuniao(self) -> None:
        """Com cliente dominante sem 'reunião', tema é informações_{cliente}."""
        detector = self._make_detector()
        result = detector.determine_primary_theme("dados sobre DEXCO", [], "DEXCO")
        assert result == "informações_dexco"

    def test_sem_cliente_dominante_quais_clientes(self) -> None:
        """Sem cliente dominante e 'clientes' na query, tema é listagem_clientes."""
        detector = self._make_detector()
        result = detector.determine_primary_theme("quais clientes temos", [], None)
        assert result == "listagem_clientes"

    def test_sem_cliente_dominante_problema(self) -> None:
        """Sem cliente dominante e 'problema' na query (sem 'qual'), tema é resolução_problemas."""
        detector = self._make_detector()
        result = detector.determine_primary_theme("o problema identificado no sistema", [], None)
        assert result == "resolução_problemas"

    def test_sem_cliente_dominante_padrao(self) -> None:
        """Sem padrões reconhecíveis, tema é informações_gerais."""
        detector = self._make_detector()
        result = detector.determine_primary_theme("como funciona o processo", [], None)
        assert result == "informações_gerais"

    def test_cliente_nome_lowercase_no_tema(self) -> None:
        """Nome do cliente é convertido para lowercase no tema."""
        detector = self._make_detector()
        result = detector.determine_primary_theme("reunião ARCO", [], "ARCO")
        assert result == "reunião_arco"

    @pytest.mark.parametrize("query,expected", [
        ("quais os nomes dos clientes", "listagem_clientes"),
        ("qual cliente estava na reunião", "identificação_cliente"),
        ("o erro que ocorreu no sistema", "resolução_problemas"),
    ])
    def test_temas_por_padrao_de_query(self, query: str, expected: str) -> None:
        """Temas baseados em padrões de keywords na query sem cliente dominante."""
        detector = self._make_detector()
        result = detector.determine_primary_theme(query, [], None)
        assert result == expected


class TestQueryTypeDetectorDetectQueryType:
    """Testa detect_query_type — método público movido de InsightsAgent."""

    def _make_detector(self) -> object:
        from src.kt_search.query_type_detector import QueryTypeDetector

        return QueryTypeDetector()

    def test_highlights_summary_detectado(self) -> None:
        """Query com 'principais pontos' retorna highlights_summary."""
        detector = self._make_detector()
        result = detector.detect_query_type("quais os principais pontos da reunião", [])
        assert result == "highlights_summary"

    def test_project_listing_detectado(self) -> None:
        """Query com 'quais projetos' retorna project_listing."""
        detector = self._make_detector()
        result = detector.detect_query_type("quais projetos foram mencionados", [])
        assert result == "project_listing"

    def test_metadata_listing_detectado_base_conhecimento(self) -> None:
        """'base de conhecimento' dispara metadata_listing."""
        detector = self._make_detector()
        result = detector.detect_query_type("o que temos na base de conhecimento", [])
        assert result == "metadata_listing"

    def test_metadata_listing_detectado_kts_disponiveis(self) -> None:
        """'quais kts temos' dispara metadata_listing."""
        detector = self._make_detector()
        result = detector.detect_query_type("quais kts temos disponíveis", [])
        assert result == "metadata_listing"

    def test_analise_especifica_retorna_general(self) -> None:
        """Query de análise específica de KT retorna 'general' (usa LLM)."""
        detector = self._make_detector()
        result = detector.detect_query_type("resuma os pontos do kt iflow", [])
        assert result == "general"

    def test_participants_detectado(self) -> None:
        """'quem participou' retorna participants."""
        detector = self._make_detector()
        result = detector.detect_query_type("quem participou da reunião", [])
        assert result == "participants"

    def test_decision_detectado(self) -> None:
        """Query com 'decisão' retorna decision."""
        detector = self._make_detector()
        result = detector.detect_query_type("qual foi a decisão tomada", [])
        assert result == "decision"

    def test_problem_detectado(self) -> None:
        """Query com 'problema' retorna problem."""
        detector = self._make_detector()
        result = detector.detect_query_type("qual o problema identificado", [])
        assert result == "problem"

    def test_general_quando_sem_padrao(self) -> None:
        """Query sem padrões específicos retorna 'general'."""
        detector = self._make_detector()
        result = detector.detect_query_type("como funciona o processo de aprovação", [])
        assert result == "general"

    def test_client_not_found_com_fns_fornecidas(self) -> None:
        """Se cliente não existe na base e extract_client_fn retorna nome, retorna client_not_found.

        Query escolhida pontua >= 8: "quais"(3) + "kts"(2) + "cliente"(2) + "temos"(1) = 8.
        """
        detector = self._make_detector()
        result = detector.detect_query_type(
            "quais kts temos do cliente xpto",
            [],
            extract_client_fn=lambda _q: "xpto",
            client_exists_fn=lambda _c: False,
        )
        assert result == "client_not_found"

    def test_metadata_listing_quando_cliente_existe(self) -> None:
        """Se cliente existe na base, não retorna client_not_found — retorna metadata_listing."""
        detector = self._make_detector()
        result = detector.detect_query_type(
            "quais kts temos do cliente dexco",
            [],
            extract_client_fn=lambda _q: "dexco",
            client_exists_fn=lambda _c: True,
        )
        assert result == "metadata_listing"

    def test_sem_extract_fn_nao_verifica_cliente(self) -> None:
        """Sem extract_client_fn, a verificação de cliente é pulada — não levanta erro."""
        detector = self._make_detector()
        result = detector.detect_query_type(
            "quais kts temos do cliente xpto",
            [],
        )
        # Sem as fns, retorna metadata_listing (não verifica existência do cliente)
        assert result == "metadata_listing"

    def test_metadata_listing_via_score_multicamada(self) -> None:
        """Query com múltiplas palavras de listagem atinge score >= 8."""
        detector = self._make_detector()
        # "liste" (3) + "kts" (2) + "temos" (1) + "base" (1) + "conhecimento" (1) = 8
        result = detector.detect_query_type("liste os kts que temos na base de conhecimento", [])
        assert result == "metadata_listing"
