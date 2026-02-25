"""Pipeline com seleção interativa de reuniões KT.

Apresenta a lista completa de reuniões disponíveis no TL:DV e permite
ao usuário selecionar quais deseja baixar e indexar. Útil para controlar
exatamente quais vídeos entram na base de dados.

Diferença em relação a run_full_pipeline.py:
    A Fase 1 (Ingestion) é substituída por um fluxo interativo:
    1. Lista todas as reuniões da conta TL:DV com status e nome
    2. Usuário digita os números das reuniões desejadas
    3. Confirmação antes de iniciar o download
    As Fases 2 (Indexação) e 3 (Validação) são idênticas ao pipeline completo.

Uso:
    uv run python scripts/run_select_pipeline.py
    uv run python scripts/run_select_pipeline.py --force-clean
    uv run python scripts/run_select_pipeline.py --skip-indexing

Exemplo:
    uv run python scripts/run_select_pipeline.py
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Garantir que a raiz do projeto está no sys.path para imports de src/, utils/ e scripts/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.run_full_pipeline import _print_summary
from src.config.settings import DIRECTORY_PATHS, TLDV_API_KEY
from src.config.startup import initialize_application
from src.kt_ingestion.json_consolidator import JSONConsolidator
from src.kt_ingestion.smart_processor import SmartMeetingProcessor
from src.kt_ingestion.tldv_client import MeetingData, MeetingStatus, TLDVClient
from src.services.kt_indexing_service import get_kt_indexing_service
from src.services.kt_ingestion_service import get_kt_ingestion_service
from utils.exception_setup import ApplicationError
from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# CONSTANTES DE EXIBIÇÃO
# ════════════════════════════════════════════════════════════════════════════

_STATUS_LABELS: dict[MeetingStatus, str] = {
    MeetingStatus.COMPLETED: "concluído  ",
    MeetingStatus.PROCESSING: "processando",
    MeetingStatus.FAILED: "falha      ",
    MeetingStatus.PENDING: "pendente   ",
}

_NAME_MAX_LEN = 75

# ════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPAL
# ════════════════════════════════════════════════════════════════════════════


class SelectivePipelineRunner:
    """Pipeline com seleção interativa de reuniões KT.

    Substitui a Fase 1 (ingestion automática) por seleção interativa.
    As Fases 2 (indexação) e 3 (validação) delegam para KTIndexingService.
    """

    def __init__(self) -> None:
        """Inicializa com referências aos services e diretório de transcrições."""
        self._ingestion_svc = get_kt_ingestion_service()
        self._indexing_svc = get_kt_indexing_service()
        self._transcriptions_dir: Path = DIRECTORY_PATHS["transcriptions"]

    # ────────────────────────────────────────────────────────────────────────
    # EXIBIÇÃO E SELEÇÃO INTERATIVA
    # ────────────────────────────────────────────────────────────────────────

    def _display_meetings(self, meetings: list[MeetingData], existing_ids: set[str]) -> None:
        """Exibe tabela numerada de reuniões no terminal.

        Args:
            meetings: Lista de reuniões obtidas da API TL:DV.
            existing_ids: IDs das reuniões já baixadas em disco.
        """
        print()
        print(f"  {'Nº':>3}   {'Status':<12}  Nome")
        print(f"  {'─' * 3}   {'─' * 12}  {'─' * _NAME_MAX_LEN}")

        for i, meeting in enumerate(meetings, start=1):
            status_label = _STATUS_LABELS.get(meeting.status, "desconhecido")
            name = meeting.name if len(meeting.name) <= _NAME_MAX_LEN else meeting.name[: _NAME_MAX_LEN - 3] + "..."
            badge = " (já baixado)" if meeting.id in existing_ids else ""
            print(f"  {i:>3}   {status_label:<12}  {name}{badge}")

        print()

    def _parse_selection(self, raw_input: str, total: int) -> list[int] | None:
        """Parseia a entrada do usuário e retorna índices 0-based válidos.

        Aceita:
            - Números separados por vírgula: "1, 3, 4"
            - Palavra-chave "all" para selecionar todos

        Args:
            raw_input: String digitada pelo usuário.
            total: Total de reuniões disponíveis.

        Returns:
            Lista de índices 0-based sem duplicatas, preservando a ordem.
            None se a entrada contiver valores inválidos.
        """
        stripped = raw_input.strip().lower()

        if stripped == "all":
            return list(range(total))

        indices: list[int] = []
        for part in stripped.split(","):
            part = part.strip()
            if not part.isdigit():
                print(f"  Valor inválido: '{part}' — digite apenas números inteiros.")
                return None
            n = int(part)
            if n < 1 or n > total:
                print(f"  Número fora do intervalo: {n} — válido de 1 a {total}.")
                return None
            indices.append(n - 1)  # Converter para índice 0-based

        # Remover duplicatas mantendo ordem de seleção
        return list(dict.fromkeys(indices))

    def _interactive_select(self, meetings: list[MeetingData], existing_ids: set[str]) -> list[MeetingData]:
        """Exibe a lista de reuniões e coleta a seleção do usuário.

        Loop interativo até o usuário confirmar uma seleção válida ou sair.

        Args:
            meetings: Lista completa de reuniões disponíveis na conta.
            existing_ids: IDs de reuniões já presentes em data/transcriptions/.

        Returns:
            Lista de MeetingData das reuniões selecionadas e confirmadas.

        Raises:
            SystemExit: Se o usuário digitar 'q' para cancelar.
        """
        self._display_meetings(meetings, existing_ids)

        while True:
            print('Selecione os vídeos (ex: 1, 3, 4 | "all" para todos | "q" para sair):')
            raw = input("> ").strip()

            if raw.lower() == "q":
                print("\nOperação cancelada pelo usuário.")
                raise SystemExit(0) from None

            if not raw:
                print("  Entrada vazia. Digite os números ou 'all'.\n")
                continue

            indices = self._parse_selection(raw, len(meetings))
            if indices is None:
                print()
                continue

            if not indices:
                print("  Nenhum vídeo selecionado. Tente novamente.\n")
                continue

            selected = [meetings[i] for i in indices]

            print()
            print(f"Selecionados {len(selected)} vídeo(s):")
            for meeting in selected:
                badge = " (já baixado — será reprocessado)" if meeting.id in existing_ids else ""
                print(f"  • {meeting.name}{badge}")
            print()

            confirm = input("Confirmar download e processamento? (s/n): ").strip().lower()
            if confirm == "s":
                print()
                return selected
            if confirm == "n":
                print("\nSeleção cancelada. Escolha novamente.")
                self._display_meetings(meetings, existing_ids)
                continue

            print("  Resposta inválida. Digite 's' para confirmar ou 'n' para voltar.\n")

    # ────────────────────────────────────────────────────────────────────────
    # FASE 1 — INGESTION SELETIVA
    # ────────────────────────────────────────────────────────────────────────

    def run_ingestion(self) -> dict[str, Any]:
        """Fase 1 (interativa): lista reuniões e baixa apenas as selecionadas.

        Diferente do pipeline completo, não há lógica incremental automática —
        o usuário controla explicitamente o que será baixado.

        Returns:
            Dicionário com estatísticas da execução (meetings_found, meetings_downloaded, etc.).

        Raises:
            ApplicationError: Se TLDV_API_KEY não estiver configurada.
        """
        logger.info("═" * 120)
        logger.info("FASE 1 — INGESTION SELETIVA: Seleção interativa de reuniões TL:DV")
        logger.info("═" * 120)

        if not TLDV_API_KEY:
            raise ApplicationError(
                message="TLDV_API_KEY não configurada no .env",
                status_code=503,
                error_code="SERVICE_UNAVAILABLE",
            )

        stats: dict[str, Any] = {
            "meetings_found": 0,
            "meetings_already_downloaded": 0,
            "meetings_downloaded": 0,
            "meetings_skipped_incomplete": 0,
            "meetings_failed": 0,
            "errors": [],
        }

        client = TLDVClient(api_key=TLDV_API_KEY)
        consolidator = JSONConsolidator(output_dir=self._transcriptions_dir)
        processor = SmartMeetingProcessor(tldv_client=client, consolidator=consolidator)

        print()
        print("Buscando reuniões disponíveis no TL:DV...")
        all_meetings = client.list_meetings()
        stats["meetings_found"] = len(all_meetings)

        if not all_meetings:
            print("Nenhuma reunião encontrada na conta TL:DV.")
            processor.shutdown_background_threads()
            return stats

        print(f"Encontradas {len(all_meetings)} reunião(ões).")

        existing_ids = self._ingestion_svc._get_existing_meeting_ids()
        stats["meetings_already_downloaded"] = len(existing_ids)

        selected_meetings = self._interactive_select(all_meetings, existing_ids)
        logger.info(f"Iniciando download de {len(selected_meetings)} reunião(ões) selecionada(s)")

        for i, meeting in enumerate(selected_meetings):
            logger.info(f"Processando {i + 1}/{len(selected_meetings)}: {meeting.name}")
            try:
                self._ingestion_svc._process_single_meeting(
                    meeting, processor, consolidator, stats
                )
            except ApplicationError as e:
                logger.error(f"Erro ao processar reunião '{meeting.name}': {e.message}")
                stats["meetings_failed"] += 1
                stats["errors"].append(f"Ingestion — {meeting.name}: {e.message}")
            except Exception as e:
                logger.error(f"Erro inesperado ao processar reunião '{meeting.name}': {e}")
                stats["meetings_failed"] += 1
                stats["errors"].append(f"Ingestion — {meeting.name}: {e!s}")

        logger.info(
            f"Fase 1 concluída — "
            f"baixadas: {stats['meetings_downloaded']}, "
            f"incompletas: {stats['meetings_skipped_incomplete']}, "
            f"falhas: {stats['meetings_failed']}"
        )
        processor.shutdown_background_threads()
        return stats

    # ────────────────────────────────────────────────────────────────────────
    # ORQUESTRAÇÃO COMPLETA
    # ────────────────────────────────────────────────────────────────────────

    def run_full_pipeline(self, force_clean: bool = False, skip_indexing: bool = False) -> bool:
        """Orquestra as 3 fases do pipeline seletivo.

        Args:
            force_clean: Se True, apaga todos os dados antes de iniciar.
            skip_indexing: Se True, pula a Fase 2 (indexação no ChromaDB).

        Returns:
            True se todas as fases executadas concluíram com sucesso.
        """
        start_time = datetime.now()
        success = True
        ingestion_stats: dict[str, Any] = {}
        indexing_stats: dict[str, Any] = {}
        validation_info: dict[str, Any] = {}

        logger.info("═" * 120)
        logger.info("KT TRANSCRIBER — PIPELINE SELETIVO")
        logger.info(f"Início: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        if force_clean:
            logger.warning("Modo: FORCE CLEAN — todos os dados serão apagados antes da seleção")
        logger.info("═" * 120)

        if force_clean:
            self._ingestion_svc.force_clean()
            self._indexing_svc.force_clean()

        # ── Fase 1 — Ingestion interativa ────────────────────────────────────
        try:
            ingestion_stats = self.run_ingestion()
        except ApplicationError as e:
            logger.error(f"Fase 1 abortada: {e.message}")
            success = False
        except Exception as e:
            logger.error(f"Erro inesperado na Fase 1: {e}")
            success = False

        # ── Fase 2 — Indexação ───────────────────────────────────────────────
        if not skip_indexing:
            logger.info("═" * 120)
            logger.info("FASE 2 — INDEXAÇÃO: Processando JSONs para ChromaDB")
            logger.info("═" * 120)
            try:
                indexing_stats = self._indexing_svc.run_indexing()
            except ApplicationError as e:
                logger.error(f"Fase 2 abortada: {e.message}")
                success = False
            except Exception as e:
                logger.error(f"Erro inesperado na Fase 2: {e}")
                success = False
        else:
            logger.info("Fase 2 (Indexação) pulada via --skip-indexing")

        # ── Fase 3 — Validação ───────────────────────────────────────────────
        logger.info("═" * 120)
        logger.info("FASE 3 — VALIDAÇÃO: Verificando estado do ChromaDB")
        logger.info("═" * 120)
        try:
            validation_info = self._indexing_svc.get_status()
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
        return success


# ════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA
# ════════════════════════════════════════════════════════════════════════════


def main() -> None:
    """Ponto de entrada do pipeline seletivo KT."""
    parser = argparse.ArgumentParser(
        description="Pipeline KT com seleção interativa de reuniões",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  uv run python scripts/run_select_pipeline.py\n"
            "  uv run python scripts/run_select_pipeline.py --force-clean\n"
            "  uv run python scripts/run_select_pipeline.py --skip-indexing\n"
        ),
    )

    parser.add_argument(
        "--force-clean",
        action="store_true",
        help="ATENCAO: Apaga TODOS os dados (transcriptions/ + vector_db/) antes de selecionar",
    )
    parser.add_argument(
        "--skip-indexing",
        action="store_true",
        help="Pula a Fase 2 (indexação no ChromaDB) — executa apenas seleção + download",
    )

    args = parser.parse_args()

    initialize_application()

    if args.force_clean:
        logger.warning("FORCE CLEAN ativado: todos os dados processados serão apagados")

    runner = SelectivePipelineRunner()

    try:
        success = runner.run_full_pipeline(
            force_clean=args.force_clean,
            skip_indexing=args.skip_indexing,
        )
    except KeyboardInterrupt:
        logger.warning("Pipeline interrompido pelo usuário (Ctrl+C)")
        raise SystemExit(1) from None
    except Exception as e:
        logger.error(f"Erro fatal no pipeline: {e}")
        raise SystemExit(1) from e

    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
