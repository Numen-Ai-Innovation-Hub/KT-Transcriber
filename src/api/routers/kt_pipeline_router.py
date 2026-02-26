"""Router FastAPI para pipeline seletivo KT (ingestion + indexação via UI).

Endpoints:
- GET  /v1/kt-pipeline/meetings    — Lista reuniões TL:DV com badge de indexação
- POST /v1/kt-pipeline/start       — Inicia pipeline seletivo via ARQ
- GET  /v1/kt-pipeline/status/{id} — Polling de status do job
"""

import uuid

from arq.jobs import Job
from fastapi import APIRouter, Request

from src.api.schemas.kt_schemas import (
    JobStatusResponse,
    MeetingListResponse,
    SelectivePipelineRequest,
    SelectivePipelineStartResponse,
)
from src.services.kt_ingestion_service import get_kt_ingestion_service
from utils.exception_setup import ApplicationError

router = APIRouter(prefix="/v1/kt-pipeline", tags=["KT Pipeline"])


@router.get("/meetings", response_model=MeetingListResponse)
async def list_meetings() -> MeetingListResponse:
    """Lista todas as reuniões disponíveis no TL:DV.

    Cada reunião inclui already_indexed=True se o JSON já estiver em
    data/transcriptions/, indicando que foi baixada anteriormente.
    """
    service = get_kt_ingestion_service()
    meetings = service.list_meetings_with_status()
    return MeetingListResponse(meetings=meetings, total=len(meetings))


@router.post("/start", response_model=SelectivePipelineStartResponse)
async def start_selective_pipeline(
    body: SelectivePipelineRequest,
    request: Request,
) -> SelectivePipelineStartResponse:
    """Enfileira job ARQ para pipeline seletivo (ingestion + indexação).

    O job kt_selective_pipeline_task executa em sequência:
    1. force_clean (opcional) — apaga dados existentes
    2. Ingestion seletiva dos meeting_ids fornecidos
    3. Indexação incremental no ChromaDB
    """
    if request.app.state.arq_pool is None:
        raise ApplicationError(
            message="Redis indisponível — não é possível enfileirar jobs",
            status_code=503,
            error_code="SERVICE_UNAVAILABLE",
        )

    session_id = str(uuid.uuid4())
    job = await request.app.state.arq_pool.enqueue_job(
        "kt_selective_pipeline_task",
        meeting_ids=body.meeting_ids,
        session_id=session_id,
        force_clean=body.force_clean,
    )
    return SelectivePipelineStartResponse(
        job_id=job.job_id,
        session_id=session_id,
        total_meetings=len(body.meeting_ids),
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_pipeline_status(job_id: str, request: Request) -> JobStatusResponse:
    """Consulta status de um job ARQ do pipeline seletivo."""
    job = Job(job_id=job_id, redis=request.app.state.arq_pool)
    job_status = await job.status()

    result: dict | None = None
    error: str | None = None
    status_str = job_status.value if hasattr(job_status, "value") else str(job_status)

    if status_str == "complete":
        result_info = await job.result_info()
        if result_info is not None and not result_info.success:
            status_str = "failed"
            error = str(result_info.result)
        elif result_info is not None:
            result = result_info.result

    return JobStatusResponse(
        job_id=job_id,
        status=status_str,
        result=result,
        error=error,
    )
