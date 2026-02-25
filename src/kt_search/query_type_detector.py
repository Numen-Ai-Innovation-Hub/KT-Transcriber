"""
Query Type Detector - Detecção de tipo de consulta por regras.

Responsabilidade: classificar consultas em tipos funcionais (metadata_listing,
decision, problem, general, etc.) usando regex e padrões léxicos,
sem nenhuma dependência de LLM, ChromaDB ou estado de instância.
"""

import re
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
