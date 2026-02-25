"""
Search Logging - Logger estruturado para as 6 fases do pipeline RAG.

Responsabilidade: emitir logs de debug/info para cada fase do pipeline
SearchEngine sem depender de atributos de instância do motor de busca.
"""

from typing import Any

from utils.logger_setup import LoggerManager

from .chunk_selector import SelectionResult
from .query_classifier import ClassificationResult
from .query_enricher import EnrichmentResult

logger = LoggerManager.get_logger(__name__)


class PipelineLogger:
    """Logger estruturado para as fases do pipeline RAG."""

    # ════════════════════════════════════════════════════════════════════════
    # Fase 1 — Enriquecimento
    # ════════════════════════════════════════════════════════════════════════

    def log_enrichment_phase(
        self,
        original_query: str,
        enrichment_result: EnrichmentResult,
        enrichment_time: float,
        show_details: bool,
    ) -> None:
        """Loga fase de enriquecimento com detalhes ricos."""
        logger.debug(
            f"1️⃣ ENRIQUECIMENTO {'DA QUERY ' if show_details else ''}"
            f"| {enrichment_time:.3f}s | conf: {enrichment_result.confidence:.2f}"
        )

        if show_details:
            logger.debug(f'   📥 Query original: "{original_query}" (len: {len(original_query)})')
            logger.debug(f'   🔄 Query limpa: "{enrichment_result.cleaned_query}"')
            logger.debug(f'   📤 Query enriquecida: "{enrichment_result.enriched_query}"')
            logger.debug(f"   📊 Confiança do enriquecimento: {enrichment_result.confidence:.3f}")

            logger.debug(f"   🎯 Entidades detectadas ({len(enrichment_result.entities)} tipos):")
            for entity_type, entity_data in enrichment_result.entities.items():
                if entity_data.get("values"):
                    confidence = entity_data.get("confidence", 0.0)
                    values = entity_data["values"]
                    logger.debug(f"      • {entity_type}: {values} (conf: {confidence:.3f}, count: {len(values)})")
                else:
                    logger.debug(f"      • {entity_type}: [] (não detectado)")

            context_flags_true = []
            context_flags_values = []
            for key, value in enrichment_result.context.items():
                if isinstance(value, bool) and value:
                    context_flags_true.append(key)
                elif not isinstance(value, bool) and value:
                    context_flags_values.append(f"{key}={value}")

            if context_flags_true:
                logger.debug(f"   📋 Flags contexto: {', '.join(context_flags_true)}")
            if context_flags_values:
                logger.debug(f"   📋 Valores contexto: {', '.join(context_flags_values)}")

            original_words = len(original_query.split())
            enriched_words = len(enrichment_result.enriched_query.split())
            if enriched_words > original_words:
                logger.debug(
                    f"   📈 Expansão: +{enriched_words - original_words} palavras ({original_words} → {enriched_words})"
                )
        else:
            logger.debug(f'   📥 Input: "{original_query}"')
            logger.debug(f'   📤 Output: "{enrichment_result.enriched_query}"')

            entity_summary: dict[str, Any] = {}
            total_entities = 0
            for entity_type, entity_data in enrichment_result.entities.items():
                if entity_data.get("values"):
                    entity_summary[entity_type] = entity_data["values"]
                    total_entities += len(entity_data["values"])

            if entity_summary:
                logger.debug(f"   🎯 Entidades ({total_entities}): {entity_summary}")
            else:
                logger.debug("   🎯 Entidades: Nenhuma detectada")

    # ════════════════════════════════════════════════════════════════════════
    # Fase 2 — Classificação
    # ════════════════════════════════════════════════════════════════════════

    def log_classification_phase(
        self,
        classification_result: ClassificationResult,
        classification_time: float,
        show_details: bool,
    ) -> None:
        """Loga fase de classificação com detalhes ricos."""
        logger.debug(
            f"2️⃣ CLASSIFICAÇÃO {'DE QUERY ' if show_details else ''}"
            f"| {classification_time:.3f}s | conf: {classification_result.confidence:.2f}"
        )

        if show_details:
            strategy = classification_result.strategy
            logger.debug("   📊 Scores de classificação:")
            logger.debug(
                f"      🎯 {classification_result.query_type.value}:"
                f" {classification_result.confidence:.3f} ⭐ (ESCOLHIDO)"
            )

            if "debug_scores" in strategy:
                for rag_type, score in strategy["debug_scores"].items():
                    if rag_type != classification_result.query_type.value:
                        logger.debug(f"      • {rag_type}: {score:.3f}")

            logger.debug(f"   📤 Tipo RAG final: {classification_result.query_type.value}")
            logger.debug(f"   🎯 Strategy usada: {strategy.get('name', 'default')}")

            if "top_k_modifier" in strategy:
                logger.debug(f"   📏 TOP_K modifier: {strategy['top_k_modifier']}")
            if "filters" in strategy and strategy["filters"]:
                logger.debug(f"   🔍 Filtros da strategy: {strategy['filters']}")

            reasoning = strategy.get("reasoning", "Query classification based on pattern matching")
            logger.debug(f"   📋 Razão da classificação: {reasoning}")

            detected_features = []
            if "semantic_indicators" in strategy:
                detected_features.append(f"semantic_indicators={strategy['semantic_indicators']}")
            if "metadata_indicators" in strategy:
                detected_features.append(f"metadata_indicators={strategy['metadata_indicators']}")
            if "temporal_indicators" in strategy:
                detected_features.append(f"temporal_indicators={strategy['temporal_indicators']}")

            if detected_features:
                logger.debug(f"   🧠 Features detectadas: {', '.join(detected_features)}")
        else:
            logger.debug(
                f"   📤 Tipo: {classification_result.query_type.value}"
                f" | Strategy: {classification_result.strategy.get('name', 'default')}"
            )
            reasoning = classification_result.strategy.get("reasoning", "Auto-detected")
            logger.debug(f"   🎯 Razão: {reasoning}")
            logger.debug(f"   📊 Confiança: {classification_result.confidence:.3f}")

    # ════════════════════════════════════════════════════════════════════════
    # Fase 3 — ChromaDB
    # ════════════════════════════════════════════════════════════════════════

    def log_chromadb_phase(
        self,
        raw_results: list[dict[str, Any]],
        chromadb_time: float,
        enrichment_result: EnrichmentResult,
        classification_result: ClassificationResult,
        show_details: bool,
    ) -> None:
        """Loga fase de busca no ChromaDB com detalhes ricos."""
        logger.debug(f"3️⃣ BUSCA {'NO ' if show_details else ''}CHROMADB | {chromadb_time:.3f}s")

        query_type = classification_result.query_type.value
        if query_type == "SEMANTIC":
            method = "similarity_search (com embedding)"
            search_detail = "Busca por similaridade semântica usando embeddings"
        elif query_type == "METADATA":
            method = "metadata_search (sem embedding)"
            search_detail = "Busca estruturada apenas em metadados"
        elif query_type == "ENTITY":
            method = "entity_search (metadados + entidades)"
            search_detail = "Busca focada em entidades específicas"
        elif query_type == "TEMPORAL":
            method = "temporal_search (com filtros de data)"
            search_detail = "Busca com restrições temporais"
        elif query_type == "CONTENT":
            method = "content_search (busca literal)"
            search_detail = "Busca literal no conteúdo dos chunks"
        else:
            method = f"{query_type.lower()}_search"
            search_detail = "Método de busca personalizado"

        filters_applied: dict[str, str] = {}
        client_normalization_info = None

        if "clients" in enrichment_result.entities:
            client_values = enrichment_result.entities["clients"]["values"]
            if client_values:
                detected_client = client_values[0]
                normalized_client = detected_client.upper()
                filters_applied["client_name"] = normalized_client
                if detected_client.upper() != normalized_client:
                    client_normalization_info = f'"{detected_client}" → "{normalized_client}"'
                else:
                    client_normalization_info = f'"{detected_client}" → "{normalized_client}" (exact match)'

        unique_videos: set[str] = set()
        unique_clients: set[str] = set()
        similarity_scores: list[float] = []

        for result in raw_results:
            metadata = result.get("metadata", {})
            video_name_raw = metadata.get("video_name", "Unknown")
            client_name_raw = metadata.get("client_name", "Unknown")
            video_name = video_name_raw if isinstance(video_name_raw, str) else "Unknown"
            client_name = client_name_raw if isinstance(client_name_raw, str) else "Unknown"
            if video_name != "Unknown":
                unique_videos.add(video_name)
            if client_name != "Unknown":
                unique_clients.add(client_name)
            if "similarity_score" in result:
                similarity_scores.append(result["similarity_score"])

        if show_details:
            logger.debug(f"   🎯 Método de busca: {method}")
            logger.debug(f"   📋 Descrição: {search_detail}")

            if query_type == "SEMANTIC":
                logger.debug("   🧠 Embedding gerado para query enriquecida")
                if enrichment_result.enriched_query != enrichment_result.cleaned_query:
                    logger.debug("   📈 Query expandida usada para embedding")

            if filters_applied:
                logger.debug("   📥 Filtros ChromaDB aplicados:")
                for key, value in filters_applied.items():
                    logger.debug(f'      • {key}: "{value}"')
                if client_normalization_info:
                    logger.debug(f"   🔄 Normalização de cliente: {client_normalization_info}")
            else:
                logger.debug("   📥 Filtros: Nenhum filtro aplicado (busca geral)")

            logger.debug(f"   📤 Resultados brutos: {len(raw_results)} chunks")
            logger.debug("   📊 Distribuição:")
            logger.debug(
                f"      • {len(unique_videos)} vídeos únicos:"
                f" {', '.join(sorted(unique_videos)[:3])}{'...' if len(unique_videos) > 3 else ''}"
            )
            logger.debug(f"      • {len(unique_clients)} clientes únicos: {', '.join(sorted(unique_clients))}")

            if similarity_scores:
                avg_similarity = sum(similarity_scores) / len(similarity_scores)
                max_similarity = max(similarity_scores)
                min_similarity = min(similarity_scores)
                logger.debug(
                    f"   📈 Similaridade: avg={avg_similarity:.3f}, max={max_similarity:.3f}, min={min_similarity:.3f}"
                )

            strategy = classification_result.strategy
            if "top_k_modifier" in strategy:
                base_limit = strategy.get("base_limit", 20)
                search_limit = int(base_limit * strategy["top_k_modifier"])
                if len(raw_results) >= search_limit:
                    logger.debug(f"   ⚠️ Limite de busca atingido: {search_limit} chunks (pode haver mais resultados)")
        else:
            filter_display = filters_applied if filters_applied else {"nenhum": "busca_geral"}
            logger.debug(f"   📤 Resultados: {len(raw_results)} chunks | Filtros: {filter_display}")
            logger.debug(f"   🎯 Método: {method}")
            logger.debug(f"   📊 Origem: {len(unique_videos)} vídeos, {len(unique_clients)} clientes")
            if client_normalization_info:
                logger.debug(f"   🔄 Cliente: {client_normalization_info}")

    # ════════════════════════════════════════════════════════════════════════
    # Fase 4 — Descoberta de clientes
    # ════════════════════════════════════════════════════════════════════════

    def log_client_discovery_phase(
        self,
        client_time: float,
        show_details: bool,
        dynamic_client_manager: Any,
    ) -> None:
        """Loga fase de descoberta de clientes.

        Args:
            client_time: Tempo gasto na fase de descoberta.
            show_details: Se True, exibe detalhes completos.
            dynamic_client_manager: Instância do DynamicClientManager para consulta de clientes.
        """
        logger.debug(f"4️⃣ DESCOBERTA {'DE CLIENTES' if show_details else 'CLIENTES'} | {client_time:.3f}s")

        if show_details:
            logger.debug("   🎯 Processo: Dynamic Client Manager ativo")
            logger.debug("   📋 Função: Enriquecer metadados com descoberta dinâmica de clientes")

            try:
                clients = dynamic_client_manager.discover_clients()
                client_info = []
                total_chunks = 0

                for client_name, client_data in clients.items():
                    chunk_count = client_data.chunk_count
                    if chunk_count > 0:
                        client_info.append(f"{client_name} ({chunk_count} chunks)")
                        total_chunks += chunk_count

                if client_info:
                    logger.debug(f"   🔍 Clientes na base ({len(client_info)} clientes, {total_chunks} chunks total):")
                    for info in client_info:
                        logger.debug(f"      • {info}")
                else:
                    logger.debug("   🔍 Clientes disponíveis: Consultando ChromaDB dynamicamente...")

                logger.debug(
                    f"   🔄 Cache de clientes: {'HIT' if hasattr(dynamic_client_manager, '_client_cache') else 'MISS'}"
                )

            except Exception as e:
                logger.debug(f"   ⚠️ Erro ao obter clientes: {str(e)[:50]}...")
                logger.debug("   🔍 Fallback: Consultando ChromaDB diretamente...")

            logger.debug("   📤 Resultado: Metadados de contexto client enrichment aplicado")
            _perf = "Rápido" if client_time < 1.0 else "Normal" if client_time < 3.0 else "Lento"
            logger.debug(f"   ⚡ Performance: {client_time:.3f}s ({_perf})")
        else:
            try:
                clients = dynamic_client_manager.discover_clients()
                client_count = len([c for c, data in clients.items() if data.chunk_count > 0])
                logger.debug(f"   🔍 {client_count} clientes na base | Enriquecimento: {client_time:.3f}s")
            except Exception:
                logger.debug(f"   🎯 Enriquecimento dinâmico: {client_time:.3f}s")

    # ════════════════════════════════════════════════════════════════════════
    # Fase 5 — Seleção de chunks
    # ════════════════════════════════════════════════════════════════════════

    def log_selection_phase(
        self,
        selection_result: SelectionResult,
        raw_results: list[dict[str, Any]],
        top_k: int,
        selection_time: float,
        show_details: bool,
    ) -> None:
        """Loga fase de seleção de chunks com detalhes ricos."""
        logger.debug(f"5️⃣ SELEÇÃO {'INTELIGENTE ' if show_details else 'CHUNKS '}| {selection_time:.3f}s")

        if show_details:
            logger.debug("   🎯 ChunkSelector: Seleção inteligente com Quality + Diversity")
            logger.debug(f"   📊 TOP_K adaptativo calculado: {top_k}")
            logger.debug(f"      Base: 20 → Modificado: {top_k} (baseado no tipo de query)")
            logger.debug(f"   🔍 Estratégia selecionada: {selection_result.selection_strategy}")

            strategies = {
                "all_candidates": "Manter todos os candidatos (metadata listing)",
                "quality_filter": "Filtrar por quality threshold",
                "top_k_limit": "Limitar aos TOP_K melhores",
                "diversity_selection": "Seleção com diversidade",
            }
            strategy_desc = strategies.get(selection_result.selection_strategy, "Estratégia personalizada")
            logger.debug(f"   📋 Descrição: {strategy_desc}")
            logger.debug(
                f"   📤 Resultado da seleção: {len(selection_result.selected_chunks)}/{len(raw_results)} chunks"
            )

            quality_scores = [chunk.get("quality_score", 0.0) for chunk in raw_results if "quality_score" in chunk]
            quality_threshold = 0.3

            if quality_scores:
                avg_quality = sum(quality_scores) / len(quality_scores)
                max_quality = max(quality_scores)
                min_quality = min(quality_scores)
                quality_passed = sum(1 for score in quality_scores if score >= quality_threshold)

                logger.debug("   🏆 Quality Analysis:")
                logger.debug(f"      • Threshold: {quality_threshold}")
                logger.debug(f"      • Passed threshold: {quality_passed}/{len(quality_scores)} chunks")
                logger.debug(f"      • Scores: avg={avg_quality:.3f}, max={max_quality:.3f}, min={min_quality:.3f}")
                logger.debug(f"      • Quality gate: {'✅ PASSED' if quality_passed > 0 else '❌ FAILED'}")

            logger.debug(f"   ✅ Quality threshold met: {selection_result.quality_threshold_met}")

            if selection_result.selection_strategy == "diversity_selection":
                logger.debug("   🌈 Diversity: Seleção balanceada entre vídeos/clientes")

            chunks_per_second = len(raw_results) / selection_time if selection_time > 0 else float("inf")
            logger.debug(f"   ⚡ Performance: {chunks_per_second:.0f} chunks/s processados")
        else:
            strategy_short = {
                "all_candidates": "Manter todos",
                "quality_filter": "Quality filter",
                "top_k_limit": "TOP_K limit",
                "diversity_selection": "Diversity",
            }.get(selection_result.selection_strategy, selection_result.selection_strategy)

            logger.debug(
                f"   📤 Selecionados: {len(selection_result.selected_chunks)}/{len(raw_results)} | TOP_K: {top_k}"
            )
            logger.debug(
                f"   🎯 Estratégia: {strategy_short}"
                f" | Quality: {'✅' if selection_result.quality_threshold_met else '❌'}"
            )

    # ════════════════════════════════════════════════════════════════════════
    # Fase 6 — Insights
    # ════════════════════════════════════════════════════════════════════════

    def log_insights_phase(self, insights_result: Any, insights_time: float, show_details: bool) -> None:
        """Loga fase de geração de insights com detalhes ricos."""
        logger.debug(
            f"6️⃣ {'GERAÇÃO DE ' if show_details else ''}"
            f"INSIGHTS | {insights_time:.3f}s | conf: {insights_result.confidence:.2f}"
        )

        if show_details:
            logger.debug("   🎯 InsightsAgent: Geração de resposta inteligente final")

            processing_time = getattr(insights_result, "processing_time", insights_time)
            is_fast_track = processing_time < 0.01

            if is_fast_track:
                template = "metadata_listing (fast-track)"
                method = "Template automático - Sem chamada LLM"
                llm_cost = "R$ 0.00"
            else:
                template = "LLM-generated"
                method = "GPT-4o-mini (texto + contextos)"
                estimated_tokens = len(insights_result.insight) * 1.3
                cost_estimate = estimated_tokens * 0.00001
                llm_cost = f"~R$ {cost_estimate:.4f}"

            logger.debug(f"   📋 Template usado: {template}")
            logger.debug(f"   🤖 Método: {method}")
            logger.debug(f"   💰 Custo estimado: {llm_cost}")
            logger.debug(f"   ⚡ Fast-track: {'✅ Ativo' if is_fast_track else '❌ Inativo'}")

            if hasattr(insights_result, "unique_videos"):
                logger.debug(f"   🔄 Agrupamento: Por video_name ({insights_result.unique_videos} vídeos únicos)")
            else:
                logger.debug("   🔄 Processamento: Análise semântica completa de contextos")

            confidence_level = insights_result.confidence
            if confidence_level >= 0.9:
                confidence_desc, confidence_emoji = "Muito Alta", "🟢"
            elif confidence_level >= 0.7:
                confidence_desc, confidence_emoji = "Alta", "🟡"
            elif confidence_level >= 0.5:
                confidence_desc, confidence_emoji = "Média", "🟠"
            else:
                confidence_desc, confidence_emoji = "Baixa", "🔴"

            logger.debug(f"   📊 Confiança final: {confidence_level:.3f} ({confidence_desc}) {confidence_emoji}")

            response_length = len(insights_result.insight)
            if response_length > 500:
                response_desc = "Resposta detalhada"
            elif response_length > 200:
                response_desc = "Resposta moderada"
            elif response_length > 50:
                response_desc = "Resposta concisa"
            else:
                response_desc = "Resposta muito breve"

            logger.debug(f"   📝 Resposta: {response_length} chars ({response_desc})")

            if insights_time < 1.0:
                perf_desc, perf_emoji = "Excelente", "🚀"
            elif insights_time < 3.0:
                perf_desc, perf_emoji = "Boa", "⚡"
            elif insights_time < 5.0:
                perf_desc, perf_emoji = "Aceitável", "⏱️"
            else:
                perf_desc, perf_emoji = "Lenta", "🐌"

            logger.debug(f"   ⚡ Performance: {insights_time:.3f}s ({perf_desc}) {perf_emoji}")
        else:
            is_fast_track = insights_time < 0.01
            template = "fast-track" if is_fast_track else "LLM"
            method_desc = "Template" if is_fast_track else "GPT-4o-mini"
            logger.debug(f"   📤 Template: {template} | Método: {method_desc}")
            logger.debug(
                f"   🎯 Confiança: {insights_result.confidence:.3f} | {'🚀 Fast' if is_fast_track else '🤖 LLM'}"
            )
