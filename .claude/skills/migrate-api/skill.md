# SKILL: /migrate-api

**Propósito:** Criar a camada de orquestração — services, routers, tasks e scripts.
Conecta o domínio ao mundo externo (HTTP, filas, CLI).

**Argumento:** sem argumento — opera no projeto atual, processa todos os domínios do plano

**Pré-requisito:** `/migrate-domain` concluído.

---

## Procedimento

### FASE 1 — Services (`src/services/`)

Para cada domínio com necessidade de orquestração, criar `src/services/<nome>_service.py`.

**Padrão obrigatório — Singleton thread-safe:**
```python
import threading
from utils.exception_setup import ApplicationError
from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)

class ExampleService:
    """Serviço de orquestração para <domínio>.

    Singleton thread-safe. Usar get_example_service() para obter instância.
    """

    _instance: "ExampleService | None" = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        # Inicializar componentes do domínio aqui
        pass

    @classmethod
    def get_instance(cls) -> "ExampleService":
        """Retorna instância singleton (double-checked locking)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance


def get_example_service() -> ExampleService:
    """Factory para injeção de dependência nos routers."""
    return ExampleService.get_instance()
```

**Regras do service:**
- Raise `ApplicationError` para erros de domínio — NUNCA retornar dict com erro
- Log sem stacktrace: `logger.warning()` ou `logger.error()` (NUNCA `logger.exception()`)
- NUNCA importar de `src/api/`
- NUNCA `logger.exception()` — apenas global handler em `src/api/main.py` usa isso
- `warm_up()` para modelos LLM pesados — chamar no lifespan de `src/api/main.py`

### FASE 2 — Routers (`src/api/routers/`)

Para cada domínio com endpoints HTTP, criar `src/api/routers/<nome>_router.py`.

**Padrão obrigatório:**
```python
from fastapi import APIRouter, Depends
from src.services.example_service import ExampleService, get_example_service
from src.api.schemas import ExampleRequest, ExampleResponse

router = APIRouter(prefix="/v1/example", tags=["Example"])


@router.post("/", response_model=ExampleResponse)
async def process_example(
    request: ExampleRequest,
    service: ExampleService = Depends(get_example_service),
) -> ExampleResponse:
    """Processa exemplo e retorna resultado."""
    result = service.process(request.data)
    return ExampleResponse(result=result)
```

**Regras do router:**
- ZERO lógica de negócio — delega tudo ao service
- NUNCA capturar `Exception` genérica — o global handler em `src/api/main.py` trata
- NUNCA `logger.exception()` — apenas global handler usa isso
- Schemas Pydantic para request e response (nunca `dict` raw)
- Prefix `/v1/<recurso>` obrigatório

**Registrar em `src/api/main.py`:**
```python
from src.api.routers.example_router import router as example_router
app.include_router(example_router)
```

### FASE 3 — Tasks ARQ (`src/tasks/`)

Criar tasks apenas para operações em que o utilizador **não pode/deve esperar** a resposta HTTP.
O critério é experiência do utilizador e confiabilidade — não tempo absoluto.

**Padrão obrigatório:**
```python
from typing import Any
from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)


async def process_example_task(ctx: dict[str, Any], data: str) -> dict[str, Any]:
    """Task ARQ para processamento assíncrono de exemplo.

    Args:
        ctx: Contexto ARQ (injetado automaticamente).
        data: Dado a processar.

    Returns:
        Resultado do processamento.

    Raises:
        ApplicationError: Propagada para o ARQ framework registrar job como failed.
    """
    logger.info(f"Iniciando task com data={data!r}")

    # Usar service (não importar domínio diretamente)
    from src.services.example_service import get_example_service
    service = get_example_service()
    result = service.process(data)  # ApplicationError propaga — ARQ registra como failed
    logger.info(f"Task concluída com sucesso")
    return {"result": result}
```

