"""
Search Formatters - Funções de formatação e conveniência do Search Engine.

Responsabilidades:
- Formatação de SearchResponse para exibição no terminal (print_results)
- Formatação para Microsoft Teams (formatar_resultado_teams, main_teams)
- Funções de conveniência para uso externo (search_kt_knowledge, quick_search)
"""

from typing import Any

from utils.logger_setup import LoggerManager

from .search_engine import SearchEngine, SearchResponse

logger = LoggerManager.get_logger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# Convenience functions for external use
# ════════════════════════════════════════════════════════════════════════════


def search_kt_knowledge(query: str) -> SearchResponse:
    """Convenience function for KT knowledge search."""
    search_engine = SearchEngine()
    return search_engine.search(query)


def quick_search(query: str) -> dict[str, Any]:
    """Quick search returning only the intelligent response."""
    response = search_kt_knowledge(query)
    return response.intelligent_response


# ════════════════════════════════════════════════════════════════════════════
# Teams integration
# ════════════════════════════════════════════════════════════════════════════


def formatar_resultado_teams(response: SearchResponse, pergunta: str) -> str:
    """Formata SearchResponse para exibição no Microsoft Teams.

    Args:
        response: Resultado tipado do SearchEngine.
        pergunta: Pergunta original do usuário.

    Returns:
        Texto formatado em markdown compatível com Teams.
    """
    linhas = ["🎥 **Transcrição de KT - Resultado da Consulta**", f" **Pergunta:** {pergunta}", ""]

    # Insights diretos
    insight_text = response.intelligent_response.get("answer", "")
    if insight_text:
        linhas.extend(["💡 **INSIGHTS:**", "=" * 50])
        for line in insight_text.strip().split("\n"):
            if line.strip():
                linhas.append(f"• {line.strip()}")

    # Contextos encontrados
    if response.contexts:
        linhas.extend(["", "**FONTES ENCONTRADAS:**", "=" * 50])

        for i, context in enumerate(response.contexts, 1):
            video_name = context.get("video_name", "Unknown")
            speaker = context.get("speaker", "Unknown")
            timestamp = context.get("timestamp", "00:00")
            content = context.get("content", "")
            video_link = context.get("original_url", "")

            linhas.append(f"\n**{i}. [{video_name}] {speaker} ({timestamp}):**")
            if content:
                linhas.append(f"   {content}")
            if video_link:
                linhas.append(f"   🎥 [Assistir momento específico]({video_link})")

    # Métricas de busca
    stats = response.summary_stats
    if stats:
        linhas.extend(["", "**MÉTRICAS DE BUSCA:**", "-" * 30])
        linhas.append(f"•  Tempo total: {response.processing_time:.2f}s")
        confidence = response.intelligent_response.get("confidence", 0.0)
        if confidence:
            linhas.append(f"•  Confiança: {confidence * 100:.1f}%")
        chunks_selected = stats.get("chunks_selected", 0)
        if chunks_selected:
            linhas.append(f"•  Fontes utilizadas: {chunks_selected} contextos")

    return "\n".join(linhas)


def main_teams(payload: dict[str, Any]) -> dict[str, Any]:
    """Entry point para o Teams Gateway Python.

    Args:
        payload: dict com chave 'text' contendo a pergunta do usuário.

    Returns:
        dict com 'success' + 'mensagem' em caso de sucesso,
        ou 'erro' + 'mensagem' em caso de falha.
    """
    try:
        pergunta = payload.get("text", "").strip()

        if not pergunta:
            return {
                "erro": "Pergunta não fornecida",
                "mensagem": "🎥 **Transcrição de KT**\n\nDigite sua pergunta sobre as transcrições.",
            }

        search_engine = SearchEngine()
        search_result = search_engine.search(pergunta, show_details=False)

        if not search_result.success:
            return {
                "erro": "Erro na consulta",
                "mensagem": f"{search_result.error_message or 'Erro desconhecido'}",
            }

        resposta_formatada = formatar_resultado_teams(search_result, pergunta)
        return {"success": True, "mensagem": resposta_formatada}

    except Exception as e:
        return {"erro": "Erro interno", "mensagem": f"Erro no processamento: {str(e)}"}


