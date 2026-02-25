"""Utilitários do domínio kt_indexing — Transcrição de KT.

Funções auxiliares para processamento de chunks, metadados e normalização.
Migrado de src/core/processing/utils.py do projeto legado (sem setup_logging).
"""

import json
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)


def load_and_validate_json(file_path: Path) -> dict[str, Any]:
    """Carrega e valida arquivo JSON de transcrição.

    Args:
        file_path: Caminho para o arquivo JSON.

    Returns:
        Dicionário com dados do JSON.
    """
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Arquivo JSON inválido (esperado dict): {file_path}")

    logger.debug(f"JSON carregado: {file_path.name}")
    return data


def normalize_client_name(client_name: str) -> str:
    """Normaliza nome do cliente para formato padronizado.

    Args:
        client_name: Nome original do cliente.

    Returns:
        Nome normalizado em uppercase com underscores.
    """
    if not client_name:
        return "CLIENTE_DESCONHECIDO"

    # Remover acentos
    normalized = unicodedata.normalize("NFD", client_name)
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")

    # Uppercase e substituir espaços por underscore
    normalized = normalized.upper().strip()
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"[^A-Z0-9_]", "", normalized)

    return normalized or "CLIENTE_DESCONHECIDO"


def extract_client_name_smart(video_name: str, client_patterns: dict[str, list[str]] | None = None) -> str:
    """Extrai nome do cliente do nome do vídeo com detecção inteligente.

    Prioridade:
    1. Notação [BRACKET] — ex: "[DEXCO]", "[VISSIMO]"
    2. Padrões mapeados explicitamente via client_patterns
    3. Fallback: "DEXCO" (cliente padrão do projeto)

    Args:
        video_name: Nome do vídeo/reunião.
        client_patterns: Mapeamento de cliente para padrões de detecção.

    Returns:
        Nome do cliente normalizado em uppercase.
    """
    if not video_name:
        return "CLIENTE_DESCONHECIDO"

    video_upper = video_name.upper()

    # Prioridade 1: notação [BRACKET] — ex: "[DEXCO]", "[Víssimo]"
    bracket = re.search(r"\[([^\]]+)\]", video_name)
    if bracket:
        return normalize_client_name(bracket.group(1).strip())

    # Prioridade 2: padrões mapeados explicitamente
    if client_patterns:
        for client_name, patterns in client_patterns.items():
            for pattern in patterns:
                if pattern.upper() in video_upper:
                    return normalize_client_name(client_name)

    # Fallback: cliente padrão do projeto
    return "DEXCO"


def extract_client_name(video_name: str) -> str:
    """Alias simples para extract_client_name_smart.

    Args:
        video_name: Nome do vídeo.

    Returns:
        Nome do cliente detectado.
    """
    return extract_client_name_smart(video_name)


def extract_sap_modules_from_title(title: str) -> list[str]:
    """Extrai módulos SAP mencionados no título da reunião.

    Args:
        title: Título da reunião ou vídeo.

    Returns:
        Lista de módulos SAP detectados.
    """
    known_modules = [
        "MM",
        "SD",
        "FI",
        "CO",
        "HR",
        "PP",
        "PM",
        "QM",
        "WM",
        "EWM",
        "TM",
        "GTS",
        "LE",
        "PS",
        "RE",
        "RM",
        "SM",
        "SRM",
        "CRM",
        "BW",
        "BI",
        "BTP",
        "ABAP",
        "FIORI",
        "CPI",
        "IFLOW",
    ]
    title_upper = title.upper()
    found = []
    for module in known_modules:
        pattern = r"\b" + re.escape(module) + r"\b"
        if re.search(pattern, title_upper):
            found.append(module)
    return found


def format_datetime(dt_value: Any = None) -> str:
    """Formata valor de data/hora para string ISO.

    Quando chamada sem argumentos, retorna a data/hora atual em formato ISO.

    Args:
        dt_value: Valor de data (datetime, string ou None). Se None, usa datetime.now().

    Returns:
        String ISO 8601.
    """
    if dt_value is None:
        return datetime.now().isoformat()
    if not dt_value:
        return ""
    if isinstance(dt_value, datetime):
        return dt_value.isoformat()
    if isinstance(dt_value, str):
        return dt_value
    return str(dt_value)


def safe_filename(name: str, max_length: int = 200) -> str:
    """Gera nome de arquivo seguro a partir de uma string.

    Args:
        name: Nome original.
        max_length: Comprimento máximo do nome.

    Returns:
        Nome de arquivo seguro.
    """
    # Remover acentos
    normalized = unicodedata.normalize("NFD", name)
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")

    # Substituir caracteres inválidos por underscore
    safe = re.sub(r"[^\w\s.-]", "_", normalized)
    safe = re.sub(r"\s+", "_", safe.strip())

    return safe[:max_length]


def create_client_variations(client_name: str) -> list[str]:
    """Cria variações do nome do cliente para busca fuzzy.

    Args:
        client_name: Nome do cliente normalizado.

    Returns:
        Lista de variações do nome.
    """
    variations = {client_name}

    # Versão sem underscore
    without_underscore = client_name.replace("_", " ")
    variations.add(without_underscore)

    # Versão lowercase
    variations.add(client_name.lower())
    variations.add(without_underscore.lower())

    # Versão sem acentos
    no_accent = unicodedata.normalize("NFD", client_name)
    no_accent = "".join(c for c in no_accent if unicodedata.category(c) != "Mn")
    variations.add(no_accent)

    return list(variations)


