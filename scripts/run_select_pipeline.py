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
from pathlib import Path

# Garantir que a raiz do projeto está no sys.path para imports de src/, utils/ e scripts/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.run_full_pipeline import FullPipelineRunner  # type: ignore[attr-defined]
from src.config.settings import TLDV_API_KEY
from src.config.startup import initialize_application
from src.kt_ingestion.json_consolidator import JSONConsolidator
from src.kt_ingestion.smart_processor import SmartMeetingProcessor
from src.kt_ingestion.tldv_client import MeetingData, MeetingStatus, TLDVClient
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


class SelectivePipelineRunner(FullPipelineRunner):
    """Pipeline com seleção interativa de reuniões KT.

    Herda toda a lógica de FullPipelineRunner e substitui apenas a Fase 1
    (ingestion) por um fluxo interativo onde o usuário escolhe quais
    reuniões deseja processar.
    """

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
    # FASE 1 — INGESTION SELETIVA (substitui a do pai)
    # ────────────────────────────────────────────────────────────────────────

    def run_ingestion(self) -> bool:
        """Fase 1 (interativa): lista reuniões e baixa apenas as selecionadas.

        Diferente do pipeline completo, não há lógica incremental automática —
        o usuário controla explicitamente o que será baixado.
        Reuniões não concluídas (status != COMPLETED) são puladas com aviso.

        Returns:
            True se ao menos uma reunião foi baixada com sucesso ou selecionada.
            False se erro crítico (ex: API key ausente).
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

        client = TLDVClient(api_key=TLDV_API_KEY)
        consolidator = JSONConsolidator(output_dir=self.transcriptions_dir)
        processor = SmartMeetingProcessor(tldv_client=client, consolidator=consolidator)

        print()
        print("Buscando reuniões disponíveis no TL:DV...")
        all_meetings = client.list_meetings()
        self.stats["meetings_found"] = len(all_meetings)

        if not all_meetings:
            print("Nenhuma reunião encontrada na conta TL:DV.")
            return False

        print(f"Encontradas {len(all_meetings)} reunião(ões).")

        existing_ids = self._get_existing_meeting_ids()
        self.stats["meetings_already_downloaded"] = sum(1 for m in all_meetings if m.id in existing_ids)

        # Seleção interativa — retorna somente as escolhidas e confirmadas
        selected_meetings = self._interactive_select(all_meetings, existing_ids)

        logger.info(f"Iniciando download de {len(selected_meetings)} reunião(ões) selecionada(s)")

        for i, meeting in enumerate(selected_meetings):
            logger.info(f"Processando {i + 1}/{len(selected_meetings)}: {meeting.name}")
            try:
                self._process_single_meeting(meeting, processor, consolidator)
            except ApplicationError as e:
                logger.error(f"Erro ao processar reunião '{meeting.name}': {e.message}")
                self.stats["meetings_failed"] += 1
                self.stats["errors"].append(f"Ingestion — {meeting.name}: {e.message}")
            except Exception as e:
                logger.error(f"Erro inesperado ao processar reunião '{meeting.name}': {e}")
                self.stats["meetings_failed"] += 1
                self.stats["errors"].append(f"Ingestion — {meeting.name}: {e!s}")

        logger.info(
            f"Fase 1 concluída — "
            f"baixadas: {self.stats['meetings_downloaded']}, "
            f"incompletas: {self.stats['meetings_skipped_incomplete']}, "
            f"falhas: {self.stats['meetings_failed']}"
        )

        processor.shutdown_background_threads()
        return True


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
            skip_ingestion=False,
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
