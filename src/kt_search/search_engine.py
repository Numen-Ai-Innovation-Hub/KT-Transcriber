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
from .query_classifier import ClassificationResult, QueryClassifier, QueryType
from .query_enricher import EnrichmentResult, QueryEnricher
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

        self.chromadb_manager = ChromaDBStore()
        self.embedding_generator = EmbeddingGenerator()
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

            raw_results = self._execute_chromadb_search(enrichment_result, classification_result, query)
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

    def _execute_chromadb_search(
        self, enrichment_result: EnrichmentResult, classification_result: ClassificationResult, query: str
    ) -> list[dict[str, Any]]:
        """Execute ChromaDB search based on query type and strategy"""

        strategy = classification_result.strategy
        query_type = classification_result.query_type

        try:
            if query_type == QueryType.SEMANTIC:
                return self._execute_semantic_search(enrichment_result, strategy, query_type, query)

            elif query_type == QueryType.METADATA:
                return self._execute_metadata_search(enrichment_result, strategy, query_type, query)

            elif query_type == QueryType.ENTITY:
                return self._execute_entity_search(enrichment_result, strategy, query_type, query)

            elif query_type == QueryType.TEMPORAL:
                return self._execute_temporal_search(enrichment_result, strategy, query_type, query)

            elif query_type == QueryType.CONTENT:
                return self._execute_content_search(enrichment_result, strategy, query_type, query)

            else:
                logger.warning(f"Unknown query type {query_type}, using semantic search")
                return self._execute_semantic_search(enrichment_result, strategy, query_type, query)

        except Exception as e:
            logger.error(f"ChromaDB search failed: {e}")
            if SEARCH_CONFIG["fail_fast"]:
                raise
            return []

    def _execute_semantic_search(
        self,
        enrichment_result: EnrichmentResult,
        strategy: dict[str, Any],
        query_type: QueryType | None = None,
        query: str = "",
    ) -> list[dict[str, Any]]:
        """Execute semantic similarity search"""

        # Generate embedding for enriched query
        embedding = self.embedding_generator.generate_query_embedding(enrichment_result.enriched_query)

        if not embedding:
            raise Exception("Failed to generate query embedding")

        # Build filters from strategy and entities
        qt_val: str = query_type.value if query_type else ""
        filters = self._build_chromadb_filters(enrichment_result.entities, strategy, qt_val, query)

        # Calculate search limit with buffer for selection
        base_limit = strategy.get("top_k_modifier", 1.0) * SEARCH_CONFIG["default_top_k"]
        search_limit = int(base_limit * 2)  # Get more for selection algorithm

        # Execute similarity search
        results = self.chromadb_manager.query_similarity(
            query_embedding=embedding, limit=search_limit, where_filter=filters, include_metadata=True
        )

        search_results = results.get("results", [])

        # If no results with filters, try without filters as fallback
        if not search_results and filters:
            logger.warning(f"No results with filters {filters}, trying without filters as fallback")
            fallback_results = self.chromadb_manager.query_similarity(
                query_embedding=embedding,
                limit=search_limit,
                where_filter=None,  # No filters
                include_metadata=True,
            )
            search_results = fallback_results.get("results", [])
            if search_results:
                logger.info(f"Fallback search without filters found {len(search_results)} results")

        return search_results

    def _calculate_adaptive_metadata_limit(self, has_filters: bool = False, target_coverage: float = 0.95) -> int:
        """
        Calculate adaptive limit based on collection size for metadata queries

        Args:
            has_filters: Whether the query has specific filters
            target_coverage: Desired coverage ratio (0.95 = 95% of collection)

        Returns:
            int: Adaptive limit that scales with collection size
        """
        try:
            # Get current collection size
            collection_stats = self.chromadb_manager.get_collection_stats()
            collection_size = collection_stats.get("total_documents", 1000)  # Default fallback

            if not has_filters:
                # For global metadata listing: ensure coverage of all videos
                # Use target_coverage to get most of collection while maintaining performance
                adaptive_limit = max(
                    int(collection_size * target_coverage),  # Scale with collection
                    200,  # Minimum for small collections
                    min(2000, collection_size),  # Maximum cap for performance
                )
                logger.debug(
                    f"Adaptive metadata limit: {adaptive_limit}"
                    f" (collection_size: {collection_size}, coverage: {target_coverage})"
                )
                return adaptive_limit
            else:
                # For filtered searches: use much larger limit to ensure all videos are captured
                # For client-specific metadata listings, we need enough chunks to cover ALL videos
                return min(1000, collection_size)  # Increased from 200 to 1000 to capture all client videos

        except Exception as e:
            logger.warning(f"Failed to calculate adaptive limit: {e}. Using fallback.")
            # Fallback to larger static limit if adaptive calculation fails
            return 500 if not has_filters else 1000  # Increased from 200 to 1000 for filtered searches

    def _execute_metadata_search(
        self,
        enrichment_result: EnrichmentResult,
        strategy: dict[str, Any],
        query_type: QueryType | None = None,
        query: str = "",
    ) -> list[dict[str, Any]]:
        """Execute metadata-only search for listings"""

        # Build metadata filters
        qt_val: str = query_type.value if query_type else ""
        filters = self._build_chromadb_filters(enrichment_result.entities, strategy, qt_val, query)

        # Calculate adaptive search limit based on collection size
        search_limit = self._calculate_adaptive_metadata_limit(
            has_filters=bool(filters),
            target_coverage=1.0,  # 100% coverage to ensure ALL videos are captured
        )

        # Execute metadata search
        results = self.chromadb_manager.query_metadata(where_filter=filters, limit=search_limit, include_content=True)

        return results.get("results", [])

    def _execute_entity_search(
        self,
        enrichment_result: EnrichmentResult,
        strategy: dict[str, Any],
        query_type: QueryType | None = None,
        query: str = "",
    ) -> list[dict[str, Any]]:
        """Execute entity-focused search"""

        # Build entity-specific filters
        filters = self._build_entity_filters(enrichment_result.entities, strategy)

        # Search limit for entity queries
        search_limit = int(strategy.get("top_k_modifier", 1.2) * SEARCH_CONFIG["default_top_k"])

        # Execute metadata search with entity focus
        results = self.chromadb_manager.query_metadata(where_filter=filters, limit=search_limit, include_content=True)

        return results.get("results", [])

    def _execute_temporal_search(
        self,
        enrichment_result: EnrichmentResult,
        strategy: dict[str, Any],
        query_type: QueryType | None = None,
        query: str = "",
    ) -> list[dict[str, Any]]:
        """Execute temporal-constrained search"""

        # Build temporal filters
        filters = self._build_temporal_filters(enrichment_result.entities, strategy)

        # Extract temporal filtering info for post-processing
        temporal_filter = filters.pop("_temporal_filter", None) if filters else None

        # Search limit for temporal queries (larger since we'll filter post-search)
        search_limit = int(strategy.get("top_k_modifier", 1.3) * SEARCH_CONFIG["default_top_k"] * 2)

        # Execute metadata search without temporal constraints (to avoid ChromaDB errors)
        results = self.chromadb_manager.query_metadata(
            where_filter=filters if filters else None, limit=search_limit, include_content=True
        )

        # Apply temporal filtering in post-processing
        all_results = results.get("results", [])
        if temporal_filter:
            all_results = self._apply_temporal_filter(all_results, temporal_filter)

        # Sort by date (most recent first)
        def _date_key(x: dict[str, Any]) -> str:
            val = x.get("metadata", {}).get("meeting_date", "")
            return val if isinstance(val, str) else ""

        sorted_results = sorted(all_results, key=_date_key, reverse=True)

        return sorted_results

    def _apply_temporal_filter(
        self, results: list[dict[str, Any]], temporal_filter: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Apply temporal filtering in post-processing (string date comparison)"""
        if not temporal_filter or not results:
            return results

        start_date = temporal_filter.get("start_date")
        filter_type = temporal_filter.get("type", "gte")

        if not start_date:
            return results

        filtered_results = []
        for result in results:
            metadata = result.get("metadata", {})
            meeting_date = metadata.get("meeting_date")

            if not meeting_date:
                continue

            # String date comparison (YYYY-MM-DD format)
            if filter_type == "gte":
                if meeting_date >= start_date:
                    filtered_results.append(result)
            elif filter_type == "lte":
                if meeting_date <= start_date:
                    filtered_results.append(result)

        # 🚨 P2-2 FIX: Melhor debug e relaxamento do filtro temporal
        if not filtered_results and results:
            logger.info(f"🔄 Filtro temporal muito restritivo (0/{len(results)} resultados)")
            logger.info(f"   📅 Filtro aplicado: meeting_date >= {start_date}")

            # Debug: mostrar algumas datas dos dados para diagnóstico
            sample_dates = []
            for result in results[:5]:  # Amostra de 5 resultados
                metadata = result.get("metadata", {})
                meeting_date = metadata.get("meeting_date", "N/A")
                sample_dates.append(meeting_date)
            logger.info(f"   📋 Amostra de datas disponíveis: {sample_dates}")

            # 🚨 P4-1 FIX: Fallback inteligente - não relaxar para anos diferentes
            from datetime import datetime, timedelta

            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
                current_year = datetime.now().year
                query_year = start_date_obj.year

                # Só aplicar fallback se for do mesmo ano ou ano recente
                if filter_type == "gte" and abs(current_year - query_year) <= 1:
                    # Para "últimos X dias" do ano atual/recente, relaxar período
                    relaxed_start_date = (start_date_obj - timedelta(days=30)).strftime("%Y-%m-%d")
                    logger.info(f"   🔧 Relaxando período (mesmo ano): {start_date} → {relaxed_start_date}")

                    # Aplicar filtro relaxado
                    for result in results:
                        metadata = result.get("metadata", {})
                        meeting_date = metadata.get("meeting_date")

                        if meeting_date and meeting_date >= relaxed_start_date:
                            filtered_results.append(result)

                    if filtered_results:
                        logger.info(f"✅ Fallback temporal: {len(filtered_results)} resultados encontrados")
                    else:
                        logger.warning("⚠️ Mesmo com fallback relaxado, 0 resultados")

                elif abs(current_year - query_year) > 1:
                    # Para anos muito diferentes, não aplicar fallback
                    logger.info(f"   🚫 Ano da query ({query_year}) muito diferente do atual ({current_year})")
                    logger.info(f"   📅 Não aplicando fallback - dados realmente não existem para {query_year}")

            except ValueError as e:
                logger.warning(f"Erro ao aplicar fallback temporal: {e}")

        return filtered_results

    def _execute_content_search(
        self,
        enrichment_result: EnrichmentResult,
        strategy: dict[str, Any],
        query_type: QueryType | None = None,
        query: str = "",
    ) -> list[dict[str, Any]]:
        """Execute enhanced content search with fuzzy matching"""

        # Use enhanced search terms if available, fallback to legacy
        enhanced_terms = strategy.get("search_terms_enhanced")
        if enhanced_terms:
            logger.info(f"Using enhanced content search with terms: {enhanced_terms}")
            return self._execute_content_search_enhanced(enrichment_result, strategy, enhanced_terms)

        # Legacy fallback
        search_terms = strategy.get("search_terms", [])
        if not search_terms:
            # Extract transaction terms from entities as fallback
            if "transactions" in enrichment_result.entities:
                search_terms = enrichment_result.entities["transactions"]
                logger.info(f"Using transaction entities as search terms: {search_terms}")
            else:
                logger.warning("No search terms found for content search, falling back to semantic")
                return self._execute_semantic_search(enrichment_result, strategy, query_type, query)

        return self._execute_content_search_legacy(
            enrichment_result, strategy, search_terms, query_type=query_type, query=query
        )

    def _execute_content_search_enhanced(
        self, enrichment_result: EnrichmentResult, strategy: dict[str, Any], enhanced_terms: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Execute enhanced content search with fuzzy matching and KT title filtering"""

        # Build enhanced filters including KT title extraction
        filters = self._build_chromadb_filters_enhanced(
            enrichment_result.entities,
            strategy,
            enhanced_terms,
            "",
            enrichment_result.original_query if hasattr(enrichment_result, "original_query") else "",
        )
        logger.info(f"Enhanced search filters: {filters}")

        search_limit = int(strategy.get("top_k_modifier", 1.5) * SEARCH_CONFIG["default_top_k"])

        # Choose search method based on enhanced terms
        exact_terms = enhanced_terms.get("exact_terms", [])
        has_specific_terms = bool(exact_terms)

        results: dict[str, Any]
        if has_specific_terms:
            # For content search with specific terms, use similarity search
            search_query = " ".join(exact_terms)
            logger.info(f"Using similarity search for exact terms: {search_query}")
            sim_results = self.chromadb_manager.similarity_search(
                query_text=search_query,
                limit=search_limit * 2,  # Get more for fuzzy filtering
                filters=filters,
            )
            # Format similarity search results to match expected structure
            results = {"results": sim_results, "total_found": len(sim_results), "query_type": "similarity_search"}
        else:
            # For general content search, use metadata query
            logger.info("Using metadata query for general content search")
            results = self.chromadb_manager.query_metadata(
                where_filter=filters,
                limit=search_limit * 2,  # Get more for fuzzy filtering
                include_content=True,
            )
        results_list = results.get("results", [])
        logger.info(f"ChromaDB query returned {len(results_list)} chunks before fuzzy scoring")

        # Debug: show first few chunk IDs to verify we're getting the right chunks
        if len(results_list) > 0:
            chunk_ids = [r.get("chunk_id", r.get("id", "no-id")) for r in results_list[:5]]
            logger.info(f"First chunk IDs: {chunk_ids}")

        # If no results with filters, try direct content search for any exact terms
        if not results.get("results", []):
            logger.info("No results with filters in enhanced search, trying direct content search")
            exact_terms = enhanced_terms.get("exact_terms", [])

            if exact_terms:
                # Use manual content search for exact term matching
                all_content_results = []

                for term in exact_terms:
                    logger.info(f"Searching for exact term: '{term}'")

                    # Manual search in all chunks for this specific term
                    manual_results = self._search_term_in_all_chunks(term, search_limit)
                    all_content_results.extend(manual_results)

                    if manual_results:
                        logger.info(f"Found {len(manual_results)} chunks containing '{term}'")

                # Deduplicate and format results
                if all_content_results:
                    unique_chunks = {}
                    for result in all_content_results:
                        chunk_id = result.get("chunk_id")
                        if chunk_id and chunk_id not in unique_chunks:
                            unique_chunks[chunk_id] = result

                    results = {
                        "results": list(unique_chunks.values()),
                        "total_found": len(unique_chunks),
                        "query_type": "direct_content_search",
                    }
                    logger.info(f"Direct content search found {len(unique_chunks)} unique chunks")
                else:
                    logger.warning("No results found with direct content search")
            else:
                logger.info("No exact terms available for direct content search")

            # If still no results, fallback to broader search
            if not results.get("results", []):
                logger.info("Trying similarity search as final fallback")
                # Try similarity search with the original query
                try:
                    similarity_results = self.chromadb_manager.similarity_search(
                        query_text=enrichment_result.original_query, limit=search_limit, filters=None
                    )

                    if similarity_results:
                        formatted_results = []
                        for result in similarity_results:
                            formatted_results.append(
                                {
                                    "chunk_id": result.get("chunk_id"),
                                    "content": result.get("content", ""),
                                    "metadata": result.get("metadata", {}),
                                    "similarity_score": result.get("similarity_score", 0.0),
                                }
                            )

                        results = {
                            "results": formatted_results,
                            "total_found": len(formatted_results),
                            "query_type": "similarity_fallback",
                        }
                        logger.info(f"Similarity fallback found {len(formatted_results)} chunks")

                except Exception as e:
                    logger.error(f"Similarity search fallback failed: {e}")
                    results = {"results": [], "total_found": 0, "query_type": "failed"}

        # Apply fuzzy matching scoring
        scored_results = []
        total_chunks = len(results.get("results", []))
        chunks_above_threshold = 0

        # Skip fuzzy scoring if we have video filter applied - chunks are already highly relevant
        has_video_filter = filters and "video_name" in filters

        if has_video_filter:
            logger.info(f"Video filter detected - skipping fuzzy scoring for {total_chunks} chunks")
            scored_results = results.get("results", [])
            # Add dummy score for consistency
            for result in scored_results:
                result["fuzzy_match_score"] = 0.8  # High score since video filter ensures relevance
            chunks_above_threshold = len(scored_results)
        else:
            # Apply fuzzy scoring for general searches
            for i, result in enumerate(results.get("results", [])):
                fuzzy_score = self._calculate_fuzzy_match_score(result, enhanced_terms)

                # Debug first few chunks
                if i < 3:
                    content_snippet = result.get("content", "")[:100]
                    client_name = result.get("metadata", {}).get("client_name", "")
                    logger.info(
                        f"Debug chunk {i}: score={fuzzy_score:.3f},"
                        f" client={client_name}, content='{content_snippet}...'"
                    )

                if fuzzy_score >= 0.3:  # Threshold for inclusion
                    result["fuzzy_match_score"] = fuzzy_score
                    scored_results.append(result)
                    chunks_above_threshold += 1

        logger.info(
            f"Fuzzy scoring: {chunks_above_threshold}/{total_chunks} chunks passed"
            f" threshold {'(skipped - video filter)' if has_video_filter else '0.3'}"
        )

        # Sort by fuzzy match score
        scored_results.sort(key=lambda x: x["fuzzy_match_score"], reverse=True)

        # Limit to original search_limit
        return scored_results[:search_limit]

    def _execute_content_search_legacy(
        self,
        enrichment_result: EnrichmentResult,
        strategy: dict[str, Any],
        search_terms: list[str],
        query_type: QueryType | None = None,
        query: str = "",
    ) -> list[dict[str, Any]]:
        """Legacy content search implementation with transaction support."""

        qt_val: str = query_type.value if query_type else ""
        filters = self._build_chromadb_filters(enrichment_result.entities, strategy, qt_val, query)

        # If no client filter but has transactions, search broader
        if not filters and "transactions" in enrichment_result.entities:
            # Search without client filters for transactions
            search_limit = int(strategy.get("top_k_modifier", 1.5) * SEARCH_CONFIG["default_top_k"] * 3)
        else:
            search_limit = int(strategy.get("top_k_modifier", 1.5) * SEARCH_CONFIG["default_top_k"])

        results = self.chromadb_manager.query_metadata(where_filter=filters, limit=search_limit, include_content=True)

        # If no results with filters, try without filters for transactions
        if not results.get("results", []) and "transactions" in enrichment_result.entities:
            logger.info("No results with filters, trying broader search for transactions")
            results = self.chromadb_manager.query_metadata(
                where_filter=None,  # No filters - search all
                limit=search_limit,
                include_content=True,
            )

        # Filter results by content search terms (with transaction + client support)
        filtered_results = []
        for result in results.get("results", []):
            content = result.get("content", "").lower()
            metadata = result.get("metadata", {})

            # Check content for term matches
            content_matches = [term for term in search_terms if term.lower() in content]

            # 🚨 Enhanced: Check metadata with transaction + client name normalization
            metadata_matches = []
            for term in search_terms:
                term_lower = term.lower()

                # Check all metadata fields
                for field_name, field_value in metadata.items():
                    if isinstance(field_value, str):
                        field_lower = field_value.lower()

                        # Direct match
                        if term_lower in field_lower:
                            metadata_matches.append(term)
                            break

                        # Client name normalization: "pc factory" <-> "pc_factory"
                        if field_name == "client_name":
                            normalized_term = term_lower.replace(" ", "_")
                            normalized_field = field_lower.replace("_", " ")

                            if (
                                normalized_term in field_lower
                                or term_lower in normalized_field
                                or normalized_term == field_lower
                                or term_lower == normalized_field
                            ):
                                metadata_matches.append(term)
                                break

            # Include result if found in content OR metadata
            if content_matches or metadata_matches:
                result["content_match_terms"] = content_matches
                result["metadata_match_terms"] = metadata_matches
                result["search_score"] = len(content_matches) + len(metadata_matches)
                filtered_results.append(result)

        # Sort by search score (more matches = higher score)
        filtered_results.sort(key=lambda x: x.get("search_score", 0), reverse=True)

        return filtered_results

    def _calculate_fuzzy_match_score(self, result: dict[str, Any], enhanced_terms: dict[str, Any]) -> float:
        """
        Calculate fuzzy matching score for a result based on enhanced search terms

        Args:
            result: ChromaDB result with content and metadata
            enhanced_terms: Enhanced search terms from classifier

        Returns:
            float: Fuzzy match score between 0.0 and 1.0
        """
        import re
        from difflib import SequenceMatcher

        score = 0.0
        content = result.get("content", "").lower()
        metadata = result.get("metadata", {})

        # 1. Exact term matches (highest score) - check content AND metadata
        exact_matches = 0
        for term in enhanced_terms.get("exact_terms", []):
            term_found = False

            # Check content
            if term.lower() in content:
                term_found = True

            # Check all metadata fields for exact term matches (especially for transactions)
            if not term_found:
                for field_name, field_value in metadata.items():
                    if isinstance(field_value, str) and term.lower() in field_value.lower():
                        # Debug first ZEWM0008 match found
                        if term == "ZEWM0008" and exact_matches == 0:
                            logger.info(f"Found ZEWM0008 in metadata field '{field_name}': {field_value[:100]}")
                        term_found = True
                        break

            if term_found:
                exact_matches += 1
                score += 0.4  # High score for exact matches

        # 2. Client variations matching
        client_matches = 0
        client_name = metadata.get("client_name", "").lower()
        for variation in enhanced_terms.get("client_variations", []):
            variation_lower = variation.lower()

            # Exact client match
            if variation_lower == client_name:
                client_matches += 1
                score += 0.3
                break

            # Fuzzy client match
            elif variation_lower in client_name or client_name in variation_lower:
                client_matches += 1
                score += 0.2
                break

            # Sequence similarity for clients
            similarity = SequenceMatcher(None, variation_lower, client_name).ratio()
            if similarity >= 0.8:
                client_matches += 1
                score += 0.2 * similarity
                break

        # 3. Partial/fuzzy term matching
        fuzzy_matches = 0
        all_searchable_text = f"{content} {metadata.get('video_name', '')} {client_name}".lower()

        for term in enhanced_terms.get("fuzzy_terms", []):
            term_lower = term.lower()

            if term_lower in all_searchable_text:
                fuzzy_matches += 1
                score += 0.15
            else:
                # Word-boundary fuzzy matching
                words = re.findall(r"\b\w+\b", all_searchable_text)
                for word in words:
                    if len(word) >= 3 and len(term_lower) >= 3:
                        similarity = SequenceMatcher(None, term_lower, word).ratio()
                        if similarity >= 0.75:
                            fuzzy_matches += 1
                            score += 0.1 * similarity
                            break

        # 4. Partial term matches
        partial_matches = 0
        for term in enhanced_terms.get("partial_terms", []):
            if term.lower() in all_searchable_text:
                partial_matches += 1
                score += 0.1

        # 5. Video name/title matching (for KT-specific queries)
        video_name = metadata.get("video_name", "").lower()
        for pattern in enhanced_terms.get("search_patterns", []):
            pattern_lower = pattern.lower()
            if pattern_lower in video_name:
                score += 0.25
                break

            # Fuzzy video name matching
            similarity = SequenceMatcher(None, pattern_lower, video_name).ratio()
            if similarity >= 0.6:
                score += 0.15 * similarity
                break

        # Apply noise filtering penalties before normalizing
        content_length = len(content)

        # Strong penalties for noise content
        if content_length < 20:  # Chunks like "Beleza?" (8 chars)
            score *= 0.1  # Reduce score to 10% of original
        elif content_length < 50:  # Small fragmentary content
            score *= 0.4  # Reduce score to 40% of original

        # Additional conversational noise patterns
        conversational_patterns = [
            r"^(beleza\?|ok\.|tá\.|é\.?|ah\.?|então\.)$",
            r"^(deixa eu ver|eu não vou lembrar|será que é)",
            r"^[a-záàâãéèêíìîóòôõúùû]{1,5}[\.\?]?$",  # Very short words
            r"^(é\s+a\s+mesma|tem\s+outra|é\s+que\s+tem)",  # Common fragments
        ]

        content_clean = content.strip().lower()
        for pattern in conversational_patterns:
            if re.match(pattern, content_clean, re.IGNORECASE):
                score *= 0.05  # Severe penalty for conversational noise
                break

        # Normalize score to [0, 1] range
        max_possible_score = 1.0
        normalized_score = min(score, max_possible_score)

        # Add debug info to result
        if normalized_score > 0:
            result["match_details"] = {
                "exact_matches": exact_matches,
                "client_matches": client_matches,
                "fuzzy_matches": fuzzy_matches,
                "partial_matches": partial_matches,
                "raw_score": score,
                "normalized_score": normalized_score,
            }

        return normalized_score

    def _search_term_in_all_chunks(self, search_term: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        Search for a specific term in all chunks using manual scan
        This is used as fallback when ChromaDB filters fail

        Args:
            search_term: The exact term to search for
            limit: Maximum number of results to return

        Returns:
            List of chunks containing the search term
        """
        try:
            # Get all chunks from ChromaDB
            all_results = self.chromadb_manager.collection.get(include=["documents", "metadatas"])

            matching_results = []
            search_term_lower = search_term.lower()

            logger.debug(f"Scanning {len(all_results.get('ids', []))} chunks for term '{search_term}'")

            ids_list = all_results.get("ids") or []
            docs_list = all_results.get("documents") or []
            metas_list = all_results.get("metadatas") or []
            for _i, (chunk_id, document, metadata) in enumerate(zip(ids_list, docs_list, metas_list, strict=True)):
                # Check content
                content_match = document and search_term_lower in document.lower()

                # Check metadata fields
                metadata_match = False
                matched_field = None
                if metadata:
                    for field_name, field_value in metadata.items():
                        if isinstance(field_value, str) and search_term_lower in field_value.lower():
                            metadata_match = True
                            matched_field = field_name
                            break

                # If match found, add to results
                if content_match or metadata_match:
                    # Calculate relevance score
                    relevance_score = 0.5  # Base score

                    if content_match:
                        # Count occurrences in content
                        occurrences = document.lower().count(search_term_lower)
                        relevance_score += min(occurrences * 0.2, 0.5)  # Max 0.5 bonus

                    if metadata_match:
                        # Higher score for metadata matches
                        relevance_score += 0.3

                        # Extra score for important fields
                        if matched_field in [
                            "highlights_summary",
                            "searchable_tags",
                            "transactions",
                            "technical_terms",
                        ]:
                            relevance_score += 0.2

                    result = {
                        "chunk_id": chunk_id,
                        "content": document or "",
                        "metadata": metadata or {},
                        "relevance_score": relevance_score,
                        "match_details": {
                            "term": search_term,
                            "content_match": content_match,
                            "metadata_match": metadata_match,
                            "matched_field": matched_field,
                        },
                    }
                    matching_results.append(result)

                    # Stop if we have enough results
                    if len(matching_results) >= limit:
                        break

            # Sort by relevance score (highest first)
            def _relevance_key(x: dict[str, Any]) -> float:
                v = x.get("relevance_score", 0)
                return v if isinstance(v, (int, float)) else 0.0

            matching_results.sort(key=_relevance_key, reverse=True)

            logger.info(
                f"Manual search for '{search_term}' found {len(matching_results)} matches"
                f" in {len(all_results.get('ids', []))} chunks"
            )

            return matching_results

        except Exception as e:
            logger.error(f"Manual search for '{search_term}' failed: {e}")
            return []

    def _build_chromadb_filters_enhanced(
        self,
        entities: dict[str, Any],
        strategy: dict[str, Any],
        enhanced_terms: dict[str, Any],
        query_type: str | None = None,
        original_query: str = "",
    ) -> dict[str, Any] | None:
        """Build enhanced ChromaDB filters (ChromaDB-compatible only)"""

        # Use base filters only - ChromaDB doesn't support complex filters
        filters = self._build_chromadb_filters(entities, strategy, query_type or "", original_query)

        # Store KT title patterns for post-processing (not in ChromaDB filter)
        kt_title_filters = self._extract_kt_title_filter(enhanced_terms)
        if kt_title_filters:
            # Store for post-processing after ChromaDB search
            strategy["_kt_title_post_filter"] = kt_title_filters

        return filters

    def _extract_kt_title_filter(self, enhanced_terms: dict[str, Any]) -> dict[str, Any] | None:
        """
        Extract KT title filter patterns from enhanced terms

        Returns filter patterns for post-processing since ChromaDB
        doesn't support complex string operations
        """

        # Collect all potential title parts
        title_parts = []
        title_parts.extend(enhanced_terms.get("partial_terms", []))
        title_parts.extend(enhanced_terms.get("fuzzy_terms", []))

        # Filter out very short or common terms
        meaningful_parts = [
            part
            for part in title_parts
            if len(part) >= 3 and part.lower() not in ["the", "and", "for", "with", "como", "para"]
        ]

        if meaningful_parts:
            return {
                "title_parts": meaningful_parts,
                "match_type": "contains_all",  # All parts should be found
            }

        return None

    def _build_chromadb_filters(
        self,
        entities: dict[str, Any],
        strategy: dict[str, Any],
        query_type: str | None = None,
        original_query: str = "",
    ) -> dict[str, Any] | None:
        """Build ChromaDB WHERE filters based on entities, strategy and query context"""
        filters: dict[str, Any] = {}

        # CONTEXTUAL HIERARCHICAL FILTERING:
        # For METADATA queries about clients, prioritize client filters over video filters
        # For other query types, maintain video > client hierarchy

        qt = query_type or ""
        is_metadata_client_query = qt == "METADATA" and any(
            term in original_query.lower() for term in ["cliente", "client", "kts do", "kts da"]
        )

        is_metadata_global_query = qt == "METADATA" and any(
            term in original_query.lower()
            for term in ["todos", "todas", "lista todos", "base de conhecimento", "nossa base"]
        )

        if is_metadata_global_query:
            # For global metadata queries, ignore ALL filters to return complete dataset
            logger.debug("METADATA GLOBAL QUERY: No filters applied for complete base listing")
            # Return empty filters to get all data
            return filters if filters else None
        elif is_metadata_client_query and "clients" in entities:
            # For metadata client listings, prioritize client filter to get ALL content
            client_values = entities["clients"]["values"]
            if client_values:
                detected_client = client_values[0]

                # Get all client variations dynamically from ChromaDB
                client_variations = self._get_client_variations(detected_client)

                if len(client_variations) > 1:
                    # Use OR filter for multiple variations
                    filters = {"$or": [{"client_name": variation} for variation in client_variations]}
                    logger.debug(f"METADATA CLIENT QUERY: Using OR filter for client variations: {client_variations}")
                else:
                    # Single variation - use direct filter
                    client_name = client_variations[0] if client_variations else detected_client.upper()
                    filters["client_name"] = client_name
                    logger.debug(f"METADATA CLIENT QUERY: Single client filter: {detected_client} → {client_name}")

                # Video filters are ignored to ensure complete client coverage
                if "video_references" in entities:
                    logger.debug("Video filters ignored for complete client metadata listing")
        elif "video_references" in entities:
            # For non-metadata queries, video is more specific than client, so prioritize it
            video_references = entities["video_references"]["values"]
            if video_references:
                video_filters = self._build_video_filters(video_references)
                if video_filters:
                    filters = video_filters
                    logger.debug(f"Applied video filters for references: {video_references}")
                    logger.debug("Video filtering overrides client filtering (hierarchical)")
        elif "clients" in entities and "client_name" not in filters:
            # Only apply client filter if no video was detected
            client_values = entities["clients"]["values"]
            if client_values:
                detected_client = client_values[0]
                normalized_client = self._normalize_client_for_filter(detected_client)
                if normalized_client:
                    filters["client_name"] = normalized_client
                    logger.debug(f"Applied client-only filter: {detected_client} → {normalized_client}")

        # Add strategy-specific filters
        if "video_name" not in filters and "client_name" not in filters:
            strategy_filters = strategy.get("filters", {})
            filters.update(strategy_filters)
        else:
            logger.debug("Strategy filters skipped due to existing entity filtering prioritization")

        return filters if filters else None

    def _get_client_variations(self, detected_client: str) -> list[str]:
        """
        Get all variations of a client name that exist in the ChromaDB

        Returns all client names that fuzzy match the detected client
        """
        try:
            # Get all unique client names from ChromaDB
            all_docs = self.chromadb_manager.collection.get(include=["metadatas"])

            raw_metas = all_docs.get("metadatas") if all_docs else None
            if not all_docs or not raw_metas:
                return [detected_client.upper()]

            # Extract all unique client names from the database
            actual_clients: set[str] = set()
            for metadata in raw_metas:
                client_name_raw = metadata.get("client_name")
                if isinstance(client_name_raw, str) and client_name_raw.strip():
                    actual_clients.add(client_name_raw.strip())

            if not actual_clients:
                return [detected_client.upper()]

            # Find all variations that match the detected client
            import unicodedata

            def normalize_for_comparison(text: str) -> str:
                """Remove accents and normalize for fuzzy matching"""
                return unicodedata.normalize("NFD", text.upper()).encode("ascii", "ignore").decode("ascii")

            detected_upper = detected_client.upper()
            detected_normalized = normalize_for_comparison(detected_client)
            matching_variations = []

            for actual_client in actual_clients:
                actual_upper = actual_client.upper()
                actual_normalized = normalize_for_comparison(actual_client)

                # 1. Exact match (case insensitive)
                if actual_upper == detected_upper:
                    matching_variations.append(actual_client)
                # 2. Accent-normalized match (case insensitive, accent insensitive)
                elif actual_normalized == detected_normalized:
                    matching_variations.append(actual_client)
                # 3. Fuzzy match for similar names
                elif (detected_normalized in actual_normalized and len(detected_normalized) >= 3) or (
                    actual_normalized in detected_normalized and len(actual_normalized) >= 3
                ):
                    matching_variations.append(actual_client)

            if matching_variations:
                logger.debug(
                    f"Found {len(matching_variations)} client variations for '{detected_client}': {matching_variations}"
                )
                return matching_variations
            else:
                logger.warning(f"No client variations found for '{detected_client}' in database")
                return [detected_client.upper()]

        except Exception as e:
            logger.error(f"Error finding client variations: {e}")
            return [detected_client.upper()]

    def _normalize_client_for_filter(self, detected_client: str) -> str | None:
        """
        Normalize client name to match actual data in ChromaDB

        Uses dynamic lookup in ChromaDB to find the best match instead of hardcoded mappings
        """
        if not detected_client:
            return None

        try:
            # Get all unique client names from ChromaDB
            all_docs = self.chromadb_manager.collection.get(include=["metadatas"])

            raw_metas_norm = all_docs.get("metadatas") if all_docs else None
            if not all_docs or not raw_metas_norm:
                logger.warning("No metadata available for client normalization")
                return detected_client.upper()

            # Extract all unique client names from the database
            actual_clients_norm: set[str] = set()
            for metadata in raw_metas_norm:
                client_name_raw = metadata.get("client_name")
                if isinstance(client_name_raw, str) and client_name_raw.strip():
                    actual_clients_norm.add(client_name_raw.strip())

            if not actual_clients_norm:
                logger.warning("No client names found in database")
                return detected_client.upper()

            detected_upper = detected_client.upper().strip()

            # 1. Exact match (case insensitive)
            for actual_client in actual_clients_norm:
                if actual_client.upper() == detected_upper:
                    logger.debug(f"Client exact match: {detected_client} → {actual_client}")
                    return actual_client

            # 2. Fuzzy match without accents (most common issue)
            import unicodedata

            def remove_accents(text: str) -> str:
                """Remove accents from text"""
                return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii")

            detected_no_accent = remove_accents(detected_upper)

            for actual_client in actual_clients_norm:
                actual_no_accent = remove_accents(actual_client.upper())
                if actual_no_accent == detected_no_accent:
                    logger.debug(f"Client accent-normalized match: {detected_client} → {actual_client}")
                    return actual_client

            # 3. Partial match (contains)
            for actual_client in actual_clients_norm:
                if detected_upper in actual_client.upper() or actual_client.upper() in detected_upper:
                    logger.debug(f"Client partial match: {detected_client} → {actual_client}")
                    return actual_client

            # 4. No match found - return None to skip filter
            available = sorted(actual_clients_norm)
            logger.warning(f"No matching client found for '{detected_client}' in database. Available: {available}")
            return None

        except Exception as e:
            logger.error(f"Error during client normalization: {e}")
            # Fallback to original client name
            return detected_client.upper()

    def _build_video_filters(self, video_references: list[str]) -> dict[str, Any] | None:
        """
        Build video filters based on detected video references

        video_references already contains the actual video names from fuzzy matching
        """
        try:
            if not video_references:
                return None

            # video_references already contains actual video names, so use them directly
            filter_dict: dict[str, Any]
            if len(video_references) == 1:
                filter_dict = {"video_name": video_references[0]}
                logger.debug(f"Single video filter: {filter_dict}")
                return filter_dict
            else:
                filter_dict = {"$or": [{"video_name": video} for video in video_references]}
                logger.debug(f"Multiple video filter: {filter_dict}")
                return filter_dict

        except Exception as e:
            logger.warning(f"Error building video filters: {e}")
            return None

    def _build_entity_filters(self, entities: dict[str, Any], strategy: dict[str, Any]) -> dict[str, Any] | None:
        """Build entity-specific filters"""
        filters = {}

        # Client-specific entity search
        if "clients" in entities:
            client_values = entities["clients"]["values"]
            if client_values:
                # Apply same normalization as other queries
                detected_client = client_values[0]
                normalized_client = self._normalize_client_for_filter(detected_client)
                if normalized_client:
                    filters["client_name"] = normalized_client

        # Participant filtering
        if "participants" in entities:
            participant_values = entities["participants"]["values"]
            if participant_values:
                # Note: ChromaDB doesn't support complex text search in WHERE
                # This would need to be handled in post-processing
                pass

        # Add non-empty content filter for entity searches
        # Note: This is a conceptual filter, actual implementation depends on ChromaDB capabilities

        return filters if filters else None

    def _build_temporal_filters(self, entities: dict[str, Any], strategy: dict[str, Any]) -> dict[str, Any] | None:
        """Build temporal constraint filters"""
        filters = {}

        # Apply temporal constraints from strategy
        temporal_filters = strategy.get("temporal_filters", {})
        filters.update(temporal_filters)

        # Client filtering if present
        if "clients" in entities:
            client_values = entities["clients"]["values"]
            if client_values:
                # Apply same normalization as other queries
                detected_client = client_values[0]
                normalized_client = self._normalize_client_for_filter(detected_client)
                if normalized_client:
                    filters["client_name"] = normalized_client

        return filters if filters else None


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
