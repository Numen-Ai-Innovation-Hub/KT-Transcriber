"""Testes unitários para search_formatters — formatação de SearchResponse."""

from typing import Any
from unittest.mock import MagicMock, patch

# ════════════════════════════════════════════════════════════════════════════
# HELPERS INLINE
# ════════════════════════════════════════════════════════════════════════════


def make_response(
    *,
    success: bool = True,
    answer: str = "Resposta de teste gerada pelo LLM.",
    confidence: float = 0.85,
    contexts: list[dict[str, Any]] | None = None,
    summary_stats: dict[str, Any] | None = None,
    query_type: str = "SEMANTIC",
    processing_time: float = 0.5,
    error_message: str | None = None,
) -> Any:
    """Cria SearchResponse com valores padrão para testes.

    Não requer ChromaDB nem OpenAI — é uma dataclass simples.
    """
    from src.kt_search.search_engine import SearchResponse

    return SearchResponse(
        intelligent_response={
            "answer": answer,
            "confidence": confidence,
            "processing_time": 0.1,
            "details": "",
        },
        contexts=contexts if contexts is not None else [],
        summary_stats=summary_stats if summary_stats is not None else {
            "chunks_selected": 3,
            "selection_strategy": "quality_diversity",
            "total_chunks_found": 10,
            "clients_involved": ["DEXCO"],
            "quality_threshold_met": True,
        },
        query_type=query_type,
        processing_time=processing_time,
        success=success,
        error_message=error_message,
    )


def make_context(
    *,
    video_name: str = "KT Finance",
    speaker: str = "Ana",
    timestamp: str = "00:05",
    content: str = "Texto de contexto relevante.",
    original_url: str = "",
    client: str = "DEXCO",
    rank: int = 1,
    quality_score: float = 0.9,
    similarity_score: float = 0.8,
) -> dict[str, Any]:
    """Cria contexto simulado compatível com o formato real do SearchEngine."""
    return {
        "rank": rank,
        "video_name": video_name,
        "speaker": speaker,
        "timestamp": timestamp,
        "content": content,
        "original_url": original_url,
        "client": client,
        "quality_score": quality_score,
        "similarity_score": similarity_score,
    }


# ════════════════════════════════════════════════════════════════════════════
# formatar_resultado_teams
# ════════════════════════════════════════════════════════════════════════════


