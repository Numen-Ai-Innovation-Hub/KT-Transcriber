# SKILL: /migrate-tests

**Propósito:** Garantir que o projeto migrado funciona — em três dimensões distintas:
unit tests (lógica isolada), smoke test (stack sobe), e2e test (fluxo completo).

**Argumento:** sem argumento — opera no projeto atual, gera testes para todos os módulos

**Pré-requisito:** `/migrate-api` concluído.

---

## Três Dimensões Obrigatórias

### DIMENSÃO 1 — Unit Tests (`tests/test_<módulo>.py`)

**Passo crítico:** Ler a implementação ANTES de escrever qualquer assert.

**Por quê:** Asserts incorretos vêm de suposições sobre o contrato real. A implementação
pode retornar valores em português, usar defaults diferentes do esperado, ou ter
comportamentos em edge cases não óbvios.

**Checklist por módulo:**
1. Ler o arquivo de implementação completamente
2. Registrar: idioma dos valores de retorno, defaults de parâmetros, edge cases
3. Escrever asserts baseados no contrato real (não no esperado)

**Padrão de teste:**
```python
"""Testes unitários para <módulo>."""
import pytest
from unittest.mock import MagicMock, patch

# ✅ Helpers inline — não importar de conftest
def make_test_data(content: str = "exemplo") -> dict:
    return {"content": content, "metadata": {}}


class TestExampleProcessor:
    """Testes para ExampleProcessor."""

    def test_process_retorna_resultado_esperado(self) -> None:
        """Verifica que process() retorna resultado correto para input válido."""
        from src.example_domain.processor import ExampleProcessor
        processor = ExampleProcessor()
        result = processor.process("input válido")
        assert result["status"] == "success"  # verificado na implementação

    def test_process_levanta_application_error_para_input_vazio(self) -> None:
        """Verifica que process() levanta ApplicationError para input vazio."""
        from src.example_domain.processor import ExampleProcessor
        from utils.exception_setup import ApplicationError
        processor = ExampleProcessor()
        with pytest.raises(ApplicationError) as exc_info:
            processor.process("")
        assert exc_info.value.status_code == 422

    @patch("src.example_domain.processor.external_api_call")
    def test_process_com_dependencia_externa_mockada(self, mock_api: MagicMock) -> None:
        """Verifica comportamento com API externa mockada."""
        mock_api.return_value = {"data": "resultado mockado"}
        from src.example_domain.processor import ExampleProcessor
        processor = ExampleProcessor()
        result = processor.process("input")
        assert result is not None
        mock_api.assert_called_once()
```

**Regras dos unit tests:**
- NÃO importar de `tests.conftest` — helpers inline no próprio arquivo
- Mocks para qualquer dependência externa (API, filesystem, Redis)
- Executados com `pytest tests/` (sem marca — devem ser rápidos, zero I/O externo)
- Atualizar `conftest.py` com novas chaves de `DIRECTORY_PATHS` se necessário:
  ```python
  # Em tests/conftest.py — adicionar novos paths de dados de teste
  @pytest.fixture
  def test_data_dir(tmp_path: Path) -> Path:
      return tmp_path / "test_data"
  ```

**Regras de scope de fixtures:**

- Fixtures com `scope="module"` ou `scope="session"` NÃO podem depender de fixtures
  com `scope="function"` (default) — pytest falha com `ScopeError` se um teste combinar
  fixtures incompatíveis
- Fixtures `autouse=True` com scope `function` são aplicadas a **todos** os testes do projeto
  — usar apenas para isolamento universal (ex: `tmp_path`, `monkeypatch` de env vars)
  e não para mocks de dependências específicas
- Regra prática: fixtures de infraestrutura (TestClient, conexão DB) devem ter
  `scope="function"` a menos que sejam explicitamente stateless e idempotentes
- Verificar compatibilidade de scope sempre que uma fixture declara outra fixture como argumento

**Anti-padrões de isolamento:**

- **NUNCA** usar `monkeypatch` e `unittest.mock.patch` para o mesmo alvo no mesmo teste
  — o último a executar ganha; o comportamento é não intencional e confuso
  — escolher um mecanismo por teste: `monkeypatch` (via fixture) OU `patch` (contextmanager)
  — preferir `monkeypatch` via fixture (cleanup automático, mais idiomático em pytest)

- **NUNCA** chamar `_reset_singleton()` em `setup_method` E em fixture `autouse` para o mesmo objeto
  — duplicação de reset pode mascarar dependências entre testes
  — um único ponto de reset por teste: preferir fixture com `autouse=True` e `scope="function"`

### DIMENSÃO 2 — Smoke Test (`tests/test_smoke.py`)

Marcado com `@pytest.mark.smoke`. Verifica que a stack completa sobe sem erros.

