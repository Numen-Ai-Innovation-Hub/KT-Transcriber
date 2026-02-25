"""Testes unitários para search_cli — interface de linha de comando."""

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ════════════════════════════════════════════════════════════════════════════
# HELPERS INLINE
# ════════════════════════════════════════════════════════════════════════════


def make_response(success: bool = True, answer: str = "Resposta de teste.") -> Any:
    """Cria SearchResponse mínimo para testes de CLI."""
    from src.kt_search.search_engine import SearchResponse

    return SearchResponse(
        intelligent_response={"answer": answer, "confidence": 0.8, "processing_time": 0.1},
        contexts=[],
        summary_stats={},
        query_type="SEMANTIC",
        processing_time=0.3,
        success=success,
        error_message=None,
    )


# ════════════════════════════════════════════════════════════════════════════
# interactive_mode
# ════════════════════════════════════════════════════════════════════════════


class TestInteractiveMode:
    """Testa o REPL interativo — SearchEngine mockado, input controlado."""

    def test_sair_encerra_loop_sem_busca(self) -> None:
        """Input 'sair' encerra o loop sem acionar engine.search."""
        with (
            patch("src.kt_search.search_cli.SearchEngine") as mock_se_class,
            patch("src.kt_search.search_cli.print_results"),
            patch("builtins.input", side_effect=["sair"]),
        ):
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine

            from src.kt_search.search_cli import interactive_mode

            interactive_mode()

        mock_engine.search.assert_not_called()

    def test_quit_encerra_loop(self) -> None:
        """Input 'quit' também encerra o loop."""
        with (
            patch("src.kt_search.search_cli.SearchEngine") as mock_se_class,
            patch("src.kt_search.search_cli.print_results"),
            patch("builtins.input", side_effect=["quit"]),
        ):
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine

            from src.kt_search.search_cli import interactive_mode

            interactive_mode()

        mock_engine.search.assert_not_called()

    def test_exit_encerra_loop(self) -> None:
        """Input 'exit' também encerra o loop."""
        with (
            patch("src.kt_search.search_cli.SearchEngine") as mock_se_class,
            patch("src.kt_search.search_cli.print_results"),
            patch("builtins.input", side_effect=["exit"]),
        ):
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine

            from src.kt_search.search_cli import interactive_mode

            interactive_mode()

        mock_engine.search.assert_not_called()

    def test_query_valida_chama_search(self) -> None:
        """Query real chama engine.search e repassa para print_results."""
        mock_resp = make_response()
        with (
            patch("src.kt_search.search_cli.SearchEngine") as mock_se_class,
            patch("src.kt_search.search_cli.print_results") as mock_print,
            patch("builtins.input", side_effect=["Transações do módulo FI", "sair"]),
        ):
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine
            mock_engine.search.return_value = mock_resp

            from src.kt_search.search_cli import interactive_mode

            interactive_mode()

        mock_engine.search.assert_called_once_with("Transações do módulo FI", show_details=False)
        mock_print.assert_called_once_with(mock_resp, show_details=False)

    def test_detalhes_ativa_show_details_para_proxima_query(self) -> None:
        """Input 'detalhes' alterna show_details para True na próxima consulta."""
        mock_resp = make_response()
        with (
            patch("src.kt_search.search_cli.SearchEngine") as mock_se_class,
            patch("src.kt_search.search_cli.print_results") as mock_print,
            patch("builtins.input", side_effect=["detalhes", "Consulta com detalhes", "sair"]),
        ):
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine
            mock_engine.search.return_value = mock_resp

            from src.kt_search.search_cli import interactive_mode

            interactive_mode()

        mock_engine.search.assert_called_once_with("Consulta com detalhes", show_details=True)
        mock_print.assert_called_once_with(mock_resp, show_details=True)

    def test_detalhes_duplo_desativa_show_details(self) -> None:
        """Dois inputs 'detalhes' consecutivos retornam show_details para False."""
        mock_resp = make_response()
        with (
            patch("src.kt_search.search_cli.SearchEngine") as mock_se_class,
            patch("src.kt_search.search_cli.print_results") as mock_print,
            patch("builtins.input", side_effect=["detalhes", "detalhes", "Consulta normal", "sair"]),
        ):
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine
            mock_engine.search.return_value = mock_resp

            from src.kt_search.search_cli import interactive_mode

            interactive_mode()

        mock_engine.search.assert_called_once_with("Consulta normal", show_details=False)
        mock_print.assert_called_once_with(mock_resp, show_details=False)

    def test_help_nao_aciona_busca(self) -> None:
        """Input 'help' exibe ajuda mas não chama engine.search."""
        with (
            patch("src.kt_search.search_cli.SearchEngine") as mock_se_class,
            patch("src.kt_search.search_cli.print_results"),
            patch("builtins.input", side_effect=["help", "sair"]),
        ):
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine

            from src.kt_search.search_cli import interactive_mode

            interactive_mode()

        mock_engine.search.assert_not_called()

    def test_ajuda_nao_aciona_busca(self) -> None:
        """Input 'ajuda' tem o mesmo comportamento de 'help'."""
        with (
            patch("src.kt_search.search_cli.SearchEngine") as mock_se_class,
            patch("src.kt_search.search_cli.print_results"),
            patch("builtins.input", side_effect=["ajuda", "sair"]),
        ):
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine

            from src.kt_search.search_cli import interactive_mode

            interactive_mode()

        mock_engine.search.assert_not_called()

    def test_query_vazia_continua_sem_busca(self) -> None:
        """String vazia não aciona busca — loop prossegue para próxima entrada."""
        with (
            patch("src.kt_search.search_cli.SearchEngine") as mock_se_class,
            patch("src.kt_search.search_cli.print_results"),
            patch("builtins.input", side_effect=["", "sair"]),
        ):
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine

            from src.kt_search.search_cli import interactive_mode

            interactive_mode()

        mock_engine.search.assert_not_called()

    def test_keyboard_interrupt_encerra_graciosamente(self) -> None:
        """KeyboardInterrupt durante input encerra o modo interativo sem propagar exceção."""
        with (
            patch("src.kt_search.search_cli.SearchEngine"),
            patch("src.kt_search.search_cli.print_results"),
            patch("builtins.input", side_effect=KeyboardInterrupt),
        ):
            from src.kt_search.search_cli import interactive_mode

            # Não deve propagar — tratado internamente
            interactive_mode()

    def test_engine_instanciado_com_verbose_false(self) -> None:
        """SearchEngine é instanciado com verbose=False no modo interativo."""
        with (
            patch("src.kt_search.search_cli.SearchEngine") as mock_se_class,
            patch("src.kt_search.search_cli.print_results"),
            patch("builtins.input", side_effect=["sair"]),
        ):
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine

            from src.kt_search.search_cli import interactive_mode

            interactive_mode()

        mock_se_class.assert_called_once_with(verbose=False)

    def test_multiplas_queries_processadas_sequencialmente(self) -> None:
        """Duas queries seguidas são processadas e exibidas na ordem correta."""
        mock_resp = make_response()
        with (
            patch("src.kt_search.search_cli.SearchEngine") as mock_se_class,
            patch("src.kt_search.search_cli.print_results") as mock_print,
            patch("builtins.input", side_effect=["primeira query", "segunda query", "sair"]),
        ):
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine
            mock_engine.search.return_value = mock_resp

            from src.kt_search.search_cli import interactive_mode

            interactive_mode()

        assert mock_engine.search.call_count == 2
        assert mock_print.call_count == 2
        mock_engine.search.assert_any_call("primeira query", show_details=False)
        mock_engine.search.assert_any_call("segunda query", show_details=False)


