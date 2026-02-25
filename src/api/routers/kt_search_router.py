"""Router para endpoints de busca KT.

Endpoints síncronos (CLI / Teams):
- POST /v1/kt-search/                              — Busca KT via pipeline RAG (retorna resultado imediatamente)

Endpoints de pipeline assíncrono (Streamlit):
- POST /v1/kt-search/pipeline/start                — Inicia pipeline: enfileira enrich_task, retorna session_id + job_id
- POST /v1/kt-search/pipeline/{session_id}/classify  — Enfileira fase 2
- POST /v1/kt-search/pipeline/{session_id}/chromadb  — Enfileira fase 3
- POST /v1/kt-search/pipeline/{session_id}/discover  — Enfileira fase 4
- POST /v1/kt-search/pipeline/{session_id}/select    — Enfileira fase 5
- POST /v1/kt-search/pipeline/{session_id}/insights  — Enfileira fase 6
- GET  /v1/kt-search/pipeline/status/{job_id}        — Consulta status de qualquer job ARQ
- GET  /v1/kt-search/pipeline/{session_id}/result    — Lê resultado final do Redis (404 se não pronto)
"""

import json
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from src.api.schemas.kt_schemas import (
    KTSearchRequest,
    KTSearchResponse,
    PipelineStartRequest,
    PipelineStartResponse,
    StageJobResponse,
    StageStatusResponse,
)
from src.services.kt_search_service import KTSearchService, get_kt_search_service

router = APIRouter(prefix="/v1/kt-search", tags=["KT Search"])


# ════════════════════════════════════════════════════════════════════════════
# ENDPOINT SÍNCRONO (CLI / Teams) — inalterado
# ════════════════════════════════════════════════════════════════════════════


@router.post("/", response_model=KTSearchResponse)
async def search_kt(
    request: KTSearchRequest,
    service: KTSearchService = Depends(get_kt_search_service),
) -> KTSearchResponse:
    """Executa busca KT via pipeline RAG e retorna resposta com insights."""
    result = service.search(request.query)
    return KTSearchResponse(**result)


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE ASSÍNCRONO — início e estágios individuais
# ════════════════════════════════════════════════════════════════════════════


@router.post("/pipeline/start", response_model=PipelineStartResponse)
async def pipeline_start(body: PipelineStartRequest, request: Request) -> PipelineStartResponse:
    """Inicia o pipeline RAG assíncrono.

    Gera um session_id único, enfileira a Fase 1 (enriquecimento da query) e
    retorna o session_id + job_id para polling. O Streamlit usa o session_id para
    enfileirar os estágios subsequentes após cada conclusão.
    """
    session_id = str(uuid.uuid4())
    job = await request.app.state.arq_pool.enqueue_job("kt_search_enrich_task", query=body.query, session_id=session_id)
    return PipelineStartResponse(session_id=session_id, job_id=job.job_id)


@router.post("/pipeline/{session_id}/classify", response_model=StageJobResponse)
async def pipeline_classify(session_id: str, request: Request) -> StageJobResponse:
    """Enfileira a Fase 2 do pipeline: classificação contextual do tipo RAG."""
    job = await request.app.state.arq_pool.enqueue_job("kt_search_classify_task", session_id=session_id)
    return StageJobResponse(session_id=session_id, job_id=job.job_id, stage="classify")


@router.post("/pipeline/{session_id}/chromadb", response_model=StageJobResponse)
async def pipeline_chromadb(session_id: str, request: Request) -> StageJobResponse:
    """Enfileira a Fase 3 do pipeline: busca ChromaDB (5 estratégias + early-exit)."""
    job = await request.app.state.arq_pool.enqueue_job("kt_search_chromadb_task", session_id=session_id)
    return StageJobResponse(session_id=session_id, job_id=job.job_id, stage="chromadb")


