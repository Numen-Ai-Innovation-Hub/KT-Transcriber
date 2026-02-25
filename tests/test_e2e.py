"""Testes E2E — fluxos completos com stack real rodando.

Execução: uv run python -m pytest tests/ -m e2e
Requer: FastAPI + Redis Cloud + ARQ Worker rodando simultaneamente
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

# ════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def client(require_redis: None) -> Generator[TestClient, None, None]:
    """TestClient com stack completa (requer Redis).

    Usa context manager para garantir que o lifespan rode
    e app.state.arq_pool seja inicializado.
    """
    from src.api.main import app

    with TestClient(app) as test_client:
        yield test_client


# ════════════════════════════════════════════════════════════════════════════
# E2E — Ingestion
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
def test_e2e_kt_ingestion_enfileira_job(client: TestClient) -> None:
    """POST /v1/kt-ingestion/run enfileira job e retorna job_id."""
    payload = {
        "client_name": "ClienteE2E",
        "meeting_id": "mtg-e2e-test-001",
    }
    response = client.post("/v1/kt-ingestion/run", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert "job_id" in body
    assert body["job_id"]


@pytest.mark.e2e
def test_e2e_kt_ingestion_status_job_invalido_retorna_404_ou_pending(client: TestClient) -> None:
    """GET /v1/kt-ingestion/status/{job_id} com ID inválido retorna 404 ou status pending."""
    response = client.get("/v1/kt-ingestion/status/job-inexistente-xyz")
    # ARQ retorna o status do job — pode ser not found (404) ou unknown
    assert response.status_code in (200, 404)


# ════════════════════════════════════════════════════════════════════════════
# E2E — Indexing
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
def test_e2e_kt_indexing_enfileira_job(client: TestClient) -> None:
    """POST /v1/kt-indexing/run enfileira job de indexação e retorna job_id."""
    response = client.post("/v1/kt-indexing/run", json={})
    assert response.status_code == 200

    body = response.json()
    assert "job_id" in body
    assert body["job_id"]


@pytest.mark.e2e
def test_e2e_kt_indexing_status_geral(client: TestClient) -> None:
    """GET /v1/kt-indexing/status retorna status da indexação."""
    response = client.get("/v1/kt-indexing/status")
    assert response.status_code == 200


# ════════════════════════════════════════════════════════════════════════════
# E2E — Search (fluxo principal de negócio)
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
def test_e2e_kt_search_query_basica_retorna_resposta(client: TestClient) -> None:
    """POST /v1/kt-search/ com query válida retorna SearchResponse estruturada.

    Este é o fluxo principal de negócio: query → enriquecimento → classificação
    → ChromaDB → seleção → resposta.
    """
    payload = {"query": "quais módulos SAP foram discutidos nas reuniões?"}
    response = client.post("/v1/kt-search/", json=payload)

    # 200 esperado; se ChromaDB vazio, pode retornar 200 com lista vazia
    assert response.status_code == 200

    body = response.json()
    # Verificar estrutura da resposta conforme SearchResponse
    assert "success" in body or "query_type" in body or "intelligent_response" in body


@pytest.mark.e2e
def test_e2e_kt_search_query_vazia_retorna_erro_validacao(client: TestClient) -> None:
    """POST /v1/kt-search/ com query vazia retorna erro 422 de validação."""
    payload = {"query": ""}
    response = client.post("/v1/kt-search/", json=payload)

    # Query vazia deve falhar na validação Pydantic ou no domínio
    assert response.status_code in (422, 400)


@pytest.mark.e2e
def test_e2e_health_check_com_stack_rodando(client: TestClient) -> None:
    """GET /health confirma que stack está funcionando durante E2E."""
    response = client.get("/v1/health")
    assert response.status_code == 200