class TestFormataResultadoTeams:
    """Testa formatar_resultado_teams — sem I/O externo (SearchResponse é dataclass)."""

    def test_retorna_string(self) -> None:
        """Função retorna str."""
        from src.kt_search.search_formatters import formatar_resultado_teams

        result = formatar_resultado_teams(make_response(), "Pergunta de teste")
        assert isinstance(result, str)

    def test_contem_pergunta_original(self) -> None:
        """Saída contém a pergunta passada como argumento."""
        from src.kt_search.search_formatters import formatar_resultado_teams

        result = formatar_resultado_teams(make_response(), "Como funciona o módulo FI?")
        assert "Como funciona o módulo FI?" in result

    def test_contem_cabecalho_transcricao_kt(self) -> None:
        """Saída inclui o cabeçalho padrão de Transcrição de KT."""
        from src.kt_search.search_formatters import formatar_resultado_teams

        result = formatar_resultado_teams(make_response(), "pergunta")
        assert "Transcrição de KT" in result

    def test_insight_presente_aparece_na_saida(self) -> None:
        """Quando answer está preenchido, seção INSIGHTS aparece com o conteúdo."""
        from src.kt_search.search_formatters import formatar_resultado_teams

        result = formatar_resultado_teams(
            make_response(answer="O módulo FI é responsável por finanças."), "pergunta"
        )
        assert "INSIGHTS" in result
        assert "O módulo FI" in result

    def test_sem_answer_nao_exibe_secao_insights(self) -> None:
        """Com answer vazio, seção INSIGHTS não aparece na saída."""
        from src.kt_search.search_formatters import formatar_resultado_teams

        result = formatar_resultado_teams(make_response(answer=""), "pergunta")
        assert "INSIGHTS" not in result

    def test_contextos_listados_em_secao_fontes(self) -> None:
        """Contextos são listados na seção FONTES ENCONTRADAS."""
        from src.kt_search.search_formatters import formatar_resultado_teams

        ctx = make_context(video_name="KT SD")
        result = formatar_resultado_teams(make_response(contexts=[ctx]), "pergunta")
        assert "FONTES ENCONTRADAS" in result
        assert "KT SD" in result

    def test_sem_contextos_sem_secao_fontes(self) -> None:
        """Sem contextos, seção FONTES ENCONTRADAS não aparece."""
        from src.kt_search.search_formatters import formatar_resultado_teams

        result = formatar_resultado_teams(make_response(contexts=[]), "pergunta")
        assert "FONTES ENCONTRADAS" not in result

    def test_metricas_aparecem_com_summary_stats(self) -> None:
        """Seção MÉTRICAS DE BUSCA é incluída quando summary_stats não está vazio."""
        from src.kt_search.search_formatters import formatar_resultado_teams

        result = formatar_resultado_teams(
            make_response(summary_stats={"chunks_selected": 5}), "pergunta"
        )
        assert "MÉTRICAS DE BUSCA" in result

    def test_link_original_url_aparece_no_resultado(self) -> None:
        """Link TL:DV é incluído quando original_url está preenchido."""
        from src.kt_search.search_formatters import formatar_resultado_teams

        ctx = make_context(original_url="https://tldv.io/video123")
        result = formatar_resultado_teams(make_response(contexts=[ctx]), "pergunta")
        assert "https://tldv.io/video123" in result

    def test_processamento_time_aparece_nas_metricas(self) -> None:
        """processing_time do SearchResponse aparece na seção de métricas."""
        from src.kt_search.search_formatters import formatar_resultado_teams

        result = formatar_resultado_teams(
            make_response(processing_time=1.23, summary_stats={"chunks_selected": 2}), "pergunta"
        )
        assert "1.23" in result

    def test_multiplos_contextos_numerados(self) -> None:
        """Múltiplos contextos aparecem com numeração sequencial."""
        from src.kt_search.search_formatters import formatar_resultado_teams

        ctx1 = make_context(video_name="KT EWM", rank=1)
        ctx2 = make_context(video_name="KT FI", rank=2)
        result = formatar_resultado_teams(make_response(contexts=[ctx1, ctx2]), "pergunta")
        assert "KT EWM" in result
        assert "KT FI" in result
        assert "1." in result
        assert "2." in result


# ════════════════════════════════════════════════════════════════════════════
# main_teams
# ════════════════════════════════════════════════════════════════════════════


