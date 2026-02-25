"""
Exception handling - Portável e reutilizável.

Define exceções de aplicação sem acoplar com frameworks específicos.
Não implementa lógica de logging, HTTP handlers ou respostas.

Princípios:
- ApplicationError representa erros esperados/contratuais
- Não force stacktrace (isso é responsabilidade de handlers globais)
- Timezone-aware timestamps (UTC)
- Campos estáveis para OpenAPI
- Zero acoplamento com FastAPI/Flask/etc
"""

from datetime import UTC, datetime
from typing import Any


class ApplicationError(Exception):
    """
    Exceção base para erros de aplicação (esperados/contratuais).

    Representa erros de domínio, validação ou integração que são parte
    do contrato da aplicação. Deve ser capturada por handlers globais
    e convertida em resposta HTTP padronizada.

    Attributes:
        message: Mensagem client-safe (não vaza detalhes internos)
        status_code: Código HTTP sugerido (default: 500)
        error_code: Código estável para clientes (ex: "INVALID_INPUT")
        context: Metadados opcionais para debug/logging (não expostos ao cliente)
        timestamp: Momento do erro (timezone-aware UTC)

    Examples:
        # Erro de validação
        raise ApplicationError(
            "Invalid package format",
            status_code=422,
            error_code="VALIDATION_ERROR",
            context={"field": "package", "value": "INVALID"}
        )

        # Erro de integração
        raise ApplicationError(
            "SAP service unavailable",
            status_code=503,
            error_code="SERVICE_UNAVAILABLE",
            context={"service": "SAP", "operation": "query_packages"}
        )

        # Erro de quota
        raise ApplicationError(
            "API quota exceeded",
            status_code=429,
            error_code="QUOTA_EXCEEDED",
            context={"provider": "Gemini", "limit": "20/day"}
        )

    Usage Guidelines:
        - Logar no máximo UMA VEZ quando criado/capturado (sem stacktrace)
        - Não capturar no router/endpoint (deixe handlers globais lidarem)
        - Sempre usar raise ... from e para preservar cadeia de exceções
        - Handler global converte em resposta HTTP padronizada
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or "INTERNAL_ERROR"
        self.context = context or {}
        self.timestamp = datetime.now(UTC)

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return (
            f"ApplicationError(message={self.message!r}, "
            f"status_code={self.status_code}, "
            f"error_code={self.error_code!r})"
        )


def is_quota_error(exc: Exception) -> bool:
    """
    Detecta erro de quota/rate limit de forma portável.

    Tenta detectar por atributos estruturados primeiro, fallback para substring.
    Útil para centralizar lógica de retry/backoff.

    Args:
        exc: Exceção capturada

    Returns:
        True se for erro de quota/rate limit

    Examples:
        try:
            api_call()
        except Exception as e:
            if is_quota_error(e):
                logger.warning("API quota exceeded, retry later")
            else:
                logger.error(f"API error: {e}")
            raise
    """
    # Tenta detectar por status_code estruturado (ex: requests.HTTPError)
    if hasattr(exc, "status_code") and exc.status_code == 429:
        return True

    # Tenta detectar por response.status_code (ex: requests.Response)
    if hasattr(exc, "response") and hasattr(exc.response, "status_code"):
        if exc.response.status_code == 429:
            return True

    # Fallback: substring na mensagem de erro (Gemini, OpenAI, etc)
    error_msg = str(exc).lower()
    quota_indicators = [
        "resource_exhausted",
        "quota exceeded",
        "rate limit",
        "429",
    ]

    return any(indicator in error_msg for indicator in quota_indicators)
