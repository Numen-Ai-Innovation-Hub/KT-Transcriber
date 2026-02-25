"""Pipeline completo de processamento KT — Ingestion + Indexação + Validação.

Orquestra as três fases do sistema KT Transcriber de forma incremental:

Fase 1 — Ingestion:  TL:DV API → JSONs estruturados em data/transcriptions/
Fase 2 — Indexação:  JSONs → ChromaDB em data/vector_db/ (chunks + embeddings + LLM metadata)
Fase 3 — Validação:  ChromaDB → estatísticas e confirmação

Por padrão, opera de forma INCREMENTAL:
    - Ingestion: pula reuniões já salvas em transcriptions/
    - Indexação: pula vídeos cujo meeting_id já está no ChromaDB

Uso:
    uv run python scripts/run_full_pipeline.py                    # Incremental (padrão)
    uv run python scripts/run_full_pipeline.py --force-clean      # Apaga tudo e reprocessa
    uv run python scripts/run_full_pipeline.py --skip-ingestion   # Apenas indexação + validação
    uv run python scripts/run_full_pipeline.py --skip-indexing    # Apenas ingestion
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Garantir que a raiz do projeto está no sys.path para imports de src/ e utils/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.config.startup import initialize_application
from src.services.kt_indexing_service import get_kt_indexing_service
from src.services.kt_ingestion_service import get_kt_ingestion_service
from utils.exception_setup import ApplicationError
from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# RELATÓRIO FINAL
# ════════════════════════════════════════════════════════════════════════════


def _print_summary(
    ingestion_stats: dict[str, Any],
    indexing_stats: dict[str, Any],
    validation_info: dict[str, Any],
    start_time: datetime,
    success: bool,
) -> None:
    """Imprime resumo final do pipeline.

    Args:
        ingestion_stats: Estatísticas da fase de ingestion.
        indexing_stats: Estatísticas da fase de indexação.
        validation_info: Informações do ChromaDB (fase de validação).
        start_time: Horário de início do pipeline.
        success: True se todas as fases concluíram com sucesso.
    """
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    status_label = "CONCLUÍDO COM SUCESSO" if success else "CONCLUÍDO COM FALHAS"

    logger.info("═" * 120)
    logger.info(f"PIPELINE KT — {status_label}")
    logger.info("─" * 120)
    logger.info(f"Duração total:             {duration:.1f}s")
    logger.info("─" * 120)

    if ingestion_stats:
        logger.info("FASE 1 — INGESTION:")
        logger.info(f"  Reuniões na API:          {ingestion_stats.get('meetings_found', 0)}")
        logger.info(f"  Já baixadas (skip):       {ingestion_stats.get('meetings_already_downloaded', 0)}")
        logger.info(f"  Baixadas nesta execução:  {ingestion_stats.get('meetings_downloaded', 0)}")
        logger.info(f"  Incompletas (skip):       {ingestion_stats.get('meetings_skipped_incomplete', 0)}")
        logger.info(f"  Falhas:                   {ingestion_stats.get('meetings_failed', 0)}")
        logger.info("─" * 120)

    if indexing_stats:
        logger.info("FASE 2 — INDEXAÇÃO:")
        logger.info(f"  Já indexados (skip):      {indexing_stats.get('videos_already_indexed', 0)}")
        logger.info(f"  Indexados nesta execução: {indexing_stats.get('videos_indexed', 0)}")
        logger.info(f"  Chunks gerados:           {indexing_stats.get('chunks_indexed', 0)}")
        logger.info(f"  Falhas:                   {indexing_stats.get('videos_failed', 0)}")
        logger.info("─" * 120)

    logger.info("FASE 3 — VALIDAÇÃO:")
    logger.info(f"  Total de documentos:      {validation_info.get('total_documents', 0)}")
    logger.info(f"  Clientes indexados:       {validation_info.get('unique_clients', [])}")
    logger.info("─" * 120)

    all_errors: list[str] = ingestion_stats.get("errors", []) + indexing_stats.get("errors", [])
    if all_errors:
        logger.warning(f"Erros encontrados ({len(all_errors)}):")
        for err in all_errors:
            logger.warning(f"  • {err}")

    logger.info("═" * 120)


# ════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA
# ════════════════════════════════════════════════════════════════════════════


def main() -> None:
    """Ponto de entrada do pipeline KT.

    Parseia argumentos de linha de comando e executa o pipeline completo.
    """
    parser = argparse.ArgumentParser(
        description="Pipeline completo de processamento KT Transcriber",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  uv run python scripts/run_full_pipeline.py\n"
            "  uv run python scripts/run_full_pipeline.py --force-clean\n"
            "  uv run python scripts/run_full_pipeline.py --skip-ingestion\n"
            "  uv run python scripts/run_full_pipeline.py --skip-indexing\n"
        ),
    )
    parser.add_argument(
        "--force-clean",
        action="store_true",
        help="ATENCAO: Apaga TODOS os dados (transcriptions/ + vector_db/) e reprocessa do zero",
    )
    parser.add_argument(
        "--skip-ingestion",
        action="store_true",
        help="Pula a Fase 1 (download do TL:DV) — usa JSONs já existentes em transcriptions/",
    )
    parser.add_argument(
        "--skip-indexing",
        action="store_true",
        help="Pula a Fase 2 (indexação no ChromaDB) — executa apenas ingestion + validação",
    )
    args = parser.parse_args()

    if args.skip_ingestion and args.skip_indexing:
        parser.error("Não é possível usar --skip-ingestion e --skip-indexing ao mesmo tempo")

    initialize_application()

    ingestion_svc = get_kt_ingestion_service()
    indexing_svc = get_kt_indexing_service()

    start_time = datetime.now()
    success = True
    ingestion_stats: dict[str, Any] = {}
    indexing_stats: dict[str, Any] = {}
    validation_info: dict[str, Any] = {}

    logger.info("═" * 120)
    logger.info("KT TRANSCRIBER — PIPELINE COMPLETO")
    logger.info(f"Início: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    if args.force_clean:
        logger.warning("Modo: FORCE CLEAN — todos os dados serão apagados e reprocessados")
    else:
        logger.info("Modo: INCREMENTAL — apenas dados novos serão processados")
    logger.info("═" * 120)

    if args.force_clean:
        ingestion_svc.force_clean()
        indexing_svc.force_clean()

    # ────────────────────────────────────────────────────────────────────────
    # FASE 1 — INGESTION
    # ────────────────────────────────────────────────────────────────────────
    if not args.skip_ingestion:
        logger.info("═" * 120)
        logger.info("FASE 1 — INGESTION: Capturando reuniões do TL:DV")
        logger.info("═" * 120)
        try:
            ingestion_stats = ingestion_svc.run_ingestion()
        except ApplicationError as e:
            logger.error(f"Fase 1 abortada: {e.message}")
            success = False
        except Exception as e:
            logger.error(f"Erro inesperado na Fase 1: {e}")
            success = False
    else:
        logger.info("Fase 1 (Ingestion) pulada via --skip-ingestion")

    # ────────────────────────────────────────────────────────────────────────
    # FASE 2 — INDEXAÇÃO
    # ────────────────────────────────────────────────────────────────────────
    if not args.skip_indexing:
        logger.info("═" * 120)
        logger.info("FASE 2 — INDEXAÇÃO: Processando JSONs para ChromaDB")
        logger.info("═" * 120)
        try:
            indexing_stats = indexing_svc.run_indexing()
        except ApplicationError as e:
            logger.error(f"Fase 2 abortada: {e.message}")
            success = False
        except Exception as e:
            logger.error(f"Erro inesperado na Fase 2: {e}")
            success = False
    else:
        logger.info("Fase 2 (Indexação) pulada via --skip-indexing")

    # ────────────────────────────────────────────────────────────────────────
    # FASE 3 — VALIDAÇÃO
    # ────────────────────────────────────────────────────────────────────────
    logger.info("═" * 120)
    logger.info("FASE 3 — VALIDAÇÃO: Verificando estado do ChromaDB")
    logger.info("═" * 120)
    try:
        validation_info = indexing_svc.get_status()
        if not validation_info.get("total_documents"):
            logger.warning("ChromaDB existe mas não contém documentos")
            success = False
    except ApplicationError as e:
        logger.error(f"Fase 3 abortada: {e.message}")
        success = False
    except Exception as e:
        logger.error(f"Erro inesperado na Fase 3: {e}")
        success = False

    _print_summary(ingestion_stats, indexing_stats, validation_info, start_time, success)

    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("Pipeline interrompido pelo usuário (Ctrl+C)")
        raise SystemExit(1) from None
