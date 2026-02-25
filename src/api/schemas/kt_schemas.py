"""Schemas Pydantic para endpoints KT.

Cobre os três domínios:
- kt_search  → KTSearchRequest, KTSearchResponse, pipeline schemas
- kt_ingestion → AsyncJobResponse, JobStatusResponse
- kt_indexing  → AsyncJobResponse, JobStatusResponse, KTIndexingStatusResponse
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
