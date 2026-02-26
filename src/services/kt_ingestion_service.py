"""Serviço de orquestração para ingestão KT.

Singleton thread-safe. Encapsula TLDVClient + SmartMeetingProcessor + JSONConsolidator.
Usar get_kt_ingestion_service() para obter a instância.
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config.settings import DIRECTORY_PATHS, TLDV_API_KEY
from src.kt_indexing.kt_indexing_utils import extract_client_name_smart
from src.kt_ingestion.json_consolidator import JSONConsolidator
from src.kt_ingestion.smart_processor import SmartMeetingProcessor
from src.kt_ingestion.tldv_client import MeetingData, TLDVClient
from utils.exception_setup import ApplicationError
from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)


class KTIngestionService:
    """Serviço de orquestração para ingestão de reuniões KT.

    Singleton thread-safe. Encapsula TLDVClient, SmartMeetingProcessor e JSONConsolidator.
    Cada chamada a run_ingestion() opera de forma incremental — pula reuniões já baixadas.
    """

    _instance: "KTIngestionService | None" = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        """Inicializa o serviço com diretório de transcrições."""
        self._transcriptions_dir: Path = DIRECTORY_PATHS["transcriptions"]
        self._transcriptions_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_instance(cls) -> "KTIngestionService":
        """Retorna instância singleton (double-checked locking)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ────────────────────────────────────────────────────────────────────────
    # OPERAÇÕES PÚBLICAS
    # ────────────────────────────────────────────────────────────────────────

    def force_clean(self) -> None:
        """Remove todos os JSONs de transcrição do disco.

        Raises:
            ApplicationError: Se ocorrer erro durante a limpeza.
        """
        logger.warning(f"Iniciando limpeza de transcriptions/ em {self._transcriptions_dir}")
        removed = 0
        for json_file in self._transcriptions_dir.glob("*.json"):
            json_file.unlink()
            removed += 1
        logger.warning(f"Limpeza concluída — {removed} JSON(s) removidos de transcriptions/")

    def run_ingestion(self) -> dict[str, Any]:
        """Executa ingestion incremental de reuniões TL:DV.

        Baixa apenas reuniões novas (que não estejam em transcriptions/).
        Apenas reuniões com status COMPLETED são processadas.

        Returns:
            Dicionário com estatísticas da execução (meetings_found, meetings_downloaded, etc.).

        Raises:
            ApplicationError: Se TLDV_API_KEY não estiver configurada.
        """
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

        all_meetings = client.list_meetings()
        stats["meetings_found"] = len(all_meetings)
        logger.info(f"Reuniões encontradas na API: {len(all_meetings)}")

        existing_ids = self._get_existing_meeting_ids()
        stats["meetings_already_downloaded"] = len(existing_ids)
        logger.info(f"Reuniões já baixadas em disco: {len(existing_ids)}")

        new_meetings = [m for m in all_meetings if m.id not in existing_ids]

        if not new_meetings:
            logger.info("Nenhuma reunião nova para baixar — ingestion concluída (incremental)")
            processor.shutdown_background_threads()
            return stats

        logger.info(f"Reuniões novas para processar: {len(new_meetings)}")

        for i, meeting in enumerate(new_meetings):
            logger.info(f"Processando {i + 1}/{len(new_meetings)}: {meeting.name}")
            try:
                self._process_single_meeting(meeting, processor, consolidator, stats)
            except ApplicationError as e:
                logger.error(f"Erro ao processar reunião '{meeting.name}': {e.message}")
                stats["meetings_failed"] += 1
                stats["errors"].append(f"Ingestion — {meeting.name}: {e.message}")
            except Exception as e:
                logger.error(f"Erro inesperado ao processar reunião '{meeting.name}': {e}")
                stats["meetings_failed"] += 1
                stats["errors"].append(f"Ingestion — {meeting.name}: {e!s}")

        processor.shutdown_background_threads()
        logger.info(
            f"Ingestion concluída — "
            f"baixadas: {stats['meetings_downloaded']}, "
            f"incompletas: {stats['meetings_skipped_incomplete']}, "
            f"falhas: {stats['meetings_failed']}"
        )
        return stats

    def list_meetings_with_status(self) -> list[dict[str, Any]]:
        """Lista reuniões disponíveis no TL:DV com flag de indexação.

        Retorna cada reunião com already_indexed=True se o JSON já estiver em
        data/transcriptions/ (indica que foi baixada — pode ou não estar no ChromaDB).

        Returns:
            Lista de dicts com id, name, status, duration, already_indexed.

        Raises:
            ApplicationError: Se TLDV_API_KEY não estiver configurada.
        """
        if not TLDV_API_KEY:
            raise ApplicationError(
                message="TLDV_API_KEY não configurada no .env",
                status_code=503,
                error_code="SERVICE_UNAVAILABLE",
            )

        client = TLDVClient(api_key=TLDV_API_KEY)
        all_meetings = client.list_meetings()
        existing_ids = self._get_existing_meeting_ids()

        return [
            {
                "id": m.id,
                "name": m.name,
                "status": m.status.value,
                "duration": m.duration,
                "already_indexed": m.id in existing_ids,
            }
            for m in all_meetings
        ]

    def run_selective_ingestion(self, meeting_ids: list[str]) -> dict[str, Any]:
        """Executa ingestion seletiva das reuniões informadas.

        Baixa e processa apenas os meetings cujos IDs foram fornecidos,
        independentemente de já estarem em disco (usuário escolheu explicitamente).

        Args:
            meeting_ids: Lista de IDs de reuniões a baixar.

        Returns:
            Dicionário com estatísticas da execução.

        Raises:
            ApplicationError: Se TLDV_API_KEY não estiver configurada.
        """
        if not TLDV_API_KEY:
            raise ApplicationError(
                message="TLDV_API_KEY não configurada no .env",
                status_code=503,
                error_code="SERVICE_UNAVAILABLE",
            )

        stats: dict[str, Any] = {
            "meetings_found": len(meeting_ids),
            "meetings_downloaded": 0,
            "meetings_skipped_incomplete": 0,
            "meetings_failed": 0,
            "errors": [],
        }

        ids_set = set(meeting_ids)
        client = TLDVClient(api_key=TLDV_API_KEY)
        consolidator = JSONConsolidator(output_dir=self._transcriptions_dir)
        processor = SmartMeetingProcessor(tldv_client=client, consolidator=consolidator)

        all_meetings = client.list_meetings()
        selected = [m for m in all_meetings if m.id in ids_set]

        if not selected:
            logger.warning(f"Nenhuma reunião encontrada para {len(meeting_ids)} ID(s) fornecidos")
            processor.shutdown_background_threads()
            return stats

        logger.info(f"Reuniões selecionadas para download: {len(selected)}")

        for i, meeting in enumerate(selected):
            logger.info(f"Processando {i + 1}/{len(selected)}: {meeting.name}")
            try:
                self._process_single_meeting(meeting, processor, consolidator, stats)
            except ApplicationError as e:
                logger.error(f"Erro ao processar reunião '{meeting.name}': {e.message}")
                stats["meetings_failed"] += 1
                stats["errors"].append(f"Ingestion — {meeting.name}: {e.message}")
            except Exception as e:
                logger.error(f"Erro inesperado ao processar reunião '{meeting.name}': {e}")
                stats["meetings_failed"] += 1
                stats["errors"].append(f"Ingestion — {meeting.name}: {e!s}")

        processor.shutdown_background_threads()
        logger.info(
            f"Ingestion seletiva concluída — "
            f"baixadas: {stats['meetings_downloaded']}, "
            f"incompletas: {stats['meetings_skipped_incomplete']}, "
            f"falhas: {stats['meetings_failed']}"
        )
        return stats

    # ────────────────────────────────────────────────────────────────────────
    # PRIVADOS
    # ────────────────────────────────────────────────────────────────────────

    def _get_existing_meeting_ids(self) -> set[str]:
        """Retorna IDs de reuniões já baixadas (JSONs em transcriptions/).

        Returns:
            Set com meeting_ids já presentes em disco.
        """
        existing_ids: set[str] = set()
        for json_file in self._transcriptions_dir.glob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                meeting_id = data.get("metadata", {}).get("meeting_id") or data.get("meeting_id", "")
                if meeting_id:
                    existing_ids.add(meeting_id)
            except Exception as e:
                logger.warning(f"Erro ao ler meeting_id de {json_file.name}: {e}")
        return existing_ids

    def _build_structured_json(self, meeting_data: dict[str, Any], client_name: str) -> dict[str, Any]:
        """Converte formato plano do SmartMeetingProcessor para estrutura esperada pelo IndexingEngine.

        Args:
            meeting_data: Dict retornado por SmartMeetingProcessor.process_meeting_smart().
            client_name: Nome do cliente normalizado.

        Returns:
            Dict estruturado compatível com IndexingEngine.process_single_video().
        """
        transcript_segments = meeting_data.get("transcript", [])
        return {
            "metadata": {
                "video_name": meeting_data.get("video_name", ""),
                "client_name": client_name,
                "meeting_id": meeting_data.get("meeting_id", ""),
                "meeting_url": meeting_data.get("meeting_url", ""),
                "happened_at": meeting_data.get("happened_at", ""),
                "duration": meeting_data.get("duration", 0),
                "total_segments": meeting_data.get("total_segments", len(transcript_segments)),
                "total_highlights": meeting_data.get("total_highlights", 0),
                "consolidated_at": datetime.now().isoformat(),
            },
            "transcript": {"segments": transcript_segments},
            "highlights": meeting_data.get("highlights", []),
        }

    def _process_single_meeting(
        self,
        meeting: MeetingData,
        processor: SmartMeetingProcessor,
        consolidator: JSONConsolidator,
        stats: dict[str, Any],
    ) -> None:
        """Baixa e salva uma reunião individual.

        Args:
            meeting: Dados da reunião obtidos da API TL:DV.
            processor: Processador smart já inicializado.
            consolidator: Consolidador JSON para persistência.
            stats: Dicionário de estatísticas (mutado in-place).
        """
        client_name = extract_client_name_smart(meeting.name)
        logger.info(f"Processando reunião: '{meeting.name}' | cliente: {client_name}")

        meeting_data = processor.process_meeting_smart(
            meeting_id=meeting.id,
            client_name=client_name,
            video_name=meeting.name,
            wait_for_complete=True,
        )

        if not meeting_data.get("is_complete"):
            logger.warning(
                f"Reunião '{meeting.name}' não está completa — "
                f"status: {meeting_data.get('status', 'unknown')}. Pulando."
            )
            stats["meetings_skipped_incomplete"] += 1
            return

        structured_data = self._build_structured_json(meeting_data, client_name)
        video_name = meeting_data.get("video_name", meeting.name)
        safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in str(video_name))
        filename = f"{safe_name}.json"

        consolidator.save_consolidated_json(structured_data, filename=filename)
        segments_count = len(meeting_data.get("transcript", []))
        logger.info(f"Reunião salva: '{video_name}' — {segments_count} segmentos, arquivo: {filename}")
        stats["meetings_downloaded"] += 1


def get_kt_ingestion_service() -> KTIngestionService:
    """Factory para injeção de dependência nos routers."""
    return KTIngestionService.get_instance()