# ════════════════════════════════════════════════════════════════════════════
# Terminal display
# ════════════════════════════════════════════════════════════════════════════


def print_results(response: SearchResponse, show_details: bool = False) -> None:
    """Exibe resultados da consulta RAG no terminal.

    Args:
        response: SearchResponse retornado pelo SearchEngine.
        show_details: Se True, exibe métricas técnicas detalhadas.
    """
    if not response.success:
        logger.info("═" * 120)
        logger.info("CONSULTA SEM RESULTADOS")
        logger.info("─" * 40)
        logger.info(f"  {response.error_message}")
        logger.info("─" * 40)
        logger.info(f"  Tempo total: {response.processing_time:.2f}s")
        logger.info("═" * 120)
        return

    logger.info("═" * 120)

    # Resposta inteligente
    logger.info("RESPOSTA INTELIGENTE:")
    logger.info("─" * 40)

    answer_text = response.intelligent_response.get("answer", "").strip()
    if answer_text:
        for line in answer_text.split("\n"):
            if line.strip():
                logger.info(f"  {line.strip()}")
    else:
        logger.info("  Não foi possível gerar resposta.")

    if response.intelligent_response.get("details"):
        logger.info(f"  Detalhes: {response.intelligent_response['details']}")

    # Contextos encontrados
    logger.info("CONTEXTOS ENCONTRADOS:")
    logger.info("─" * 40)

    if response.contexts:
        for context in response.contexts:
            content = context.get("content", "")
            video_link = context.get("original_url", "")

            if video_link:
                client_info = (
                    f"  Cliente: {context.get('client', 'N/A')}"
                    f" | Reunião: {context.get('video_name', 'N/A')}"
                    f"\n     Link: {video_link}"
                )
            else:
                client_info = f"  Cliente: {context.get('client', 'N/A')} | Reunião: {context.get('video_name', 'N/A')}"

            if response.query_type == "METADATA":
                logger.info(f"{context['rank']}. {client_info.strip()}")
            else:
                if content and content.strip():
                    logger.info(f"{context['rank']}. {content}")
                else:
                    logger.info(f"{context['rank']}. Contexto relevante — {context.get('speaker', 'Participante')}")

                logger.info(client_info)

                if context.get("timestamp") and context["timestamp"] not in ("Unknown", ""):
                    logger.info(f"     Tempo: {context['timestamp']}")

                if show_details:
                    logger.debug(
                        f"     Qualidade: {context.get('quality_score', 0.0):.2f}"
                        f" | Relevância: {context.get('similarity_score', 0.0):.2f}"
                    )
    else:
        logger.info("  Nenhum contexto específico encontrado.")

    # Métricas técnicas (apenas com show_details=True)
    if show_details:
        logger.info("MÉTRICAS DETALHADAS:")
        logger.info("─" * 40)
        confidence = response.intelligent_response.get("confidence", 0.0)
        confidence_icon = "OK" if confidence > 0.8 else "AVG" if confidence > 0.5 else "LOW"
        logger.info(f"  Tempo total:                {response.processing_time:.4f}s")
        logger.info(f"  Tempo insights:             {response.intelligent_response.get('processing_time', 0.0):.4f}s")
        logger.info(f"  Tipo de consulta:           {response.query_type}")
        logger.info(f"  Estratégia de seleção:      {response.summary_stats.get('selection_strategy', 'N/A')}")
        logger.info(f"  Chunks encontrados:         {response.summary_stats.get('total_chunks_found', 0)}")
        logger.info(f"  Chunks selecionados:        {response.summary_stats.get('chunks_selected', 0)}")
        logger.info(f"  Clientes envolvidos:        {len(response.summary_stats.get('clients_involved', []))}")
        logger.info(f"  Limiar qualidade atingido:  {response.summary_stats.get('quality_threshold_met', 'N/A')}")
        logger.info(f"  [{confidence_icon}] Confiança:            {confidence:.1%}")

    logger.info("═" * 120)