**Por que NÃO capturar Exception:** o ARQ framework captura automaticamente exceções não tratadas,
grava o traceback no Redis e marca o job como `failed`. O router de polling (`GET /jobs/{id}`)
lê esse status. Capturar `Exception` genérica e retornar `{"status": "error"}` esconde falhas
reais e viola o princípio Fail-Fast do template.

**Registrar em `src/tasks/arq_worker.py`:**
```python
from src.tasks.example_task import process_example_task

class WorkerSettings:
    functions = [process_example_task, ...]
```

**Regras das tasks:**
- Primeiro parâmetro SEMPRE `ctx: dict[str, Any]`
- NUNCA `asyncio.run()` dentro de task
- Idempotentes — podem ser executadas N vezes com mesmo resultado
- Parâmetros serializáveis (str, int, float, list, dict — nunca objetos Python)
- `arq_worker.py` NÃO deve ter bloco `if __name__ == "__main__":`
  → Entry point exclusivo é `arq src.tasks.arq_worker.WorkerSettings`
  → Bloco `__main__` cria ambiguidade sobre como iniciar o worker e usa API interna do ARQ
    que pode mudar entre versões; remover qualquer bloco herdado do legado
  → Scripts de conveniência para iniciar o worker pertencem em `scripts/`, não em `arq_worker.py`

**Padrão de endpoint assíncrono no router:**
```python
@router.post("/async", response_model=AsyncJobResponse)
async def enqueue_example(request: ExampleRequest) -> AsyncJobResponse:
    """Enfileira processamento assíncrono e retorna job_id."""
    job = await arq_pool.enqueue_job("process_example_task", request.data)
    return AsyncJobResponse(job_id=job.job_id)


@router.get("/async/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Consulta status de job assíncrono."""
    job = await arq_pool.fetch_job(job_id)
    return JobStatusResponse(status=job.status, result=job.result)
```

### FASE 4 — Scripts (`scripts/`)

Para operações pontuais/administrativas fora do workflow HTTP:

**Padrão obrigatório:**
```python
"""Script: <descrição em uma linha>

Execução: .venv/Scripts/python.exe scripts/<nome>.py
"""
import sys
from pathlib import Path

# Garantir que src/ está no path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.services.example_service import get_example_service


def main() -> None:
    """Ponto de entrada do script."""
    service = get_example_service()
    # ...


if __name__ == "__main__":
    main()
```

**Regras dos scripts:**
- `if __name__ == "__main__":` obrigatório
- Importa de services/domínio — NUNCA duplica lógica
- NÃO sobrescrever `scripts/auto_init.py` (é do template)
- `load_dotenv()` no início (scripts não passam pelo lifespan do FastAPI)

### FASE 5 — Validação

1. `python -c "from src.api.main import app"` — import sem crash
2. Verificar que todos os routers estão registrados em `src/api/main.py`
3. Verificar que todas as tasks estão em `WorkerSettings.functions`
4. Verificar ausência de `main.py` na raiz do projeto:
   - Se existir: remover — entry point da aplicação é exclusivamente `uvicorn src.api.main:app`
   - Exceção: projetos CLI puro (Typer sem FastAPI) podem ter `main.py` na raiz
5. `ruff check src scripts` + `mypy --config-file=pyproject.toml src scripts`

**Critério de conclusão:** Todos os endpoints/operações do legado têm equivalente no projeto migrado.
Sem `main.py` na raiz. Sem `if __name__ == "__main__"` em `arq_worker.py`.

---

## FASE FINAL — Registro de Feedback

Ao concluir, registrar entrada em `.claude/skills-feedback/migrate-api.md`:

```markdown
## [YYYY-MM-DD] Projeto: <nome>

**Services criados:** <N>
**Routers criados:** <N>
**Tasks ARQ criadas:** <N>
**Scripts criados:** <N>

**O que funcionou bem:**
- <ponto positivo>

**O que foi difícil:**
- <ponto de atrito>

**Sugestão de melhoria para esta SKILL:**
- <proposta>
```