class TestMainTeams:
    """Testa main_teams — entry point do Teams Gateway."""

    def test_payload_vazio_retorna_chave_erro(self) -> None:
        """Payload sem 'text' retorna dict com chave 'erro'."""
        from src.kt_search.search_formatters import main_teams

        result = main_teams({})
        assert "erro" in result
        assert "mensagem" in result

    def test_text_vazio_retorna_chave_erro(self) -> None:
        """Payload com text vazio (só espaços) retorna dict com 'erro'."""
        from src.kt_search.search_formatters import main_teams

        result = main_teams({"text": "   "})
        assert "erro" in result

    def test_text_none_equivalente_a_vazio(self) -> None:
        """Payload sem chave 'text' retorna erro (mesmo comportamento que text vazio)."""
        from src.kt_search.search_formatters import main_teams

        result = main_teams({"text": ""})
        assert "erro" in result

    def test_busca_sucesso_retorna_success_true(self) -> None:
        """Busca bem-sucedida retorna {'success': True, 'mensagem': ...}."""
        from src.kt_search.search_formatters import main_teams

        mock_response = make_response(success=True, answer="Resposta ok.")
        with patch("src.kt_search.search_formatters.SearchEngine") as mock_se_class:
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine
            mock_engine.search.return_value = mock_response

            result = main_teams({"text": "Pergunta válida sobre módulo FI"})

        assert result.get("success") is True
        assert "mensagem" in result
        assert isinstance(result["mensagem"], str)

    def test_busca_falha_retorna_chave_erro(self) -> None:
        """Busca com success=False retorna dict com 'erro'."""
        from src.kt_search.search_formatters import main_teams

        mock_response = make_response(success=False, error_message="Nenhum resultado encontrado")
        with patch("src.kt_search.search_formatters.SearchEngine") as mock_se_class:
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine
            mock_engine.search.return_value = mock_response

            result = main_teams({"text": "Pergunta sem resultados"})

        assert "erro" in result
        assert "mensagem" in result

    def test_busca_falha_mensagem_contem_erro_original(self) -> None:
        """A mensagem de erro reflete o error_message da SearchResponse."""
        from src.kt_search.search_formatters import main_teams

        mock_response = make_response(success=False, error_message="ChromaDB indisponível")
        with patch("src.kt_search.search_formatters.SearchEngine") as mock_se_class:
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine
            mock_engine.search.return_value = mock_response

            result = main_teams({"text": "qualquer pergunta"})

        assert "ChromaDB indisponível" in result.get("mensagem", "")

    def test_excecao_interna_retorna_erro(self) -> None:
        """Exceção inesperada durante inicialização do SearchEngine retorna 'erro'."""
        from src.kt_search.search_formatters import main_teams

        with patch("src.kt_search.search_formatters.SearchEngine") as mock_se_class:
            mock_se_class.side_effect = RuntimeError("Falha catastrófica")

            result = main_teams({"text": "Pergunta qualquer"})

        assert "erro" in result
        assert "mensagem" in result

    def test_search_chamado_com_pergunta_correta(self) -> None:
        """engine.search é invocado com a pergunta extraída do payload."""
        from src.kt_search.search_formatters import main_teams

        mock_response = make_response(success=True)
        with patch("src.kt_search.search_formatters.SearchEngine") as mock_se_class:
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine
            mock_engine.search.return_value = mock_response

            main_teams({"text": "Pergunta específica"})

        mock_engine.search.assert_called_once_with("Pergunta específica", show_details=False)


# ════════════════════════════════════════════════════════════════════════════
# print_results
# ════════════════════════════════════════════════════════════════════════════


class TestPrintResults:
    """Testa print_results — exibição de resultados no terminal via logger."""

    def test_success_false_usa_logger_info(self) -> None:
        """Quando success=False, logger.info é chamado (exibe mensagem de erro)."""
        from src.kt_search.search_formatters import print_results

        response = make_response(success=False, error_message="Sem resultados")
        with patch("src.kt_search.search_formatters.logger") as mock_logger:
            print_results(response)

        assert mock_logger.info.called

    def test_success_false_retorna_cedo(self) -> None:
        """Com success=False, logger.debug NÃO é chamado (retorno antecipado)."""
        from src.kt_search.search_formatters import print_results

        response = make_response(success=False, error_message="Sem resultados")
        with patch("src.kt_search.search_formatters.logger") as mock_logger:
            print_results(response)

        assert not mock_logger.debug.called

    def test_success_true_usa_logger_info(self) -> None:
        """Quando success=True, logger.info é chamado com conteúdo da resposta."""
        from src.kt_search.search_formatters import print_results

        response = make_response(success=True, answer="Resposta válida de teste.")
        with patch("src.kt_search.search_formatters.logger") as mock_logger:
            print_results(response)

        assert mock_logger.info.called

    def test_show_details_false_nao_chama_debug(self) -> None:
        """Com show_details=False, logger.debug não é chamado."""
        from src.kt_search.search_formatters import print_results

        response = make_response(success=True, contexts=[make_context()])
        with patch("src.kt_search.search_formatters.logger") as mock_logger:
            print_results(response, show_details=False)

        assert not mock_logger.debug.called

    def test_show_details_true_chama_debug(self) -> None:
        """Com show_details=True, logger.debug é chamado para exibir qualidade dos chunks."""
        from src.kt_search.search_formatters import print_results

        response = make_response(
            success=True,
            contexts=[make_context(quality_score=0.9, similarity_score=0.8)],
        )
        with patch("src.kt_search.search_formatters.logger") as mock_logger:
            print_results(response, show_details=True)

        assert mock_logger.debug.called

    def test_contextos_vazios_exibe_mensagem_ausencia(self) -> None:
        """Sem contextos, logger recebe mensagem indicando ausência de contextos."""
        from src.kt_search.search_formatters import print_results

        response = make_response(success=True, contexts=[])
        with patch("src.kt_search.search_formatters.logger") as mock_logger:
            print_results(response)

        calls_text = " ".join(str(c) for c in mock_logger.info.call_args_list)
        assert "contexto" in calls_text.lower()

    def test_query_type_metadata_usa_rank(self) -> None:
        """Com query_type='METADATA', logger.info é chamado (exibe rank e client_info)."""
        from src.kt_search.search_formatters import print_results

        ctx = make_context(content="", timestamp="")
        response = make_response(success=True, query_type="METADATA", contexts=[ctx])
        with patch("src.kt_search.search_formatters.logger") as mock_logger:
            print_results(response)

        assert mock_logger.info.called

    def test_show_details_true_exibe_metricas(self) -> None:
        """Com show_details=True, seção de métricas detalhadas é logada."""
        from src.kt_search.search_formatters import print_results

        response = make_response(success=True)
        with patch("src.kt_search.search_formatters.logger") as mock_logger:
            print_results(response, show_details=True)

        calls_text = " ".join(str(c) for c in mock_logger.info.call_args_list)
        assert "MÉTRICAS" in calls_text or "Tempo" in calls_text or "Confiança" in calls_text

    def test_contexto_com_original_url_exibe_link(self) -> None:
        """Contexto com original_url inclui o link na saída do logger."""
        from src.kt_search.search_formatters import print_results

        ctx = make_context(original_url="https://tldv.io/abc")
        response = make_response(success=True, contexts=[ctx])
        with patch("src.kt_search.search_formatters.logger") as mock_logger:
            print_results(response)

        calls_text = " ".join(str(c) for c in mock_logger.info.call_args_list)
        assert "https://tldv.io/abc" in calls_text