@router.post("/pipeline/{session_id}/discover", response_model=StageJobResponse)
async def pipeline_discover(session_id: str, request: Request) -> StageJobResponse:
    """Enfileira a Fase 4 do pipeline: descoberta dinâmica de clientes."""
    job = await request.app.state.arq_pool.enqueue_job("kt_search_discover_task", session_id=session_id)
    return StageJobResponse(session_id=session_id, job_id=job.job_id, stage="discover")


@router.post("/pipeline/{session_id}/select", response_model=StageJobResponse)
async def pipeline_select(session_id: str, request: Request) -> StageJobResponse:
    """Enfileira a Fase 5 do pipeline: seleção inteligente de chunks."""
    job = await request.app.state.arq_pool.enqueue_job("kt_search_select_task", session_id=session_id)
    return StageJobResponse(session_id=session_id, job_id=job.job_id, stage="select")


@router.post("/pipeline/{session_id}/insights", response_model=StageJobResponse)
async def pipeline_insights(session_id: str, request: Request) -> StageJobResponse:
    """Enfileira a Fase 6 do pipeline: geração de insights LLM e resposta final."""
    job = await request.app.state.arq_pool.enqueue_job("kt_search_insights_task", session_id=session_id)
    return StageJobResponse(session_id=session_id, job_id=job.job_id, stage="insights")


# ════════════════════════════════════════════════════════════════════════════
# POLLING E RESULTADO
# ════════════════════════════════════════════════════════════════════════════


@router.get("/pipeline/status/{job_id}", response_model=StageStatusResponse)
async def pipeline_status(job_id: str, request: Request) -> StageStatusResponse:
    """Consulta o status de um job ARQ de estágio do pipeline.

    Retorna arq_status (queued | in_progress | complete | not_found | failed) e
    stage_ready=True quando o job completou E a chave Redis do estágio foi confirmada.
    O session_id é extraído do resultado do job quando disponível.
    """
    from arq.jobs import Job, JobStatus

    job = Job(job_id=job_id, redis=request.app.state.arq_pool)
    job_status = await job.status()
    # .value evita o comportamento de str(StrEnum) em Python 3.11+ que retorna
    # "JobStatus.complete" em vez de "complete"
    arq_status: str = job_status.value

    session_id = ""
    stage_ready = False
    error: str | None = None

    if job_status == JobStatus.complete:
        result_info = await job.result_info()

        if result_info is not None and not result_info.success:
            # Job completou mas falhou (exceção levantada dentro da task)
            arq_status = "failed"
            error = str(result_info.result)
        else:
            result: dict = result_info.result if result_info else {}
            session_id = result.get("session_id", "")
            stage = result.get("stage", "")
            early_exit: bool = result.get("early_exit", False)

            if session_id and stage:
                # Para early-exit no chromadb, a chave pronta é a final
                key = f"kt_search:{session_id}:final" if early_exit else f"kt_search:{session_id}:stage:{stage}"
                exists = await request.app.state.arq_pool.exists(key)
                stage_ready = bool(exists)
            else:
                # session_id ou stage ausentes no resultado — considera ready para não bloquear
                stage_ready = True

    return StageStatusResponse(
        session_id=session_id,
        job_id=job_id,
        arq_status=arq_status,
        stage_ready=stage_ready,
        error=error,
    )


@router.get("/pipeline/{session_id}/result", response_model=KTSearchResponse)
async def pipeline_result(session_id: str, request: Request) -> KTSearchResponse | JSONResponse:
    """Lê o resultado final do pipeline do Redis.

    Retorna 404 se o resultado ainda não estiver disponível (pipeline em andamento).
    """
    key = f"kt_search:{session_id}:final"
    raw = await request.app.state.arq_pool.get(key)

    if raw is None:
        return JSONResponse(
            status_code=404,
            content={"detail": "Resultado do pipeline ainda não disponível. Aguarde a conclusão da Fase 6."},
        )

    data: dict = json.loads(raw)
    return KTSearchResponse(**data)
