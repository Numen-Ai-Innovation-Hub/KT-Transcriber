"""
FastAPI application - Backend HTTP.

Endpoints:
- GET /health - Health check
- GET / - Root endpoint
- TODO: Adicionar routers customizados

Global Exception Handlers:
- ApplicationError → JSON padronizado
- RequestValidationError → Validação Pydantic
- Exception → 500 sem leak de detalhes
"""

import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from src.api.routers import health
from utils.exception_setup import ApplicationError
from utils.logger_setup import get_logger

# Logger criado ANTES de configurar LOG_DIR (fallback tolerante permite isso)
logger = get_logger(__name__)

# LOG_DIR para configuração no lifespan
LOG_DIR = Path(__file__).parent.parent.parent / "logs"


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:  # noqa: ARG001 - app usado pelo FastAPI
    """
    Lifespan event handler para inicialização e shutdown do FastAPI.

    Startup:
    - Inicializa aplicação (logging, diretórios) via initialize_application()
    - TODO: warm_up() de services com modelos pesados (elimina cold-start)
    - TODO: ARQ pool para endpoints assíncronos

    Shutdown:
    - TODO: Fechar ARQ pool se criado
    """
    from src.config.startup import initialize_application

    initialize_application()
    logger.info("Serviços inicializados com sucesso")

    # TODO: warm_up() de services com modelos LLM pesados (elimina cold-start)
    # from src.services.example_service import get_example_service
    # get_example_service().warm_up()

    # TODO: ARQ pool para endpoints assíncronos (descomentar se usar ARQ)
    # from arq.connections import RedisSettings, create_pool
    # app.state.arq_pool = await create_pool(RedisSettings(...))

    yield

    # TODO: Fechar ARQ pool (descomentar se usar ARQ)
    # await app.state.arq_pool.aclose()
    logger.info("Encerrando serviços da aplicação")


# Criar app FastAPI
app = FastAPI(
    title="Python FastAPI Template",
    version="1.0.0",
    description="Template base para projetos Python + FastAPI + ARQ + Redis",
    lifespan=lifespan,
)

# CORS - Lista explícita de origins permitidos (dev + prod)
ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173,http://127.0.0.1:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Lista explícita (não wildcard)
    allow_credentials=False,  # True apenas se usar cookies/auth
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "X-Request-ID",  # Header customizado para tracking
    ],
    expose_headers=["*"],
)


# ════════════════════════════════════════════════════════════════════════════
# GLOBAL EXCEPTION HANDLERS (ÚNICA FONTE DE logger.exception)
# ════════════════════════════════════════════════════════════════════════════


@app.exception_handler(ApplicationError)
async def application_error_handler(request: Request, exc: ApplicationError) -> JSONResponse:
    """
    Handler para ApplicationError (erros de domínio).

    ÚNICO lugar onde logger.exception() é permitido para erros esperados.
    """
    request_id = str(uuid.uuid4())

    # Log com stacktrace APENAS aqui
    logger.exception(
        f"ApplicationError capturado: {exc.message} "
        f"(status={exc.status_code}, code={exc.error_code}, request_id={request_id})"
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": "application_error",
                "code": exc.error_code,
                "message": exc.message,
                "timestamp": datetime.now(UTC).isoformat(),
                "request_id": request_id,
                "context": exc.context,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handler para erros de validação Pydantic."""
    request_id = str(uuid.uuid4())

    # Sanitizar erros (remover bytes e outros objetos não-serializáveis)
    errors: list[dict[str, Any]] = []
    errors_summary: list[str] = []

    for error in exc.errors():
        sanitized_error: dict[str, Any] = {}
        for key, value in error.items():
            if isinstance(value, bytes):
                sanitized_error[key] = f"<bytes: {len(value)} bytes>"
            elif isinstance(value, str):
                sanitized_error[key] = value
            elif isinstance(value, (int, float, bool, type(None))):
                sanitized_error[key] = value
            elif isinstance(value, (list, tuple)):
                sanitized_error[key] = [str(v) for v in value]
            else:
                sanitized_error[key] = str(value)

        errors.append(sanitized_error)

        # Cria resumo para log
        error_type = error.get("type", "unknown")
        error_loc = error.get("loc", [])
        error_msg = error.get("msg", "")
        input_value = error.get("input")

        if isinstance(input_value, str) and len(input_value) > 200:
            input_desc = f"<string com {len(input_value)} caracteres>"
        elif isinstance(input_value, dict) and any(isinstance(v, str) and len(v) > 200 for v in input_value.values()):
            input_desc = f"<dict com {len(input_value)} campos, alguns com texto longo>"
        else:
            input_desc = str(input_value)[:100]

        errors_summary.append(
            f"{error_type} em {'.'.join(str(x) for x in error_loc)}: {error_msg} (input: {input_desc})"
        )

    endpoint_info = f"{request.method} {request.url.path}"
    logger.warning(
        f"Erro de validação em {endpoint_info} ({len(errors)} erro(s)): "
        f"{'; '.join(errors_summary)} (request_id={request_id})"
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "type": "validation_error",
                "code": "VALIDATION_ERROR",
                "message": "Erro de validação nos dados de entrada",
                "timestamp": datetime.now(UTC).isoformat(),
                "request_id": request_id,
                "context": {"details": errors},
            }
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handler para exceções não tratadas (500).

    ÚNICO lugar onde logger.exception() é permitido para erros inesperados.
    NÃO vaza detalhes da exceção na resposta (segurança).
    """
    request_id = str(uuid.uuid4())

    # Log com stacktrace APENAS aqui
    logger.exception(f"Erro inesperado: {type(exc).__name__} (request_id={request_id})")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "type": "internal_error",
                "code": "INTERNAL_ERROR",
                "message": "Erro interno do servidor",
                "timestamp": datetime.now(UTC).isoformat(),
                "request_id": request_id,
            }
        },
    )


# ════════════════════════════════════════════════════════════════════════════
# ROUTERS
# ════════════════════════════════════════════════════════════════════════════

app.include_router(health.router)

# TODO: Adicionar routers customizados aqui
# Exemplo:
# from src.api.routers import users, tasks
# app.include_router(users.router, prefix="/v1/users", tags=["Users"])
# app.include_router(tasks.router, prefix="/v1/tasks", tags=["Tasks"])


# ════════════════════════════════════════════════════════════════════════════
# BUILT-IN ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint - informações básicas da API."""
    return {
        "name": "Python FastAPI Template",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/v1/health",
    }
