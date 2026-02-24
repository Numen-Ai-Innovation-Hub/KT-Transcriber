"""Smart Meeting Processor — Transcrição de KT.

Processamento inteligente de duas fases: dados imediatos + completude em background.
"""

import re
import threading
from typing import Any

from src.kt_ingestion.json_consolidator import JSONConsolidator
from src.kt_ingestion.tldv_client import MeetingStatus, TLDVClient
from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)


class SmartMeetingProcessor:
    """Processador inteligente de reuniões com completude em background.

    Fase 1 (imediata): Obtém dados básicos disponíveis imediatamente.
    Fase 2 (background): Aguarda processamento completo e atualiza dados.

    Estratégia:
    - Dados imediatos são retornados sem espera para não bloquear o fluxo.
    - Dados completos são obtidos em thread separada e salvos quando prontos.
    """

    def __init__(self, tldv_client: TLDVClient, consolidator: JSONConsolidator | None = None):
        """Inicializa o processador.

        Args:
            tldv_client: Cliente TL:DV autenticado.
            consolidator: Consolidador JSON. Se None, cria um padrão.
        """
        self.client = tldv_client
        self.consolidator = consolidator or JSONConsolidator()
        self._background_threads: list[threading.Thread] = []

    def process_meeting_smart(
        self,
        meeting_id: str,
        client_name: str,
        video_name: str | None = None,
        wait_for_complete: bool = False,
    ) -> dict[str, Any]:
        """Processa reunião com estratégia inteligente de duas fases.

        Args:
            meeting_id: ID da reunião no TL:DV.
            client_name: Nome do cliente.
            video_name: Nome do vídeo (opcional, usa nome da reunião se None).
            wait_for_complete: Se True, aguarda processamento completo (bloqueante).

        Returns:
            Dicionário com dados disponíveis da reunião.
        """
        logger.info(f"Iniciando processamento smart para reunião: {meeting_id}")

        # Fase 1: dados imediatos
        immediate_data = self._process_immediate_data(meeting_id, client_name, video_name)

        if wait_for_complete:
            # Modo bloqueante: aguardar completude
            return self._process_final_upgrade(meeting_id, client_name, video_name, immediate_data)

        # Fase 2: completude em background (não bloqueante)
        if immediate_data.get("status") != MeetingStatus.COMPLETED.value:
            self._start_background_completion(meeting_id, client_name, video_name, immediate_data)

        return immediate_data

    def _process_immediate_data(
        self, meeting_id: str, client_name: str, video_name: str | None
    ) -> dict[str, Any]:
        """Obtém dados imediatamente disponíveis da reunião.

        Args:
            meeting_id: ID da reunião.
            client_name: Nome do cliente.
            video_name: Nome do vídeo.

        Returns:
            Dicionário com dados disponíveis no momento.
        """
        try:
            meeting = self.client.get_meeting_status(meeting_id)
            resolved_name = video_name or self._normalize_video_name(meeting.name)

            immediate_data: dict[str, Any] = {
                "meeting_id": meeting_id,
                "video_name": resolved_name,
                "client_name": client_name,
                "status": meeting.status.value,
                "meeting_url": meeting.url,
                "happened_at": meeting.happened_at,
                "duration": meeting.duration,
                "transcript": [],
                "highlights": [],
                "is_complete": meeting.status == MeetingStatus.COMPLETED,
            }

            # Se já está completo, obter dados completos
            if meeting.status == MeetingStatus.COMPLETED:
                immediate_data = self._enrich_with_full_data(meeting_id, immediate_data)

            logger.info(
                f"Dados imediatos obtidos para '{resolved_name}' — status: {meeting.status.value}"
            )
            return immediate_data

        except Exception as e:
            logger.error(f"Erro ao obter dados imediatos da reunião {meeting_id}: {e}")
            return {
                "meeting_id": meeting_id,
                "client_name": client_name,
                "video_name": video_name or meeting_id,
                "status": "unknown",
                "transcript": [],
                "highlights": [],
                "is_complete": False,
                "error": str(e),
            }

    def _enrich_with_full_data(self, meeting_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Enriquece dados com transcrição e highlights completos.

        Args:
            meeting_id: ID da reunião.
            data: Dados parciais da reunião.

        Returns:
            Dados enriquecidos com transcrição e highlights.
        """
        try:
            transcript = self.client.get_meeting_transcript(meeting_id)
            highlights = self.client.get_meeting_highlights(meeting_id)

            data["transcript"] = transcript
            data["highlights"] = highlights
            data["total_segments"] = len(transcript)
            data["total_highlights"] = len(highlights)
            data["is_complete"] = True

            logger.info(
                f"Dados completos obtidos — {len(transcript)} segmentos, {len(highlights)} highlights"
            )
        except Exception as e:
            logger.error(f"Erro ao enriquecer dados completos da reunião {meeting_id}: {e}")

        return data

    def _start_background_completion(
        self,
        meeting_id: str,
        client_name: str,
        video_name: str | None,
        initial_data: dict[str, Any],
    ) -> None:
        """Inicia thread de background para aguardar completude.

        Args:
            meeting_id: ID da reunião.
            client_name: Nome do cliente.
            video_name: Nome do vídeo.
            initial_data: Dados iniciais já obtidos.
        """
        thread = threading.Thread(
            target=self._background_completion_worker,
            args=(meeting_id, client_name, video_name, initial_data),
            daemon=True,
        )
        thread.start()
        self._background_threads.append(thread)
        logger.info(f"Thread de completude iniciada para reunião: {meeting_id}")

    def _background_completion_worker(
        self,
        meeting_id: str,
        client_name: str,
        video_name: str | None,
        initial_data: dict[str, Any],
    ) -> None:
        """Worker executado em background para obter dados completos.

        Args:
            meeting_id: ID da reunião.
            client_name: Nome do cliente.
            video_name: Nome do vídeo.
            initial_data: Dados iniciais.
        """
        try:
            logger.info(f"Background: aguardando completude da reunião {meeting_id}")
            completed_meeting = self.client.wait_for_completion(meeting_id)
            logger.info(f"Background: reunião {meeting_id} completada — {completed_meeting.status.value}")

            final_data = self._process_final_upgrade(meeting_id, client_name, video_name, initial_data)

            if final_data.get("is_complete"):
                self.consolidator.save_consolidated_json(final_data)
                logger.info(f"Background: dados completos salvos para reunião {meeting_id}")

        except Exception as e:
            logger.error(f"Background: erro ao completar reunião {meeting_id}: {e}")

    def _process_final_upgrade(
        self,
        meeting_id: str,
        client_name: str,
        video_name: str | None,
        initial_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Processa versão final com dados completos.

        Args:
            meeting_id: ID da reunião.
            client_name: Nome do cliente.
            video_name: Nome do vídeo.
            initial_data: Dados parciais iniciais.

        Returns:
            Dicionário com todos os dados completos.
        """
        final_data = initial_data.copy()
        return self._enrich_with_full_data(meeting_id, final_data)

    def _is_data_better(self, new_data: dict[str, Any], existing_data: dict[str, Any]) -> bool:
        """Verifica se os novos dados são melhores que os existentes.

        Args:
            new_data: Novos dados obtidos.
            existing_data: Dados existentes.

        Returns:
            True se novos dados têm mais informação.
        """
        new_segments = len(new_data.get("transcript", []))
        existing_segments = len(existing_data.get("transcript", []))
        return new_segments > existing_segments or (new_data.get("is_complete") and not existing_data.get("is_complete"))

    def _normalize_video_name(self, name: str) -> str:
        """Normaliza nome do vídeo para uso interno.

        Args:
            name: Nome original do vídeo.

        Returns:
            Nome normalizado.
        """
        if not name:
            return "reuniao_kt"
        # Remove caracteres especiais, mantém letras, números, hífens e underscores
        normalized = re.sub(r"[^\w\s-]", "", name)
        normalized = re.sub(r"\s+", "_", normalized.strip())
        return normalized.lower()

    def shutdown_background_threads(self, timeout: float = 30.0) -> None:
        """Aguarda conclusão das threads de background.

        Args:
            timeout: Timeout máximo em segundos por thread.
        """
        for thread in self._background_threads:
            if thread.is_alive():
                thread.join(timeout=timeout)

        active = sum(1 for t in self._background_threads if t.is_alive())
        if active > 0:
            logger.warning(f"{active} thread(s) de background ainda ativas após timeout")
        else:
            logger.info("Todas as threads de background concluídas")
