"""Router para health checks e status do sistema."""

from fastapi import APIRouter

from src.config.settings import REDIS_HOST, REDIS_PORT

router = APIRouter(prefix="/v1", tags=["Health"])


# ════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════


@router.get("/health")
async def health_check() -> dict[str, str | dict[str, str | int]]:
    """
    Health check endpoint - verifica se aplicação está funcionando.

    Returns:
        Status da aplicação e serviços configurados
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "services": {
            "redis": f"{REDIS_HOST}:{REDIS_PORT}",
        },
    }
