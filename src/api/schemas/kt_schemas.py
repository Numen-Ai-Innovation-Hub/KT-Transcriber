"""Schemas Pydantic para endpoints KT.

Cobre os quatro domínios:
- kt_search   → KTSearchRequest, KTSearchResponse, pipeline schemas
- kt_ingestion → AsyncJobResponse, JobStatusResponse
- kt_indexing  → AsyncJobResponse, JobStatusResponse, KTIndexingStatusResponse
- kt_pipeline  → MeetingItemResponse, MeetingListResponse, SelectivePipelineRequest, SelectivePipelineStartResponse
"""

from typing import Any

from pydantic import BaseModel, Field

# ════════════════════════════════════════════════════════════════════════════
# BUSCA
# ════════════════════════════════════════════════════════════════════════════


class KTSearchRequest(BaseModel):
    """Request para busca KT via pipeline RAG."""

    query: str = Field(..., min_length=3, description="Pergunta ou consulta sobre as transcrições KT")


class KTSearchResponse(BaseModel):
    """Response da busca KT com insights e contextos."""

    answer: str
    contexts: list[dict[str, Any]]
    query_type: str
    processing_time: float
    success: bool


class PipelineStartRequest(BaseModel):
    """Request para iniciar pipeline RAG transparente."""

    query: str = Field(..., min_length=3, description="Pergunta ou consulta sobre as transcrições KT")


class PipelineStartResponse(BaseModel):
    """Response do início do pipeline — retorna session_id e job_id do primeiro estágio."""

    session_id: str
    job_id: str
    stage: str = "enrich"
    status: str = "enqueued"


class StageJobResponse(BaseModel):
    """Response de enfileiramento de um estágio do pipeline."""

    session_id: str
    job_id: str
    stage: str
    status: str = "enqueued"


class StageStatusResponse(BaseModel):
    """Status de um job ARQ de estágio do pipeline."""

    session_id: str
    job_id: str
    arq_status: str  # queued | in_progress | complete | not_found | failed
    stage_ready: bool  # True quando arq_status=="complete" E chave Redis confirmada
    error: str | None = None


# ════════════════════════════════════════════════════════════════════════════
# JOBS ASSÍNCRONOS (ARQ)
# ════════════════════════════════════════════════════════════════════════════


class AsyncJobResponse(BaseModel):
    """Response de operação enfileirada via ARQ."""

    job_id: str
    status: str = "enqueued"
    message: str = "Job enfileirado com sucesso"


class JobStatusResponse(BaseModel):
    """Status de um job ARQ."""

    job_id: str
    status: str  # queued | in_progress | complete | not_found | failed
    result: dict[str, Any] | None = None
    error: str | None = None


# ════════════════════════════════════════════════════════════════════════════
# STATUS DE INDEXAÇÃO
# ════════════════════════════════════════════════════════════════════════════


class KTIndexingStatusResponse(BaseModel):
    """Status atual do ChromaDB."""

    total_documents: int
    collection_name: str
    unique_clients: list[str]
    embedding_dimensions: int


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE SELETIVO (ingestion + indexação via UI)
# ════════════════════════════════════════════════════════════════════════════


class MeetingItemResponse(BaseModel):
    """Dados de uma reunião TL:DV com badge de indexação."""

    id: str
    name: str
    status: str  # completed | processing | failed | pending
    duration: float
    already_indexed: bool


class MeetingListResponse(BaseModel):
    """Lista de reuniões disponíveis no TL:DV."""

    meetings: list[MeetingItemResponse]
    total: int


class SelectivePipelineRequest(BaseModel):
    """Request para iniciar pipeline seletivo de ingestion + indexação."""

    meeting_ids: list[str] = Field(..., min_length=1, description="IDs das reuniões a baixar e indexar")
    force_clean: bool = Field(default=False, description="Se True, apaga todos os dados antes de iniciar")


class SelectivePipelineStartResponse(BaseModel):
    """Response do início do pipeline seletivo."""

    job_id: str
    session_id: str
    total_meetings: int
    status: str = "enqueued"