```python
"""Smoke tests — verificam que a stack completa sobe sem erros.

Execução: pytest tests/ -m smoke
Requer: Redis Cloud configurado no .env (REDIS_HOST, REDIS_PORT, REDIS_PASSWORD)
"""
import pytest
import redis


@pytest.mark.smoke
def test_fastapi_importa_sem_crash() -> None:
    """FastAPI inicializa sem erros de import ou configuração."""
    from src.api.main import app
    assert app is not None


@pytest.mark.smoke
def test_redis_conecta() -> None:
    """Redis Cloud responde ao ping."""
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
def test_arq_worker_conecta() -> None:
    """ARQ worker consegue conectar ao Redis."""
    from src.tasks.arq_worker import WorkerSettings
    assert hasattr(WorkerSettings, "functions")
    assert len(WorkerSettings.functions) > 0


@pytest.mark.smoke
def test_health_endpoint_responde_200() -> None:
    """GET /health responde 200 OK."""
    from fastapi.testclient import TestClient
    from src.api.main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200


@pytest.mark.smoke
def test_env_carregado_corretamente() -> None:
    """Variáveis obrigatórias do .env estão presentes."""
    from src.config.settings import REDIS_HOST, REDIS_PORT
    assert REDIS_HOST, "REDIS_HOST não configurado no .env"
    assert REDIS_PORT > 0, "REDIS_PORT inválido"
```

**Executar com:** `pytest tests/ -m smoke`

### DIMENSÃO 3 — E2E Test (`tests/test_e2e.py`)

Marcado com `@pytest.mark.e2e`. Testa fluxos completos de utilizador real.

```python
"""Testes E2E — fluxos completos com stack real rodando.

Execução: pytest tests/ -m e2e
Requer: FastAPI + Redis Cloud + ARQ Worker rodando simultaneamente
"""
import time
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client() -> TestClient:
    from src.api.main import app
    return TestClient(app)


@pytest.mark.e2e
def test_fluxo_sincrono_completo(client: TestClient) -> None:
    """POST /v1/example → processa → retorna resultado."""
    response = client.post("/v1/example/", json={"data": "input de teste"})
    assert response.status_code == 200
    result = response.json()
    assert "result" in result


@pytest.mark.e2e
def test_fluxo_assincrono_completo(client: TestClient) -> None:
    """POST /v1/example/async → job_id → polling → resultado."""
    # Enfileira
    response = client.post("/v1/example/async", json={"data": "input assíncrono"})
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert job_id

    # Poll até completar (max 30s)
    for _ in range(30):
        status_response = client.get(f"/v1/example/async/jobs/{job_id}")
        assert status_response.status_code == 200
        status = status_response.json()["status"]
        if status in ("complete", "failed"):
            break
        time.sleep(1)

    assert status == "complete"
    assert status_response.json()["result"] is not None
```

**Regras dos E2E tests:**
- Usa stack real (FastAPI + Redis Cloud + ARQ rodando) — sem mocks de infraestrutura
- **O e2e DEVE cobrir o fluxo principal de negócio do projeto** — não apenas health/listing
  - Identificar: qual é o fluxo central? (ex: processar documento → gerar questão → validar resposta)
  - Esse fluxo deve ter pelo menos 1 teste e2e completo ponta a ponta
  - Criar `tests/fixtures/` com arquivo real de teste se o fluxo principal exigir (ex: PDF pequeno)
- **Classificação correta:** teste que valida apenas entrada inválida (4xx sem tocar infraestrutura)
  NÃO é e2e — é unit test ou smoke. E2e pressupõe que Redis + ARQ + I/O real estão envolvidos
- `@pytest.mark.e2e` em todos os testes desta dimensão
- **Executar com:** `pytest tests/ -m e2e`

---

## Ordem de Execução

```
# 1. Unit tests — rápidos, zero I/O externo
pytest tests/

# 2. Smoke test — com Redis rodando
pytest tests/ -m smoke

# 3. E2E — com FastAPI + Redis + ARQ rodando
pytest tests/ -m e2e
```

**Critério de conclusão:**
- `pytest tests/` — todos os unit tests passam
- `pytest tests/ -m smoke` — stack sobe e responde
- `pytest tests/ -m e2e` — fluxos completos funcionam
- `pyproject.toml` tem `pythonpath = ["."]` em `[tool.pytest.ini_options]`
  → Sem isso, `pytest tests/` falha no Windows com `ModuleNotFoundError: No module named 'src'`
- `pyproject.toml` tem markers `smoke` e `e2e` declarados em `[tool.pytest.ini_options]`:
  ```toml
  [tool.pytest.ini_options]
  pythonpath = ["."]
  markers = [
      "smoke: testes que verificam que a stack sobe sem erros (requer Redis)",
      "e2e: testes de fluxo completo (requer FastAPI + Redis + ARQ rodando)",
  ]
  ```
- Relatório de cobertura: nenhum arquivo de domínio com Stmts > 50 e cobertura < 20%
  → Arquivos com cobertura próxima de zero são sinal de código morto — remover ou criar testes
  → Verificar com: `pytest tests/ --cov=src --cov-report=term-missing`

---

## FASE FINAL — Registro de Feedback

Ao concluir, registrar entrada em `.claude/skills-feedback/migrate-tests.md`:

```markdown
## [YYYY-MM-DD] Projeto: <nome>

**Unit tests criados:** <N> testes em <N> arquivos
**Smoke tests criados:** <N> verificações
**E2E tests criados:** <N> fluxos

**O que funcionou bem:**
- <ponto positivo>

**O que foi difícil:**
- <ponto de atrito (ex: mocks complexos, timing em E2E)>

**Sugestão de melhoria para esta SKILL:**
- <proposta>
```