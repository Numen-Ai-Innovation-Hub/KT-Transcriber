"""Domínio kt_ingestion — Transcrição de KT.

Responsável pela ingestão de transcrições via TL:DV API e consolidação de JSONs.
"""

from .json_consolidator import JSONConsolidator
from .kt_ingestion_constants import (
    BACKGROUND_THREAD_TIMEOUT,
    FILE_ENCODING,
    MAX_BACKGROUND_THREADS,
    TLDV_MAX_WAIT_SECONDS,
    TLDV_POLL_INTERVAL_SECONDS,
    TLDV_STATUS_DONE,
)
from .smart_processor import SmartMeetingProcessor
from .tldv_client import Highlight, MeetingData, MeetingStatus, TLDVClient, TranscriptSegment

__all__ = [
    # Cliente TL:DV
    "TLDVClient",
    "MeetingStatus",
    "MeetingData",
    "TranscriptSegment",
    "Highlight",
    # Consolidador
    "JSONConsolidator",
    # Processador
    "SmartMeetingProcessor",
    # Constantes
    "TLDV_STATUS_DONE",
    "TLDV_MAX_WAIT_SECONDS",
    "TLDV_POLL_INTERVAL_SECONDS",
    "FILE_ENCODING",
    "BACKGROUND_THREAD_TIMEOUT",
    "MAX_BACKGROUND_THREADS",
]
