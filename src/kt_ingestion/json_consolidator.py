"""Consolidador JSON — Transcrição de KT.

Consolida dados de reuniões TL:DV em formato JSON padronizado para indexação.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config.settings import DIRECTORY_PATHS
from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)


class JSONConsolidator:
    """Consolida dados de transcrição em JSON padronizado.

    Recebe dados brutos do TL:DV (meeting, transcript, highlights) e gera
    um JSON estruturado com todos os campos necessários para indexação.
    """

    def __init__(self, output_dir: Path | None = None):
        """Inicializa o consolidador de JSON.

        Args:
            output_dir: Diretório de saída. Default: DIRECTORY_PATHS["transcriptions"].
        """
        self.output_dir = output_dir or DIRECTORY_PATHS["transcriptions"]

    def create_consolidated_json(
        self,
        meeting_data: dict[str, Any],
        client_name: str,
        video_name: str | None = None,
    ) -> dict[str, Any]:
        """Cria JSON consolidado a partir dos dados brutos da reunião.

        Args:
            meeting_data: Dados completos retornados por TLDVClient.get_complete_meeting_data().
            client_name: Nome do cliente para o qual a reunião pertence.
            video_name: Nome do vídeo/reunião. Se None, usa meeting_data["meeting"]["name"].

        Returns:
            Dicionário com JSON consolidado e estruturado.
        """
        meeting_info = meeting_data.get("meeting", {})
        transcript = meeting_data.get("transcript", [])
        highlights = meeting_data.get("highlights", [])

        resolved_video_name = video_name or meeting_info.get("name", "Reunião KT")

        consolidated = {
            "video_name": resolved_video_name,
            "client_name": client_name,
            "meeting_id": meeting_info.get("id", ""),
            "meeting_url": meeting_info.get("url", ""),
            "happened_at": meeting_info.get("happened_at", ""),
            "duration": meeting_info.get("duration", 0),
            "organizer": meeting_info.get("organizer"),
            "invitees": meeting_info.get("invitees", []),
            "template": meeting_info.get("template", "meeting"),
            "transcript": transcript,
            "highlights": highlights,
            "consolidated_at": datetime.now().isoformat(),
            "total_segments": len(transcript),
            "total_highlights": len(highlights),
        }

        logger.info(
            f"JSON consolidado criado para '{resolved_video_name}' — "
            f"{len(transcript)} segmentos, {len(highlights)} highlights"
        )
        return consolidated

    def save_consolidated_json(
        self,
        consolidated_data: dict[str, Any],
        filename: str | None = None,
    ) -> Path:
        """Salva JSON consolidado no diretório de transcrições.

        Args:
            consolidated_data: Dicionário com dados consolidados.
            filename: Nome do arquivo. Se None, gera baseado no video_name.

        Returns:
            Path do arquivo salvo.
        """
        if not filename:
            video_name = consolidated_data.get("video_name", "reuniao")
            safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in video_name)
            filename = f"{safe_name}.json"

        output_path = self.output_dir / filename

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(consolidated_data, f, ensure_ascii=False, indent=2)

        logger.info(f"JSON consolidado salvo em: {output_path}")
        return output_path

    def process_from_tldv_data(
        self,
        meeting_data: dict[str, Any],
        client_name: str,
        video_name: str | None = None,
        save: bool = True,
    ) -> dict[str, Any]:
        """Processa dados TL:DV completos e opcionalmente salva o JSON.

        Args:
            meeting_data: Dados retornados por TLDVClient.get_complete_meeting_data().
            client_name: Nome do cliente.
            video_name: Nome do vídeo (opcional).
            save: Se True, salva o arquivo JSON em disco.

        Returns:
            Dicionário com JSON consolidado.
        """
        consolidated = self.create_consolidated_json(meeting_data, client_name, video_name)

        if save:
            self.save_consolidated_json(consolidated)

        return consolidated

    def process_from_chunked_data(
        self,
        chunked_data: dict[str, Any],
        client_name: str,
        save: bool = True,
    ) -> dict[str, Any]:
        """Processa dados já fragmentados em chunks e opcionalmente salva o JSON.

        Args:
            chunked_data: Dados fragmentados com campo "chunks".
            client_name: Nome do cliente.
            save: Se True, salva o arquivo JSON em disco.

        Returns:
            Dicionário com JSON consolidado.
        """
        chunked_data["client_name"] = client_name

        if save:
            video_name = chunked_data.get("video_name", "reuniao")
            safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in video_name)
            output_path = self.output_dir / f"{safe_name}.json"

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(chunked_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Dados fragmentados salvos em: {output_path}")

        return chunked_data
