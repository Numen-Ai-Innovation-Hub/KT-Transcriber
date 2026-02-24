"""Helpers específicos do domínio KT Transcriber.

Funções auxiliares com convenções de nomenclatura e padrões do projeto KT.
"""

import re
from pathlib import Path


def build_meeting_key(meeting_id: str, suffix: str = "") -> str:
    """Constrói chave padronizada para identificar uma reunião no Redis/cache.

    Args:
        meeting_id: ID único da reunião.
        suffix: Sufixo opcional (ex: "status", "result").

    Returns:
        Chave no formato 'meeting:{id}:{suffix}' ou 'meeting:{id}'.
    """
    base = f"meeting:{meeting_id}"
    return f"{base}:{suffix}" if suffix else base


def build_job_key(job_id: str, field: str = "") -> str:
    """Constrói chave padronizada para tracking de jobs no Redis.

    Args:
        job_id: ID único do job ARQ.
        field: Campo do job (ex: "status", "progress", "result", "error").

    Returns:
        Chave no formato 'job:{id}:{field}' ou 'job:{id}'.
    """
    base = f"job:{job_id}"
    return f"{base}:{field}" if field else base


def extract_video_name_from_path(path: str | Path) -> str:
    """Extrai nome limpo do vídeo a partir de um caminho de arquivo.

    Remove sufixos gerados pelo pipeline KT (chunks, transcript, normalized, enriched).

    Args:
        path: Caminho para o arquivo de transcrição/chunk.

    Returns:
        Nome do vídeo sem extensão, normalizado.
    """
    stem = Path(path).stem
    # Remove sufixos comuns gerados pelo pipeline
    stem = re.sub(r"_(chunks|transcript|normalized|enriched)$", "", stem)
    return stem
