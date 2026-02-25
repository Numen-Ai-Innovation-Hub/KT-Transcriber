"""Router para endpoints de indexação KT.

Endpoints:
- POST /v1/kt-indexing/run             — Enfileira indexação de JSONs no ChromaDB (async via ARQ)
- GET  /v1/kt-indexing/status          — Status atual do ChromaDB (documentos, clientes)
- GET  /v1/kt-indexing/status/{job_id} — Status de job ARQ específico
"""

from fastapi import APIRouter, Depends, Request

from src.api.schemas.kt_schemas import AsyncJobResponse, JobStatusResponse, KTIndexingStatusResponse
from src.services.kt_indexing_service import KTIndexingService, get_kt_indexing_service

router = APIRouter(prefix="/v1/kt-indexing", tags=["KT Indexing"])


@router.post("/run", response_model=AsyncJobResponse)
async def run_indexing(request: Request) -> AsyncJobResponse:
    """Enfileira job de indexação de JSONs no ChromaDB via ARQ.

    A indexação pode levar minutos — o job é processado em background pelo ARQ worker.
    Use GET /status/{job_id} para acompanhar o progresso.
    """
    job = await request.app.state.arq_pool.enqueue_job("kt_indexing_task")
    return AsyncJobResponse(job_id=job.job_id)


@router.get("/status", response_model=KTIndexingStatusResponse)
async def get_indexing_status(
    service: KTIndexingService = Depends(get_kt_indexing_service),
) -> KTIndexingStatusResponse:
    """Retorna status atual do ChromaDB (total de documentos, clientes indexados, etc.)."""
    info = service.get_status()
    return KTIndexingStatusResponse(
        total_documents=info.get("total_documents", 0),
        collection_name=info.get("collection_name", ""),
        unique_clients=info.get("unique_clients", []),
        embedding_dimensions=info.get("embedding_dimensions", 1536),
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_indexing_job_status(job_id: str, request: Request) -> JobStatusResponse:
    """Consulta status de job de indexação ARQ."""
    from arq.jobs import Job

    job = Job(job_id=job_id, redis=request.app.state.arq_pool)
    job_status = await job.status()
    result: dict | None = None
    if job_status.value == "complete":
        result = await job.result()
    return JobStatusResponse(job_id=job_id, status=job_status.value, result=result)
