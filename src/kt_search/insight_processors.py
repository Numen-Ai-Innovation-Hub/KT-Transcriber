"""
Insight Processors - Processamento puro de conteúdo, scoring e formatação LLM.

Responsabilidade: todas as transformações de conteúdo que não dependem de
OpenAI, ChromaDB ou estado de instância. São funções puras reutilizáveis
pelo InsightsAgent para análise contextual, filtro semântico e formatação.
"""

import re
import unicodedata
from typing import Any

from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)


class InsightProcessors:
    """Processadores puros de conteúdo, scoring e formatação — sem OpenAI, sem ChromaDB."""

    # ════════════════════════════════════════════════════════════════════════
    # Análise contextual
    # ════════════════════════════════════════════════════════════════════════

    def analyze_context_relevance(self, query: str, search_results: list[Any]) -> dict[str, Any]:
        """
        Analisa a relevância contextual dos resultados para guiar a geração de insights.

        Args:
            query: Pergunta original.
            search_results: Resultados da busca.

        Returns:
            Dict com análise contextual: tema principal, entidades, contexto dominante.
        """
        if not search_results:
            return {"primary_theme": "unknown", "main_entities": [], "dominant_context": None, "confidence": 0.0}

        query_entities = self.extract_entities_from_query(query)

        video_frequency: dict[str, int] = {}
        client_mentions: dict[str, int] = {}

        for result in search_results:
            if hasattr(result, "original_result"):
                video_name = getattr(result.original_result, "video_name", "Video_KT")
            else:
                video_name = getattr(result, "video_name", "Video_KT")

            video_frequency[video_name] = video_frequency.get(video_name, 0) + 1

            for client in ["ARCO", "VÍSSIMO", "VISSIMO", "DAVÍSSIMO", "GRAN CRU"]:
                if client in video_name.upper():
                    client_mentions[client] = client_mentions.get(client, 0) + 1

        dominant_video = max(video_frequency.items(), key=lambda x: x[1])[0] if video_frequency else None
        dominant_client = max(client_mentions.items(), key=lambda x: x[1])[0] if client_mentions else None

        primary_theme = self.determine_primary_theme(query, search_results, dominant_client)

        return {
            "primary_theme": primary_theme,
            "main_entities": query_entities,
            "dominant_context": {
                "video": dominant_video,
                "client": dominant_client,
                "video_frequency": video_frequency,
                "client_mentions": client_mentions,
            },
            "confidence": (
                min(1.0, max(video_frequency.values()) / len(search_results)) if video_frequency else 0.0
            ),
        }

    def determine_primary_theme(self, query: str, results: list[Any], dominant_client: str | None) -> str:
        """
        Determina o tema principal da consulta baseado no contexto.

        Args:
            query: Pergunta original.
            results: Resultados da busca (disponíveis para uso futuro).
            dominant_client: Cliente dominante detectado nos resultados.

        Returns:
            String descrevendo o tema principal.
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

    # ════════════════════════════════════════════════════════════════════════
    # Extração de entidades e conteúdo
    # ════════════════════════════════════════════════════════════════════════

    def extract_entities_from_query(self, query: str) -> list[str]:
        """Extrai entidades relevantes da query (clientes e termos técnicos)."""
        entities = []
        query_upper = query.upper()

        clients = ["ARCO", "VÍSSIMO", "VISSIMO", "DAVÍSSIMO", "GRAN CRU"]
        for client in clients:
            if client in query_upper:
                entities.append(client)

        technical_terms = ["CPI", "FIORI", "ABAP", "BTP", "MM", "SD", "FI", "CO", "KT"]
        for term in technical_terms:
            if term in query_upper:
                entities.append(term)

        return entities

    def extract_query_keywords(self, query: str) -> list[str]:
        """
        Extrai palavras-chave relevantes da query para filtro semântico.

        Args:
            query: Query original do usuário.

        Returns:
            Lista de palavras-chave relevantes.
        """
        query_lower = query.lower()

        stop_words = {
            "o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das",
            "em", "no", "na", "nos", "nas", "por", "para", "com", "sem", "sobre", "que", "qual",
            "quais", "quando", "onde", "como", "quem", "temos", "tem", "há", "foi", "foram",
            "é", "são", "estar", "esta", "este", "estes", "estas", "ser", "sido",
        }

        words = re.findall(r"\b[a-záàâãéêíóôõúç]{3,}\b", query_lower)
        keywords = [word for word in words if word not in stop_words]

        technical_terms = [
            "integração", "integrações", "cpi", "kt", "fiori", "mm", "sd", "fi", "co", "abap", "btp"
        ]
        for term in technical_terms:
            if term in query_lower and term not in keywords:
                keywords.append(term)

        client_names = ["víssimo", "vissimo", "arco", "davíssimo", "gran", "cru"]
        for client in client_names:
            if client in query_lower and client not in keywords:
                keywords.append(client)

        return keywords

    def extract_content_from_result(self, result: Any) -> str:
        """
        Extrai conteúdo textual de um resultado para análise semântica.

        Args:
            result: Resultado da busca (ContextualizedResult ou SearchResult).

        Returns:
            Conteúdo textual do resultado.
        """
        content = ""

        if hasattr(result, "original_result"):
            search_result = result.original_result
            if hasattr(result, "context_window"):
                content = getattr(result.context_window, "full_context_text", "")
            if not content and search_result:
                content = getattr(search_result, "content", "")
                if not content:
                    content = getattr(search_result, "main_content", "")
                if not content:
                    content = getattr(search_result, "text", "")
        else:
            content = getattr(result, "content", "")
            if not content:
                content = getattr(result, "main_content", "")
            if not content:
                content = getattr(result, "text", "")
            if not content:
                content = str(result) if result else ""

        if not content.strip():
            logger.debug(f"⚠️ Conteúdo vazio extraído de resultado tipo: {type(result)}")
            logger.debug(f"   Atributos disponíveis: {[attr for attr in dir(result) if not attr.startswith('_')]}")

        return content.strip() if content else ""

    def extract_title_from_content(self, content: str) -> str:
        """Extrai título do contexto para title matching."""
        lines = content.strip().split("\n")
        first_line = lines[0] if lines else ""

        if any(keyword in first_line.lower() for keyword in ["kt", "reunião", "meeting", "ajuste", "sustentação"]):
            return first_line.strip()

        for line in lines[:3]:
            if ("KT" in line or "reunião" in line.lower()) and len(line.strip()) < 200:
                return line.strip()

        return ""

    def extract_client_from_query(self, query_lower: str) -> str:
        """Extrai nome do cliente mencionado na query."""
        client_patterns = [
            r"cliente\s+([A-Za-z][A-Za-z0-9_]*)",
            r"sobre\s+o\s+cliente\s+([A-Za-z][A-Za-z0-9_]*)",
            r"informações\s+.*cliente\s+([A-Za-z][A-Za-z0-9_]*)",
        ]

        for pattern in client_patterns:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                return match.group(1).upper()

        return ""

    # ════════════════════════════════════════════════════════════════════════
    # Normalização
    # ════════════════════════════════════════════════════════════════════════

    def normalize_for_matching(self, text: str) -> str:
        """Normaliza texto removendo acentos, pontuação e espaços extras."""
        text = unicodedata.normalize("NFD", text)
        text = "".join(c for c in text if unicodedata.category(c) != "Mn")
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    # ════════════════════════════════════════════════════════════════════════
    # Filtro semântico
    # ════════════════════════════════════════════════════════════════════════

    def apply_semantic_filter(self, search_results: list[Any], original_query: str) -> list[Any]:
        """
        Aplica filtro semântico para manter apenas contextos relevantes à query original.

        Args:
            search_results: Lista de resultados da busca.
            original_query: Query original do usuário.

        Returns:
            Lista filtrada de resultados relevantes.
        """
        if not search_results or not original_query:
            return search_results

        query_keywords = self.extract_query_keywords(original_query)
        logger.debug(f"Palavras-chave extraídas da query: {query_keywords}")

        SEMANTIC_RELEVANCE_THRESHOLD = 0.05

        filtered_results = []
        for result in search_results:
            content = self.extract_content_from_result(result)
            semantic_score = self.calculate_semantic_relevance(content, query_keywords, original_query)

            if semantic_score >= SEMANTIC_RELEVANCE_THRESHOLD:
                filtered_results.append(result)
                logger.debug(f"Contexto mantido (score: {semantic_score:.2f}): {content[:100]}...")
            else:
                logger.debug(f"Contexto filtrado (score: {semantic_score:.2f}): {content[:100]}...")

        if not filtered_results and search_results:
            best_result = max(
                search_results,
                key=lambda r: self.calculate_semantic_relevance(
                    self.extract_content_from_result(r), query_keywords, original_query
                ),
            )
            filtered_results = [best_result]
            logger.info("Nenhum contexto passou no filtro semântico - mantendo o melhor resultado")

        return filtered_results

    # ════════════════════════════════════════════════════════════════════════
    # Scoring de relevância
    # ════════════════════════════════════════════════════════════════════════

    def calculate_semantic_relevance(
        self, content: str, query_keywords: list[str], original_query: str
    ) -> float:
        """
        Calcula relevância semântica entre conteúdo e query original.

        Args:
            content: Conteúdo do resultado.
            query_keywords: Palavras-chave da query.
            original_query: Query original para análise contextual.

        Returns:
            Score de relevância semântica (0.0 a 1.0).
        """
        if not content or not query_keywords:
            return 0.0

        content_lower = content.lower()
        original_query_lower = original_query.lower()

        keyword_matches = sum(1 for keyword in query_keywords if keyword in content_lower)
        keyword_score = (keyword_matches / len(query_keywords)) * 0.4

        context_score = 0.0

        if any(term in original_query_lower for term in ["integração", "integrações", "integrar"]):
            integration_terms = [
                "integração", "integrações", "cpi", "api", "interface",
                "conectores", "btp", "j1b-tax", "j1b", "tax",
            ]
            integration_matches = sum(1 for term in integration_terms if term in content_lower)
            context_score = min(1.0, integration_matches / 3) * 0.35

            if any(term in content_lower for term in ["j1b-tax", "j1b", "cpi", "api"]) and integration_matches > 0:
                context_score *= 1.2
            elif (
                any(term in content_lower for term in ["fiscal", "tributário", "imposto"])
                and integration_matches == 0
            ):
                context_score *= 0.5

        elif any(client in original_query_lower for client in ["víssimo", "vissimo", "arco"]):
            client_matches = sum(
                1
                for client in ["víssimo", "vissimo", "arco"]
                if client in content_lower and client in original_query_lower
            )
            context_score = min(1.0, client_matches) * 0.35

        else:
            domain_terms = ["reunião", "meeting", "kt", "conhecimento", "transferência", "projeto"]
            domain_matches = sum(1 for term in domain_terms if term in content_lower)
            context_score = min(1.0, domain_matches / 3) * 0.35

        theme_score = 0.0
        if len(content) > 50:
            query_themes = {
                "técnico": ["erro", "problema", "solução", "implementação", "configuração"],
                "negócio": ["cliente", "projeto", "decisão", "aprovação", "requisito"],
                "reunião": ["participou", "discutido", "decidido", "apresentou", "falou"],
            }

            max_theme_score = 0.0
            for _theme, terms in query_themes.items():
                query_theme_matches = sum(1 for term in terms if term in original_query_lower)
                content_theme_matches = sum(1 for term in terms if term in content_lower)

                if query_theme_matches > 0:
                    theme_relevance = min(1.0, content_theme_matches / max(1, query_theme_matches))
                    max_theme_score = max(max_theme_score, theme_relevance)

            theme_score = max_theme_score * 0.25

        title_bonus = 0.0
        content_title = self.extract_title_from_content(content)
        if content_title:
            title_bonus = self.calculate_title_matching_bonus(original_query, content_title)

        final_score = keyword_score + context_score + theme_score + title_bonus
        return min(1.0, final_score)

    def calculate_title_matching_bonus(self, query: str, title: str) -> float:
        """Calcula bonus por matching entre query e título."""
        if not query or not title:
            return 0.0

        query_normalized = self.normalize_for_matching(query.lower())
        title_normalized = self.normalize_for_matching(title.lower())

        query_tokens = set(query_normalized.split())
        title_tokens = set(title_normalized.split())

        common_words = {"de", "da", "do", "em", "no", "na", "com", "para", "o", "a", "e", "um", "uma"}
        query_tokens = query_tokens - common_words
        title_tokens = title_tokens - common_words

        if not query_tokens or not title_tokens:
            return 0.0

        intersection = query_tokens.intersection(title_tokens)
        union = query_tokens.union(title_tokens)

        if len(union) == 0:
            return 0.0

        jaccard_score = len(intersection) / len(union)

        if jaccard_score >= 0.5:
            return 0.4
        elif jaccard_score >= 0.3:
            return 0.25
        elif jaccard_score >= 0.15:
            return 0.15
        elif jaccard_score > 0:
            return 0.05

        return 0.0

    def calculate_confidence(self, results: list[Any], insight: str) -> float:
        """
        Calcula confiança do insight baseado na qualidade dos resultados.

        Args:
            results: Resultados da busca.
            insight: Insight gerado.

        Returns:
            Score de confiança (0.0 a 1.0).
        """
        if not results or not insight:
            return 0.0

        base_confidence = 0.6
        high_relevance_bonus = sum(0.1 for r in results if getattr(r, "relevance_score", 0) > 0.8)

        unique_videos = len({getattr(r, "video_name", "") for r in results})
        diversity_bonus = 0.1 if unique_videos > 1 else 0.05

        length_bonus = 0.1 if 50 <= len(insight) <= 800 else 0.0

        specificity_bonus = (
            0.1
            if any(
                word in insight.lower()
                for word in [
                    "decidido", "aprovado", "problema", "solução",
                    "insight", "descoberto", "identificado",
                ]
            )
            else 0.0
        )

        return min(
            1.0,
            base_confidence + high_relevance_bonus + diversity_bonus + length_bonus + specificity_bonus,
        )

    # ════════════════════════════════════════════════════════════════════════
    # Formatação
    # ════════════════════════════════════════════════════════════════════════

    def format_insight_text(self, raw_insight: str) -> str:
        """
        Formata o texto de insight para melhor legibilidade.

        Args:
            raw_insight: Texto bruto retornado pelo OpenAI.

        Returns:
            Texto formatado com quebras de linha e numeração melhorada.
        """
        if not raw_insight:
            return raw_insight

        formatted_text = raw_insight
        formatted_text = re.sub(r"(\d+)\.\s+", r"\n\n**\1.** ", formatted_text)
        formatted_text = re.sub(r"(\. )([A-Z][^.]{80,})", r"\1\n\n\2", formatted_text)
        formatted_text = re.sub(r"(?<!\*\*)([A-Z][a-zA-Z\s]{10,}:)(?!\*\*)", r"**\1**", formatted_text)
        formatted_text = formatted_text.lstrip("\n")
        formatted_text = re.sub(r"\n{3,}", "\n\n", formatted_text)

        return formatted_text

    def format_contexts_for_llm(
        self, search_results: list[Any], context_analysis: dict[str, Any] | None = None
    ) -> str:
        """
        Formata contextos dos resultados para envio ao LLM com filtro semântico.

        Args:
            search_results: Resultados da busca semântica.
            context_analysis: Análise contextual com query original para filtro semântico.

        Returns:
            String formatada com contextos filtrados por relevância semântica.
        """
        is_metadata_listing = (
            context_analysis
            and "original_query" in context_analysis
            and any(
                word in context_analysis["original_query"].lower()
                for word in ["liste", "quais", "disponíveis"]
            )
        )

        if context_analysis and "original_query" in context_analysis and not is_metadata_listing:
            search_results = self.apply_semantic_filter(search_results, context_analysis["original_query"])
            logger.info(f"Filtro semântico aplicado: {len(search_results)} contextos mantidos após filtragem")
        elif is_metadata_listing:
            logger.info(f"Filtro semântico PULADO para metadata listing: {len(search_results)} contextos mantidos")

        formatted_contexts = []

        is_metadata_query = any(
            getattr(result, "metadata", {}).get("is_metadata_result", False)
            if hasattr(result, "metadata")
            else getattr(result, "original_result", result).metadata.get("is_metadata_result", False)
            if hasattr(getattr(result, "original_result", result), "metadata")
            else False
            for result in search_results[:1]
        )

        max_results = 4 if is_metadata_query else 2
        for i, result in enumerate(search_results[:max_results], 1):
            if isinstance(result, dict):
                search_result = result
                content = result.get("content", "")
                metadata = result.get("metadata", {})
            elif hasattr(result, "original_result"):
                search_result = result.original_result
                content = getattr(
                    result.context_window, "full_context_text", getattr(search_result, "content", "")
                )
                metadata = getattr(search_result, "metadata", {})
            else:
                search_result = result
                content = getattr(result, "content", "")
                metadata = getattr(result, "metadata", {})

            if not content or content.strip() == "":
                if hasattr(search_result, "main_content"):
                    content = getattr(search_result, "main_content", "")
                elif hasattr(search_result, "text"):
                    content = getattr(search_result, "text", "")
                elif hasattr(search_result, "transcript"):
                    content = getattr(search_result, "transcript", "")
                logger.warning(f"⚠️ Contexto vazio detectado para resultado {i} - tentando fontes alternativas")

            if not content or content.strip() == "":
                logger.error(f"❌ Contexto {i} completamente vazio - pulando resultado")
                continue

            if metadata.get("is_video_result"):
                client = metadata.get("client", "N/A")
                context_text = f"{i}. [{client}] {content}"
            else:
                video_name = metadata.get("video_name", "Video_Sem_Nome")
                if video_name in ["Unknown", "", None]:
                    client_name = metadata.get("client_name", metadata.get("client", ""))
                    if client_name:
                        video_name = f"KT_{client_name}"
                    else:
                        video_name = f"Resultado_{i}"
                video_name = video_name[:30]
                context_text = f"{i}. {video_name}: {content}"

            if context_text.strip() and len(context_text.split(":")) > 1 and context_text.split(":")[1].strip():
                formatted_contexts.append(context_text)
            else:
                logger.warning(f"⚠️ Context_text inválido para resultado {i}: '{context_text[:50]}...'")
                formatted_contexts.append(f"{i}. Contexto_Relevante: {content[:200]}...")

        return "\n\n".join(formatted_contexts) if formatted_contexts else ""

    # ════════════════════════════════════════════════════════════════════════
    # Configuração adaptativa
    # ════════════════════════════════════════════════════════════════════════

    def get_performance_config(self, query_type: str, num_results: int) -> dict[str, Any]:
        """
        Configuração adaptativa de performance baseada no tipo de query e contexto.

        Estratégia:
        - METADATA/ENTITY: Respostas concisas possíveis → configuração rápida.
        - SEMANTIC: Contexto rico necessário → configuração balanceada.
        - HIGHLIGHTS: Estrutura complexa → configuração completa.

        Args:
            query_type: Tipo de query detectado.
            num_results: Número de resultados disponíveis.

        Returns:
            Dict com parâmetros de configuração para a chamada ao LLM.
        """
        if query_type in ["metadata_listing", "project_listing"]:
            return {
                "strategy": "fast_listing",
                "max_tokens": 400,
                "temperature": 0.0,
                "top_p": 0.8,
                "timeout": 8.0,
            }

        if query_type in ["participants", "general"] and num_results <= 5:
            return {
                "strategy": "quick_response",
                "max_tokens": 600,
                "temperature": 0.0,
                "top_p": 0.85,
                "timeout": 10.0,
            }

        if query_type == "highlights_summary":
            return {
                "strategy": "quick_analysis",
                "max_tokens": 800,
                "temperature": 0.0,
                "top_p": 0.85,
                "timeout": 10.0,
            }

        return {
            "strategy": "balanced_insight",
            "max_tokens": 800,
            "temperature": 0.0,
            "top_p": 0.9,
            "timeout": 12.0,
        }
