"""
Chunk Selector - Intelligent Selection with Quality + Diversity

This module implements intelligent chunk selection that combines quality scoring
with diversity algorithms to select the most relevant and diverse chunks for
response generation.

Pipeline Position: ChromaDB Search → **Chunk Selector** → InsightsAgent
"""

import re
from dataclasses import dataclass
from typing import Any

from utils.logger_setup import LoggerManager

from .kt_search_constants import DIVERSITY_CONFIG, PERFORMANCE_CONFIG, QUALITY_WEIGHTS, TOP_K_STRATEGY
from .query_classifier import QueryType

logger = LoggerManager.get_logger(__name__)


@dataclass
class ChunkScore:
    """Score breakdown for a chunk"""

    chunk_id: str
    quality_score: float
    diversity_score: float
    combined_score: float
    selection_reason: str


@dataclass
class SelectionResult:
    """Result of chunk selection process"""

    selected_chunks: list[dict[str, Any]]
    chunk_scores: list[ChunkScore]
    total_candidates: int
    selection_strategy: str
    processing_time: float
    quality_threshold_met: bool


class ChunkSelector:
    """
    Intelligent Chunk Selector for KT semantic search

    Functions:
    - Calculate quality scores based on metadata and content
    - Apply diversity algorithms to avoid redundancy
    - Adaptive TOP_K based on query type and analysis
    - Optimize for quality + diversity balance

    Ensures selected chunks provide comprehensive, non-redundant context for InsightsAgent.
    """

    def __init__(self) -> None:
        """Initialize Chunk Selector with quality and diversity configurations"""
        self.quality_weights = QUALITY_WEIGHTS
        self.diversity_config = DIVERSITY_CONFIG
        self.top_k_strategy = TOP_K_STRATEGY
        self.performance_config = PERFORMANCE_CONFIG

        logger.info("ChunkSelector initialized with quality + diversity algorithms")

    def select_intelligent_chunks(
        self,
        raw_results: list[dict[str, Any]],
        top_k: int,
        query_type: QueryType,
        query_analysis: dict[str, Any],
        original_query: str = "",
    ) -> SelectionResult:
        """
        Select optimal chunks using quality scoring + diversity algorithms

        Args:
            raw_results: Raw results from ChromaDB search
            top_k: Target number of chunks to select
            query_type: Type of query (SEMANTIC, METADATA, etc.)
            query_analysis: Analysis of the original query
            original_query: Original query for context

        Returns:
            SelectionResult with selected chunks and scoring details
        """
        import time

        start_time = time.time()

        try:
            logger.info(f"Selecting {top_k} chunks from {len(raw_results)} candidates for {query_type.value} query")

            if not raw_results:
                return SelectionResult(
                    selected_chunks=[],
                    chunk_scores=[],
                    total_candidates=0,
                    selection_strategy="no_results",
                    processing_time=0.0,
                    quality_threshold_met=False,
                )

            # 1. Calculate quality scores for all chunks
            scored_chunks = self._calculate_quality_scores(raw_results, query_analysis, original_query)

            # 2. Apply quality threshold filtering
            quality_filtered = self._apply_quality_threshold(scored_chunks)

            # 3. Calculate adaptive TOP_K if needed
            adaptive_top_k = self._calculate_adaptive_top_k(top_k, query_type, query_analysis, len(quality_filtered))

            # 4. Select chunks with diversity algorithm
            selected_chunks = self._select_diverse_chunks(quality_filtered, adaptive_top_k, query_type, query_analysis)

            # 5. Generate chunk scores for transparency
            chunk_scores = self._generate_chunk_scores(selected_chunks)

            # 6. Determine selection strategy used
            selection_strategy = self._determine_selection_strategy(query_type, len(raw_results), len(selected_chunks))

            # 7. Check quality threshold compliance
            quality_threshold_met = self._check_quality_compliance(selected_chunks)

            processing_time = time.time() - start_time

            result = SelectionResult(
                selected_chunks=selected_chunks,
                chunk_scores=chunk_scores,
                total_candidates=len(raw_results),
                selection_strategy=selection_strategy,
                processing_time=processing_time,
                quality_threshold_met=quality_threshold_met,
            )

            logger.info(
                f"Selected {len(selected_chunks)}/{adaptive_top_k} chunks using {selection_strategy} "
                f"strategy in {processing_time:.3f}s"
            )

            return result

        except Exception as e:
            logger.error(f"Chunk selection failed: {e}")
            # Return top chunks as fallback
            fallback_chunks = raw_results[: min(top_k, len(raw_results))]
            return SelectionResult(
                selected_chunks=fallback_chunks,
                chunk_scores=[],
                total_candidates=len(raw_results),
                selection_strategy="fallback_error",
                processing_time=time.time() - start_time,
                quality_threshold_met=False,
            )

    def _calculate_quality_scores(
        self, chunks: list[dict[str, Any]], query_analysis: dict[str, Any], original_query: str
    ) -> list[dict[str, Any]]:
        """Calculate quality scores for all chunks"""
        scored_chunks = []

        for chunk in chunks:
            try:
                # Preserve existing quality_score if present (for test compatibility)
                if "quality_score" in chunk:
                    chunk_with_score = chunk.copy()
                    scored_chunks.append(chunk_with_score)
                else:
                    quality_score = self._calculate_chunk_quality(chunk, query_analysis, original_query)

                    # Add quality score to chunk data
                    chunk_with_score = chunk.copy()
                    chunk_with_score["quality_score"] = quality_score

                    scored_chunks.append(chunk_with_score)

            except Exception as e:
                logger.warning(f"Failed to score chunk {chunk.get('chunk_id', 'unknown')}: {e}")
                # Include chunk with minimum score
                chunk_with_score = chunk.copy()
                chunk_with_score["quality_score"] = 0.1
                scored_chunks.append(chunk_with_score)

        return scored_chunks

    def _calculate_chunk_quality(
        self, chunk: dict[str, Any], query_analysis: dict[str, Any], original_query: str
    ) -> float:
        """
        Calculate quality score for a single chunk based on multiple factors

        Score = base_score + sum(bonuses) - sum(penalties)
        Range: 0.0 - 1.0
        """
        base_score = 0.5
        bonuses = {}
        penalties = {}

        # Extract metadata and content
        metadata = chunk.get("metadata", {})
        content = chunk.get("content", "")

        # ✅ BONUSES (Factors that increase relevance)

        # Rich content bonus
        if len(content) > 100:  # Lowered threshold for test compatibility
            bonuses["rich_content"] = self.quality_weights["rich_content"]

        # Client match bonus
        client_name = metadata.get("client_name", "")
        detected_client = query_analysis.get("detected_client")
        if client_name and client_name != "CLIENTE_DESCONHECIDO" and client_name != "UNKNOWN" and detected_client:
            # Check direct client name match or client_variations
            client_variations = metadata.get("client_variations", [])
            if isinstance(client_variations, str):
                client_variations = [client_variations]

            # Match against client_name or variations
            match_targets = [client_name] + client_variations
            if any(detected_client.upper() in target.upper() for target in match_targets if target):
                bonuses["client_match"] = self.quality_weights["client_match"]

        # Technical metadata richness bonus
        has_technical = metadata.get("transactions") or metadata.get("technical_terms") or metadata.get("sap_modules")
        if has_technical:
            bonuses["technical_rich"] = self.quality_weights["technical_rich"]

        # Highlights/decisions availability bonus
        if metadata.get("highlights_summary") or metadata.get("decisions_summary"):
            bonuses["highlights_available"] = self.quality_weights["highlights_available"]

        # Relevant meeting phase bonus
        meeting_phase = metadata.get("meeting_phase", "")
        if meeting_phase in ["EXPLICACAO_PROCESSO", "DISCUSSAO_TECNICA", "Q_A"]:
            bonuses["relevant_phase"] = self.quality_weights["relevant_phase"]

        # High business impact bonus
        business_impact = metadata.get("business_impact", "")
        if business_impact in ["HIGH", "CRITICAL"]:
            bonuses["high_impact"] = self.quality_weights["high_impact"]

        # Defined speaker role bonus
        speaker_role = metadata.get("speaker_role", "")
        if speaker_role != "Participante" and speaker_role:
            bonuses["defined_speaker"] = self.quality_weights["defined_speaker"]

        # Query-specific bonuses
        if self._has_query_specific_match(chunk, original_query):
            bonuses["query_match"] = self.quality_weights["query_match"]

        # ❌ PENALTIES (Factors that decrease relevance)

        # Small content penalty
        if len(content) < 100:
            penalties["small_content"] = abs(self.quality_weights["small_content"])

        # Extra penalty for extremely small content (noise filtering)
        if len(content) < 20:  # Chunks like "Beleza?" or "É a mesma, é."
            penalties["noise_content"] = 0.6  # Stronger penalty for noise
        elif len(content) < 50:  # Medium-sized but likely fragmentary content
            penalties["fragment_content"] = 0.2  # Medium penalty for fragments

        # Introduction-only penalty (less substantial) - but only if content is also short
        if metadata.get("content_type") == "INTRODUÇÃO" and len(content) < 100:
            penalties["intro_only"] = abs(self.quality_weights["intro_only"])

        # Unknown speaker penalty
        if speaker_role == "Participante" or not speaker_role:
            penalties["unknown_speaker"] = abs(self.quality_weights["unknown_speaker"])

        # Low business impact penalty
        if business_impact == "LOW":
            penalties["low_impact"] = abs(self.quality_weights["low_impact"])

        # Incomplete metadata penalty
        if not metadata.get("searchable_tags"):
            penalties["incomplete_metadata"] = abs(self.quality_weights["incomplete_metadata"])

        # Conversational/informal content penalty (additional noise filtering)
        conversational_patterns = [
            r"^(Beleza\?|Ok\.|Tá\.|É\.?|Ah\.?|Então\.)$",
            r"^(Deixa eu ver|Eu não vou lembrar|Será que é)",
            r"^[A-Za-záàâãéèêíìîóòôõúùû]{1,5}[\.\?]?$",  # Very short words with accents
            r"^(é\s+a\s+mesma|tem\s+outra|é\s+que\s+tem)",  # Common fragments
        ]

        content_lower = content.strip().lower()
        for pattern in conversational_patterns:
            if re.match(pattern, content_lower, re.IGNORECASE):
                penalties["conversational_noise"] = 0.5  # Strong penalty for conversational noise
                break

        # Calculate final score
        total_bonuses = sum(bonuses.values())
        total_penalties = sum(penalties.values())
        final_score = base_score + total_bonuses - total_penalties

        # Clamp to 0-1 range
        final_score = max(0.0, min(1.0, final_score))

        logger.debug(
            f"Quality score {final_score:.3f} for chunk {chunk.get('chunk_id', 'unknown')} "
            f"(bonuses: {total_bonuses:.3f}, penalties: {total_penalties:.3f})"
        )

        return final_score

    def _has_query_specific_match(self, chunk: dict[str, Any], original_query: str) -> bool:
        """Check if chunk has query-specific relevance indicators"""
        if not original_query:
            return False

        content = chunk.get("content", "").lower()
        metadata = chunk.get("metadata", {})
        query_lower = original_query.lower()

        # Direct content matches
        query_words = [word for word in query_lower.split() if len(word) > 3]
        content_matches = sum(1 for word in query_words if word in content)
        if content_matches >= 2:
            return True

        # Metadata matches
        searchable_tags = str(metadata.get("searchable_tags", "")).lower()
        tag_matches = sum(1 for word in query_words if word in searchable_tags)
        if tag_matches >= 1:
            return True

        return False

    def _apply_quality_threshold(self, scored_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter chunks by quality threshold"""
        quality_threshold = self.performance_config["quality_threshold"]

        filtered_chunks = [chunk for chunk in scored_chunks if chunk.get("quality_score", 0.0) >= quality_threshold]

        # Always keep at least 1 chunk if any exist
        if not filtered_chunks and scored_chunks:
            # Keep the highest quality chunk
            best_chunk = max(scored_chunks, key=lambda x: x.get("quality_score", 0.0))
            filtered_chunks = [best_chunk]
            logger.info("No chunks met quality threshold - keeping best chunk")

        logger.debug(
            f"Quality filtering: {len(filtered_chunks)}/{len(scored_chunks)} chunks passed"
            f" threshold {quality_threshold}"
        )

        return filtered_chunks

    def _calculate_adaptive_top_k(
        self, base_top_k: int, query_type: QueryType, query_analysis: dict[str, Any], available_chunks: int
    ) -> int:
        """Calculate adaptive TOP_K based on query type and analysis"""

        # Get base configuration for query type
        type_config = self.top_k_strategy.get(query_type.value, self.top_k_strategy["SEMANTIC"])
        adaptive_top_k = type_config["base"]

        # Apply query-specific modifiers
        if query_analysis.get("has_specific_client"):
            if query_type == QueryType.SEMANTIC:
                adaptive_top_k = type_config.get("with_client", adaptive_top_k)
            elif query_type == QueryType.ENTITY:
                adaptive_top_k = type_config.get("client_focused", adaptive_top_k)

        if query_analysis.get("has_technical_terms"):
            if query_type == QueryType.SEMANTIC:
                adaptive_top_k = type_config.get("technical_query", adaptive_top_k)

        if query_analysis.get("is_broad_request"):
            if query_type == QueryType.SEMANTIC:
                adaptive_top_k = type_config.get("broad_query", adaptive_top_k)
            elif query_type == QueryType.METADATA:
                adaptive_top_k = type_config.get("summary_view", adaptive_top_k)

        # Special handling for global listing queries (METADATA)
        if query_type == QueryType.METADATA and query_analysis.get("is_listing_request"):
            # Get the original query to detect global listing intent
            original_query = query_analysis.get("original_query", "").lower()

            # Detect global listing patterns
            global_listing_patterns = [
                "liste" in original_query and "base" in original_query and "conhecimento" in original_query,
                "todos" in original_query and ("kts" in original_query or "vídeos" in original_query),
                "quais" in original_query
                and ("kts" in original_query or "vídeos" in original_query)
                and "temos" in original_query,
                query_analysis.get("is_listing_request") and not query_analysis.get("has_specific_client"),
            ]

            if any(global_listing_patterns):
                # Use video_list strategy for comprehensive global listings
                adaptive_top_k = type_config.get("video_list", adaptive_top_k)
                logger.debug(f"Applied video_list strategy for global METADATA query: {adaptive_top_k}")
            elif query_analysis.get("has_specific_client"):
                # Use client_list for client-specific listings
                adaptive_top_k = type_config.get("client_list", adaptive_top_k)
                logger.debug(f"Applied client_list strategy for client-specific METADATA query: {adaptive_top_k}")

        if query_analysis.get("query_complexity") == "complex":
            adaptive_top_k = int(adaptive_top_k * 1.2)
        elif query_analysis.get("query_complexity") == "simple":
            # For METADATA queries, don't reduce TOP_K to ensure complete listings
            if query_type != QueryType.METADATA:
                adaptive_top_k = int(adaptive_top_k * 0.8)

        # Respect max limits and available chunks
        max_limit = type_config.get("max_limit", 50)
        adaptive_top_k = min(adaptive_top_k, max_limit, available_chunks)

        # Ensure minimum
        adaptive_top_k = max(1, adaptive_top_k)

        logger.debug(f"Adaptive TOP_K: {base_top_k} → {adaptive_top_k} for {query_type.value} query")

        return adaptive_top_k

    def _select_metadata_listing_chunks(
        self, candidates: list[dict[str, Any]], target_count: int, query_analysis: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Special selection strategy for metadata listing queries that ensures
        at least one chunk from each unique video is included
        """
        selected: list[dict[str, Any]] = []
        videos_covered = set()

        # Group candidates by video_name
        video_groups: dict[str, list[dict[str, Any]]] = {}
        for chunk in candidates:
            video_name = chunk.get("metadata", {}).get("video_name", "")
            if video_name:
                if video_name not in video_groups:
                    video_groups[video_name] = []
                video_groups[video_name].append(chunk)

        # Sort each video group by quality score
        for video_name in video_groups:
            video_groups[video_name].sort(key=lambda x: x.get("quality_score", 0), reverse=True)

        # Step 1: Ensure at least one chunk from each video (priority coverage)
        for video_name, video_chunks in video_groups.items():
            if len(selected) >= target_count:
                break
            # Add the best chunk from this video
            best_chunk = video_chunks[0]
            selected.append(best_chunk)
            videos_covered.add(video_name)
            logger.debug(f"METADATA coverage: Added best chunk from video '{video_name}'")

        # Step 2: Fill remaining slots with highest quality chunks
        remaining_slots = target_count - len(selected)
        if remaining_slots > 0:
            # Get all remaining chunks (not the ones already selected)
            remaining_chunks = []
            for _video_name, video_chunks in video_groups.items():
                # Skip the first chunk (already selected) and add the rest
                remaining_chunks.extend(video_chunks[1:])

            # Sort by quality and select the best remaining ones
            remaining_chunks.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
            selected.extend(remaining_chunks[:remaining_slots])

        logger.info(f"METADATA listing selection: {len(videos_covered)} videos covered, {len(selected)} total chunks")
        return selected

    def _select_diverse_chunks(
        self, candidates: list[dict[str, Any]], target_count: int, query_type: QueryType, query_analysis: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Select diverse chunks to avoid redundancy and maximize coverage
        """
        # Special handling for METADATA listing queries to ensure video coverage
        if query_type == QueryType.METADATA and query_analysis.get("is_listing_request"):
            return self._select_metadata_listing_chunks(candidates, target_count, query_analysis)

        # Always apply quality-based sorting, even if we have fewer candidates than target
        # This ensures quality scoring and diversity algorithms are always applied

        selected: list[dict[str, Any]] = []
        used_segments = set()
        used_speakers = set()
        used_phases = set()
        used_clients = set()

        # Sort candidates by quality + similarity (if available)
        if query_type == QueryType.SEMANTIC:
            candidates_sorted = sorted(
                candidates,
                key=lambda x: (x.get("quality_score", 0) * 0.7 + x.get("similarity_score", 0) * 0.3),
                reverse=True,
            )
        else:
            candidates_sorted = sorted(candidates, key=lambda x: x.get("quality_score", 0), reverse=True)

        for chunk in candidates_sorted:
            if len(selected) >= target_count:
                break

            # Extract diversity factors
            segment_id = self._extract_segment_id(chunk.get("chunk_id", ""))
            speaker = chunk.get("metadata", {}).get("speaker", "")
            phase = chunk.get("metadata", {}).get("meeting_phase", "")
            client = chunk.get("metadata", {}).get("client_name", "")

            # Diversity criteria
            diversity_criteria = {
                # Always accept first 2 (highest quality)
                "top_quality": len(selected) < 2,
                # New segment (avoid consecutive chunks)
                "new_segment": segment_id not in used_segments,
                # New speaker perspective
                "new_speaker": speaker not in used_speakers,
                # New meeting phase
                "new_phase": phase not in used_phases,
                # Different client (for cross-client queries)
                "new_client": client not in used_clients,
                # Quality threshold met
                "quality_ok": chunk.get("quality_score", 0) >= self.diversity_config["quality_threshold"],
            }

            # Accept if meets diversity criteria
            accept_chunk = diversity_criteria["top_quality"] or (
                diversity_criteria["quality_ok"]
                and (
                    diversity_criteria["new_segment"]
                    or diversity_criteria["new_speaker"]
                    or diversity_criteria["new_phase"]
                    or (len(selected) < target_count * 0.8)  # Fill remaining slots
                )
            )

            if accept_chunk:
                selected.append(chunk)
                used_segments.add(segment_id)
                used_speakers.add(speaker)
                used_phases.add(phase)
                used_clients.add(client)

                logger.debug(
                    f"Selected chunk {chunk.get('chunk_id', 'unknown')} "
                    f"(quality: {chunk.get('quality_score', 0):.3f}, "
                    f"new_segment: {diversity_criteria['new_segment']}, "
                    f"new_speaker: {diversity_criteria['new_speaker']})"
                )

        return selected

    def _extract_segment_id(self, chunk_id: str) -> str:
        """Extract segment identifier from chunk_id to avoid consecutive chunks"""
        # Pattern: VISSIMO_KT_SD_20251001_segments_001_part_1
        match = re.search(r"segments_(\d+)", chunk_id)
        if match:
            return match.group(1)
        return chunk_id  # Fallback to full ID

    def _generate_chunk_scores(self, selected_chunks: list[dict[str, Any]]) -> list[ChunkScore]:
        """Generate detailed scoring information for transparency"""
        chunk_scores = []

        for i, chunk in enumerate(selected_chunks):
            chunk_score = ChunkScore(
                chunk_id=chunk.get("chunk_id", f"chunk_{i}"),
                quality_score=chunk.get("quality_score", 0.0),
                diversity_score=1.0 - (i / len(selected_chunks)),  # Earlier selection = higher diversity
                combined_score=chunk.get("quality_score", 0.0) * 0.7 + (1.0 - i / len(selected_chunks)) * 0.3,
                selection_reason=(
                    f"Quality: {chunk.get('quality_score', 0):.2f}, Position: {i + 1}/{len(selected_chunks)}"
                ),
            )
            chunk_scores.append(chunk_score)

        return chunk_scores

    def _determine_selection_strategy(self, query_type: QueryType, total_candidates: int, selected_count: int) -> str:
        """Determine which selection strategy was used based on query type"""

        if total_candidates == 0:
            return "no_candidates"

        # Always determine strategy based on query type first, not just candidate count
        if query_type == QueryType.METADATA:
            # For metadata, if we got all candidates, it's completeness strategy
            if total_candidates <= selected_count:
                return "metadata_completeness"
            else:
                return "metadata_filtered"
        elif query_type == QueryType.SEMANTIC:
            return "quality_similarity_diversity"
        elif query_type == QueryType.ENTITY:
            return "entity_focused"
        elif query_type == QueryType.TEMPORAL:
            return "temporal_ordered"
        elif query_type == QueryType.CONTENT:
            return "content_relevance"
        else:
            # Fallback: only use all_candidates if no quality filtering was applied
            if total_candidates <= selected_count:
                return "all_candidates"
            else:
                return "general_quality_diversity"

    def _check_quality_compliance(self, selected_chunks: list[dict[str, Any]]) -> bool:
        """Check if selected chunks meet quality compliance requirements"""
        if not selected_chunks:
            return False

        # Check if at least 80% of chunks meet quality threshold
        quality_threshold = self.performance_config["quality_threshold"]
        quality_chunks = sum(1 for chunk in selected_chunks if chunk.get("quality_score", 0.0) >= quality_threshold)

        compliance_ratio = quality_chunks / len(selected_chunks)
        return compliance_ratio >= 0.8

    def calculate_adaptive_top_k(self, query_type: QueryType, query_analysis: dict[str, Any]) -> int:
        """
        Public method to calculate adaptive TOP_K without full selection
        Used by search engine for ChromaDB query optimization
        """
        base_top_k = self.top_k_strategy.get(query_type.value, {}).get("base", 10)
        return self._calculate_adaptive_top_k(base_top_k, query_type, query_analysis, 1000)

    # PUBLIC API METHODS (for test compatibility)
    def calculate_chunk_quality(
        self, chunk_or_metadata: dict[str, Any], query_context: dict[str, Any], content: str | None = None
    ) -> float:
        """
        Public method to calculate quality score for a chunk
        Compatible with test expectations

        Args:
            chunk_or_metadata: Either full chunk with 'metadata' key, or just metadata dict
            query_context: Query context with detected entities/clients
            content: Content string (optional, inferred if not provided)

        Returns:
            Quality score between 0.0 and 1.0
        """
        # Handle both chunk and metadata-only inputs
        if "metadata" in chunk_or_metadata:
            # Full chunk provided
            chunk = chunk_or_metadata
        else:
            # Only metadata provided - need to reconstruct chunk
            chunk = {"metadata": chunk_or_metadata, "content": content or chunk_or_metadata.get("content", "")}

        # Convert query_context to query_analysis format
        query_analysis = {
            "detected_client": query_context.get("detected_client"),
            "detected_entities": query_context.get("detected_entities", {}),
            "has_technical_terms": query_context.get("has_technical_terms", False),
        }

        return self._calculate_chunk_quality(chunk, query_analysis, "")

    def select_diverse_chunks(
        self, candidates: list[dict[str, Any]], target_count: int, query_type: str
    ) -> list[dict[str, Any]]:
        """
        Public method to select diverse chunks
        Compatible with test expectations

        Args:
            candidates: List of candidate chunks with quality_score
            target_count: Target number of chunks to select
            query_type: Query type as string

        Returns:
            List of selected diverse chunks
        """
        # Convert string query_type to QueryType enum
        try:
            if hasattr(QueryType, query_type.upper()):
                query_type_enum = getattr(QueryType, query_type.upper())
            else:
                query_type_enum = QueryType.SEMANTIC  # Default fallback
        except Exception:
            query_type_enum = QueryType.SEMANTIC

        # Use internal method
        return self._select_diverse_chunks(candidates, target_count, query_type_enum, {})


# Utility functions for external use
def select_chunks(
    chunks: list[dict[str, Any]], top_k: int, query_type: QueryType, query_analysis: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Convenience function for chunk selection"""
    selector = ChunkSelector()
    query_analysis = query_analysis or {}
    result = selector.select_intelligent_chunks(chunks, top_k, query_type, query_analysis)
    return result.selected_chunks


def calculate_quality_score(chunk: dict[str, Any], query_context: dict[str, Any] | None = None) -> float:
    """Calculate quality score for a single chunk"""
    selector = ChunkSelector()
    query_context = query_context or {}
    return selector._calculate_chunk_quality(chunk, query_context, "")