def rate_limit_sleep(delay: float) -> None:
    """Aplica rate limiting entre requisições.

    Args:
        delay: Tempo em segundos para aguardar.
    """
    if delay > 0:
        time.sleep(delay)


def calculate_estimated_processing_time(segment_count: int, rate_limit_delay: float = 0.1) -> float:
    """Calcula tempo estimado de processamento.

    Args:
        segment_count: Número de segmentos a processar.
        rate_limit_delay: Delay entre requisições em segundos.

    Returns:
        Tempo estimado em segundos.
    """
    # Estimativa conservadora: ~2s por segmento + delays de rate limit
    return segment_count * (2.0 + rate_limit_delay)


def extract_enriched_tldv_fields(meeting_data: dict[str, Any]) -> dict[str, Any]:
    """Extrai campos enriquecidos dos dados TL:DV para metadados.

    Suporta formato aninhado ({"metadata": {...}, "transcript": {...}, "highlights": [...]})
    e formato flat (campos na raiz) — fallback automático para retrocompatibilidade.

    Args:
        meeting_data: JSON consolidado da reunião.

    Returns:
        Dicionário com campos extraídos.
    """
    meta = meeting_data.get("metadata", meeting_data)
    highlights = meeting_data.get("highlights", [])

    return {
        "original_url": meta.get("meeting_url", meta.get("original_url", "")),
        "meeting_date": _extract_date_from_iso(meta.get("happened_at", "")),
        "duration_seconds": meta.get("duration", 0),
        "highlights_summary": _build_highlights_summary(highlights),
        "organizer": _extract_organizer_name(meta.get("organizer")),
    }


def extract_participants_list(meeting_data: dict[str, Any]) -> list[str]:
    """Extrai lista de participantes dos dados da reunião.

    Args:
        meeting_data: Dados completos da reunião.

    Returns:
        Lista de nomes dos participantes.
    """
    meeting_info = meeting_data.get("meeting", {})
    invitees = meeting_info.get("invitees") or []

    participants = []
    for invitee in invitees:
        if isinstance(invitee, dict):
            name = invitee.get("name") or invitee.get("email", "")
            if name:
                participants.append(name)
        elif isinstance(invitee, str):
            participants.append(invitee)

    return participants


def extract_highlights_summary(highlights: list[dict]) -> str:
    """Cria resumo textual dos highlights da reunião.

    Args:
        highlights: Lista de highlights da reunião.

    Returns:
        Texto com resumo dos highlights.
    """
    return _build_highlights_summary(highlights)


def extract_decisions_summary(highlights: list[dict]) -> str:
    """Extrai resumo de decisões dos highlights.

    Args:
        highlights: Lista de highlights.

    Returns:
        Texto com as principais decisões.
    """
    decisions = []
    for highlight in highlights:
        text = highlight.get("text", "")
        source = highlight.get("source", "")
        if source in ["decision", "action_item"] or "decid" in text.lower():
            decisions.append(text)

    return " | ".join(decisions[:5]) if decisions else ""


def handle_processing_error(error: Exception, context: str) -> None:
    """Registra erro de processamento de forma padronizada.

    Args:
        error: Exceção ocorrida.
        context: Contexto onde o erro ocorreu.
    """
    logger.error(f"Erro de processamento em '{context}': {error}")


def sanitize_metadata_value(value: Any) -> str | int | float | bool | None:
    """Sanitiza valor de metadado para compatibilidade com ChromaDB.

    Args:
        value: Valor a sanitizar.

    Returns:
        Valor compatível com ChromaDB (str, int, float, bool, ou None).
    """
    if value is None:
        return None
    if isinstance(value, bool | int | float):
        return value
    if isinstance(value, list | tuple):
        return ", ".join(str(item) for item in value if item)
    if isinstance(value, dict):
        return None  # ChromaDB não suporta dicts aninhados
    return str(value)


def _extract_date_from_iso(iso_string: str) -> str:
    """Extrai apenas a data (YYYY-MM-DD) de uma string ISO.

    Args:
        iso_string: String no formato ISO 8601.

    Returns:
        Data no formato YYYY-MM-DD ou string vazia.
    """
    if not iso_string:
        return ""
    try:
        return iso_string[:10]  # YYYY-MM-DD
    except Exception as e:
        logger.warning(f"Falha ao extrair data de '{iso_string}': {e}")
        return ""


def _build_highlights_summary(highlights: list[dict]) -> str:
    """Constrói resumo textual dos highlights.

    Args:
        highlights: Lista de highlights.

    Returns:
        Resumo em texto.
    """
    if not highlights:
        return ""
    texts = [h.get("text", "") for h in highlights[:5] if h.get("text")]
    return " | ".join(texts)


def _extract_organizer_name(organizer: dict | None) -> str:
    """Extrai nome do organizador dos dados da reunião.

    Args:
        organizer: Dicionário com dados do organizador.

    Returns:
        Nome do organizador ou string vazia.
    """
    if not organizer or not isinstance(organizer, dict):
        return ""
    return organizer.get("name") or organizer.get("email", "")