# ════════════════════════════════════════════════════════════════════════════
# single_query_mode
# ════════════════════════════════════════════════════════════════════════════


class TestSingleQueryMode:
    """Testa execução de consulta única."""

    def test_executa_busca_e_chama_print_results(self) -> None:
        """single_query_mode chama engine.search e print_results com a query fornecida."""
        mock_resp = make_response()
        with (
            patch("src.kt_search.search_cli.SearchEngine") as mock_se_class,
            patch("src.kt_search.search_cli.print_results") as mock_print,
        ):
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine
            mock_engine.search.return_value = mock_resp

            from src.kt_search.search_cli import single_query_mode

            single_query_mode("Módulos SAP disponíveis")

        mock_engine.search.assert_called_once_with("Módulos SAP disponíveis", show_details=False)
        mock_print.assert_called_once_with(mock_resp, show_details=False)

    def test_verbose_false_usa_show_details_false(self) -> None:
        """verbose=False (padrão) propaga show_details=False para search e print_results."""
        mock_resp = make_response()
        with (
            patch("src.kt_search.search_cli.SearchEngine") as mock_se_class,
            patch("src.kt_search.search_cli.print_results") as mock_print,
        ):
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine
            mock_engine.search.return_value = mock_resp

            from src.kt_search.search_cli import single_query_mode

            single_query_mode("consulta", verbose=False)

        mock_engine.search.assert_called_once_with("consulta", show_details=False)
        mock_print.assert_called_once_with(mock_resp, show_details=False)

    def test_verbose_true_propaga_show_details(self) -> None:
        """verbose=True propaga show_details=True para engine.search e print_results."""
        mock_resp = make_response()
        with (
            patch("src.kt_search.search_cli.SearchEngine") as mock_se_class,
            patch("src.kt_search.search_cli.print_results") as mock_print,
        ):
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine
            mock_engine.search.return_value = mock_resp

            from src.kt_search.search_cli import single_query_mode

            single_query_mode("Módulos SAP", verbose=True)

        mock_engine.search.assert_called_once_with("Módulos SAP", show_details=True)
        mock_print.assert_called_once_with(mock_resp, show_details=True)

    def test_engine_instanciado_com_verbose_correto(self) -> None:
        """SearchEngine é instanciado com o mesmo valor de verbose recebido."""
        mock_resp = make_response()
        with (
            patch("src.kt_search.search_cli.SearchEngine") as mock_se_class,
            patch("src.kt_search.search_cli.print_results"),
        ):
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine
            mock_engine.search.return_value = mock_resp

            from src.kt_search.search_cli import single_query_mode

            single_query_mode("query", verbose=True)

        mock_se_class.assert_called_once_with(verbose=True)

    def test_engine_instanciado_com_verbose_false_por_padrao(self) -> None:
        """Sem verbose, SearchEngine é instanciado com verbose=False."""
        mock_resp = make_response()
        with (
            patch("src.kt_search.search_cli.SearchEngine") as mock_se_class,
            patch("src.kt_search.search_cli.print_results"),
        ):
            mock_engine = MagicMock()
            mock_se_class.return_value = mock_engine
            mock_engine.search.return_value = mock_resp

            from src.kt_search.search_cli import single_query_mode

            single_query_mode("query")

        mock_se_class.assert_called_once_with(verbose=False)


