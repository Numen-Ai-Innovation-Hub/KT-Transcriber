"""
Search Engine - Main RAG System Orchestrator

This module implements the main search engine that orchestrates the entire RAG pipeline.
It coordinates query enrichment, classification, ChromaDB search, chunk selection, and
response generation through the InsightsAgent.

Pipeline Position: **Search Engine** → (Orchestrates entire pipeline)
"""

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .insights_agent import InsightsAgent

from utils.logger_setup import LoggerManager

from .chunk_selector import ChunkSelector
from .dynamic_client_manager import DynamicClientManager
from .kt_search_constants import SEARCH_CONFIG
from .query_classifier import QueryClassifier, QueryType
from .query_enricher import QueryEnricher
from .search_logging import PipelineLogger
from .search_response_builder import SearchResponseBuilder
from .search_types import SearchResponse

logger = LoggerManager.get_logger(__name__)

__all__ = ["SearchEngine", "SearchResponse"]


class SearchEngine:
    """
    Main Search Engine - Advanced RAG System Orchestrator

    Orchestrates the complete pipeline:
    1. Query Enrichment (universal)
    2. Query Classification (contextual)
    3. ChromaDB Search (type-specific)
    4. Chunk Selection (quality + diversity)
    5. Insights Generation (existing InsightsAgent)

    Supports 5 RAG types: SEMANTIC, METADATA, ENTITY, TEMPORAL, CONTENT
    """

    def __init__(self, verbose: bool = False) -> None:
        """Initialize Search Engine with all pipeline components."""
        self.verbose = verbose

        # Initialize core pipeline components
        self.query_enricher = QueryEnricher()
        self.query_classifier = QueryClassifier()
        self.chunk_selector = ChunkSelector()
        self.dynamic_client_manager = DynamicClientManager()

        # Initialize integration components
        self._initialize_integrations()

        # Performance tracking
        self.search_stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "avg_processing_time": 0.0,
        }

        # Helpers extraídos — sem estado de instância
        self._response_builder = SearchResponseBuilder()
        self._pipeline_logger = PipelineLogger()

        logger.info("SearchEngine initialized successfully with all pipeline components")

    def _initialize_integrations(self) -> None:
        """Initialize existing system integrations."""
        from src.kt_indexing.chromadb_store import ChromaDBStore, EmbeddingGenerator

        from .chromadb_search_executor import ChromaDBSearchExecutor

        self.chromadb_manager = ChromaDBStore()
        self.embedding_generator = EmbeddingGenerator()
        self._chromadb_executor = ChromaDBSearchExecutor(self.chromadb_manager, self.embedding_generator)
        self.insights_agent = self._initialize_insights_agent()

        logger.info("Successfully integrated with existing components")

    def _initialize_insights_agent(self) -> "InsightsAgent":
        """Initialize InsightsAgent with OpenAI client from settings."""
        from .insights_agent import InsightsAgent

        return InsightsAgent()  # auto-inicializa internamente a partir de settings

    def _show_system_stats(self) -> None:
        """Mostra estatísticas do sistema RAG"""
        try:
            # Get ChromaDB stats
            stats = (
                self.chromadb_manager.get_collection_stats()
                if hasattr(self.chromadb_manager, "get_collection_stats")
                else {}
            )

            logger.debug("📊 Estatísticas do Sistema:")
            logger.debug("   Collection: kt_chunks")
            if "count" in stats:
                logger.debug(f"   📦 Total chunks: {stats['count']}")
            else:
                logger.debug("   📦 Sistema pronto para consultas")

            # Check OpenAI API (simplified)
            from src.config.settings import OPENAI_API_KEY

            if OPENAI_API_KEY:
                logger.debug("   🔑 OpenAI API: Configurada")
            else:
                logger.debug("   ⚠️ OpenAI API: Não configurada")

        except Exception as e:
            logger.debug(f"   ⚠️ Erro ao obter estatísticas: {e}")
            logger.warning(f"Failed to get system stats: {e}")

    def search(self, query: str, show_details: bool = False) -> SearchResponse:
        """
        Main search interface - processes query through complete RAG pipeline

        Args:
            query: Natural language query
            show_details: Whether to show detailed processing information

        Returns:
            SearchResponse with intelligent response and contexts
        """
        start_time = time.time()

        try:
            # Rich logging header
            logger.debug(f"🔍 Processando: '{query}'")

            # Start pipeline logging
            if show_details:
                logger.debug("📝 PIPELINE RAG DETALHADO:")
            else:
                logger.debug("📝 PIPELINE RAG:")
            logger.debug("-" * 40)

            logger.info(f"Processing search query: '{query[:100]}{'...' if len(query) > 100 else ''}'")

            # Update stats
            self.search_stats["total_queries"] += 1

            # Validate input
            if not self._validate_query(query):
                return self._response_builder.create_error_response("Invalid query", query, start_time)

            # PHASE 1: Query Preprocessing and Enrichment
            enrichment_start = time.time()

            enrichment_result = self.query_enricher.enrich_query_universal(query)
            enrichment_time = time.time() - enrichment_start

            if enrichment_result.confidence < 0.1:
                return self._response_builder.create_error_response("Query enrichment failed", query, start_time)

            # Rich enrichment logging
            self._pipeline_logger.log_enrichment_phase(query, enrichment_result, enrichment_time, show_details)

            logger.debug(f"Query enriched successfully: {len(enrichment_result.entities)} entities detected")

            # PHASE 2: Query Classification
            classification_start = time.time()

            classification_result = self.query_classifier.classify_query_with_context(
                enrichment_result.cleaned_query, enrichment_result.entities, enrichment_result.context
            )
            classification_time = time.time() - classification_start

            # Rich classification logging
            self._pipeline_logger.log_classification_phase(classification_result, classification_time, show_details)

            logger.debug(
                f"Query classified as {classification_result.query_type.value} "
                f"with {classification_result.confidence:.2f} confidence"
            )

            # 🚨 P1-1 FIX: Validar cliente inexistente ANTES do ChromaDB search
            if self._response_builder.should_stop_for_nonexistent_client(query):
                logger.info("🚫 Cliente inexistente detectado - parando pipeline")
                discovered_clients: list[str] = []
                try:
                    discovery = self.dynamic_client_manager.discover_clients()
                    discovered_clients = list(discovery.keys())
                except Exception as e:
                    logger.warning(f"Não foi possível descobrir clientes para resposta de erro: {e}")
                return self._response_builder.create_client_not_found_response(
                    query, start_time, discovered_clients
                )

            # PHASE 3: ChromaDB Search
            chromadb_start = time.time()

            raw_results = self._chromadb_executor.execute_search(enrichment_result, classification_result, query)
            chromadb_time = time.time() - chromadb_start

            # Rich ChromaDB logging
            self._pipeline_logger.log_chromadb_phase(
                raw_results, chromadb_time, enrichment_result, classification_result, show_details
            )

            logger.debug(f"ChromaDB search returned {len(raw_results)} raw results")

            # PHASE 4: Dynamic Client Discovery (if needed)
            client_time = 0.0
            if classification_result.query_type in [QueryType.ENTITY, QueryType.METADATA]:
                client_start = time.time()

                raw_results = self.dynamic_client_manager.enrich_with_client_discovery(
                    raw_results, enrichment_result.entities
                )
                client_time = time.time() - client_start

                # Rich client discovery logging
                self._pipeline_logger.log_client_discovery_phase(
                    client_time, show_details, self.dynamic_client_manager
                )

            # PHASE 5: Intelligent Chunk Selection
            selection_start = time.time()

            query_analysis = self._response_builder.analyze_query_complexity(
                enrichment_result, classification_result, query
            )
            top_k = self.chunk_selector.calculate_adaptive_top_k(classification_result.query_type, query_analysis)

            selection_result = self.chunk_selector.select_intelligent_chunks(
                raw_results, top_k, classification_result.query_type, query_analysis, query
            )
            selection_time = time.time() - selection_start

            # Rich selection logging
            self._pipeline_logger.log_selection_phase(
                selection_result, raw_results, top_k, selection_time, show_details
            )

            logger.debug(
                f"Selected {len(selection_result.selected_chunks)} chunks using "
                f"{selection_result.selection_strategy} strategy"
            )

            # PHASE 6: Insights Generation (Existing InsightsAgent)
            insights_start = time.time()

            insights_result = self.insights_agent.generate_direct_insight(
                original_query=query, search_results=selection_result.selected_chunks
            )
            insights_time = time.time() - insights_start

            if not insights_result:
                return self._response_builder.create_error_response(
                    "Failed to generate insights", query, start_time
                )

            # Rich insights logging
            self._pipeline_logger.log_insights_phase(insights_result, insights_time, show_details)

            logger.debug(f"Insights generated with {insights_result.confidence:.2f} confidence")

            # PHASE 7: Format Final Response
            response = self._response_builder.format_final_response(
                query, insights_result, selection_result, classification_result, start_time
            )

            # Update success stats
            self.search_stats["successful_queries"] += 1
            processing_time = time.time() - start_time
            self._update_avg_processing_time(processing_time)

            # Final summary log
            if show_details:
                logger.debug("📊 MÉTRICAS DETALHADAS:")
            else:
                logger.debug(
                    "📊 TOTAL: "
                    f"{processing_time:.3f}s | {classification_result.query_type.value} | "
                    f"TOP_K: {top_k} | {len(selection_result.selected_chunks)} chunks | "
                    f"✅ {insights_result.confidence:.0%}"
                )

            logger.info(f"Search completed successfully in {processing_time:.3f}s")

            return response

        except Exception as e:
            logger.error(f"Search failed with error: {e}")
            self.search_stats["failed_queries"] += 1
            return self._response_builder.create_error_response(f"Search error: {str(e)}", query, start_time)

    def _validate_query(self, query: str) -> bool:
        """Validate input query"""
        if not query or not isinstance(query, str):
            return False

        if len(query.strip()) < SEARCH_CONFIG["min_query_length"]:
            return False

        if len(query) > SEARCH_CONFIG["max_query_length"]:
            return False

        return True

    def _update_avg_processing_time(self, processing_time: float) -> None:
        """Update average processing time statistics"""
        current_avg = self.search_stats["avg_processing_time"]
        total_successful = self.search_stats["successful_queries"]

        if total_successful == 1:
            self.search_stats["avg_processing_time"] = processing_time
        else:
            # Running average calculation
            new_avg = ((current_avg * (total_successful - 1)) + processing_time) / total_successful
            self.search_stats["avg_processing_time"] = new_avg

    def get_search_stats(self) -> dict[str, Any]:
        """Get search engine performance statistics"""
        return self.search_stats.copy()

    def health_check(self) -> dict[str, Any]:
        """Perform health check on all components"""
        health_status = {
            "search_engine": True,
            "query_enricher": True,
            "query_classifier": True,
            "chunk_selector": True,
            "chromadb_manager": True,
            "embedding_generator": True,
            "insights_agent": True,
            "overall_healthy": True,
        }

        try:
            # Test ChromaDB connection
            self.chromadb_manager.get_collection_stats()

            # Test embedding generation
            test_embedding = self.embedding_generator.generate_query_embedding("test query")
            if not test_embedding:
                health_status["embedding_generator"] = False

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health_status["chromadb_manager"] = False
            health_status["overall_healthy"] = False

        return health_status
