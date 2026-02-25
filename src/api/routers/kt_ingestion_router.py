"""Router para endpoints de ingestion KT.

Endpoints:
- POST /v1/kt-ingestion/run    — Enfileira ingestion de reuniões TL:DV (async via ARQ)
- GET  /v1/kt-ingestion/status/{job_id} — Consulta status do job ARQ
"""

from fastapi import APIRouter, Request

from src.api.schemas.kt_schemas import AsyncJobResponse, JobStatusResponse

router = APIRouter(prefix="/v1/kt-ingestion", tags=["KT Ingestion"])


@router.post("/run", response_model=AsyncJobResponse)
async def run_ingestion(request: Request) -> AsyncJobResponse:
    """Enfileira job de ingestion de reuniões TL:DV via ARQ.

    A ingestion pode levar minutos — o job é processado em background pelo ARQ worker.
    Use GET /run/status/{job_id} para acompanhar o progresso.
    """
    job = await request.app.state.arq_pool.enqueue_job("kt_ingestion_task")
    return AsyncJobResponse(job_id=job.job_id)


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_ingestion_status(job_id: str, request: Request) -> JobStatusResponse:
    """Consulta status de job de ingestion ARQ."""
    from arq.jobs import Job

    job = Job(job_id=job_id, redis=request.app.state.arq_pool)
    job_status = await job.status()
    result: dict | None = None
    if str(job_status) == "complete":
        result = await job.result()
    return JobStatusResponse(job_id=job_id, status=str(job_status), result=result)
