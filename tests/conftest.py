"""
Pytest fixtures para testes.

Este arquivo contém fixtures compartilhados entre todos os testes do projeto.
"""

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# ════════════════════════════════════════════════════════════════════════════
# FASTAPI CLIENT FIXTURE
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def client() -> TestClient:
    """
    Fixture que retorna TestClient do FastAPI.

    Uso:
        def test_endpoint(client):
            response = client.get("/health")
            assert response.status_code == 200

    Returns:
        TestClient configurado
    """
    from src.api.main import app

    return TestClient(app)


# ════════════════════════════════════════════════════════════════════════════
# ISOLATED TEST DIRECTORIES (Temporary Paths)
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def isolated_test_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    """
    Fixture que isola testes usando diretórios temporários.

    Sobrescreve DIRECTORY_PATHS de settings.py com tmp_path para garantir
    que testes não afetem dados reais. Auto-cleanup após teste.

    IMPORTANTE: As chaves de temp_dirs DEVEM espelhar DIRECTORY_PATHS de settings.py.
    Ver regra completa no comentário abaixo e em tests/CLAUDE.md.

    Uso:
        def test_file_creation(isolated_test_dirs):
            # isolated_test_dirs é tmp_path
            file = isolated_test_dirs / "test.txt"
            file.write_text("test")
            assert file.exists()

    Args:
        tmp_path: Fixture pytest que fornece Path temporário
        monkeypatch: Fixture pytest para monkey-patching

    Yields:
        Path temporário isolado
    """
    # Importar settings DEPOIS de monkeypatch para pegar valores corretos
    from src.config import settings

    # REGRA OBRIGATÓRIA: As chaves aqui DEVEM ser idênticas às chaves de
    # DIRECTORY_PATHS em src/config/settings.py.
    # Ao adicionar/renomear chave em DIRECTORY_PATHS → atualizar aqui também.
    # Chaves inventadas fazem o monkeypatch silenciar erros reais de path.
    temp_dirs: dict[str, Path] = {
        "sqlite_db": tmp_path / "sqlite_db",
        "vector_db": tmp_path / "vector_db",
        "transcriptions": tmp_path / "transcriptions",
    }

    for temp_dir in temp_dirs.values():
        temp_dir.mkdir(parents=True, exist_ok=True)

    # Monkeypatch DIRECTORY_PATHS
    monkeypatch.setattr(settings, "DIRECTORY_PATHS", temp_dirs)

    # Monkeypatch LOG_DIR para tmp_path (evita criar logs/ durante testes)
    monkeypatch.setattr(settings, "LOG_DIR", tmp_path / "logs")
    (tmp_path / "logs").mkdir(exist_ok=True)

    yield tmp_path

    # Cleanup automático pelo pytest (tmp_path é auto-removido)


# ════════════════════════════════════════════════════════════════════════════
# FIXTURES DE INFRAESTRUTURA (smoke / e2e)
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def require_redis() -> None:
    """
    Fixture que verifica disponibilidade do Redis (Cloud ou local) antes de testes smoke/e2e.

    Faz pytest.skip se Redis não estiver acessível (credenciais ausentes ou serviço indisponível).

    Uso obrigatório em todos os testes smoke e e2e:
        def test_algo(require_redis):
            ...
    """
    import redis

    from src.config.settings import REDIS_HOST, REDIS_PASSWORD, REDIS_PORT

    try:
        r = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD if REDIS_PASSWORD else None,
            socket_connect_timeout=2,
        )
        r.ping()
    except Exception as e:
        pytest.skip(
            f"Redis não disponível em {REDIS_HOST}:{REDIS_PORT} — {e}. Configure .env com credenciais Redis Cloud."
        )


# ════════════════════════════════════════════════════════════════════════════
# SINGLETON RESET HELPER
# ════════════════════════════════════════════════════════════════════════════


def _reset_all_singletons() -> None:
    """
    Helper para resetar todos os singletons entre testes (DRY).

    IMPORTANTE: Adicionar aqui TODOS os singletons do projeto.

    Uso em teste:
        from tests.conftest import _reset_all_singletons

        def test_singleton_isolation():
            _reset_all_singletons()  # Reset antes do teste
            service = get_my_service()
            # ... teste ...
    """
    from src.services.kt_indexing_service import KTIndexingService
    from src.services.kt_ingestion_service import KTIngestionService
    from src.services.kt_search_service import KTSearchService

    KTIngestionService._instance = None  # type: ignore[attr-defined]
    KTIndexingService._instance = None  # type: ignore[attr-defined]
    KTSearchService._instance = None  # type: ignore[attr-defined]


# ════════════════════════════════════════════════════════════════════════════
# ENV VARIABLES FIXTURES
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def test_env_vars() -> dict[str, str]:
    """
    Fixture que retorna variáveis de ambiente para testes.

    Returns:
        Dict com env vars de teste
    """
    return {
        "APP_ENVIRONMENT": "development",
        "LOG_LEVEL": "DEBUG",
        # TODO: Adicionar variáveis de ambiente específicas do projeto
    }


@pytest.fixture(autouse=True, scope="session")
def set_test_env_vars(test_env_vars: dict[str, str]) -> None:
    """
    Fixture que configura env vars para todos os testes.

    Rodada automaticamente uma vez por sessão de testes.

    Args:
        test_env_vars: Dict com env vars de teste
    """
    for key, value in test_env_vars.items():
        os.environ.setdefault(key, value)