# ════════════════════════════════════════════════════════════════════════════
# main — ponto de entrada CLI
# ════════════════════════════════════════════════════════════════════════════


class TestMain:
    """Testa o ponto de entrada CLI (main) — argparse + roteamento."""

    def test_query_arg_chama_single_query_mode(self) -> None:
        """--query redireciona para single_query_mode com a query fornecida."""
        with (
            patch("src.kt_search.search_cli.single_query_mode") as mock_single,
            patch("src.kt_search.search_cli.interactive_mode") as mock_interactive,
            patch.dict(sys.modules, {"src.config.startup": MagicMock()}),
            patch.object(sys, "argv", ["prog", "--query", "Pergunta via CLI"]),
        ):
            from src.kt_search.search_cli import main

            main()

        mock_single.assert_called_once_with("Pergunta via CLI", verbose=False)
        mock_interactive.assert_not_called()

    def test_flag_q_chama_single_query_mode(self) -> None:
        """Alias -q funciona igual a --query."""
        with (
            patch("src.kt_search.search_cli.single_query_mode") as mock_single,
            patch("src.kt_search.search_cli.interactive_mode"),
            patch.dict(sys.modules, {"src.config.startup": MagicMock()}),
            patch.object(sys, "argv", ["prog", "-q", "Alias curto"]),
        ):
            from src.kt_search.search_cli import main

            main()

        mock_single.assert_called_once_with("Alias curto", verbose=False)

    def test_sem_query_chama_interactive_mode(self) -> None:
        """Sem --query, redireciona para interactive_mode."""
        with (
            patch("src.kt_search.search_cli.single_query_mode") as mock_single,
            patch("src.kt_search.search_cli.interactive_mode") as mock_interactive,
            patch.dict(sys.modules, {"src.config.startup": MagicMock()}),
            patch.object(sys, "argv", ["prog"]),
        ):
            from src.kt_search.search_cli import main

            main()

        mock_interactive.assert_called_once()
        mock_single.assert_not_called()

    def test_verbose_flag_repassa_para_single_mode(self) -> None:
        """--verbose propaga verbose=True para single_query_mode."""
        with (
            patch("src.kt_search.search_cli.single_query_mode") as mock_single,
            patch("src.kt_search.search_cli.interactive_mode"),
            patch.dict(sys.modules, {"src.config.startup": MagicMock()}),
            patch.object(sys, "argv", ["prog", "-q", "consulta", "--verbose"]),
        ):
            from src.kt_search.search_cli import main

            main()

        mock_single.assert_called_once_with("consulta", verbose=True)

    def test_flag_v_equivale_a_verbose(self) -> None:
        """Alias -v equivale a --verbose."""
        with (
            patch("src.kt_search.search_cli.single_query_mode") as mock_single,
            patch("src.kt_search.search_cli.interactive_mode"),
            patch.dict(sys.modules, {"src.config.startup": MagicMock()}),
            patch.object(sys, "argv", ["prog", "-q", "query", "-v"]),
        ):
            from src.kt_search.search_cli import main

            main()

        mock_single.assert_called_once_with("query", verbose=True)

    def test_keyboard_interrupt_em_interactive_causa_sys_exit_1(self) -> None:
        """KeyboardInterrupt propagado para main() causa sys.exit(1)."""
        with (
            patch("src.kt_search.search_cli.single_query_mode"),
            patch("src.kt_search.search_cli.interactive_mode", side_effect=KeyboardInterrupt),
            patch.dict(sys.modules, {"src.config.startup": MagicMock()}),
            patch.object(sys, "argv", ["prog"]),
        ):
            from src.kt_search.search_cli import main

            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1

    def test_excecao_generica_em_interactive_causa_sys_exit_1(self) -> None:
        """Exceção inesperada propagada para main() causa sys.exit(1)."""
        with (
            patch("src.kt_search.search_cli.single_query_mode"),
            patch("src.kt_search.search_cli.interactive_mode", side_effect=RuntimeError("Boom")),
            patch.dict(sys.modules, {"src.config.startup": MagicMock()}),
            patch.object(sys, "argv", ["prog"]),
        ):
            from src.kt_search.search_cli import main

            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1

    def test_initialize_application_e_chamada(self) -> None:
        """initialize_application é invocada uma vez durante main()."""
        mock_startup = MagicMock()
        with (
            patch("src.kt_search.search_cli.single_query_mode"),
            patch("src.kt_search.search_cli.interactive_mode"),
            patch.dict(sys.modules, {"src.config.startup": mock_startup}),
            patch.object(sys, "argv", ["prog"]),
        ):
            from src.kt_search.search_cli import main

            main()

        mock_startup.initialize_application.assert_called_once()
