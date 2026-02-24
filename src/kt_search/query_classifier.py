"""
Query Classifier - Contextual Classification System

This module implements contextual query classification that determines the RAG type
based on query + enriched context. Uses the enrichment data to make more accurate
classifications than pattern matching alone.

Pipeline Position: Query Enricher → **Query Classifier** → ChromaDB Search
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from utils.logger_setup import LoggerManager

from .kt_search_constants import QUERY_PATTERNS

logger = LoggerManager.get_logger(__name__)


class QueryType(Enum):
    """Supported RAG query types"""

    SEMANTIC = "SEMANTIC"  # Busca por significado/conteúdo
    METADATA = "METADATA"  # Busca estruturada/listagem
    ENTITY = "ENTITY"  # Busca por entidades específicas
    TEMPORAL = "TEMPORAL"  # Busca por períodos
    CONTENT = "CONTENT"  # Busca literal no conteúdo


@dataclass
class ClassificationResult:
    """Result of query classification"""

    query_type: QueryType
    confidence: float
    strategy: dict[str, Any]
    reasoning: str
    fallback_types: list[QueryType]
    processing_time: float


class QueryClassifier:
    """
    Contextual Query Classifier for KT semantic search

    Functions:
    - Classify RAG type based on enriched query + context
    - Determine search strategy for each type
    - Provide fallback options for hybrid queries
    - Calculate classification confidence

    Uses enrichment data for more accurate classification than patterns alone.
    """

    def __init__(self):
        """Initialize Query Classifier with patterns and strategies"""
        self.query_patterns = QUERY_PATTERNS
        self.classification_strategies = self._load_classification_strategies()
        self.hybrid_rules = self._load_hybrid_rules()

        # Enhanced patterns for KT-specific detection
        self.specific_kt_patterns = {
            "kt_with_title_and_date": r"kt\s*[-\s]*([a-záéíóúãõç\s]+)[-\s]*\d{8}_\d{6}",
            "kt_with_common_types": r"kt\s+(sustentação|iflow|correção|estratégia|estorno|integração|mm|fi|sd|ewm)",
            "discussion_about_kt": r"(no|do|sobre)\s+kt\s*[-\s]*([a-záéíóúãõç\s]+)",
            "kt_analysis_request": r"(temas|pontos|informações|transações|problemas|principais)\s.*kt",
            "specific_kt_reference": r"discutidos?\s+no\s+kt",
        }

        self.analysis_indicators = [
            "temas relevantes",
            "principais pontos",
            "resumo",
            "resuma",
            "principais ponto",
            "o que motivou",
            "transações explicadas",
            "foram discutidos",
            "pontos discutidos",
            "informações sobre",
            "detalhes",
            "conteúdo",
            "explicadas no",
            "abordados no",
        ]

        self.real_temporal_indicators = [
            r"últimos?\s+\d+\s+(dias?|semanas?|meses?|anos?)",
            r"(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+\d{4}",
            r"kts?\s+dos?\s+últimos?",
            r"reuniões\s+de\s+\w+",
            r"problemas\s+recentes?",
            r"nos?\s+últimos?",
        ]

        logger.info("QueryClassifier initialized with enhanced KT-specific detection")

    def classify_query_with_context(
        self, original_query: str, entities: dict[str, Any], context: dict[str, Any]
    ) -> ClassificationResult:
        """
        Classify query type using enriched context for maximum accuracy

        Args:
            original_query: Original query text
            entities: Detected entities from enrichment
            context: Contextual information from enrichment

        Returns:
            ClassificationResult with type, strategy, and confidence
        """
        import time

        start_time = time.time()

        try:
            logger.info(
                f"Classifying query with context: '{original_query[:50]}{'...' if len(original_query) > 50 else ''}'"
            )

            # 1. Run all classification methods
            pattern_score = self._classify_by_patterns(original_query)
            entity_score = self._classify_by_entities(entities, original_query)
            context_score = self._classify_by_context(context)

            # 2. Weighted combination for final classification
            final_scores = self._combine_classification_scores(pattern_score, entity_score, context_score)

            # 3. Determine primary type and confidence
            primary_type, confidence = self._get_primary_classification(final_scores)

            # 4. Generate search strategy for the classified type
            strategy = self._generate_search_strategy(primary_type, entities, context)

            # 5. Determine fallback types for hybrid handling
            fallback_types = self._get_fallback_types(final_scores, primary_type)

            # 6. Generate reasoning explanation
            reasoning = self._generate_reasoning(primary_type, entities, context, final_scores)

            processing_time = time.time() - start_time

            result = ClassificationResult(
                query_type=primary_type,
                confidence=confidence,
                strategy=strategy,
                reasoning=reasoning,
                fallback_types=fallback_types,
                processing_time=processing_time,
            )

            logger.info(
                f"Query classified as {primary_type.value} with {confidence:.2f} confidence in {processing_time:.3f}s"
            )

            return result

        except Exception as e:
            logger.error(f"Query classification failed: {e}")
            # Return safe fallback
            return ClassificationResult(
                query_type=QueryType.SEMANTIC,
                confidence=0.3,
                strategy=self._get_default_strategy(QueryType.SEMANTIC),
                reasoning=f"Fallback classification due to error: {str(e)}",
                fallback_types=[QueryType.METADATA],
                processing_time=time.time() - start_time,
            )

    def _classify_by_patterns(self, query: str) -> dict[QueryType, float]:
        """Enhanced classification that differentiates KT-specific vs temporal patterns"""
        # 1. Run original classification
        scores = {qtype: 0.0 for qtype in QueryType}
        query_lower = query.lower()

        # Apply existing patterns with semantic override logic
        for query_type, patterns in self.query_patterns.items():
            qtype_enum = QueryType(query_type)
            for pattern in patterns:
                if pattern in query_lower:
                    pattern_weight = self._get_pattern_weight(pattern, query_type)
                    scores[qtype_enum] += pattern_weight

        # Override METADATA classification for semantic queries starting with "quais"
        if query_lower.startswith("quais") and any(
            semantic_word in query_lower
            for semantic_word in [
                "decisões",
                "problemas",
                "riscos",
                "valores",
                "custos",
                "questões",
                "foram tomadas",
                "importantes",
                "identificados",
                "mencionados",
                "discutidos",
            ]
        ):
            logger.info("🔄 OVERRIDE: 'Quais' detectado com contexto semântico - mudando METADATA → SEMANTIC")
            scores[QueryType.METADATA] = 0.1  # Reduzir drasticamente
            scores[QueryType.SEMANTIC] = 0.9  # Aumentar para semântico

        # 2. Detect KT-specific vs temporal
        kt_detection = self._detect_specific_kt_query(query)

        # 3. Apply override based on detection
        if kt_detection["is_specific_kt"] and kt_detection["confidence"] >= 0.7:
            logger.info(f"🎯 KT ESPECÍFICO detectado: {query}")
            logger.info(f"   📋 Título extraído: {kt_detection.get('kt_title_extracted')}")
            logger.info(f"   📊 Confiança: {kt_detection['confidence']:.2f}")
            logger.info(f"   🔍 Reasoning: {'; '.join(kt_detection['reasoning'])}")

            # Check if query has semantic analysis indicators
            query_lower = query.lower()
            has_analysis_request = any(
                indicator in query_lower
                for indicator in [
                    "resuma",
                    "resumo",
                    "principais pontos",
                    "pontos discutidos",
                    "foram discutidos",
                    "informações sobre",
                    "o que foi",
                    "como foram",
                    "quais foram",
                    "detalhes",
                    "decisões",
                    "problemas",
                    "riscos",
                    "valores",
                    "custos",
                    "questões técnicas",
                    "foram tomadas",
                    "importantes",
                    "identificados",
                    "mencionados",
                    "discutidos",
                ]
            )

            if has_analysis_request:
                # Semantic analysis of specific KT
                scores[QueryType.SEMANTIC] = 0.95  # Alta prioridade para análise semântica
                scores[QueryType.CONTENT] = 0.3  # Backup busca literal
                scores[QueryType.TEMPORAL] = 0.0  # ❌ Evitar temporal incorreto
                scores[QueryType.METADATA] = 0.0  # ❌ Evitar listagem genérica
                scores[QueryType.ENTITY] = 0.0
                logger.info("   🎯 Classificado como SEMANTIC (análise de KT específico)")
            else:
                # Literal search in specific KT
                scores[QueryType.CONTENT] = 0.95  # Alta prioridade para busca específica
                scores[QueryType.SEMANTIC] = 0.3  # Backup semântico
                scores[QueryType.TEMPORAL] = 0.0  # ❌ Evitar temporal incorreto
                scores[QueryType.METADATA] = 0.0  # ❌ Evitar listagem genérica
                scores[QueryType.ENTITY] = 0.0
                logger.info("   🎯 Classificado como CONTENT (busca literal em KT específico)")

            return scores

        elif kt_detection["is_temporal_period"] and kt_detection["confidence"] >= 0.7:
            logger.info(f"⏰ PERÍODO TEMPORAL detectado: {query}")
            logger.info(f"   📊 Confiança: {kt_detection['confidence']:.2f}")

            # Boost TEMPORAL mantendo lógica original
            temporal_boost = 0.8
            scores[QueryType.TEMPORAL] = max(scores.get(QueryType.TEMPORAL, 0), temporal_boost)

            return scores

        # 3. If no specific detection, use original logic
        logger.debug(f"Usando classificação padrão para: {query}")

        # Normalize scores
        max_score = max(scores.values()) if any(scores.values()) else 1.0
        if max_score > 0:
            scores = {qtype: score / max_score for qtype, score in scores.items()}

        logger.debug(f"Pattern classification scores: {scores}")
        return scores

    def _classify_by_entities(self, entities: dict[str, Any], original_query: str = "") -> dict[QueryType, float]:
        """Classify based on detected entities with INTELLIGENT CONTEXT-AWARE approach"""
        scores = {qtype: 0.0 for qtype in QueryType}

        if not entities:
            return scores

        # ARCHITECTURE-ALIGNED Entity classification rules with INTENT DETECTION
        for entity_type, entity_data in entities.items():
            entity_values = entity_data.get("values", [])

            if entity_type == "clients" and entity_values:
                # Client detection SUPPORTS but doesn't AUTOMATICALLY mean ENTITY query
                # Most client mentions are actually SEMANTIC questions ABOUT the client
                scores[QueryType.ENTITY] += 0.2  # Further reduced - presence ≠ entity question
                scores[QueryType.SEMANTIC] += 0.6  # Increased - "F110 no ambiente Dexco" is semantic
                scores[QueryType.METADATA] += 0.15  # Reduced - only for actual listing requests

            elif entity_type == "transactions" and entity_values:
                # Transactions mentioned are usually SEMANTIC questions ABOUT the transaction
                # "F110 no ambiente Dexco" = asking about F110, not listing transactions
                scores[QueryType.SEMANTIC] += 0.7  # Increased - asking ABOUT transactions is semantic
                scores[QueryType.CONTENT] += 0.4  # Reduced - literal search is secondary intent
                scores[QueryType.ENTITY] += 0.1  # Minimal - transactions are rarely entity-focused

            elif entity_type == "temporal" and entity_values:
                # Temporal is highest priority when detected
                scores[QueryType.TEMPORAL] += 0.8  # Keep high - temporal patterns are explicit
                scores[QueryType.METADATA] += 0.1  # Further reduced - temporal ≠ metadata listing

            elif entity_type == "participants" and entity_values:
                # INTELLIGENT PARTICIPANT DETECTION - only ENTITY if asking about participants
                # Check if query actually asks about participants vs just mentioning them
                if self._is_asking_about_participants(original_query):
                    scores[QueryType.ENTITY] += 0.7  # High score only if actually asking about participants
                    scores[QueryType.SEMANTIC] += 0.2  # Lower semantic score
                else:
                    # Just mentioning participants, not asking about them
                    scores[QueryType.ENTITY] += 0.1  # Very low entity score
                    scores[QueryType.SEMANTIC] += 0.5  # Higher semantic score

            elif entity_type == "sap_modules" and entity_values:
                # SAP modules are technical content, primarily semantic
                scores[QueryType.SEMANTIC] += 0.6  # Increased - module questions are semantic
                scores[QueryType.METADATA] += 0.1  # Further reduced - not primarily metadata

        logger.debug(f"Intelligent context-aware entity classification scores: {scores}")
        return scores

    def _classify_by_context(self, context: dict[str, Any]) -> dict[QueryType, float]:
        """Classify based on contextual information"""
        scores = {qtype: 0.0 for qtype in QueryType}

        # Listing intent signals (Enhanced)
        if context.get("is_listing_request", False):
            scores[QueryType.METADATA] += 0.8  # Increased from 0.6

        # Comparison intent signals
        if context.get("is_comparison_request", False):
            scores[QueryType.SEMANTIC] += 0.5  # Increased from 0.4
            scores[QueryType.ENTITY] += 0.4  # Increased from 0.3

        # Broad request signals
        if context.get("is_broad_request", False):
            scores[QueryType.METADATA] += 0.5  # Increased from 0.4
            scores[QueryType.SEMANTIC] += 0.4  # Increased from 0.3

        # Query complexity signals - FIXED LOGIC
        complexity = context.get("query_complexity", "medium")
        if complexity == "complex":
            scores[QueryType.SEMANTIC] += 0.3  # Complex queries are semantic
        elif complexity == "simple":
            # FIXED: Simple queries without specific patterns should be SEMANTIC (fallback)
            # Don't automatically push simple queries to METADATA/ENTITY
            scores[QueryType.SEMANTIC] += 0.3  # Simple questions are still semantic
            # Removed: scores[QueryType.METADATA] += 0.2
            # Removed: scores[QueryType.ENTITY] += 0.2

        # Specific client signals
        if context.get("has_specific_client", False):
            scores[QueryType.SEMANTIC] += 0.4  # Client info questions are semantic
            scores[QueryType.ENTITY] += 0.2  # Reduced - specific client doesn't always mean entity query

        # Technical complexity signals
        if context.get("technical_complexity") == "high":
            scores[QueryType.SEMANTIC] += 0.4
            scores[QueryType.CONTENT] += 0.2

        # Temporal scope signals
        if context.get("has_temporal", False):
            scores[QueryType.TEMPORAL] += 0.5

        logger.debug(f"Context classification scores: {scores}")
        return scores

    def _combine_classification_scores(
        self,
        pattern_scores: dict[QueryType, float],
        entity_scores: dict[QueryType, float],
        context_scores: dict[QueryType, float],
    ) -> dict[QueryType, float]:
        """Combine classification scores with PRIORITY-BASED weighted approach"""
        combined_scores = {qtype: 0.0 for qtype in QueryType}

        # ARCHITECTURE-BASED PRIORITY ORDER:
        # 1. CONTENT RAG → highest specificity (literal search indicators)
        # 2. METADATA RAG → clear listing/counting patterns
        # 3. TEMPORAL RAG → explicit temporal patterns
        # 4. ENTITY RAG → participant/client questions
        # 5. SEMANTIC RAG → fallback for everything else

        # Base weights for different classification methods
        pattern_weight = 0.5  # Patterns are PRIMARY (increased from 0.3)
        entity_weight = 0.3  # Entities provide context (decreased from 0.4)
        context_weight = 0.2  # Context provides nuance (decreased from 0.3)

        for qtype in QueryType:
            combined_scores[qtype] = (
                pattern_scores.get(qtype, 0.0) * pattern_weight
                + entity_scores.get(qtype, 0.0) * entity_weight
                + context_scores.get(qtype, 0.0) * context_weight
            )

        # PRIORITY OVERRIDE LOGIC - Architecture compliance
        priority_multipliers = {
            QueryType.CONTENT: 2.0,  # Highest priority - literal search is very specific
            QueryType.METADATA: 1.8,  # High priority - listing is clear intent
            QueryType.TEMPORAL: 1.6,  # High priority - temporal patterns are explicit
            QueryType.ENTITY: 1.3,  # Medium priority - can be confused with semantic
            QueryType.SEMANTIC: 1.0,  # Base priority - fallback for everything
        }

        # Apply priority multipliers
        for qtype, score in combined_scores.items():
            if score > 0.1:  # Only apply to types with some evidence
                combined_scores[qtype] = score * priority_multipliers[qtype]

        # INTENT-BASED BOOSTERS - Architecture-specific patterns
        # Apply strong boosts for high-specificity patterns

        # CONTENT RAG boosters - highest priority
        content_score = pattern_scores.get(QueryType.CONTENT, 0.0)
        if content_score > 0.3:
            combined_scores[QueryType.CONTENT] += 1.0  # Strong boost for literal search

        # METADATA RAG boosters - clear listing intent
        metadata_score = pattern_scores.get(QueryType.METADATA, 0.0)
        if metadata_score > 0.3:
            combined_scores[QueryType.METADATA] += 0.8  # Strong boost for listing

        # TEMPORAL RAG boosters - explicit time patterns
        temporal_score = pattern_scores.get(QueryType.TEMPORAL, 0.0)
        if temporal_score > 0.3:
            combined_scores[QueryType.TEMPORAL] += 0.8  # Strong boost for temporal

        # ENTITY vs SEMANTIC disambiguation
        entity_score = pattern_scores.get(QueryType.ENTITY, 0.0)
        semantic_score = pattern_scores.get(QueryType.SEMANTIC, 0.0)

        # SEMANTIC boost for specific question patterns (priority)
        if semantic_score > 0.3:
            combined_scores[QueryType.SEMANTIC] += 0.8  # Strong boost for semantic questions

        # ENTITY should only win with clear entity patterns and no semantic intent
        elif entity_score > 0.5 and semantic_score < 0.2:
            combined_scores[QueryType.ENTITY] += 0.4  # Reduced boost - entity must be clear

        # General information queries prefer SEMANTIC
        elif semantic_score > 0.1:
            combined_scores[QueryType.SEMANTIC] += 0.5  # Prefer semantic for information queries

        logger.debug(f"Priority-adjusted classification scores: {combined_scores}")
        return combined_scores

    def _get_primary_classification(self, scores: dict[QueryType, float]) -> tuple[QueryType, float]:
        """Determine primary classification and confidence"""
        if not any(scores.values()):
            # No strong signals, default to SEMANTIC
            return QueryType.SEMANTIC, 0.3

        # Get highest scoring type
        primary_type = max(scores, key=lambda k: scores[k])
        primary_score = scores[primary_type]

        # Calculate confidence based on actual score + enhancements
        sorted_scores = sorted(scores.values(), reverse=True)

        # Base confidence from the score itself (scaled up)
        confidence = primary_score * 1.4  # Scale factor to reach higher confidence

        # Score separation bonus (clear winner gets boost)
        if len(sorted_scores) > 1:
            score_separation = sorted_scores[0] - sorted_scores[1]
            separation_bonus = min(0.2, score_separation * 0.5)
            confidence += separation_bonus

        # Pattern-specific bonuses for high-confidence patterns
        pattern_confidence_bonus = self._get_pattern_confidence_bonus(primary_type, scores)
        confidence += pattern_confidence_bonus

        # Apply tiered confidence levels with higher thresholds
        if confidence >= 0.65:
            confidence = max(0.8, confidence)  # Strong signals get 0.8+
        elif confidence >= 0.45:
            confidence = max(0.7, confidence)  # Good signals get 0.7+
        elif confidence >= 0.25:
            confidence = max(0.6, confidence)  # Decent signals get 0.6+
        else:
            confidence = max(0.3, confidence)  # Weak signals get 0.3+

        # Apply bounds
        confidence = max(0.3, min(0.95, confidence))

        return primary_type, confidence

    def _get_pattern_confidence_bonus(self, query_type: QueryType, scores: dict[QueryType, float]) -> float:
        """Get confidence bonus based on pattern quality and type-specific characteristics"""
        bonus = 0.0

        # Type-specific high-confidence patterns
        if query_type == QueryType.METADATA:
            # METADATA patterns are usually very clear
            if scores[query_type] > 0.5:
                bonus += 0.15

        elif query_type == QueryType.ENTITY:
            # ENTITY patterns with participation words are clear
            if scores[query_type] > 0.4:
                bonus += 0.15

        elif query_type == QueryType.TEMPORAL:
            # TEMPORAL patterns are usually explicit
            if scores[query_type] > 0.5:
                bonus += 0.2

        elif query_type == QueryType.CONTENT:
            # CONTENT patterns like "onde mencionaram" are very specific
            if scores[query_type] > 0.5:
                bonus += 0.2

        elif query_type == QueryType.SEMANTIC:
            # SEMANTIC is default but can be boosted with multiple signals
            if len([s for s in scores.values() if s > 0.1]) >= 2:
                bonus += 0.1  # Multiple signals boost confidence

        return bonus

    def _get_fallback_types(self, scores: dict[QueryType, float], primary_type: QueryType) -> list[QueryType]:
        """Determine fallback types for hybrid queries"""
        # Sort by score, excluding primary type
        remaining_scores = {qtype: score for qtype, score in scores.items() if qtype != primary_type}
        sorted_types = sorted(remaining_scores.items(), key=lambda x: x[1], reverse=True)

        # Include types with score > 0.3 as potential fallbacks
        fallback_types = [qtype for qtype, score in sorted_types if score > 0.3]

        # Limit to top 2 fallbacks
        return fallback_types[:2]

    def _generate_search_strategy(
        self, query_type: QueryType, entities: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate specific search strategy for the classified type"""

        if query_type == QueryType.SEMANTIC:
            return self._get_semantic_strategy(entities, context)

        elif query_type == QueryType.METADATA:
            return self._get_metadata_strategy(entities, context)

        elif query_type == QueryType.ENTITY:
            return self._get_entity_strategy(entities, context)

        elif query_type == QueryType.TEMPORAL:
            return self._get_temporal_strategy(entities, context)

        elif query_type == QueryType.CONTENT:
            return self._get_content_strategy(entities, context)

        else:
            return self._get_default_strategy(query_type)

    def _get_semantic_strategy(self, entities: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Generate strategy for SEMANTIC RAG"""
        strategy: dict[str, Any] = {
            "type": "SEMANTIC",
            "use_embedding": True,
            "primary_fields": ["content"],
            "boost_fields": ["highlights_summary", "decisions_summary", "content_type"],
            "filters": {},
            "top_k_modifier": 1.0,
            "client_detected": False,
            "technical_detected": False,
        }

        # Client-specific boost
        if "clients" in entities:
            client = entities["clients"]["values"][0] if entities["clients"]["values"] else None
            if client:
                strategy["filters"]["client_name"] = client
                strategy["top_k_modifier"] = 1.5
                strategy["client_detected"] = True
                strategy["detected_client"] = client

        # Technical query optimization
        if "transactions" in entities or context.get("technical_complexity") == "high":
            strategy["boost_fields"].extend(["transactions", "technical_terms", "sap_modules"])
            strategy["top_k_modifier"] = 0.8  # More focused
            strategy["technical_detected"] = True

        return strategy

    def _get_metadata_strategy(self, entities: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Generate strategy for METADATA RAG"""
        strategy = {
            "type": "METADATA",
            "use_embedding": False,
            "aggregation": "distinct",
            "primary_fields": ["video_name", "client_name"],
            "sort_by": "client_name ASC",
            "top_k_modifier": 2.0,  # More results for listings
        }

        # Determine what to list
        if context.get("is_listing_request"):
            if any("vídeo" in word for word in context.get("query_keywords", [])):
                strategy["target"] = "videos"
                strategy["display_fields"] = ["video_name", "client_name", "meeting_date", "original_url"]
            elif any("cliente" in word for word in context.get("query_keywords", [])):
                strategy["target"] = "clients"
                strategy["display_fields"] = ["client_name", "count(chunks)", "latest_meeting_date"]
            else:
                strategy["target"] = "general"
                strategy["display_fields"] = ["video_name", "client_name", "meeting_date"]

        return strategy

    def _get_entity_strategy(self, entities: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Generate strategy for ENTITY RAG"""
        strategy = {
            "type": "ENTITY",
            "use_embedding": False,
            "primary_fields": ["participants_mentioned", "client_name"],
            "aggregation": "unique_merge",
            "top_k_modifier": 1.2,
            "client_detected": False,
            "participants_detected": False,
        }

        # Client-focused entity search
        if "clients" in entities:
            client = entities["clients"]["values"][0] if entities["clients"]["values"] else None
            if client:
                strategy["filters"] = {"client_name": client}
                strategy["focus"] = "client_entities"
                strategy["client_detected"] = True
                strategy["detected_client"] = client

        # Participant-focused search
        if "participants" in entities or "participou" in context.get("original_query", "").lower():
            strategy["target"] = "participants"
            strategy["primary_fields"] = ["participants_mentioned", "participants_list"]
            strategy["related_fields"] = ["speaker", "speaker_role", "meeting_phase"]
            strategy["participants_detected"] = True

        return strategy

    def _get_temporal_strategy(self, entities: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Generate strategy for TEMPORAL RAG"""
        strategy = {
            "type": "TEMPORAL",
            "use_embedding": False,
            "primary_fields": ["meeting_date", "processing_date"],
            "sort_by": "meeting_date DESC",
            "top_k_modifier": 1.3,
        }

        # Parse temporal constraints
        if "temporal" in entities:
            temporal_values = entities["temporal"]["values"]
            strategy["temporal_filters"] = self._parse_temporal_constraints(temporal_values)

        # Recent-focused vs date-specific
        temporal_scope = context.get("temporal_scope", "general")
        if temporal_scope == "recent":
            strategy["focus"] = "recent"
            strategy["top_k_modifier"] = 0.8
        elif temporal_scope == "specific_date":
            strategy["focus"] = "date_range"
            strategy["top_k_modifier"] = 1.5

        return strategy

    def _get_content_strategy(self, entities: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Generate strategy for CONTENT RAG"""
        strategy: dict[str, Any] = {
            "type": "CONTENT",
            "use_embedding": False,
            "search_method": "enhanced_text_search",
            "primary_field": "content",
            "case_sensitive": False,
            "highlight_matches": True,
            "top_k_modifier": 1.5,
        }

        # Extract enhanced search terms for fuzzy matching
        strategy["search_terms_enhanced"] = self._extract_literal_terms_enhanced(entities, context)
        strategy["search_terms"] = self._extract_literal_terms(entities, context)  # Legacy compatibility

        # Determine search type based on enhanced terms
        enhanced_terms = strategy["search_terms_enhanced"]
        if enhanced_terms["exact_terms"]:
            strategy["search_type"] = "exact_plus_fuzzy"
            strategy["partial_match"] = True
        elif enhanced_terms["client_variations"] or enhanced_terms["fuzzy_terms"]:
            strategy["search_type"] = "fuzzy_matching"
            strategy["partial_match"] = True
        else:
            strategy["search_type"] = "partial"
            strategy["partial_match"] = True

        return strategy

    def _parse_temporal_constraints(self, temporal_values: list[str]) -> dict[str, Any]:
        """Parse temporal values into ChromaDB filter constraints"""
        constraints = {}

        from datetime import timedelta

        # 🚨 P1-2 FIX: Usar data dos dados mais recentes como baseline, não data atual
        today = self._get_latest_data_date()

        for value in temporal_values:
            if value.startswith("recent_"):
                # Parse "recent_30_days" format
                parts = value.split("_")
                if len(parts) >= 3:
                    number = int(parts[1])
                    period = parts[2]

                    if period.startswith("dia"):
                        delta = timedelta(days=number)
                    elif period.startswith("semana"):
                        delta = timedelta(weeks=number)
                    elif period.startswith("mes"):
                        delta = timedelta(days=number * 30)  # Approximate
                    else:
                        continue

                    start_date = (today - delta).strftime("%Y-%m-%d")
                    # Store for post-processing (string dates work better)
                    constraints["_temporal_filter"] = {"start_date": start_date, "type": "gte"}

            elif value.startswith("specific_"):
                # Parse "specific_setembro_2024" format
                parts = value.split("_")
                if len(parts) >= 3:
                    month = parts[1]
                    year = parts[2]

                    month_numbers = {
                        "janeiro": 1,
                        "fevereiro": 2,
                        "março": 3,
                        "abril": 4,
                        "maio": 5,
                        "junho": 6,
                        "julho": 7,
                        "agosto": 8,
                        "setembro": 9,
                        "outubro": 10,
                        "novembro": 11,
                        "dezembro": 12,
                    }

                    if month in month_numbers:
                        month_num = month_numbers[month]
                        start_date_str = f"{year}-{month_num:02d}-01"

                        # Store date for post-processing instead of using $gte
                        # ChromaDB doesn't support string date comparison operators
                        constraints["_temporal_filter"] = {"start_date": start_date_str, "type": "gte"}

        # Return constraints (already cleaned for post-processing)
        return constraints

    def _get_latest_data_date(self):
        """Descobre automaticamente a data mais recente dos dados disponíveis"""
        try:
            from datetime import datetime

            # Importar ChromaDBManager para consultar dados
            from ..indexing.chromadb_manager import ChromaDBManager

            try:
                chromadb_manager = ChromaDBManager()

                # Buscar algumas amostras para encontrar a data mais recente
                results = chromadb_manager.query_metadata(
                    where_filter=None,
                    limit=50,  # Amostra pequena mas representativa
                    include_content=False,
                )

                latest_date = None
                for result in results.get("results", []):
                    metadata = result.get("metadata", {})
                    meeting_date_str = metadata.get("meeting_date")

                    if meeting_date_str:
                        try:
                            # Converter string de data para datetime
                            if isinstance(meeting_date_str, str):
                                meeting_date = datetime.strptime(meeting_date_str, "%Y-%m-%d")
                                if latest_date is None or meeting_date > latest_date:
                                    latest_date = meeting_date
                        except ValueError:
                            continue

                if latest_date:
                    logger.info(f"🗓️ Data mais recente dos dados encontrada: {latest_date.strftime('%Y-%m-%d')}")
                    return latest_date
                else:
                    logger.warning("Nenhuma data válida encontrada nos dados, usando fallback")

            except Exception as e:
                logger.warning(f"Erro ao consultar ChromaDB para data mais recente: {e}")

            # Fallback: usar data mais recente conhecida dos dados reais
            fallback_date = datetime(2025, 10, 24)  # Data mais recente real: 2025-10-24
            logger.info(f"🔄 Usando data de fallback (dados reais): {fallback_date.strftime('%Y-%m-%d')}")
            return fallback_date

        except Exception as e:
            logger.warning(f"Erro ao determinar data mais recente: {e}")
            # Em caso de erro, usar data atual como último recurso
            return datetime.now()

    def _has_specific_video_reference(self, query_lower: str) -> bool:
        """Verifica se query menciona vídeo específico consultando a base dinamicamente"""
        try:
            from ..indexing.chromadb_manager import ChromaDBManager

            # Cache para evitar consultas repetidas
            if not hasattr(self, "_video_titles_cache"):
                chromadb_manager = ChromaDBManager()
                results = chromadb_manager.query_metadata(
                    where_filter=None,
                    limit=50,  # Amostra representativa
                    include_content=False,
                )

                # Extrair títulos únicos dos vídeos
                video_titles = set()
                for result in results.get("results", []):
                    metadata = result.get("metadata", {})
                    video_name = metadata.get("video_name", "")
                    if video_name:
                        # Extrair palavras-chave relevantes do título
                        title_words = video_name.lower().replace("-", " ").split()
                        for word in title_words:
                            if len(word) > 3 and word not in ["gravacao", "reuniao", "video"]:
                                video_titles.add(word)

                self._video_titles_cache = video_titles
                logger.debug(f"Cache de títulos criado: {len(video_titles)} palavras-chave")

            # Verificar se query contém palavras-chave dos títulos de vídeos
            query_words = query_lower.replace("-", " ").split()
            matches = []
            for word in query_words:
                if len(word) > 3 and word in self._video_titles_cache:
                    matches.append(word)

            if matches:
                logger.info(f"🎬 Referência a vídeo específico detectada: {matches}")
                return True

            return False

        except Exception as e:
            logger.warning(f"Erro ao verificar referência específica a vídeo: {e}")
            # Fallback: detectar alguns padrões óbvios sem consultar base
            obvious_patterns = ["iflow", "sustentação", "correção", "kickoff"]
            return any(pattern in query_lower for pattern in obvious_patterns)

    def _extract_literal_terms_enhanced(self, entities: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """
        Extract terms with fuzzy matching capability

        Returns enhanced search terms structure for fuzzy matching
        """
        import re

        extracted_terms: dict[str, Any] = {
            "exact_terms": [],  # Termos literais exatos
            "fuzzy_terms": [],  # Variações fuzzy
            "partial_terms": [],  # Termos parciais para matching
            "client_variations": [],  # Variações de nomes de cliente
            "search_patterns": [],  # Padrões de busca combinados
        }

        original_query = context.get("original_query", "").lower()

        # 1. Extract quoted terms (highest priority)
        quoted_terms = re.findall(r'"([^"]+)"', original_query)
        extracted_terms["exact_terms"].extend(quoted_terms)

        # 2. Extract entity terms with normalization
        for entity_type, entity_data in entities.items():
            if entity_type == "transactions":
                # Transações são literais (F110, ZEWM0008)
                # Handle multiple formats: list, dict with values, or dict with normalized
                if isinstance(entity_data, list):
                    extracted_terms["exact_terms"].extend(entity_data)
                elif isinstance(entity_data, dict):
                    # Try multiple possible keys for transaction values
                    values = entity_data.get("values", []) or entity_data.get("normalized", []) or [str(entity_data)]
                    extracted_terms["exact_terms"].extend(values)
                else:
                    # Fallback for other formats
                    extracted_terms["exact_terms"].append(str(entity_data))

            elif entity_type == "clients":
                # Clientes precisam fuzzy matching
                # Handle multiple formats: list, dict with values, or dict with normalized
                if isinstance(entity_data, list):
                    client_terms = entity_data
                elif isinstance(entity_data, dict):
                    # Try multiple possible keys for client values
                    client_terms = (
                        entity_data.get("values", []) or entity_data.get("normalized", []) or [str(entity_data)]
                    )
                else:
                    client_terms = [str(entity_data)]

                for client in client_terms:
                    # Gerar variações do cliente
                    variations = self._generate_client_variations(client)
                    extracted_terms["client_variations"].extend(variations)
                    extracted_terms["fuzzy_terms"].extend(variations)

        # 3. Extract KT-specific terms (novo!)
        kt_terms = self._extract_kt_specific_terms(original_query)
        extracted_terms["partial_terms"].extend(kt_terms["title_parts"])
        extracted_terms["fuzzy_terms"].extend(kt_terms["variations"])

        # 4. Build comprehensive search patterns
        all_terms = extracted_terms["exact_terms"] + extracted_terms["fuzzy_terms"] + extracted_terms["partial_terms"]

        # Remove duplicatas e termos muito pequenos
        filtered_terms = list({term.strip() for term in all_terms if len(term.strip()) >= 2})

        extracted_terms["search_patterns"] = filtered_terms

        return extracted_terms

    def _extract_literal_terms(self, entities: dict[str, Any], context: dict[str, Any]) -> list[str]:
        """Legacy method - maintained for compatibility"""
        enhanced_terms = self._extract_literal_terms_enhanced(entities, context)
        return enhanced_terms["search_patterns"]

    def _is_asking_about_participants(self, original_query: str) -> bool:
        """
        Determine if the query is actually asking about participants vs just mentioning them

        Examples:
        - "Quem participou do KT?" → True (asking about participants)
        - "F110 no ambiente Dexco" → False (just mentions Dexco, not asking about participants)
        - "participantes da reunião" → True (asking about participants)
        - "informações sobre projeto da Víssimo" → False (mentions client, not asking about participants)
        """
        if not original_query:
            return False

        query_lower = original_query.lower()

        # Explicit participant question patterns
        participant_question_patterns = [
            "quem participou",
            "quem estava",
            "participantes",
            "pessoas envolvidas",
            "quem esteve",
            "equipe",
            "participaram",
            "membros",
            "pessoas presentes",
        ]

        # Check for explicit participant questions
        for pattern in participant_question_patterns:
            if pattern in query_lower:
                return True

        # Check for question words + participant context
        question_words = ["quem", "que pessoas", "quantas pessoas"]
        for question_word in question_words:
            if question_word in query_lower:
                return True

        # If no explicit participant questions found, it's just a mention
        return False

    def _get_pattern_weight(self, pattern: str, query_type: str) -> float:
        """Calculate weight for pattern match based on specificity"""
        # More specific patterns get higher weights
        pattern_weights = {
            # CONTENT patterns (highest priority)
            "onde mencionaram": 0.98,
            "chunk:": 0.99,
            "literal": 0.95,
            "exata": 0.95,
            # METADATA patterns (clear listing intent)
            "liste": 0.9,
            "quais": 0.8,
            "quantos": 0.8,
            "disponíveis": 0.7,
            # TEMPORAL patterns
            "últimos": 0.9,
            "recentes": 0.85,
            "setembro": 0.9,
            "2024": 0.7,
            # ENTITY patterns
            "quem participou": 0.95,
            "de qual cliente": 0.9,
            "participantes": 0.8,
            # SEMANTIC patterns (increased weights for specific phrases)
            "o que temos": 0.95,
            "principais pontos": 0.9,
            "informações sobre": 0.85,
            "como funciona": 0.9,
            "como foram": 0.85,
            "o que sabemos": 0.9,
            "sabemos sobre": 0.9,
            "temos de informação": 0.95,
            "me traga": 0.85,
            # Generic patterns
            "principais": 0.6,
            "informação": 0.5,
            "processo": 0.6,
        }

        return pattern_weights.get(pattern, 0.4)

    def _get_default_strategy(self, query_type: QueryType) -> dict[str, Any]:
        """Get default strategy for a query type"""
        default_strategies = {
            QueryType.SEMANTIC: {
                "type": "SEMANTIC",
                "use_embedding": True,
                "primary_fields": ["content"],
                "top_k_modifier": 1.0,
                "client_detected": False,
                "technical_detected": False,
            },
            QueryType.METADATA: {
                "type": "METADATA",
                "use_embedding": False,
                "aggregation": "distinct",
                "top_k_modifier": 2.0,
                "client_detected": False,
            },
            QueryType.ENTITY: {
                "type": "ENTITY",
                "use_embedding": False,
                "primary_fields": ["participants_mentioned"],
                "top_k_modifier": 1.2,
                "client_detected": False,
                "participants_detected": False,
            },
            QueryType.TEMPORAL: {
                "type": "TEMPORAL",
                "use_embedding": False,
                "sort_by": "meeting_date DESC",
                "top_k_modifier": 1.3,
                "temporal_detected": False,
            },
            QueryType.CONTENT: {
                "type": "CONTENT",
                "search_method": "text_search",
                "primary_field": "content",
                "top_k_modifier": 1.5,
                "literal_detected": False,
            },
        }

        return default_strategies.get(query_type, default_strategies[QueryType.SEMANTIC])

    def _generate_reasoning(
        self, primary_type: QueryType, entities: dict[str, Any], context: dict[str, Any], scores: dict[QueryType, float]
    ) -> str:
        """Generate human-readable reasoning for the classification"""
        reasoning_parts = []

        # Primary classification reason
        reasoning_parts.append(f"Classified as {primary_type.value}")

        # Entity-based reasoning
        if entities:
            entity_types = list(entities.keys())
            reasoning_parts.append(f"based on detected entities: {', '.join(entity_types)}")

        # Context-based reasoning
        context_signals = []
        if context.get("is_listing_request"):
            context_signals.append("listing intent")
        if context.get("has_specific_client"):
            context_signals.append("specific client")
        if context.get("has_temporal"):
            context_signals.append("temporal constraint")
        if context.get("technical_complexity") == "high":
            context_signals.append("technical complexity")

        if context_signals:
            reasoning_parts.append(f"and context signals: {', '.join(context_signals)}")

        # Score information
        top_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:2]
        score_info = f"(scores: {top_scores[0][0].value}={top_scores[0][1]:.2f}"
        if len(top_scores) > 1:
            score_info += f", {top_scores[1][0].value}={top_scores[1][1]:.2f}"
        score_info += ")"
        reasoning_parts.append(score_info)

        return " ".join(reasoning_parts)

    def _load_classification_strategies(self) -> dict[str, Any]:
        """Load classification strategies and rules"""
        return {
            "pattern_weight": 0.3,
            "entity_weight": 0.4,
            "context_weight": 0.3,
            "min_confidence": 0.2,
            "hybrid_threshold": 0.4,
        }

    def _load_hybrid_rules(self) -> dict[str, Any]:
        """Load rules for hybrid query handling"""
        return {
            "priority_order": [QueryType.ENTITY, QueryType.SEMANTIC, QueryType.TEMPORAL, QueryType.METADATA],
            "combination_rules": {
                (QueryType.SEMANTIC, QueryType.ENTITY): "entity_filtered_semantic",
                (QueryType.TEMPORAL, QueryType.METADATA): "temporal_filtered_metadata",
                (QueryType.CONTENT, QueryType.SEMANTIC): "content_enhanced_semantic",
            },
        }

    def _detect_specific_kt_query(self, query: str) -> dict[str, Any]:
        """
        Detecta se query busca KT específico vs período temporal

        KT ESPECÍFICO:
        - "Qual os temas relevantes discutidos no KT - Estorno em massa-20251022_150336"
        - "Resuma os principais pontos discutidos no KT sustentação - Ajuste no PO de frete"
        - "Quais transações foram explicadas no KT Correção iFlow PC Factory"

        PERÍODO TEMPORAL:
        - "KTs dos últimos 30 dias"
        - "Reuniões de setembro de 2024"
        - "Problemas recentes na Víssimo"
        """
        query_lower = query.lower()

        result: dict[str, Any] = {
            "is_specific_kt": False,
            "is_temporal_period": False,
            "kt_title_extracted": None,
            "confidence": 0.0,
            "reasoning": [],
            "matched_patterns": [],
        }

        # 1. Verificar padrões de KT específico
        import re

        kt_pattern_matches = 0
        for pattern_name, pattern_regex in self.specific_kt_patterns.items():
            if re.search(pattern_regex, query_lower, re.IGNORECASE):
                kt_pattern_matches += 1
                result["matched_patterns"].append(pattern_name)

                # Extrair título se possível
                match = re.search(pattern_regex, query_lower, re.IGNORECASE)
                if match and match.groups():
                    result["kt_title_extracted"] = match.group(1).strip()

        # 2. Verificar indicadores de análise específica
        analysis_matches = 0
        for indicator in self.analysis_indicators:
            if indicator in query_lower:
                analysis_matches += 1
                result["reasoning"].append(f"Analysis indicator: '{indicator}'")

        # 3. Calcular confiança para KT específico
        if kt_pattern_matches > 0 or analysis_matches > 0:
            result["is_specific_kt"] = True

            # Base confidence from pattern matches
            pattern_confidence = min(0.9, kt_pattern_matches * 0.3)
            analysis_confidence = min(0.6, analysis_matches * 0.15)

            result["confidence"] = max(pattern_confidence, analysis_confidence)

            if kt_pattern_matches > 0:
                result["reasoning"].append(f"KT patterns matched: {kt_pattern_matches}")
            if analysis_matches > 0:
                result["reasoning"].append(f"Analysis indicators: {analysis_matches}")

        # 4. Verificar se é temporal real (só se não for KT específico)
        if not result["is_specific_kt"]:
            temporal_matches = 0
            for temporal_pattern in self.real_temporal_indicators:
                if re.search(temporal_pattern, query_lower, re.IGNORECASE):
                    temporal_matches += 1

            if temporal_matches > 0:
                result["is_temporal_period"] = True
                result["confidence"] = min(0.9, temporal_matches * 0.4)
                result["reasoning"].append(f"Temporal patterns: {temporal_matches}")

        return result

    def _extract_kt_specific_terms(self, query: str) -> dict[str, list[str]]:
        """
        Extrair termos específicos de KT para fuzzy matching

        Example:
        "KT iflow PC Factory" → {
            "title_parts": ["iflow", "pc", "factory"],
            "variations": ["iFlow", "PC Factory", "pc_factory"],
            "combinations": ["iflow pc factory", "pc factory"]
        }
        """
        import re

        result: dict[str, list[str]] = {"title_parts": [], "variations": [], "combinations": []}

        # Padrões para extrair título de KT
        kt_title_patterns = [
            r"kt\s+([a-záéíóúãõç\s]+?)(?:\s+\d{8}_\d{6}|$)",  # "KT título data"
            r"no\s+kt\s+([a-záéíóúãõç\s]+)",  # "no KT título"
            r"kt\s*[-\s]*([a-záéíóúãõç\s]+?)[-\s]*\d{8}",  # "KT - título-data"
        ]

        extracted_title = None
        for pattern in kt_title_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                extracted_title = match.group(1).strip()
                break

        if extracted_title:
            # Dividir título em partes
            title_parts = [part.strip() for part in re.split(r"[\s\-_]+", extracted_title) if len(part.strip()) >= 2]
            result["title_parts"] = title_parts

            # Gerar variações comuns
            for part in title_parts:
                # Variações de case
                result["variations"].extend([part.lower(), part.upper(), part.capitalize()])

                # Variações com underscore/space
                if " " in part:
                    result["variations"].append(part.replace(" ", "_"))
                if "_" in part:
                    result["variations"].append(part.replace("_", " "))

            # Combinações de partes
            if len(title_parts) >= 2:
                result["combinations"].append(" ".join(title_parts))
                result["combinations"].append("_".join(title_parts))

        # Adicionar termos específicos encontrados diretamente na query
        specific_terms = re.findall(r"\b(iflow|pc\s+factory|víssimo|vissimo|dexco|arco)\b", query, re.IGNORECASE)
        result["variations"].extend(specific_terms)

        return result

    def _generate_client_variations(self, client_name: str) -> list[str]:
        """
        Gerar variações de nome de cliente para fuzzy matching

        Example: "PC Factory" → ["PC Factory", "PC_FACTORY", "pc factory", "pc_factory"]
        """
        variations = [client_name]
        client_lower = client_name.lower()

        # Variações básicas
        variations.extend([client_lower, client_name.upper(), client_name.capitalize()])

        # Variações com separadores
        if " " in client_name:
            variations.append(client_name.replace(" ", "_"))
            variations.append(client_name.replace(" ", ""))

        if "_" in client_name:
            variations.append(client_name.replace("_", " "))
            variations.append(client_name.replace("_", ""))

        # Remover duplicatas
        return list(set(variations))


# Utility functions for external use
def classify_query(query: str, enrichment_result) -> ClassificationResult:
    """Convenience function for query classification"""
    classifier = QueryClassifier()
    return classifier.classify_query_with_context(query, enrichment_result.entities, enrichment_result.context)


def get_query_type(query: str) -> QueryType:
    """Quick query type detection without full classification"""
    classifier = QueryClassifier()
    pattern_scores = classifier._classify_by_patterns(query)
    primary_type, _ = classifier._get_primary_classification(pattern_scores)
    return primary_type
