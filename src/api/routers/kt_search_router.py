"""Router para endpoints de busca KT.

Endpoints:
- POST /v1/kt-search/ — Busca KT via pipeline RAG (síncrono, retorna insights imediatamente)
"""

from fastapi import APIRouter, Depends

from src.api.schemas.kt_schemas import KTSearchRequest, KTSearchResponse
from src.services.kt_search_service import KTSearchService, get_kt_search_service

router = APIRouter(prefix="/v1/kt-search", tags=["KT Search"])


@router.post("/", response_model=KTSearchResponse)
async def search_kt(
    request: KTSearchRequest,
    service: KTSearchService = Depends(get_kt_search_service),
) -> KTSearchResponse:
    """Executa busca KT via pipeline RAG e retorna resposta com insights."""
    result = service.search(request.query)
    return KTSearchResponse(**result)
