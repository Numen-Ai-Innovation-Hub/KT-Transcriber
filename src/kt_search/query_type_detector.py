"""
Query Type Detector - Detecção de tipo de consulta por regras.

Responsabilidade: classificar consultas em tipos funcionais (metadata_listing,
decision, problem, general, etc.) usando regex e padrões léxicos,
sem nenhuma dependência de LLM, ChromaDB ou estado de instância.
"""

import re
from collections.abc import Callable
from typing import Any


class QueryTypeDetector:
    """Detecta tipo de consulta via regras e regex — sem LLM, sem ChromaDB."""

    # ════════════════════════════════════════════════════════════════════════
    # Detecção de análise específica de KT
    # ════════════════════════════════════════════════════════════════════════

    def detect_specific_kt_analysis(self, query_lower: str) -> bool:
        """
        Detecta se query busca análise específica de um KT vs listagem genérica.

        ANÁLISE ESPECÍFICA (não deve usar fast-track):
        - "Resuma os principais pontos discutidos no KT iflow PC Factory"
        - "Qual os temas relevantes discutidos no KT - Estorno em massa"
        - "O que foi abordado no KT sustentação"

        LISTAGEM GENÉRICA (pode usar fast-track):
        - "Liste todos os KTs que temos"
        - "Quantos KTs temos na base"
        - "Quais KTs estão disponíveis"

        Args:
            query_lower: Query normalizada para lowercase.

        Returns:
            True se é análise específica; False se é listagem genérica.
        """
        specific_analysis_patterns = [
            "temas.*discutidos",
            "pontos.*discutidos",
            "principais.*pontos",
            "o que foi.*abordado",
            "que foi.*explicado",
            "resuma.*pontos",
            "resumo.*do kt",
            "conteúdo.*do kt",
            "assuntos.*tratados",
            "no kt",
            "kt.*específico",
            "neste kt",
            "deste kt",
            "resuma",
            "resumir",
            "analise",
            "analisar",
            "explique",
            "explicar",
        ]

        generic_listing_patterns = [
            "liste.*kts",
            "quantos.*kts",
            "quais.*kts.*temos",
            "kts.*disponíveis",
            "kts.*que.*temos",
            "todos.*os.*kts",
        ]

        for pattern in generic_listing_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return False

        for pattern in specific_analysis_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return True

        if "kt" in query_lower and any(
            word in query_lower for word in ["iflow", "estorno", "sustentação", "correção", "pc"]
        ):
            return True

        return False

    # ════════════════════════════════════════════════════════════════════════
    # Detecção de listagem com threshold rigoroso
    # ════════════════════════════════════════════════════════════════════════

    def detect_listing_query_refined(self, query_lower: str) -> bool:
        """
        Versão refinada da detecção de listagem com threshold mais rigoroso.

        Args:
            query_lower: Query normalizada para lowercase.

        Returns:
            True se a query é claramente uma listagem genérica.
        """
        explicit_listing_patterns = [
            r"^liste\s+.*",
            r"quais.*kts.*temos",
            r"quantos.*kts.*temos",
            r"todos.*os.*kts",
            r"kts.*disponíveis",
        ]

        for pattern in explicit_listing_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return True

        return False

    # ════════════════════════════════════════════════════════════════════════
    # Determinação do tema principal
    # ════════════════════════════════════════════════════════════════════════

    # ════════════════════════════════════════════════════════════════════════
    # Detecção de tipo de query para seleção de prompt especializado
    # ════════════════════════════════════════════════════════════════════════

    def detect_query_type(
        self,
        query: str,
        results: list[Any],
        extract_client_fn: Callable[[str], str | None] | None = None,
        client_exists_fn: Callable[[str], bool] | None = None,
    ) -> str:
        """
        Detecta o tipo de consulta para usar prompt especializado no InsightsAgent.

        Classifica em: 'decision', 'problem', 'metadata_listing', 'participants',
        'highlights_summary', 'project_listing', 'client_not_found', 'general'.

        Args:
            query: Pergunta original.
            results: Resultados da busca ChromaDB.
            extract_client_fn: Função opcional para extrair nome de cliente da query.
                Assinatura: (query_lower: str) -> str | None.
            client_exists_fn: Função opcional para verificar se cliente existe na base.
                Assinatura: (client_name: str) -> bool.

        Returns:
            String com tipo detectado.
        """
        query_lower = query.lower()

        # Detectar consultas de principais pontos/highlights
        highlights_keywords = [
            "principais pontos",
            "pontos importantes",
            "resumo da reunião",
            "highlights",
            "pontos-chave",
            "tópicos principais",
        ]
        if any(keyword in query_lower for keyword in highlights_keywords):
            return "highlights_summary"

        # Detectar consultas específicas sobre projetos
        project_keywords = ["quais projetos", "projetos foram", "projetos mencionados", "lista de projetos"]
        if any(keyword in query_lower for keyword in project_keywords):
            return "project_listing"

        # Detectar consultas de metadados/listagem — expandido sem hardcoding
        metadata_keywords = [
            "quais", "que", "o que",
            "liste", "listar", "enumere", "enumerar", "mostre", "mostrar",
            "exiba", "exibir", "apresente", "apresentar",
            "listagem", "lista", "relação", "catálogo", "inventário", "índice",
            "vídeos", "videos", "kts", "reuniões", "reunioes", "meetings",
            "clientes", "projetos", "arquivos",
            "temos", "disponíveis", "disponivel", "existem", "possuímos",
            "temos acesso", "base", "conhecimento",
            "informações", "informacoes", "dados", "conteúdo", "conteudo", "material", "nomes",
        ]
        if any(keyword in query_lower for keyword in metadata_keywords):
            # CAMADA 1: padrões legados
            legacy_patterns = [
                "liste" in query_lower
                and ("vídeos" in query_lower or "kts" in query_lower or "reuniões" in query_lower),
                "mostre" in query_lower and ("vídeos" in query_lower or "kts" in query_lower),
                "quais" in query_lower
                and ("kts" in query_lower or "reuniões" in query_lower or "vídeos" in query_lower),
                "temos" in query_lower and "disponíveis" in query_lower,
                "base" in query_lower and "conhecimento" in query_lower,
            ]

            # CAMADA 2: regex flexível
            flexible_patterns = [
                r"\b(quais?|que)\s+.*\b(nomes?|clientes?)\b.*\b(temos|kt|informações?)",
                r"\bnomes?\s+.*\bclientes?\b.*\b(kt|informações?)\b",
                r"\btemos\s+.*\bclientes?\b.*\b(base|conhecimento)\b",
                r"\bclientes?\s+.*\b(disponíveis?|temos|base|conhecimento)\b",
                r"\bliste?\s+.*\b(clientes?|kts?|documentos?|vídeos?)\b",
                r"\b(quais?|que)\s+.*\b(kts?|documentos?|vídeos?)\s+.*\btemos\b",
                r"\b.*\bbase\s+.*\bconhecimento\b.*\bclientes?\b",
                r"\btemos\s+.*\binformações?\b.*\bclientes?\b",
            ]

            # CAMADA 3: pontuação por palavras-chave
            listing_score = 0
            action_verbs = ["liste", "listar", "quais", "que", "mostre", "exiba"]
            entities = ["clientes", "cliente", "kts", "kt", "documentos", "vídeos"]
            context_words = ["temos", "disponíveis", "base", "conhecimento", "informações", "nomes"]

            words = query_lower.split()
            for verb in action_verbs:
                if any(verb in word for word in words):
                    listing_score += 3
            for entity in entities:
                if any(entity in word for word in words):
                    listing_score += 2
            for context in context_words:
                if any(context in word for word in words):
                    listing_score += 1

            is_listing_query = (
                any(legacy_patterns)
                or any(re.search(pattern, query_lower) for pattern in flexible_patterns)
                or listing_score >= 8
            )

            # Verificar análise específica vs listagem genérica
            is_specific_kt_analysis = self.detect_specific_kt_analysis(query_lower)

            if is_listing_query and not is_specific_kt_analysis:
                # Verificar cliente inexistente antes do fast-track
                if "cliente" in query_lower and extract_client_fn is not None and client_exists_fn is not None:
                    client_mentioned = extract_client_fn(query_lower)
                    if client_mentioned and not client_exists_fn(client_mentioned):
                        return "client_not_found"

                return "metadata_listing"
            elif is_specific_kt_analysis:
                return "general"  # Análise específica → usa LLM

            # Verificar se resultados são do tipo metadata
            if results:
                for result in results:
                    search_result = getattr(result, "original_result", result)
                    content_type = getattr(search_result, "content_type", "")
                    category = getattr(search_result, "category", "")
                    if content_type == "metadata" or category == "metadados":
                        return "metadata_listing"

                # Fallback inteligente: resultados suficientes + query sobre vídeos/KTs
                if len(results) >= 5:
                    video_related = any(
                        term in query_lower for term in ["vídeos", "videos", "kts", "reuniões", "meetings"]
                    )
                    if video_related:
                        return "metadata_listing"

        # Detectar participantes
        participant_keywords = ["quem participou", "participantes", "quem estava", "pessoas que"]
        if any(keyword in query_lower for keyword in participant_keywords):
            return "participants"

        # Detectar decisões
        decision_keywords = ["decisão", "decidido", "aprovado", "definido", "acordo", "resolução"]
        if any(keyword in query_lower for keyword in decision_keywords):
            return "decision"

        # Detectar problemas
        problem_keywords = ["problema", "erro", "falha", "dificuldade", "issue", "bug", "crítico"]
        if any(keyword in query_lower for keyword in problem_keywords):
            return "problem"

        # Analisar categorias dos resultados
        if results:
            categories = [getattr(r, "category", "geral") for r in results]
            if categories.count("decisao") > len(categories) * 0.6:
                return "decision"
            if categories.count("problema") > len(categories) * 0.6:
                return "problem"

        return "general"

    # ════════════════════════════════════════════════════════════════════════
    # Determinação do tema principal
    # ════════════════════════════════════════════════════════════════════════

    def determine_primary_theme(self, query: str, results: list[Any], dominant_client: str | None) -> str:
        """
        Determina o tema principal da consulta baseado no contexto.

        Args:
            query: Pergunta original.
            results: Resultados da busca (não usados diretamente, mas disponíveis).
            dominant_client: Cliente dominante detectado nos resultados, se houver.

        Returns:
            String descrevendo o tema principal (ex: 'reunião_dexco', 'listagem_clientes').
        """
        query_lower = query.lower()

        if dominant_client:
            if "reunião" in query_lower or "meeting" in query_lower:
                return f"reunião_{dominant_client.lower()}"
            else:
                return f"informações_{dominant_client.lower()}"

        if any(word in query_lower for word in ["quais", "nomes", "clientes"]):
            return "listagem_clientes"
        elif any(word in query_lower for word in ["qual", "cliente", "reunião"]):
            return "identificação_cliente"
        elif any(word in query_lower for word in ["problema", "erro", "issue"]):
            return "resolução_problemas"

        return "informações_gerais"
