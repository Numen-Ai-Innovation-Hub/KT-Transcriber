"""
Search CLI - Interface de linha de comando do Search Engine.

Responsabilidades:
- Modo interativo (REPL) para múltiplas consultas
- Modo de consulta única (single_query_mode)
- Ponto de entrada CLI via argparse (main)

Uso:
    uv run python -m src.kt_search.search_engine
    uv run python -m src.kt_search.search_engine --query "PERGUNTA"
"""

import argparse
import sys

from utils.logger_setup import LoggerManager

from .search_engine import SearchEngine
from .search_formatters import print_results

logger = LoggerManager.get_logger(__name__)


def interactive_mode() -> None:
    """Modo interativo — REPL para múltiplas consultas RAG.

    Aceita queries em linguagem natural e exibe resultados formatados.
    Comandos especiais: sair, detalhes, help.
    """
    logger.info("MODO INTERATIVO — Sistema RAG KT Transcriber")
    logger.info("Digite 'sair' para encerrar | 'detalhes' para ativar métricas | 'help' para ajuda")
    logger.info("─" * 60)

    search_engine = SearchEngine(verbose=False)
    show_details = False

    while True:
        try:
            query = input("\n  Pergunta: ").strip()

            if not query:
                continue

            if query.lower() in ("sair", "quit", "exit", "q"):
                logger.info("Até logo!")
                break

            if query.lower() in ("detalhes", "details", "d"):
                show_details = not show_details
                status = "ativados" if show_details else "desativados"
                logger.info(f"  Detalhes técnicos {status}")
                continue

            if query.lower() in ("help", "ajuda", "h"):
                logger.info(
                    "\n"
                    "COMANDOS:\n"
                    "  sair / quit     — Encerrar\n"
                    "  detalhes        — Ativar/desativar métricas técnicas\n"
                    "  help / ajuda    — Esta ajuda\n"
                    "\n"
                    "EXEMPLOS DE CONSULTA:\n"
                    '  "O que temos sobre integrações da Víssimo?"\n'
                    '  "Liste os KTs disponíveis"\n'
                    '  "Quem participou do KT da Arco?"\n'
                    '  "Problemas recentes na Víssimo"\n'
                    '  "onde mencionaram ZEWM0008"'
                )
                continue

            logger.info("Processando através do pipeline RAG...")
            response = search_engine.search(query, show_details=show_details)
            print_results(response, show_details=show_details)

        except KeyboardInterrupt:
            logger.info("\nInterrompido pelo usuário. Até logo!")
            break
        except Exception as e:
            logger.error(f"Erro inesperado: {e}")


def single_query_mode(query: str, verbose: bool = False) -> None:
    """Executa uma consulta única e exibe o resultado.

    Args:
        query: Pergunta em linguagem natural.
        verbose: Se True, exibe métricas técnicas detalhadas.
    """
    search_engine = SearchEngine(verbose=verbose)
    logger.info(f"Executando consulta RAG: '{query}'")
    response = search_engine.search(query, show_details=verbose)
    print_results(response, show_details=verbose)


def main() -> None:
    """Ponto de entrada CLI do search engine.

    Parseia argumentos e roteia para modo interativo ou consulta única.

    Uso:
        uv run python -m src.kt_search.search_engine
        uv run python -m src.kt_search.search_engine --query "PERGUNTA"

    Exemplo:
        uv run python -m src.kt_search.search_engine -q "Liste os KTs disponíveis" --verbose
    """
    parser = argparse.ArgumentParser(
        description="CLI de busca semântica KT Transcriber",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  uv run python -m src.kt_search.search_engine\n"
            '  uv run python -m src.kt_search.search_engine --query "O que temos sobre SAP SD?"\n'
            '  uv run python -m src.kt_search.search_engine -q "Liste os KTs" --verbose\n'
            "\n"
            "Tipos RAG suportados:\n"
            "  SEMANTIC  — Busca por significado/conteúdo\n"
            "  METADATA  — Busca estruturada/listagem\n"
            "  ENTITY    — Busca por entidades específicas\n"
            "  TEMPORAL  — Busca por períodos\n"
            "  CONTENT   — Busca literal no conteúdo\n"
        ),
    )
    parser.add_argument("--query", "-q", type=str, help="Pergunta para consulta direta")
    parser.add_argument("--verbose", "-v", action="store_true", help="Mostrar métricas técnicas do processamento")

    args = parser.parse_args()

    from src.config.startup import initialize_application

    initialize_application()

    try:
        if args.query:
            single_query_mode(args.query, verbose=args.verbose)
        else:
            interactive_mode()
    except KeyboardInterrupt:
        logger.warning("Interrompido pelo usuário (Ctrl+C)")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
