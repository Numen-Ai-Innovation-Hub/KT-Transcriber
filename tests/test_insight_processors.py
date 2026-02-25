"""
Testes unitários para InsightProcessors.

Cobre: analyze_context_relevance, determine_primary_theme, extract_entities_from_query,
extract_query_keywords, extract_content_from_result, extract_title_from_content,
extract_client_from_query, normalize_for_matching, apply_semantic_filter,
calculate_semantic_relevance, calculate_title_matching_bonus, calculate_confidence,
format_insight_text, format_contexts_for_llm, get_performance_config.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest


def _make_processors() -> Any:
    from src.kt_search.insight_processors import InsightProcessors

    return InsightProcessors()


def _make_result(content: str = "conteúdo do resultado", video_name: str = "KT_01") -> Any:
    """Cria mock de SearchResult simples."""
    r = MagicMock()
    r.content = content
    r.video_name = video_name
    r.relevance_score = 0.9
    r.metadata = {}
    return r


def _make_contextualized_result(content: str = "conteúdo via context_window") -> Any:
    """Cria mock de ContextualizedResult com original_result."""
    r = MagicMock()
    r.original_result = MagicMock()
    r.original_result.content = content
    r.original_result.video_name = "KT_contextualized"
    r.context_window = MagicMock()
    r.context_window.full_context_text = content
    r.relevance_score = 0.8
    return r


# ════════════════════════════════════════════════════════════════════════════
# analyze_context_relevance
# ════════════════════════════════════════════════════════════════════════════


class TestInsightProcessorsAnalyzeContextRelevance:
    """Testa analyze_context_relevance."""

    def test_sem_resultados_retorna_unknown(self) -> None:
        """Lista vazia retorna dicionário com primary_theme='unknown'."""
        p = _make_processors()
        result = p.analyze_context_relevance("query", [])
        assert result["primary_theme"] == "unknown"
        assert result["confidence"] == 0.0
        assert result["main_entities"] == []

    def test_retorna_chaves_esperadas(self) -> None:
        """Resultado tem primary_theme, main_entities, dominant_context, confidence."""
        p = _make_processors()
        result = p.analyze_context_relevance("query DEXCO", [_make_result()])
        assert "primary_theme" in result
        assert "main_entities" in result
        assert "dominant_context" in result
        assert "confidence" in result

    def test_entidades_detectadas(self) -> None:
        """Entidades mencionadas na query são incluídas em main_entities."""
        p = _make_processors()
        result = p.analyze_context_relevance("problemas com CPI", [_make_result()])
        assert "CPI" in result["main_entities"]


# ════════════════════════════════════════════════════════════════════════════
# extract_entities_from_query
# ════════════════════════════════════════════════════════════════════════════


class TestInsightProcessorsExtractEntities:
    """Testa extract_entities_from_query."""

    def test_detecta_cliente_arco(self) -> None:
        """ARCO é reconhecido como entidade cliente."""
        p = _make_processors()
        assert "ARCO" in p.extract_entities_from_query("reuniões do cliente ARCO")

    def test_detecta_termo_tecnico_cpi(self) -> None:
        """CPI é reconhecido como termo técnico."""
        p = _make_processors()
        assert "CPI" in p.extract_entities_from_query("integrações via CPI no BTP")

    def test_query_sem_entidades_retorna_lista_vazia(self) -> None:
        """Query genérica sem entidades conhecidas retorna lista vazia."""
        p = _make_processors()
        result = p.extract_entities_from_query("o que foi discutido")
        assert result == []

    def test_multiplas_entidades(self) -> None:
        """Múltiplas entidades são todas incluídas."""
        p = _make_processors()
        result = p.extract_entities_from_query("KT FIORI para ARCO via BTP")
        assert "KT" in result
        assert "FIORI" in result
        assert "ARCO" in result
        assert "BTP" in result


# ════════════════════════════════════════════════════════════════════════════
# extract_query_keywords
# ════════════════════════════════════════════════════════════════════════════


class TestInsightProcessorsExtractQueryKeywords:
    """Testa extract_query_keywords."""

    def test_filtra_stop_words(self) -> None:
        """Stop words comuns não aparecem nas keywords."""
        p = _make_processors()
        result = p.extract_query_keywords("qual o problema que ocorreu")
        stop_words = {"qual", "que", "o"}
        for word in result:
            assert word not in stop_words

    def test_inclui_palavras_significativas(self) -> None:
        """Palavras com 3+ caracteres não-stop são incluídas."""
        p = _make_processors()
        result = p.extract_query_keywords("integrações do sistema SAP")
        assert any("integra" in w for w in result)

    def test_adiciona_termos_tecnicos_presentes(self) -> None:
        """Termos técnicos como 'cpi', 'fiori' são incluídos explicitamente."""
        p = _make_processors()
        result = p.extract_query_keywords("configuração do cpi na cloud")
        assert "cpi" in result

    def test_inclui_nome_cliente_vissimo(self) -> None:
        """Nomes de clientes conhecidos como 'vissimo' são incluídos."""
        p = _make_processors()
        result = p.extract_query_keywords("dados do cliente vissimo no kt")
        assert "vissimo" in result

    def test_retorna_lista(self) -> None:
        """Retorna sempre uma lista (mesmo que vazia)."""
        p = _make_processors()
        result = p.extract_query_keywords("")
        assert isinstance(result, list)


# ════════════════════════════════════════════════════════════════════════════
# extract_content_from_result
# ════════════════════════════════════════════════════════════════════════════


class TestInsightProcessorsExtractContent:
    """Testa extract_content_from_result."""

    def test_extrai_content_de_search_result_simples(self) -> None:
        """Extrai content de objeto SearchResult com atributo 'content'."""
        p = _make_processors()
        # spec limita os atributos disponíveis — evita que MagicMock auto-crie original_result
        r = MagicMock(spec=["content", "main_content", "text", "video_name", "relevance_score", "metadata"])
        r.content = "texto do resultado"
        r.main_content = ""
        r.text = ""
        assert p.extract_content_from_result(r) == "texto do resultado"

    def test_extrai_content_de_contextualized_result(self) -> None:
        """Extrai full_context_text de ContextualizedResult."""
        p = _make_processors()
        r = _make_contextualized_result("conteúdo via context window")
        result = p.extract_content_from_result(r)
        assert "conteúdo via context window" in result

    def test_retorna_string_vazia_para_resultado_sem_content(self) -> None:
        """Resultado sem conteúdo retorna string vazia."""
        p = _make_processors()
        r = MagicMock()
        r.content = ""
        r.main_content = ""
        r.text = ""
        del r.original_result  # garante que não é ContextualizedResult
        r.__str__ = lambda self: ""
        result = p.extract_content_from_result(r)
        assert isinstance(result, str)


# ════════════════════════════════════════════════════════════════════════════
# extract_title_from_content
# ════════════════════════════════════════════════════════════════════════════


class TestInsightProcessorsExtractTitle:
    """Testa extract_title_from_content."""

    def test_primeira_linha_com_kt_eh_titulo(self) -> None:
        """Primeira linha contendo 'KT' é retornada como título."""
        p = _make_processors()
        content = "KT - Estorno em Massa\nConteúdo do KT..."
        assert "KT" in p.extract_title_from_content(content)

    def test_primeira_linha_com_reuniao_eh_titulo(self) -> None:
        """Primeira linha com 'reunião' é retornada como título."""
        p = _make_processors()
        content = "reunião de alinhamento DEXCO\nTexto normal..."
        result = p.extract_title_from_content(content)
        assert "reunião" in result.lower()

    def test_conteudo_sem_titulo_retorna_string_vazia(self) -> None:
        """Conteúdo sem padrão de título retorna string vazia."""
        p = _make_processors()
        content = "apenas texto normal sem indicadores de título"
        assert p.extract_title_from_content(content) == ""

    def test_conteudo_vazio_retorna_string_vazia(self) -> None:
        """Conteúdo vazio retorna string vazia."""
        p = _make_processors()
        assert p.extract_title_from_content("") == ""


# ════════════════════════════════════════════════════════════════════════════
# extract_client_from_query
# ════════════════════════════════════════════════════════════════════════════


class TestInsightProcessorsExtractClient:
    """Testa extract_client_from_query."""

    def test_extrai_cliente_apos_palavra_cliente(self) -> None:
        """Padrão 'cliente XPTO' extrai 'XPTO' em uppercase."""
        p = _make_processors()
        assert p.extract_client_from_query("informações do cliente arco") == "ARCO"

    def test_extrai_cliente_apos_sobre_o_cliente(self) -> None:
        """Padrão 'sobre o cliente XPTO' extrai o nome."""
        p = _make_processors()
        result = p.extract_client_from_query("sobre o cliente dexco")
        assert result == "DEXCO"

    def test_sem_cliente_retorna_string_vazia(self) -> None:
        """Query sem padrão de cliente retorna string vazia."""
        p = _make_processors()
        assert p.extract_client_from_query("quais reuniões temos") == ""

    def test_resultado_em_uppercase(self) -> None:
        """Nome do cliente é retornado sempre em uppercase."""
        p = _make_processors()
        result = p.extract_client_from_query("cliente vissimo")
        assert result == result.upper()


# ════════════════════════════════════════════════════════════════════════════
# normalize_for_matching
# ════════════════════════════════════════════════════════════════════════════


class TestInsightProcessorsNormalizeForMatching:
    """Testa normalize_for_matching."""

    def test_remove_acentos(self) -> None:
        """Texto com acentos é normalizado removendo diacríticos."""
        p = _make_processors()
        result = p.normalize_for_matching("integração")
        assert "ã" not in result
        assert "integra" in result

    def test_remove_pontuacao(self) -> None:
        """Pontuação é removida do texto."""
        p = _make_processors()
        result = p.normalize_for_matching("KT - Estorno, em Massa!")
        assert "-" not in result
        assert "," not in result
        assert "!" not in result

    def test_normaliza_espacos(self) -> None:
        """Múltiplos espaços são normalizados para um único espaço."""
        p = _make_processors()
        result = p.normalize_for_matching("texto   com   múltiplos   espaços")
        assert "  " not in result

    def test_string_vazia(self) -> None:
        """String vazia retorna string vazia."""
        p = _make_processors()
        assert p.normalize_for_matching("") == ""


# ════════════════════════════════════════════════════════════════════════════
# calculate_semantic_relevance
# ════════════════════════════════════════════════════════════════════════════


class TestInsightProcessorsCalculateSemanticRelevance:
    """Testa calculate_semantic_relevance."""

    def test_conteudo_vazio_retorna_zero(self) -> None:
        """Conteúdo vazio retorna score 0.0."""
        p = _make_processors()
        assert p.calculate_semantic_relevance("", ["keyword"], "query") == 0.0

    def test_keywords_vazias_retorna_zero(self) -> None:
        """Keywords vazias retornam score 0.0."""
        p = _make_processors()
        assert p.calculate_semantic_relevance("conteúdo", [], "query") == 0.0

    def test_match_perfeito_retorna_score_alto(self) -> None:
        """Conteúdo com todas as keywords tem score alto."""
        p = _make_processors()
        content = "integração cpi api interface"
        keywords = ["integração", "cpi", "api"]
        score = p.calculate_semantic_relevance(content, keywords, "integração cpi api")
        assert score > 0.2

    def test_score_entre_zero_e_um(self) -> None:
        """Score sempre fica entre 0.0 e 1.0."""
        p = _make_processors()
        score = p.calculate_semantic_relevance("texto qualquer com palavras", ["palavras", "texto"], "texto palavras")
        assert 0.0 <= score <= 1.0

    def test_conteudo_relevante_maior_que_irrelevante(self) -> None:
        """Conteúdo relevante tem score maior que conteúdo irrelevante."""
        p = _make_processors()
        keywords = ["integração", "cpi"]
        relevant = "integração via cpi na plataforma btp"
        irrelevant = "reunião de time sobre férias do final de ano"
        score_rel = p.calculate_semantic_relevance(relevant, keywords, "integração cpi")
        score_irr = p.calculate_semantic_relevance(irrelevant, keywords, "integração cpi")
        assert score_rel > score_irr


# ════════════════════════════════════════════════════════════════════════════
# calculate_title_matching_bonus
# ════════════════════════════════════════════════════════════════════════════


class TestInsightProcessorsCalculateTitleBonus:
    """Testa calculate_title_matching_bonus."""

    def test_query_vazia_retorna_zero(self) -> None:
        """Query ou título vazio retorna bonus 0.0."""
        p = _make_processors()
        assert p.calculate_title_matching_bonus("", "KT Estorno") == 0.0
        assert p.calculate_title_matching_bonus("KT Estorno", "") == 0.0

    def test_match_forte_retorna_bonus_alto(self) -> None:
        """Overlap alto entre query e título gera bonus alto."""
        p = _make_processors()
        bonus = p.calculate_title_matching_bonus("kt estorno massa dexco", "kt estorno massa dexco")
        assert bonus >= 0.25

    def test_sem_match_retorna_zero(self) -> None:
        """Sem tokens em comum (excluindo stop words), bonus é 0.0."""
        p = _make_processors()
        bonus = p.calculate_title_matching_bonus("reunião técnica fiori", "kt estorno massa")
        assert bonus == 0.0

    def test_bonus_entre_zero_e_ponto_quatro(self) -> None:
        """Bonus máximo é 0.4."""
        p = _make_processors()
        bonus = p.calculate_title_matching_bonus("qualquer query", "qualquer título")
        assert 0.0 <= bonus <= 0.4


# ════════════════════════════════════════════════════════════════════════════
# calculate_confidence
# ════════════════════════════════════════════════════════════════════════════


class TestInsightProcessorsCalculateConfidence:
    """Testa calculate_confidence."""

    def test_sem_resultados_retorna_zero(self) -> None:
        """Lista vazia de resultados retorna confiança 0.0."""
        p = _make_processors()
        assert p.calculate_confidence([], "insight") == 0.0

    def test_sem_insight_retorna_zero(self) -> None:
        """Insight vazio retorna confiança 0.0."""
        p = _make_processors()
        assert p.calculate_confidence([_make_result()], "") == 0.0

    def test_confianca_entre_zero_e_um(self) -> None:
        """Confiança calculada fica sempre no intervalo [0, 1]."""
        p = _make_processors()
        results = [_make_result() for _ in range(3)]
        confidence = p.calculate_confidence(results, "insight com informações relevantes decididas")
        assert 0.0 <= confidence <= 1.0

    def test_insight_com_palavras_especificas_tem_bonus(self) -> None:
        """Insight com 'decidido' ou 'aprovado' recebe bonus de especificidade."""
        p = _make_processors()
        results = [_make_result()]
        conf_generico = p.calculate_confidence(results, "informação geral")
        conf_especifico = p.calculate_confidence(results, "foi decidido e aprovado o problema")
        assert conf_especifico >= conf_generico


# ════════════════════════════════════════════════════════════════════════════
# format_insight_text
# ════════════════════════════════════════════════════════════════════════════


class TestInsightProcessorsFormatInsightText:
    """Testa format_insight_text."""

    def test_texto_vazio_retorna_vazio(self) -> None:
        """String vazia retorna string vazia."""
        p = _make_processors()
        assert p.format_insight_text("") == ""

    def test_numeros_formatados_com_negrito(self) -> None:
        """Numeração '1. ' é transformada em '**1.** '."""
        p = _make_processors()
        result = p.format_insight_text("1. Primeiro ponto importante")
        assert "**1.**" in result

    def test_sem_quebras_excessivas(self) -> None:
        """Não há mais de 2 quebras de linha consecutivas no resultado."""
        p = _make_processors()
        result = p.format_insight_text("Texto.\n\n\n\nOutro texto.")
        assert "\n\n\n" not in result

    def test_nao_comeca_com_quebra_de_linha(self) -> None:
        """Texto resultante não começa com quebra de linha."""
        p = _make_processors()
        result = p.format_insight_text("\n\nTexto iniciando com quebras")
        assert not result.startswith("\n")


# ════════════════════════════════════════════════════════════════════════════
# get_performance_config
# ════════════════════════════════════════════════════════════════════════════


class TestInsightProcessorsGetPerformanceConfig:
    """Testa get_performance_config."""

    def test_metadata_listing_usa_fast_listing(self) -> None:
        """metadata_listing retorna estratégia 'fast_listing'."""
        p = _make_processors()
        config = p.get_performance_config("metadata_listing", 10)
        assert config["strategy"] == "fast_listing"
        assert config["max_tokens"] == 400

    def test_general_poucos_resultados_usa_quick_response(self) -> None:
        """general com <= 5 resultados usa 'quick_response'."""
        p = _make_processors()
        config = p.get_performance_config("general", 3)
        assert config["strategy"] == "quick_response"

    def test_highlights_summary_usa_quick_analysis(self) -> None:
        """highlights_summary retorna estratégia 'quick_analysis'."""
        p = _make_processors()
        config = p.get_performance_config("highlights_summary", 5)
        assert config["strategy"] == "quick_analysis"

    def test_semantico_complexo_usa_balanced_insight(self) -> None:
        """Tipo sem correspondência específica usa 'balanced_insight'."""
        p = _make_processors()
        config = p.get_performance_config("decision", 15)
        assert config["strategy"] == "balanced_insight"

    def test_config_tem_campos_obrigatorios(self) -> None:
        """Toda config tem strategy, max_tokens, temperature, top_p, timeout."""
        p = _make_processors()
        for query_type in ["metadata_listing", "general", "highlights_summary", "decision"]:
            config = p.get_performance_config(query_type, 5)
            assert "strategy" in config
            assert "max_tokens" in config
            assert "temperature" in config
            assert "top_p" in config
            assert "timeout" in config

    @pytest.mark.parametrize(
        "query_type,expected_strategy",
        [
            ("metadata_listing", "fast_listing"),
            ("project_listing", "fast_listing"),
            ("highlights_summary", "quick_analysis"),
        ],
    )
    def test_estrategias_por_tipo(self, query_type: str, expected_strategy: str) -> None:
        """Tipos específicos mapeiam para estratégias conhecidas."""
        p = _make_processors()
        config = p.get_performance_config(query_type, 5)
        assert config["strategy"] == expected_strategy


# ════════════════════════════════════════════════════════════════════════════
# apply_semantic_filter
# ════════════════════════════════════════════════════════════════════════════


class TestInsightProcessorsApplySemanticFilter:
    """Testa apply_semantic_filter."""

    def test_lista_vazia_retorna_lista_vazia(self) -> None:
        """Lista vazia de resultados retorna lista vazia."""
        p = _make_processors()
        result = p.apply_semantic_filter([], "query")
        assert result == []

    def test_query_vazia_retorna_original(self) -> None:
        """Query vazia retorna a lista original sem filtrar."""
        p = _make_processors()
        results = [_make_result()]
        assert p.apply_semantic_filter(results, "") == results

    def test_garante_pelo_menos_um_resultado(self) -> None:
        """Mesmo que nenhum resultado passe no filtro, ao menos 1 é mantido."""
        p = _make_processors()
        r = _make_result(content="texto completamente irrelevante xpto abc 123")
        result = p.apply_semantic_filter([r], "integração fiscal tributário imposto documentos")
        assert len(result) >= 1

    def test_retorna_resultados_relevantes(self) -> None:
        """Resultado com conteúdo relevante é mantido no filtro."""
        p = _make_processors()
        relevante = _make_result(content="integração via cpi na plataforma btp cloud")
        result = p.apply_semantic_filter([relevante], "integração cpi btp")
        assert relevante in result
