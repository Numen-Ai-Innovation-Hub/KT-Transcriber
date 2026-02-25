"""Serviço de orquestração para busca KT.

Singleton thread-safe. Encapsula SearchEngine (pipeline RAG 5 estágios).
Usar get_kt_search_service() para obter a instância.
"""

import threading
from typing import Any

from utils.exception_setup import ApplicationError
from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)


class KTSearchService:
    """Serviço de busca KT via pipeline RAG 5 estágios.

    Singleton thread-safe. Encapsula SearchEngine:
    Query Enrichment → Classification → ChromaDB Search → Chunk Selection → Insights Generation.

    O SearchEngine é inicializado na criação do singleton (warm-up no lifespan do FastAPI).
    """

    _instance: "KTSearchService | None" = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        """Inicializa o serviço e instancia o SearchEngine."""
        from src.kt_search.search_engine import SearchEngine

        self._engine: SearchEngine = SearchEngine()
        logger.info("KTSearchService inicializado com SearchEngine")

    @classmethod
    def get_instance(cls) -> "KTSearchService":
        """Retorna instância singleton (double-checked locking)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ────────────────────────────────────────────────────────────────────────
    # OPERAÇÕES PÚBLICAS
    # ────────────────────────────────────────────────────────────────────────

    @property
    def components(self) -> dict[str, Any]:
        """Expõe componentes do pipeline para as ARQ tasks de busca."""
        return {
            "query_enricher": self._engine.query_enricher,
            "query_classifier": self._engine.query_classifier,
            "chromadb_executor": self._engine._chromadb_executor,
            "dynamic_client_manager": self._engine.dynamic_client_manager,
            "chunk_selector": self._engine.chunk_selector,
            "insights_agent": self._engine.insights_agent,
            "response_builder": self._engine._response_builder,
        }

    def search(self, query: str) -> dict[str, Any]:
        """Executa busca KT via pipeline RAG.

        Args:
            query: Pergunta ou consulta sobre as transcrições KT (mínimo 3 caracteres).

        Returns:
            Dicionário com answer, contexts, query_type, processing_time, success.

        Raises:
            ApplicationError: Se query for vazia ou a busca falhar.
        """
        if not query.strip():
            raise ApplicationError(
                message="Query não pode ser vazia",
                status_code=422,
                error_code="VALIDATION_ERROR",
            )

        response = self._engine.search(query)

        if not response.success:
            raise ApplicationError(
                message=response.error_message or "Erro durante a busca KT",
                status_code=503,
                error_code="SERVICE_UNAVAILABLE",
            )

        return {
            "answer": response.intelligent_response.get("answer", ""),
            "contexts": response.contexts,
            "query_type": response.query_type,
            "processing_time": response.processing_time,
            "success": response.success,
        }


def get_kt_search_service() -> KTSearchService:
    """Factory para injeção de dependência nos routers."""
    return KTSearchService.get_instance()
