"""
Search Response Builder - Construção e formatação de SearchResponse.

Responsabilidade: transformar dados brutos do pipeline RAG em objetos
SearchResponse prontos para retorno ao caller. Zero dependência de estado
de instância — todos os métodos recebem apenas o que precisam como parâmetros.
"""

import time
from typing import Any

from utils.logger_setup import LoggerManager

from .chunk_selector import SelectionResult
from .kt_search_constants import ERROR_MESSAGES
from .query_classifier import ClassificationResult
from .search_types import SearchResponse

logger = LoggerManager.get_logger(__name__)


class SearchResponseBuilder:
    """Constrói e formata objetos SearchResponse sem estado de instância."""

    # ════════════════════════════════════════════════════════════════════════
    # Construção de respostas de sucesso
    # ════════════════════════════════════════════════════════════════════════

    def format_final_response(
        self,
        original_query: str,
        insights_result: Any,
        selection_result: SelectionResult,
        classification_result: ClassificationResult,
        start_time: float,
    ) -> SearchResponse:
        """Formata resposta final na estrutura esperada pelo caller."""
        processing_time = time.time() - start_time

        intelligent_response = {
            "answer": insights_result.insight,
            "details": self.extract_additional_details(selection_result.selected_chunks),
            "confidence": insights_result.confidence,
            "processing_time": insights_result.processing_time,
        }

        contexts = self.format_contexts_for_display(
            selection_result.selected_chunks, classification_result.query_type.value
        )

        summary_stats = {
            "total_chunks_found": selection_result.total_candidates,
            "chunks_selected": len(selection_result.selected_chunks),
            "clients_involved": self.extract_unique_clients(selection_result.selected_chunks),
            "query_type": classification_result.query_type.value,
            "processing_time": processing_time,
            "selection_strategy": selection_result.selection_strategy,
            "quality_threshold_met": selection_result.quality_threshold_met,
        }

        return SearchResponse(
            intelligent_response=intelligent_response,
            contexts=contexts,
            summary_stats=summary_stats,
            query_type=classification_result.query_type.value,
            processing_time=processing_time,
            success=True,
        )

    # ════════════════════════════════════════════════════════════════════════
    # Construção de respostas de erro
    # ════════════════════════════════════════════════════════════════════════

    def create_error_response(self, error_message: str, query: str, start_time: float) -> SearchResponse:
        """Cria SearchResponse de erro com metadados mínimos."""
        processing_time = time.time() - start_time

        return SearchResponse(
            intelligent_response={
                "answer": ERROR_MESSAGES.get("no_results", "Erro ao processar consulta"),
                "details": error_message,
                "confidence": 0.0,
                "processing_time": processing_time,
            },
            contexts=[],
            summary_stats={
                "total_chunks_found": 0,
                "chunks_selected": 0,
                "clients_involved": [],
                "query_type": "ERROR",
                "processing_time": processing_time,
            },
            query_type="ERROR",
            processing_time=processing_time,
            success=False,
            error_message=error_message,
        )

    def create_client_not_found_response(
        self, query: str, start_time: float, available_clients: list[str] | None = None
    ) -> SearchResponse:
        """Cria resposta early-exit para cliente inexistente.

        Args:
            query: Query original do usuário.
            start_time: Timestamp de início do pipeline.
            available_clients: Lista de clientes descobertos dinamicamente. Se None,
                omite a listagem de disponíveis na resposta.
        """
        processing_time = time.time() - start_time

        if available_clients:
            response_text = "**Cliente não encontrado na base de conhecimento.**\n"
            response_text += "**Clientes disponíveis:**\n"
            for client in sorted(available_clients):
                response_text += f"• {client}\n"
            response_text += (
                "**Sugestão:** Verifique a grafia do nome do cliente ou escolha um dos clientes listados acima."
            )
        else:
            response_text = (
                "**Cliente não encontrado na base de conhecimento.**\n"
                "**Sugestão:** Verifique a grafia do nome do cliente e tente novamente."
            )

        return SearchResponse(
            intelligent_response={
                "answer": response_text,
                "details": "Cliente inexistente detectado no pipeline de classificação",
                "confidence": 0.95,
                "processing_time": processing_time,
                "method": "early_exit_client_not_found",
            },
            contexts=[],
            summary_stats={
                "total_chunks_found": 0,
                "chunks_selected": 0,
                "clients_involved": [],
                "query_original": query,
            },
            query_type="EARLY_EXIT",
            processing_time=processing_time,
            success=True,
        )

    # ════════════════════════════════════════════════════════════════════════
    # Formatação de contextos
    # ════════════════════════════════════════════════════════════════════════

    def format_contexts_for_display(
        self, chunks: list[dict[str, Any]], query_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Formata contextos para exibição ao usuário."""
        if query_type == "METADATA":
            return self.format_metadata_listing_display(chunks)

        formatted_contexts = []
        for i, chunk in enumerate(chunks, 1):
            metadata = chunk.get("metadata", {})
            content = chunk.get("content", "")
            context = {
                "rank": i,
                "content": content[:300] + "..." if len(content) > 300 else content,
                "client": metadata.get("client_name", "Unknown"),
                "video_name": metadata.get("video_name", "Unknown"),
                "speaker": metadata.get("speaker", "Unknown"),
                "timestamp": (
                    f"{metadata.get('start_time_formatted', '00:00')}"
                    f"-{metadata.get('end_time_formatted', '00:00')}"
                ),
                "quality_score": chunk.get("quality_score", 0.0),
                "relevance_reason": f"Qualidade: {chunk.get('quality_score', 0.0):.2f}",
                "original_url": metadata.get("original_url", ""),
            }
            if "similarity_score" in chunk:
                context["similarity_score"] = chunk["similarity_score"]
                context["relevance_reason"] += f", Similaridade: {chunk['similarity_score']:.2f}"
            formatted_contexts.append(context)

        return formatted_contexts

    def format_metadata_listing_display(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Formata contextos para listagem de metadados — apenas vídeos únicos."""
        unique_videos: dict[str, dict[str, str]] = {}

        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            video_name = metadata.get("video_name", "")
            client_name = metadata.get("client_name", "Unknown")

            if video_name and video_name not in unique_videos:
                unique_videos[video_name] = {
                    "client": client_name,
                    "video_name": video_name,
                    "original_url": metadata.get("original_url", ""),
                }

        formatted_contexts = []
        for i, (_video_name, info) in enumerate(unique_videos.items(), 1):
            formatted_contexts.append(
                {
                    "rank": i,
                    "content": "",
                    "client": info["client"],
                    "video_name": info["video_name"],
                    "speaker": "",
                    "timestamp": "",
                    "quality_score": 1.0,
                    "relevance_reason": "Vídeo disponível na base de conhecimento",
                    "original_url": info["original_url"],
                }
            )

        return formatted_contexts

    # ════════════════════════════════════════════════════════════════════════
    # Extração e análise de chunks
    # ════════════════════════════════════════════════════════════════════════

    def extract_additional_details(self, chunks: list[dict[str, Any]]) -> str:
        """Extrai detalhes adicionais relevantes dos chunks selecionados."""
        if not chunks:
            return ""

        unique_videos = len({chunk.get("metadata", {}).get("video_name", "Unknown") for chunk in chunks})
        unique_clients = len({chunk.get("metadata", {}).get("client_name", "Unknown") for chunk in chunks})

        details = f"Informações baseadas em {len(chunks)} contextos"
        if unique_videos > 1:
            details += f" de {unique_videos} reuniões diferentes"
        if unique_clients > 1:
            details += f" envolvendo {unique_clients} clientes"

        return details

    def extract_unique_clients(self, chunks: list[dict[str, Any]]) -> list[str]:
        """Extrai nomes de clientes únicos dos chunks selecionados."""
        clients = set()
        for chunk in chunks:
            client = chunk.get("metadata", {}).get("client_name")
            if client and client != "Unknown":
                clients.add(client)
        return list(clients)

    def analyze_query_complexity(
        self,
        enrichment_result: Any,
        classification_result: ClassificationResult,
        original_query: str = "",
    ) -> dict[str, Any]:
        """Analisa complexidade da query para processamento adaptativo."""
        return {
            "query_complexity": enrichment_result.context.get("query_complexity", "medium"),
            "has_specific_client": enrichment_result.context.get("has_specific_client", False),
            "has_technical_terms": enrichment_result.context.get("has_technical_terms", False),
            "has_temporal": enrichment_result.context.get("has_temporal", False),
            "is_listing_request": enrichment_result.context.get("is_listing_request", False),
            "is_comparison_request": enrichment_result.context.get("is_comparison_request", False),
            "is_broad_request": enrichment_result.context.get("is_broad_request", False),
            "detected_client": enrichment_result.context.get("detected_client"),
            "entity_count": len(enrichment_result.entities),
            "enrichment_confidence": enrichment_result.confidence,
            "classification_confidence": classification_result.confidence,
            "original_query": original_query,
        }

    def should_stop_for_nonexistent_client(self, query: str) -> bool:
        """Verifica se a query menciona um cliente inexistente que deve parar o pipeline."""
        query_lower = query.lower()
        if "cliente" not in query_lower:
            return False

        non_existent_patterns = ["xpto", "teste", "inexistente", "naoexiste"]
        for pattern in non_existent_patterns:
            if pattern in query_lower:
                logger.info(f"🚫 Cliente obviamente inexistente detectado: {pattern}")
                return True

        return False