# ════════════════════════════════════════════════════════════════════════════
# search_kt_knowledge e quick_search
# ════════════════════════════════════════════════════════════════════════════


class TestConvenienceFunctions:
    """Testa search_kt_knowledge e quick_search — instanciam SearchEngine internamente."""

    def test_search_kt_knowledge_retorna_search_response(self) -> None:
        """search_kt_knowledge retorna objeto SearchResponse via SearchEngine."""
        from src.kt_search.search_engine import SearchResponse
        from src.kt_search.search_formatters import search_kt_knowledge

        mock_response = make_response()
        with patch("src.kt_search.search_formatters.SearchEngine") as mock_se_class:
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine
            mock_engine.search.return_value = mock_response

            result = search_kt_knowledge("Pergunta de teste")

        assert isinstance(result, SearchResponse)
        mock_engine.search.assert_called_once_with("Pergunta de teste")

    def test_search_kt_knowledge_instancia_search_engine(self) -> None:
        """search_kt_knowledge instancia SearchEngine sem argumentos extras."""
        from src.kt_search.search_formatters import search_kt_knowledge

        mock_response = make_response()
        with patch("src.kt_search.search_formatters.SearchEngine") as mock_se_class:
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine
            mock_engine.search.return_value = mock_response

            search_kt_knowledge("qualquer query")

        mock_se_class.assert_called_once_with()

    def test_quick_search_retorna_dict(self) -> None:
        """quick_search retorna dict (intelligent_response da SearchResponse)."""
        from src.kt_search.search_formatters import quick_search

        mock_response = make_response(answer="Resposta rápida.")
        with patch("src.kt_search.search_formatters.SearchEngine") as mock_se_class:
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine
            mock_engine.search.return_value = mock_response

            result = quick_search("Pergunta rápida")

        assert isinstance(result, dict)

    def test_quick_search_retorna_intelligent_response_com_answer(self) -> None:
        """quick_search retorna o campo intelligent_response contendo 'answer'."""
        from src.kt_search.search_formatters import quick_search

        mock_response = make_response(answer="Apenas o answer.")
        with patch("src.kt_search.search_formatters.SearchEngine") as mock_se_class:
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine
            mock_engine.search.return_value = mock_response

            result = quick_search("Pergunta rápida")

        assert result.get("answer") == "Apenas o answer."
