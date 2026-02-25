"""Smoke tests — verificam que a stack completa sobe sem erros.

Execução: uv run python -m pytest tests/ -m smoke
Requer: Redis Cloud configurado no .env (REDIS_HOST, REDIS_PORT, REDIS_PASSWORD)
"""

import pytest


@pytest.mark.smoke
def test_fastapi_importa_sem_crash() -> None:
    """FastAPI inicializa sem erros de import ou configuração."""
    from src.api.main import app

    assert app is not None


@pytest.mark.smoke
def test_redis_conecta(require_redis: None) -> None:
    """Redis Cloud responde ao ping."""
    import redis

    from src.config.settings import REDIS_HOST, REDIS_PASSWORD, REDIS_PORT

    client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD if REDIS_PASSWORD else None,
        socket_connect_timeout=3,
    )
    response = client.ping()
    assert response is True


@pytest.mark.smoke
def test_arq_worker_tem_functions(require_redis: None) -> None:
    """WorkerSettings tem pelo menos uma task registrada."""
    from src.tasks.arq_worker import WorkerSettings

    assert hasattr(WorkerSettings, "functions")
    assert len(WorkerSettings.functions) > 0


@pytest.mark.smoke
def test_health_endpoint_responde_200() -> None:
    """GET /health responde 200 OK."""
    from fastapi.testclient import TestClient

    from src.api.main import app

    with TestClient(app) as test_client:
        response = test_client.get("/v1/health")
    assert response.status_code == 200


@pytest.mark.smoke
def test_env_redis_configurado() -> None:
    """Variáveis REDIS_HOST e REDIS_PORT estão presentes no .env."""
    from src.config.settings import REDIS_HOST, REDIS_PORT

    assert REDIS_HOST, "REDIS_HOST não configurado no .env"
    assert REDIS_PORT > 0, f"REDIS_PORT inválido: {REDIS_PORT}"


@pytest.mark.smoke
def test_kt_ingestion_service_instancia() -> None:
    """KTIngestionService pode ser instanciado sem crash."""
    from src.services.kt_ingestion_service import get_kt_ingestion_service

    service = get_kt_ingestion_service()
    assert service is not None


@pytest.mark.smoke
def test_kt_indexing_service_instancia() -> None:
    """KTIndexingService pode ser instanciado sem crash."""
    from src.services.kt_indexing_service import get_kt_indexing_service

    service = get_kt_indexing_service()
    assert service is not None


@pytest.mark.smoke
def test_directory_paths_existem() -> None:
    """Diretórios de DIRECTORY_PATHS existem ou podem ser criados pelo startup."""
    from src.config.settings import DIRECTORY_PATHS

    assert "transcriptions" in DIRECTORY_PATHS
    assert "vector_db" in DIRECTORY_PATHS
    assert "sqlite_db" in DIRECTORY_PATHS
