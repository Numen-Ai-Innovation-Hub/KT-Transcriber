"""
Insights Agent - Agente que extrai insights diretos baseados nos resultados da busca semântica
Analisa contextos encontrados e gera insights objetivos para responder perguntas
"""
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)


@dataclass
class DirectInsightResult:
    """Resultado da análise do agente de insights"""

    insight: str
    confidence: float
    sources_used: int
    processing_time: float
    fallback_used: bool = False


class InsightsAgent:
    """
    Agente especializado em extrair insights diretos baseados em resultados de busca

    Funcionalidade:
    - Analisa múltiplos contextos encontrados na busca semântica
    - Extrai insights diretos e objetivos para responder perguntas
    - Consolida informações de diferentes fontes
    - Prioriza informações por relevância e importância
    - Gera percepções acionáveis sobre os dados encontrados
    """

    def __init__(self, openai_client: OpenAI | None = None):
        """
        Inicializa o agente de insights

        Args:
            openai_client: Cliente OpenAI para geração de insights
        """
        if openai_client is None:
            from src.config.settings import OPENAI_API_KEY
            openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
        self.openai_client = openai_client
        self.model = "gpt-4o-mini"

        # Cache simples para insights (para otimização de performance)
        self._insights_cache: dict[str, Any] = {}
        self._cache_max_size = 100

        # Templates de prompts especializados para extração de insights
        self.prompt_templates = {
            "base": self._get_base_prompt_template(),
            "decision": self._get_decision_prompt_template(),
            "problem": self._get_problem_prompt_template(),
            "general": self._get_general_prompt_template(),
            "metadata_listing": self._get_metadata_listing_template(),
            "participants": self._get_participants_template(),
            "project_listing": self._get_project_listing_template(),
            "highlights_summary": self._get_highlights_summary_template(),
        }

        logger.info(f"InsightsAgent inicializado com modelo {self.model}")

    def generate_direct_insight(
        self, original_query: str, search_results: list[Any], query_type: str = None
    ) -> DirectInsightResult | None:
        """
        Extrai insights diretos baseados nos resultados da busca

        Args:
            original_query: Pergunta original do usuário
            search_results: Lista de resultados da busca semântica

        Returns:
            DirectInsightResult com insight gerado ou None se falhou
        """
        # Cache de insights para performance
        import hashlib

        cache_key = hashlib.md5(f"{original_query}_{len(search_results)}".encode()).hexdigest()
        if cache_key in self._insights_cache:
            logger.info("Insight encontrado no cache - retornando imediatamente")
            return self._insights_cache[cache_key]

        # 🚀 CORREÇÃO CRÍTICA: Smart Response Templates para discrepâncias
        cross_client_warning = self._detect_cross_client_warning(search_results)
        if cross_client_warning:
            logger.warning(f"⚠️ Cross-client discrepancy detected: {cross_client_warning}")
            return self._generate_cross_client_response(original_query, search_results, cross_client_warning)

        if not self.openai_client:
            logger.warning("OpenAI client não disponível - usando fallback")
            return self._generate_fallback_insight(original_query, search_results)

        if not search_results:
            logger.warning("Nenhum resultado fornecido para análise")
            result = DirectInsightResult(
                insight="Não foram encontrados contextos relevantes para gerar insights sobre sua consulta.",
                confidence=0.0,
                sources_used=0,
                processing_time=0.0,
                fallback_used=True,
            )

        # Verificar qualidade mínima dos resultados
        if len(search_results) < 2:
            logger.warning("Poucos resultados para análise robusta - usando fallback")
            return self._generate_fallback_insight(original_query, search_results)

        try:
            start_time = time.time()
            suffix = "..." if len(original_query) > 100 else ""
            logger.info(
                f"Iniciando extração de insights para: '{original_query[:100]}{suffix}'"
            )

            # 1. Analisar relevância contextual dos resultados
            context_analysis = self._analyze_context_relevance(original_query, search_results)
            logger.info(f"Análise contextual: {context_analysis['primary_theme']}")

            # 2. Preparar contextos para análise com foco na relevância (incluir query original para filtro semântico)
            context_analysis["original_query"] = original_query
            formatted_contexts = self._format_contexts_for_llm(search_results, context_analysis)
            logger.info("Formatados contextos para análise LLM (com filtro semântico)")

            # 3. Detectar tipo de consulta para usar prompt especializado
            query_type = self._detect_query_type(original_query, search_results)
            logger.info(f"🎯 InsightsAgent - Tipo de consulta detectado: {query_type} para query: '{original_query}'")

            # 🚀 FASE 3 OTIMIZAÇÃO: Fast-track para queries de listagem de KTs
            if query_type == "metadata_listing":
                logger.info("⚡ FAST-TRACK: Query de metadata listing - gerando resposta com agrupamento por KTs")
                return self._generate_fast_metadata_response(original_query, search_results, start_time)

            # 🚨 P1-1 FIX: Handler para cliente inexistente
            if query_type == "client_not_found":
                logger.info("🚫 FAST-TRACK: Cliente inexistente - gerando resposta de não encontrado")
                return self._generate_client_not_found_response(original_query, start_time)

            # 4. Gerar prompt especializado com análise contextual
            prompt = self._build_specialized_prompt(query_type, original_query, formatted_contexts, context_analysis)

            # 5. Configuração adaptativa baseada no tipo de query
            performance_config = self._get_performance_config(query_type, len(search_results))

            # 6. Chamar OpenAI para análise e extração de insights
            logger.info(
                f"Enviando contextos para extração de insights OpenAI (config: {performance_config['strategy']})"
            )
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": f"Analise reuniões corporativas e extraia insights objetivos.\n\n{prompt}",
                    }
                ],
                temperature=performance_config["temperature"],
                top_p=performance_config["top_p"],
                presence_penalty=0.0,
                frequency_penalty=0.0,
                max_tokens=performance_config["max_tokens"],
                timeout=performance_config["timeout"],
            )

            # 6. Extrair e processar insight
            raw_insight = (response.choices[0].message.content or "").strip()
            direct_insight = self._format_insight_text(raw_insight)
            processing_time = time.time() - start_time

            # 7. Calcular confiança baseada na qualidade dos contextos
            confidence = self._calculate_confidence(search_results, direct_insight)

            logger.info(
                f"Insight direto gerado em {processing_time:.2f}s - "
                f"Confiança: {confidence:.1%}, Tamanho: {len(direct_insight)} chars"
            )

            result = DirectInsightResult(
                insight=direct_insight,
                confidence=confidence,
                sources_used=len(search_results),
                processing_time=processing_time,
                fallback_used=False,
            )

            # Adicionar ao cache
            if len(self._insights_cache) >= self._cache_max_size:
                # Remove o mais antigo (FIFO simples)
                oldest_key = next(iter(self._insights_cache))
                del self._insights_cache[oldest_key]
            self._insights_cache[cache_key] = result

            return result

        except Exception as e:
            logger.error(f"Erro ao gerar insight direto via OpenAI: {e}")
            # Fallback para insight estruturado
            return self._generate_fallback_insight(original_query, search_results)

    def _analyze_context_relevance(self, query: str, search_results: list[Any]) -> dict[str, Any]:
        """
        Analisa a relevância contextual dos resultados para guiar a geração de insights

        Args:
            query: Pergunta original
            search_results: Resultados da busca

        Returns:
            Dict com análise contextual: tema principal, entidades, contexto dominante
        """
        if not search_results:
            return {"primary_theme": "unknown", "main_entities": [], "dominant_context": None, "confidence": 0.0}

        # 1. Extrair entidades mencionadas na query
        query_entities = self._extract_entities_from_query(query)

        # 2. Analisar frequência de vídeos/contextos
        video_frequency: dict[str, int] = {}
        client_mentions: dict[str, int] = {}

        for result in search_results:
            # Obter nome do vídeo
            if hasattr(result, "original_result"):
                video_name = getattr(result.original_result, "video_name", "Video_KT")
                getattr(result.context_window, "full_context_text", getattr(result.original_result, "content", ""))
            else:
                video_name = getattr(result, "video_name", "Video_KT")
                getattr(result, "content", "")

            # Contar frequência de vídeos
            video_frequency[video_name] = video_frequency.get(video_name, 0) + 1

            # Extrair possíveis clientes do nome do vídeo
            for client in ["ARCO", "VÍSSIMO", "VISSIMO", "DAVÍSSIMO", "GRAN CRU"]:
                if client in video_name.upper():
                    client_mentions[client] = client_mentions.get(client, 0) + 1

        # 3. Determinar contexto dominante
        dominant_video = max(video_frequency.items(), key=lambda x: x[1])[0] if video_frequency else None
        dominant_client = max(client_mentions.items(), key=lambda x: x[1])[0] if client_mentions else None

        # 4. Determinar tema principal baseado na query e contextos
        primary_theme = self._determine_primary_theme(query, search_results, dominant_client)

        return {
            "primary_theme": primary_theme,
            "main_entities": query_entities,
            "dominant_context": {
                "video": dominant_video,
                "client": dominant_client,
                "video_frequency": video_frequency,
                "client_mentions": client_mentions,
            },
            "confidence": min(1.0, max(video_frequency.values()) / len(search_results)) if video_frequency else 0.0,
        }

    def _extract_entities_from_query(self, query: str) -> list[str]:
        """Extrai entidades relevantes da query"""
        entities = []
        query_upper = query.upper()

        # Clientes conhecidos
        clients = ["ARCO", "VÍSSIMO", "VISSIMO", "DAVÍSSIMO", "GRAN CRU"]
        for client in clients:
            if client in query_upper:
                entities.append(client)

        # Termos técnicos/módulos
        technical_terms = ["CPI", "FIORI", "ABAP", "BTP", "MM", "SD", "FI", "CO", "KT"]
        for term in technical_terms:
            if term in query_upper:
                entities.append(term)

        return entities

    def _apply_semantic_filter(self, search_results: list[Any], original_query: str) -> list[Any]:
        """
        Aplica filtro semântico para manter apenas contextos relevantes à query original

        Args:
            search_results: Lista de resultados da busca
            original_query: Query original do usuário

        Returns:
            Lista filtrada de resultados relevantes
        """
        if not search_results or not original_query:
            return search_results

        # Extrair palavras-chave da query original
        query_keywords = self._extract_query_keywords(original_query)
        logger.debug(f"Palavras-chave extraídas da query: {query_keywords}")

        filtered_results = []
        for result in search_results:
            # Extrair conteúdo do resultado
            content = self._extract_content_from_result(result)

            # Calcular relevância semântica
            semantic_score = self._calculate_semantic_relevance(content, query_keywords, original_query)

            # Aplicar threshold de relevância semântica
            SEMANTIC_RELEVANCE_THRESHOLD = 0.05  # 5% de relevância mínima (muito permissivo para debug)

            if semantic_score >= SEMANTIC_RELEVANCE_THRESHOLD:
                filtered_results.append(result)
                logger.debug(f"Contexto mantido (score: {semantic_score:.2f}): {content[:100]}...")
            else:
                logger.debug(f"Contexto filtrado (score: {semantic_score:.2f}): {content[:100]}...")

        # Garantir que pelo menos 1 resultado seja mantido se houver resultados
        if not filtered_results and search_results:
            # Manter o resultado com maior score
            best_result = max(
                search_results,
                key=lambda r: self._calculate_semantic_relevance(
                    self._extract_content_from_result(r), query_keywords, original_query
                ),
            )
            filtered_results = [best_result]
            logger.info("Nenhum contexto passou no filtro semântico - mantendo o melhor resultado")

        return filtered_results

    def _extract_query_keywords(self, query: str) -> list[str]:
        """
        Extrai palavras-chave relevantes da query para filtro semântico

        Args:
            query: Query original do usuário

        Returns:
            Lista de palavras-chave relevantes
        """
        import re

        # Normalizar query
        query_lower = query.lower()

        # Remover palavras de parada em português
        stop_words = {
            "o",
            "a",
            "os",
            "as",
            "um",
            "uma",
            "uns",
            "umas",
            "de",
            "do",
            "da",
            "dos",
            "das",
            "em",
            "no",
            "na",
            "nos",
            "nas",
            "por",
            "para",
            "com",
            "sem",
            "sobre",
            "que",
            "qual",
            "quais",
            "quando",
            "onde",
            "como",
            "quem",
            "temos",
            "tem",
            "há",
            "foi",
            "foram",
            "é",
            "são",
            "estar",
            "esta",
            "este",
            "estes",
            "estas",
            "ser",
            "sido",
        }

        # Extrair palavras (apenas letras, 3+ caracteres)
        words = re.findall(r"\b[a-záàâãéêíóôõúç]{3,}\b", query_lower)

        # Filtrar stop words
        keywords = [word for word in words if word not in stop_words]

        # Adicionar termos técnicos específicos se presentes
        technical_terms = ["integração", "integrações", "cpi", "kt", "fiori", "mm", "sd", "fi", "co", "abap", "btp"]
        for term in technical_terms:
            if term in query_lower and term not in keywords:
                keywords.append(term)

        # Adicionar nomes de clientes se presentes
        client_names = ["víssimo", "vissimo", "arco", "davíssimo", "gran", "cru"]
        for client in client_names:
            if client in query_lower and client not in keywords:
                keywords.append(client)

        return keywords

    def _extract_content_from_result(self, result: Any) -> str:
        """
        Extrai conteúdo textual de um resultado para análise semântica

        Args:
            result: Resultado da busca (ContextualizedResult ou SearchResult)

        Returns:
            Conteúdo textual do resultado
        """
        content = ""

        # Tentativa 1: ContextualizedResult
        if hasattr(result, "original_result"):
            search_result = result.original_result

            # Tentar context_window primeiro
            if hasattr(result, "context_window"):
                content = getattr(result.context_window, "full_context_text", "")

            # Se não tem context_window ou está vazio, tentar original_result
            if not content and search_result:
                content = getattr(search_result, "content", "")
                if not content:
                    content = getattr(search_result, "main_content", "")
                if not content:
                    content = getattr(search_result, "text", "")

        # Tentativa 2: SearchResult direto
        else:
            content = getattr(result, "content", "")
            if not content:
                content = getattr(result, "main_content", "")
            if not content:
                content = getattr(result, "text", "")
            if not content:
                # Último recurso: converter para string
                content = str(result) if result else ""

        # Log debug se conteúdo está vazio
        if not content.strip():
            logger.debug(f"⚠️ Conteúdo vazio extraído de resultado tipo: {type(result)}")
            logger.debug(f"   Atributos disponíveis: {[attr for attr in dir(result) if not attr.startswith('_')]}")

        return content.strip() if content else ""

    def _calculate_semantic_relevance(self, content: str, query_keywords: list[str], original_query: str) -> float:
        """
        Calcula relevância semântica entre conteúdo e query original

        Args:
            content: Conteúdo do resultado
            query_keywords: Palavras-chave da query
            original_query: Query original para análise contextual

        Returns:
            Score de relevância semântica (0.0 a 1.0)
        """
        if not content or not query_keywords:
            return 0.0

        content_lower = content.lower()
        original_query_lower = original_query.lower()

        # 1. Calcular overlap de palavras-chave (40% do score)
        keyword_matches = sum(1 for keyword in query_keywords if keyword in content_lower)
        keyword_score = (keyword_matches / len(query_keywords)) * 0.4

        # 2. Verificar contexto semântico específico (35% do score)
        context_score = 0.0

        # Se a query é sobre "integrações", priorizar conteúdo sobre integrações
        if any(term in original_query_lower for term in ["integração", "integrações", "integrar"]):
            integration_terms = [
                "integração",
                "integrações",
                "cpi",
                "api",
                "interface",
                "conectores",
                "btp",
                "j1b-tax",
                "j1b",
                "tax",
            ]
            integration_matches = sum(1 for term in integration_terms if term in content_lower)
            context_score = min(1.0, integration_matches / 3) * 0.35

            # Bonus para conteúdo que menciona tanto integração quanto tecnologias específicas
            if any(term in content_lower for term in ["j1b-tax", "j1b", "cpi", "api"]) and integration_matches > 0:
                context_score *= 1.2  # Bonus para contexto técnico relevante

            # Penalizar apenas conteúdo claramente fora do contexto (sem mencionar integrações)
            elif (
                any(term in content_lower for term in ["fiscal", "tributário", "imposto"]) and integration_matches == 0
            ):
                context_score *= 0.5  # Redução moderada para contexto fiscal puro

        # Se a query é sobre um cliente específico, priorizar conteúdo desse cliente
        elif any(client in original_query_lower for client in ["víssimo", "vissimo", "arco"]):
            client_matches = sum(
                1
                for client in ["víssimo", "vissimo", "arco"]
                if client in content_lower and client in original_query_lower
            )
            context_score = min(1.0, client_matches) * 0.35

        # Query geral - contexto baseado em relevância de domínio
        else:
            domain_terms = ["reunião", "meeting", "kt", "conhecimento", "transferência", "projeto"]
            domain_matches = sum(1 for term in domain_terms if term in content_lower)
            context_score = min(1.0, domain_matches / 3) * 0.35

        # 3. Verificar coerência temática (25% do score)
        theme_score = 0.0
        if len(content) > 50:  # Conteúdo suficiente para análise temática
            # Verificar se o conteúdo tem coerência com o tema da query
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

        # 4. BONUS PARA TITLE MATCHING - Detecta se query menciona título específico
        title_bonus = 0.0
        content_title = self._extract_title_from_content(content)
        if content_title:
            title_bonus = self._calculate_title_matching_bonus(original_query, content_title)

        final_score = keyword_score + context_score + theme_score + title_bonus
        return min(1.0, final_score)

    def _determine_primary_theme(self, query: str, results: list[Any], dominant_client: str | None) -> str:
        """Determina o tema principal da consulta baseado no contexto"""
        query_lower = query.lower()

        # Se há cliente dominante, tema é sobre esse cliente
        if dominant_client:
            if "reunião" in query_lower or "meeting" in query_lower:
                return f"reunião_{dominant_client.lower()}"
            else:
                return f"informações_{dominant_client.lower()}"

        # Análise por tipo de pergunta
        if any(word in query_lower for word in ["quais", "nomes", "clientes"]):
            return "listagem_clientes"
        elif any(word in query_lower for word in ["qual", "cliente", "reunião"]):
            return "identificação_cliente"
        elif any(word in query_lower for word in ["problema", "erro", "issue"]):
            return "resolução_problemas"

        return "informações_gerais"

    def _extract_title_from_content(self, content: str) -> str:
        """Extrai título do contexto para title matching"""
        # Procurar padrões de título no início do conteúdo
        lines = content.strip().split("\n")
        first_line = lines[0] if lines else ""

        # Se primeira linha parece ser um título (contém KT, reunião, etc)
        if any(keyword in first_line.lower() for keyword in ["kt", "reunião", "meeting", "ajuste", "sustentação"]):
            return first_line.strip()

        # Procurar por padrões de título em outras linhas
        for line in lines[:3]:  # Primeiras 3 linhas apenas
            if ("KT" in line or "reunião" in line.lower()) and len(line.strip()) < 200:
                return line.strip()

        return ""

    def _calculate_title_matching_bonus(self, query: str, title: str) -> float:
        """Calcula bonus por matching entre query e título"""
        if not query or not title:
            return 0.0

        query_lower = query.lower()
        title_lower = title.lower()

        # Normalizar termos para matching
        query_normalized = self._normalize_for_matching(query_lower)
        title_normalized = self._normalize_for_matching(title_lower)

        # Calcular overlap de tokens significativos
        query_tokens = set(query_normalized.split())
        title_tokens = set(title_normalized.split())

        # Filtrar tokens muito comuns
        common_words = {"de", "da", "do", "em", "no", "na", "com", "para", "o", "a", "e", "um", "uma"}
        query_tokens = query_tokens - common_words
        title_tokens = title_tokens - common_words

        if not query_tokens or not title_tokens:
            return 0.0

        # Calcular Jaccard similarity
        intersection = query_tokens.intersection(title_tokens)
        union = query_tokens.union(title_tokens)

        if len(union) == 0:
            return 0.0

        jaccard_score = len(intersection) / len(union)

        # Bonus progressivo baseado na qualidade do match
        if jaccard_score >= 0.5:  # Match muito forte
            return 0.4  # 40% bonus
        elif jaccard_score >= 0.3:  # Match forte
            return 0.25  # 25% bonus
        elif jaccard_score >= 0.15:  # Match moderado
            return 0.15  # 15% bonus
        elif jaccard_score > 0:  # Match fraco
            return 0.05  # 5% bonus

        return 0.0

    def _normalize_for_matching(self, text: str) -> str:
        """Normaliza texto para melhor matching"""
        # Remover acentos, pontuação e normalizar espaços
        import re
        import unicodedata

        # Normalizar unicode
        text = unicodedata.normalize("NFD", text)
        text = "".join(c for c in text if unicodedata.category(c) != "Mn")

        # Remover pontuação e caracteres especiais
        text = re.sub(r"[^\w\s]", " ", text)

        # Normalizar espaços
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def _format_contexts_for_llm(self, search_results: list[Any], context_analysis: dict[str, Any] = None) -> str:
        """
        Formata contextos dos resultados para envio ao LLM com filtro semântico

        Args:
            search_results: Resultados da busca semântica
            context_analysis: Análise contextual com query original para filtro semântico

        Returns:
            String formatada com contextos filtrados por relevância semântica
        """
        # FILTRO SEMÂNTICO: Filtrar contextos por relevância à query original
        # CORREÇÃO: Pular filtro semântico para queries de metadata listing
        is_metadata_listing = (
            context_analysis
            and "original_query" in context_analysis
            and any(word in context_analysis["original_query"].lower() for word in ["liste", "quais", "disponíveis"])
        )

        if context_analysis and "original_query" in context_analysis and not is_metadata_listing:
            search_results = self._apply_semantic_filter(search_results, context_analysis["original_query"])
            logger.info(f"Filtro semântico aplicado: {len(search_results)} contextos mantidos após filtragem")
        elif is_metadata_listing:
            logger.info(f"Filtro semântico PULADO para metadata listing: {len(search_results)} contextos mantidos")

        formatted_contexts = []

        # Para consultas de metadados, mostrar mais resultados (são mais leves)
        is_metadata_query = any(
            getattr(result, "metadata", {}).get("is_metadata_result", False)
            if hasattr(result, "metadata")
            else getattr(result, "original_result", result).metadata.get("is_metadata_result", False)
            if hasattr(getattr(result, "original_result", result), "metadata")
            else False
            for result in search_results[:1]  # Verificar apenas o primeiro
        )

        max_results = 4 if is_metadata_query else 2  # Otimizado para velocidade (<4s)
        for i, result in enumerate(search_results[:max_results], 1):
            # 🔧 FIX CRÍTICO: Extrair content corretamente do formato ChromaDB
            # ChromaDB retorna dict com keys: ['chunk_id', 'content', 'similarity_score', 'metadata']
            if isinstance(result, dict):
                # É resultado direto do ChromaDB
                search_result = result
                content = result.get("content", "")
                result.get("similarity_score", 0.0)
                metadata = result.get("metadata", {})
            elif hasattr(result, "original_result"):
                # É ContextualizedResult
                search_result = result.original_result
                content = getattr(result.context_window, "full_context_text", getattr(search_result, "content", ""))
                getattr(result, "relevance_score", 0.0)
                metadata = getattr(search_result, "metadata", {})
            else:
                # É SearchResult object
                search_result = result
                content = getattr(result, "content", "")
                getattr(result, "similarity_score", 0.0)
                metadata = getattr(result, "metadata", {})

            # 🔧 FIX CRÍTICO: Verificar se content está vazio e extrair de outras fontes se necessário
            if not content or content.strip() == "":
                # Tentar extrair content de outras fontes possíveis
                if hasattr(search_result, "main_content"):
                    content = getattr(search_result, "main_content", "")
                elif hasattr(search_result, "text"):
                    content = getattr(search_result, "text", "")
                elif hasattr(search_result, "transcript"):
                    content = getattr(search_result, "transcript", "")

                logger.warning(f"⚠️ Contexto vazio detectado para resultado {i} - tentando fontes alternativas")

            # Se ainda está vazio, logar e pular este resultado
            if not content or content.strip() == "":
                logger.error(f"❌ Contexto {i} completamente vazio - pulando resultado")
                continue

            # Verificar se é resultado de vídeo com metadados especiais
            if metadata.get("is_video_result"):
                # Formatação otimizada para vídeos
                client = metadata.get("client", "N/A")
                context_text = f"{i}. [{client}] {content}"
            else:
                # 🔧 FIX: Extrair video_name corretamente dos metadados
                video_name = metadata.get("video_name", "Video_Sem_Nome")

                # 🔧 FIX: Evitar "Unknown" - usar nome mais descritivo
                if video_name in ["Unknown", "", None]:
                    # Tentar extrair nome do cliente dos metadados
                    client_name = metadata.get("client_name", metadata.get("client", ""))
                    if client_name:
                        video_name = f"KT_{client_name}"
                    else:
                        video_name = f"Resultado_{i}"

                video_name = video_name[:30]  # Limitar tamanho
                context_text = f"{i}. {video_name}: {content}"

            # Garantir que context_text não está vazio
            if context_text.strip() and len(context_text.split(":")) > 1 and context_text.split(":")[1].strip():
                formatted_contexts.append(context_text)
            else:
                logger.warning(f"⚠️ Context_text inválido para resultado {i}: '{context_text[:50]}...'")
                # Adicionar um contexto mínimo válido
                formatted_contexts.append(f"{i}. Contexto_Relevante: {content[:200]}...")

        return "\n".join(formatted_contexts)

    def _detect_query_type(self, query: str, results: list[Any]) -> str:
        """
        Detecta o tipo de consulta para usar prompt especializado

        Args:
            query: Pergunta original
            results: Resultados da busca

        Returns:
            Tipo detectado: 'decision', 'problem', 'metadata_listing', 'participants', 'general'
        """
        query_lower = query.lower()

        # 🆕 Detectar consultas de principais pontos/highlights
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

        # Detectar consultas de metadados/listagem - EXPANDIDO SEM HARDCODING
        metadata_keywords = [
            # Palavras interrogativas
            "quais",
            "que",
            "o que",
            # Verbos de listagem/exibição
            "liste",
            "listar",
            "enumere",
            "enumerar",
            "mostre",
            "mostrar",
            "exiba",
            "exibir",
            "apresente",
            "apresentar",
            # Substantivos relacionados
            "listagem",
            "lista",
            "relação",
            "catálogo",
            "inventário",
            "índice",
            # Objetos específicos (genéricos)
            "vídeos",
            "videos",
            "kts",
            "reuniões",
            "reunioes",
            "meetings",
            "clientes",
            "projetos",
            "arquivos",
            # Expressões sobre disponibilidade
            "temos",
            "disponíveis",
            "disponivel",
            "existem",
            "possuímos",
            "temos acesso",
            "base",
            "conhecimento",
            # Palavras de informação
            "informações",
            "informacoes",
            "dados",
            "conteúdo",
            "conteudo",
            "material",
            "nomes",
        ]
        if any(keyword in query_lower for keyword in metadata_keywords):
            # 🚀 SOLUÇÃO GENÉRICA MULTICAMADA: Template detection robusto e escalável

            # CAMADA 1: Manter padrões existentes (100% compatibilidade)
            legacy_patterns = [
                "liste" in query_lower
                and ("vídeos" in query_lower or "kts" in query_lower or "reuniões" in query_lower),
                "mostre" in query_lower and ("vídeos" in query_lower or "kts" in query_lower),
                "quais" in query_lower
                and ("kts" in query_lower or "reuniões" in query_lower or "vídeos" in query_lower),
                "temos" in query_lower and "disponíveis" in query_lower,
                "base" in query_lower and "conhecimento" in query_lower,
            ]

            # CAMADA 2: Pattern matching inteligente com regex flexível
            import re

            flexible_patterns = [
                # Padrões para clientes
                r"\b(quais?|que)\s+.*\b(nomes?|clientes?)\b.*\b(temos|kt|informações?)",
                r"\bnomes?\s+.*\bclientes?\b.*\b(kt|informações?)\b",
                r"\btemos\s+.*\bclientes?\b.*\b(base|conhecimento)\b",
                r"\bclientes?\s+.*\b(disponíveis?|temos|base|conhecimento)\b",
                # Padrões para listagens gerais
                r"\bliste?\s+.*\b(clientes?|kts?|documentos?|vídeos?)\b",
                r"\b(quais?|que)\s+.*\b(kts?|documentos?|vídeos?)\s+.*\btemos\b",
                # Padrões para base de conhecimento
                r"\b.*\bbase\s+.*\bconhecimento\b.*\bclientes?\b",
                r"\btemos\s+.*\binformações?\b.*\bclientes?\b",
            ]

            # CAMADA 3: Análise por pontuação de palavras-chave
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

            # VALIDAÇÃO: Aplicar detecção multicamada com threshold mais rigoroso
            is_listing_query = (
                any(legacy_patterns)  # Camada 1: Compatibilidade
                or any(re.search(pattern, query_lower) for pattern in flexible_patterns)  # Camada 2: Regex
                or listing_score >= 8  # Camada 3: Score threshold mais rigoroso (8.0 vs 5.0 anterior)
            )

            # 🚨 PROBLEMA 3 FIX: Detectar análise específica vs listagem genérica
            is_specific_kt_analysis = self._detect_specific_kt_analysis(query_lower)

            if is_listing_query and not is_specific_kt_analysis:
                # 🚨 P1-1 FIX: Validar cliente inexistente antes do fast-track
                if "cliente" in query_lower:
                    client_mentioned = self._extract_client_from_query(query_lower)
                    if client_mentioned and not self._client_exists_in_base(client_mentioned):
                        logger.info(f"🚫 Cliente inexistente detectado: {client_mentioned}")
                        logger.info("   🎯 Template alterado: metadata_listing → client_not_found")
                        return "client_not_found"

                logger.info(
                    f"🎯 TEMPLATE DETECTION: Query clara de metadata listing detectada: '{query_lower[:50]}...'"
                )
                regex_match = any(re.search(pattern, query_lower) for pattern in flexible_patterns)
                logger.info(
                    f"   📊 Score: {listing_score}, Legacy: {any(legacy_patterns)}, Regex: {regex_match}"
                )
                return "metadata_listing"
            elif is_specific_kt_analysis:
                logger.info("🔍 SPECIFIC KT ANALYSIS: Detectada análise específica - usando LLM em vez de fast-track")
                logger.info(f"   📋 Query: '{query_lower[:50]}...' requer análise LLM")
                return "general"  # Use LLM analysis instead of fast-track

            # Verificar se resultados são do tipo metadata (suporta ContextualizedResult)
            if results:
                for result in results:
                    # Verificar se é ContextualizedResult ou SearchResult direto
                    search_result = getattr(result, "original_result", result)
                    content_type = getattr(search_result, "content_type", "")
                    category = getattr(search_result, "category", "")

                    if content_type == "metadata" or category == "metadados":
                        return "metadata_listing"

                # 🔧 FALLBACK INTELIGENTE: Se não há metadata explícita mas query pede listagem de vídeos/KTs
                # e encontramos resultados, assumir que é metadata listing
                if len(results) >= 5:  # Threshold razoável para listagem
                    video_related = any(
                        term in query_lower for term in ["vídeos", "videos", "kts", "reuniões", "meetings"]
                    )
                    if video_related:
                        logger.info(
                            f"🔧 FALLBACK TEMPLATE: {len(results)} resultados"
                            " + query relacionada a vídeos → metadata_listing"
                        )
                        return "metadata_listing"

        # Detectar consultas sobre participantes
        participant_keywords = ["quem participou", "participantes", "quem estava", "pessoas que"]
        if any(keyword in query_lower for keyword in participant_keywords):
            return "participants"

        # Detectar consultas sobre decisões
        decision_keywords = ["decisão", "decidido", "aprovado", "definido", "acordo", "resolução"]
        if any(keyword in query_lower for keyword in decision_keywords):
            return "decision"

        # Detectar consultas sobre problemas
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

    def _detect_specific_kt_analysis(self, query_lower: str) -> bool:
        """
        Detecta se query busca análise específica de um KT vs listagem genérica

        ANÁLISE ESPECÍFICA (não deve usar fast-track):
        - "Resuma os principais pontos discutidos no KT iflow PC Factory"
        - "Qual os temas relevantes discutidos no KT - Estorno em massa"
        - "O que foi abordado no KT sustentação"

        LISTAGEM GENÉRICA (pode usar fast-track):
        - "Liste todos os KTs que temos"
        - "Quantos KTs temos na base"
        - "Quais KTs estão disponíveis"
        """

        # Padrões que indicam análise específica (não listagem)
        specific_analysis_patterns = [
            # Análise de conteúdo
            "temas.*discutidos",
            "pontos.*discutidos",
            "principais.*pontos",
            "o que foi.*abordado",
            "que foi.*explicado",
            "resuma.*pontos",
            "resumo.*do kt",
            "conteúdo.*do kt",
            "assuntos.*tratados",
            # Referência a KT específico
            "no kt",
            "kt.*específico",
            "neste kt",
            "deste kt",
            # Análise vs listagem
            "resuma",
            "resumir",
            "analise",
            "analisar",
            "explique",
            "explicar",
        ]

        # Padrões que indicam listagem genérica (mantém fast-track)
        generic_listing_patterns = [
            "liste.*kts",
            "quantos.*kts",
            "quais.*kts.*temos",
            "kts.*disponíveis",
            "kts.*que.*temos",
            "todos.*os.*kts",
        ]

        import re

        # Verificar se é listagem genérica primeiro
        for pattern in generic_listing_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return False  # É listagem genérica, pode usar fast-track

        # Verificar se é análise específica
        for pattern in specific_analysis_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return True  # É análise específica, usar LLM

        # Se menciona KT específico com indicadores de análise
        if "kt" in query_lower and any(
            word in query_lower for word in ["iflow", "estorno", "sustentação", "correção", "pc"]
        ):
            return True  # KT específico mencionado

        return False  # Default: não é análise específica

    def _detect_listing_query_refined(self, query_lower: str) -> bool:
        """
        Versão refinada da detecção de listagem com threshold mais rigoroso
        """

        # Padrões explícitos de listagem (score alto)
        explicit_listing_patterns = [
            r"^liste\s+.*",  # Começa com "liste"
            r"quais.*kts.*temos",
            r"quantos.*kts.*temos",
            r"todos.*os.*kts",
            r"kts.*disponíveis",
        ]

        import re

        for pattern in explicit_listing_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return True

        return False

    def _build_specialized_prompt(
        self, query_type: str, original_query: str, contexts: str, context_analysis: dict[str, Any] = None
    ) -> str:
        """
        Constrói prompt especializado baseado no tipo de consulta e análise contextual

        Args:
            query_type: Tipo de consulta detectado
            original_query: Pergunta original
            contexts: Contextos formatados
            context_analysis: Análise contextual dos resultados

        Returns:
            Prompt especializado para extração de insights
        """
        template = self.prompt_templates.get(query_type, self.prompt_templates["general"])

        # Adicionar orientação contextual se disponível
        contextual_guidance = ""
        if context_analysis and context_analysis.get("dominant_context"):
            dominant = context_analysis["dominant_context"]
            if dominant.get("client"):
                contextual_guidance = (
                    f"\n\nCONTEXTO DOMINANTE: A maioria dos resultados refere-se ao cliente {dominant['client']}."
                )

            if context_analysis.get("primary_theme"):
                theme = context_analysis["primary_theme"]
                if "reunião" in theme:
                    contextual_guidance += (
                        "\nFOCO: Identifique especificamente sobre qual cliente/reunião a pergunta se refere."
                    )
                elif "listagem" in theme:
                    contextual_guidance += "\nFOCO: Liste todos os clientes mencionados nos contextos."

        return template.format(query=original_query, contexts=contexts) + contextual_guidance

    def _calculate_confidence(self, results: list[Any], insight: str) -> float:
        """
        Calcula confiança do insight baseado na qualidade dos resultados

        Args:
            results: Resultados da busca
            insight: Insight gerado

        Returns:
            Score de confiança (0.0 a 1.0)
        """
        if not results or not insight:
            return 0.0

        # Fatores de confiança (ajustado para GPT-4o-mini)
        base_confidence = 0.6  # Base mais alta devido à qualidade superior do modelo

        # +0.1 para cada resultado com alta relevância
        high_relevance_bonus = sum(0.1 for r in results if getattr(r, "relevance_score", 0) > 0.8)

        # +0.1 se múltiplas fontes (vídeos diferentes)
        unique_videos = len({getattr(r, "video_name", "") for r in results})
        diversity_bonus = 0.1 if unique_videos > 1 else 0.05

        # +0.1 se insight tem bom tamanho (não muito curto nem muito longo)
        length_bonus = 0.1 if 50 <= len(insight) <= 800 else 0.0

        # +0.1 se há insights específicos mencionados
        specificity_bonus = (
            0.1
            if any(
                word in insight.lower()
                for word in ["decidido", "aprovado", "problema", "solução", "insight", "descoberto", "identificado"]
            )
            else 0.0
        )

        final_confidence = min(
            1.0, base_confidence + high_relevance_bonus + diversity_bonus + length_bonus + specificity_bonus
        )

        return final_confidence

    def _generate_fallback_insight(self, query: str, results: list[Any]) -> DirectInsightResult:
        """
        Gera insight estruturado quando OpenAI não está disponível

        Args:
            query: Pergunta original
            results: Resultados da busca

        Returns:
            DirectInsightResult com insight estruturado
        """
        logger.info("Gerando insight fallback estruturado")

        if not results:
            return DirectInsightResult(
                insight="Não foram encontrados contextos relevantes para gerar insights sobre sua consulta.",
                confidence=0.0,
                sources_used=0,
                processing_time=0.0,
                fallback_used=True,
            )

        # Para poucos resultados, ser mais cauteloso na confiança
        if len(results) == 1:
            confidence_modifier = 0.3  # Baixa confiança com apenas 1 resultado
        else:
            confidence_modifier = 0.5  # Confiança moderada com poucos resultados

        # Construir insight estruturado baseado nos resultados
        insight_parts = []
        insight_parts.append(f"**Insights baseados em {len(results)} resultado(s) relevante(s):**")

        # Resumir os pontos principais
        for i, result in enumerate(results[:3], 1):
            # Lidar com ContextualizedResult ou SearchResult
            if hasattr(result, "original_result"):
                # É ContextualizedResult
                search_result = result.original_result
                content_preview = getattr(
                    result.context_window, "full_context_text", getattr(search_result, "content", "")
                )[:150]
                speaker = getattr(search_result, "speaker", f"Participante_{i}")
                timestamp = getattr(search_result, "timestamp_formatted", getattr(search_result, "timestamp", "00:00"))
            else:
                # É SearchResult direto
                search_result = result  # Define search_result também para o branch else
                content_preview = getattr(result, "main_content", getattr(result, "content", ""))[:150]
                speaker = getattr(result, "speaker", f"Participante_{i}")
                timestamp = getattr(result, "timestamp_formatted", getattr(result, "timestamp", "00:00"))

            # 🔧 FIX: Verificar se content_preview está vazio
            if not content_preview or content_preview.strip() == "":
                # Tentar extrair de outras fontes
                if hasattr(search_result, "text"):
                    content_preview = getattr(search_result, "text", "")[:150]
                elif hasattr(search_result, "main_content"):
                    content_preview = getattr(search_result, "main_content", "")[:150]

                # Se ainda vazio, usar placeholder descritivo
                if not content_preview or content_preview.strip() == "":
                    content_preview = (
                        "[Conteúdo relevante encontrado - informações disponíveis sobre o tópico consultado]"
                    )

            if len(content_preview) == 150:
                content_preview += "..."

            # 🔧 FIX: Evitar "Unknown" no speaker
            if speaker in ["Unknown", "", None]:
                speaker = f"Participante_{i}"

            insight_parts.append(f"\n**Insight {i}**: {speaker} ({timestamp}) - {content_preview}")

        if len(results) > 3:
            insight_parts.append(f"\n... e mais {len(results) - 3} insight(s) adicional(is) disponível(is).")

        # Adicionar conclusão baseada no tipo
        query_lower = query.lower()
        if "decisão" in query_lower or "decidido" in query_lower:
            insight_parts.append(
                "\n\n**Conclusão**: Os insights indicam decisões específicas tomadas nas reuniões analisadas."
            )
        elif "problema" in query_lower:
            insight_parts.append(
                "\n\n**Conclusão**: Os insights revelam problemas identificados e possíveis soluções discutidas."
            )
        else:
            insight_parts.append(
                "\n\n**Conclusão**: Os insights extraídos fornecem percepções valiosas sobre os tópicos consultados."
            )

        fallback_insight = "".join(insight_parts)

        return DirectInsightResult(
            insight=fallback_insight,
            confidence=confidence_modifier,  # Confiança baseada no número de resultados
            sources_used=len(results),
            processing_time=0.1,
            fallback_used=True,
        )

    def _get_base_prompt_template(self) -> str:
        """Template base otimizado para extração de insights"""
        return """
PERGUNTA ESPECÍFICA: "{query}"
CONTEXTOS RELEVANTES: {contexts}

INSTRUÇÃO: Responda DIRETAMENTE à pergunta usando apenas os contextos fornecidos.
Seja específico, factual e foque na pergunta exata.

🚨 IMPORTANTE - DISTINÇÃO CLIENTE vs VÍDEO:
- CLIENTE = Empresa responsável (DEXCO, VÍSSIMO, ARCO, PC_FACTORY)
- VÍDEO = Título da reunião (ex: "KT Sustentação", "KT IMS")
- Sempre identifique o CLIENTE (empresa), não confunda com título do vídeo

FORMATO DE RESPOSTA:
1. **Resposta Direta:** [Resposta específica à pergunta]
2. **Contexto Adicional:** [Informações relevantes que complementam a resposta]
3. **Insights Estratégicos:** [Percepções acionáveis baseadas nos dados]

RESPOSTA:
"""

    def _get_decision_prompt_template(self) -> str:
        """Template especializado para insights sobre decisões"""
        return """
PERGUNTA SOBRE DECISÕES: "{query}"

CONTEXTOS DAS REUNIÕES:
{contexts}

INSTRUÇÕES ESPECÍFICAS PARA INSIGHTS DE DECISÕES:
1. Identifique claramente QUAIS decisões foram tomadas e por quê
2. Extraia insights sobre QUEM tomou as decisões e seu contexto
3. Analise QUANDO foram tomadas (timestamps) e as circunstâncias
4. Se houver valores ou prazos, extraia insights sobre seu impacto
5. Se houver status de implementação, analise as implicações

FORMATO DA RESPOSTA (INSIGHTS):
**Insight sobre Decisão(ões):** [análise profunda das decisões identificadas]
**Insight sobre Responsáveis:** [percepções sobre quem decidiu e contexto]
**Insights sobre Impacto:** [valores, prazos, condições e suas implicações]
**Insight sobre Status:** [análise do andamento se mencionado]

RESPOSTA (INSIGHTS):
"""

    def _get_problem_prompt_template(self) -> str:
        """Template especializado para insights sobre problemas"""
        return """
PERGUNTA SOBRE PROBLEMAS: "{query}"

CONTEXTOS DAS REUNIÕES:
{contexts}

INSTRUÇÕES ESPECÍFICAS PARA INSIGHTS DE PROBLEMAS:
1. Identifique claramente QUAL é o problema e sua natureza
2. Extraia insights sobre a CAUSA raiz se foi discutida
3. Analise QUEM relatou o problema e o contexto organizacional
4. Se houver solução proposta, extraia insights sobre sua viabilidade
5. Se houver status de resolução, analise as implicações

FORMATO DA RESPOSTA (INSIGHTS):
**Insight sobre o Problema:** [análise profunda da natureza do problema]
**Insight sobre Causas:** [percepções sobre causas raiz se identificadas]
**Insight sobre Contexto:** [análise de quem reportou e circunstâncias]
**Insight sobre Soluções:** [análise das propostas de solução se discutidas]
**Insight sobre Resolução:** [percepções sobre status e próximos passos]

RESPOSTA (INSIGHTS):
"""

    def _get_general_prompt_template(self) -> str:
        """Template para insights gerais - BALANCEADO"""
        return """
PERGUNTA: "{query}"

INFORMAÇÕES ENCONTRADAS:
{contexts}

INSTRUÇÕES:
Responda DIRETAMENTE à pergunta fornecida usando as informações dos contextos.

🚨 P1-3 FIX: IMPORTANTE - DISTINÇÃO CLIENTE vs VÍDEO:
- CLIENTE = Empresa responsável (DEXCO, VÍSSIMO, ARCO, PC_FACTORY)
- VÍDEO = Título da reunião (ex: "KT Sustentação", "KT IMS", "KICKOFF AMS")
- Sempre identifique o CLIENTE (empresa), não confunda com título do vídeo
- Exemplo correto: "Cliente DEXCO, vídeo 'KT Sustentação'"
- Exemplo incorreto: "Cliente KT Sustentação"

DIRETRIZES:
1. Primeira prioridade: Responder especificamente o que foi perguntado
2. Se a pergunta for "sobre X", foque nas informações específicas sobre X
3. Se a pergunta for "qual/quem/quando", forneça a resposta precisa
4. Use os contextos para fundamentar sua resposta
5. Seja claro e direto, mas completo
6. Sempre distinguir entre empresa (cliente) e título do vídeo/reunião

FORMATO:
**Resposta à Pergunta:** [Resposta direta e específica baseada nos contextos]

**Detalhes Relevantes:** [Informações adicionais importantes que complementam a resposta]

RESPOSTA:
"""

    def _get_metadata_listing_template(self) -> str:
        """Template especializado para consultas de listagem de metadados"""
        return """
PERGUNTA: "{query}"
ENTIDADES ENCONTRADAS NA BASE DE CONHECIMENTO:
{contexts}

INSTRUÇÕES PARA LISTAGEM DE VÍDEOS:
1. Se a pergunta for sobre VÍDEOS, use o formato especial com links
2. Para VÍDEOS: Liste o nome do vídeo + link TL:DV se disponível
3. Para outras entidades: Use formato simples com bullets (•)
4. Extraia links TL:DV dos metadados se disponíveis
5. Seja DIRETO e OBJETIVO
6. Ordene por cliente primeiro, depois por tipo

FORMATO PARA VÍDEOS:
VÍDEOS DE KT REGISTRADOS NA BASE:
• **[CLIENTE] - [TIPO KT]**
  Link: [URL_TLDV se disponível]

FORMATO PARA OUTRAS ENTIDADES:
ENTIDADES REGISTRADAS:
• [NOME]: ([X] ocorrências)

RESPOSTA (LISTA FORMATADA):
"""

    def _get_participants_template(self) -> str:
        """Template especializado para consultas sobre participantes"""
        return """
PERGUNTA: "{query}"
CONTEXTOS COM INFORMAÇÕES DE PARTICIPANTES:
{contexts}

INSTRUÇÕES PARA PARTICIPANTES:
1. Liste OBJETIVAMENTE os participantes encontrados nos contextos
2. Para cada participante, indique:
   - Nome (real se mencionado, ou identificador como "Participante X")
   - Papel/função se mencionado
   - Contexto onde foi identificado
3. Foque em NOMES e PAPÉIS, não em conteúdo técnico
4. Se houver menções a equipas, inclua também
5. Resposta máxima: 150 palavras, foco em IDENTIFICAR PESSOAS

FORMATO DE RESPOSTA:
PARTICIPANTES IDENTIFICADOS:
• [Nome/ID]: [Papel se conhecido]

PESSOAS MENCIONADAS:
• [Nome]: [Contexto onde foi mencionado]

RESPOSTA (PARTICIPANTES):
"""

    def _get_project_listing_template(self) -> str:
        """Template especializado para consultas sobre projetos mencionados"""
        return """
PERGUNTA: "{query}"
CONTEXTOS COM INFORMAÇÕES DE PROJETOS:
{contexts}

INSTRUÇÕES PARA LISTAGEM DE PROJETOS:
1. Identifique TODOS os projetos mencionados nos contextos
2. Para cada projeto encontrado:
   - Nome do projeto (exato como mencionado)
   - Cliente associado se identificado
   - Breve descrição baseada no contexto
   - Status/situação se mencionado
3. Foque em PROJETOS ESPECÍFICOS, não em conceitos gerais
4. Se mencionarem "projeto X", "implementação Y", etc., inclua
5. Ordene por relevância/frequência de menção
6. Resposta máxima: 200 palavras, seja OBJETIVO

FORMATO DE RESPOSTA:
PROJETOS IDENTIFICADOS NAS TRANSCRIÇÕES:
• **[Nome do Projeto]** ([Cliente]): [Breve descrição]
• **[Outro Projeto]**: [Descrição e status]

RESPOSTA (LISTA DE PROJETOS):
"""

    def _format_insight_text(self, raw_insight: str) -> str:
        """
        Formata o texto de insight para melhor legibilidade

        Args:
            raw_insight: Texto bruto retornado pelo OpenAI

        Returns:
            Texto formatado com quebras de linha e numeração melhorada
        """
        if not raw_insight:
            return raw_insight

        # 1. Quebrar números seguidos de ponto em parágrafos separados
        formatted_text = raw_insight

        # Padrão: número seguido de ponto no início de frase
        import re

        formatted_text = re.sub(r"(\d+)\.\s+", r"\n\n**\1.** ", formatted_text)

        # 2. Quebrar frases muito longas em parágrafos
        # Quebrar após ponto seguido de espaço e letra maiúscula, mas manter numeração
        formatted_text = re.sub(r"(\. )([A-Z][^.]{80,})", r"\1\n\n\2", formatted_text)

        # 3. Melhorar formatação de tópicos com "**" para destacar (apenas se já não estão formatados)
        formatted_text = re.sub(r"(?<!\*\*)([A-Z][a-zA-Z\s]{10,}:)(?!\*\*)", r"**\1**", formatted_text)

        # 4. Remover quebras de linha excessivas no início
        formatted_text = formatted_text.lstrip("\n")

        # 5. Garantir que não há mais de 2 quebras de linha consecutivas
        formatted_text = re.sub(r"\n{3,}", "\n\n", formatted_text)

        return formatted_text

    def _get_performance_config(self, query_type: str, num_results: int) -> dict[str, Any]:
        """
        Configuração adaptativa de performance baseada no tipo de query e contexto

        Estratégia:
        - METADATA/ENTITY: Respostas concisas possíveis → configuração rápida
        - SEMANTIC: Contexto rico necessário → configuração balanceada
        - HIGHLIGHTS: Estrutura complexa → configuração completa
        """

        # Configurações base por tipo de query
        if query_type in ["metadata_listing", "project_listing"]:
            return {
                "strategy": "fast_listing",
                "max_tokens": 400,  # Listas podem ser concisas
                "temperature": 0.0,  # Máxima precisão
                "top_p": 0.8,  # Foco mais direto
                "timeout": 8.0,  # Timeout mais agressivo
            }

        elif query_type in ["participants", "general"] and num_results <= 5:
            return {
                "strategy": "quick_response",
                "max_tokens": 600,  # Respostas diretas
                "temperature": 0.0,
                "top_p": 0.85,
                "timeout": 10.0,
            }

        elif query_type == "highlights_summary":
            return {
                "strategy": "quick_analysis",
                "max_tokens": 800,  # Estrutura mais concisa para velocidade
                "temperature": 0.0,  # Máxima precisão sem criatividade
                "top_p": 0.85,  # Foco mais direto
                "timeout": 10.0,  # Timeout reduzido para performance
            }

        else:  # SEMANTIC e casos complexos
            return {
                "strategy": "balanced_insight",
                "max_tokens": 800,  # Contexto suficiente
                "temperature": 0.0,
                "top_p": 0.9,
                "timeout": 12.0,
            }

    def _get_highlights_summary_template(self) -> str:
        """Template especializado para resumo de principais pontos/highlights - BALANCEADO"""
        return """PERGUNTA: {query}

CONTEXTOS DAS REUNIÕES:
{contexts}

INSTRUÇÕES:
Extraia e organize os principais pontos da reunião de forma estruturada e objetiva.

ESTRATÉGIA:
1. Identifique decisões importantes tomadas
2. Liste ações definidas com responsáveis (se mencionado)
3. Destaque problemas identificados
4. Inclua informações técnicas relevantes
5. Organize por ordem de importância

FORMATO ESTRUTURADO:
**PRINCIPAIS PONTOS DA REUNIÃO:**

**🎯 DECISÕES TOMADAS:**
• [Decisão importante 1]
• [Decisão importante 2]

**📋 AÇÕES DEFINIDAS:**
• [Ação 1 - Responsável se mencionado]
• [Ação 2 - Responsável se mencionado]

**⚠️ PROBLEMAS IDENTIFICADOS:**
• [Problema 1 e contexto]
• [Problema 2 e contexto]

**🔧 ASPECTOS TÉCNICOS:**
• [Informação técnica relevante 1]
• [Informação técnica relevante 2]

DIRETRIZES:
- Se não houver informações para uma seção, omita-a
- Mantenha cada ponto claro e específico
- Priorize informações acionáveis

RESPOSTA:"""

    def _detect_cross_client_warning(self, search_results: list[Any]) -> dict | None:
        """
        Detecta se algum resultado contém warning de discrepância cliente vs entidade técnica
        """
        for result in search_results:
            # Verificar se é dict e tem cross_client_warning
            if isinstance(result, dict) and "cross_client_warning" in result:
                return result["cross_client_warning"]

            # Verificar se é objeto com atributo cross_client_warning
            elif hasattr(result, "cross_client_warning"):
                return getattr(result, "cross_client_warning", None)

        return None

    def _generate_cross_client_response(self, query: str, results: list[Any], warning: dict) -> DirectInsightResult:
        """
        Gera resposta inteligente para discrepâncias cliente vs entidade técnica

        Implementa os Smart Response Templates do handoff
        """
        entity = warning.get("entity", "ENTIDADE")
        requested_client = warning.get("requested_client", "CLIENTE_SOLICITADO")
        found_client = warning.get("found_client", "CLIENTE_ENCONTRADO")

        # Template para entidade encontrada em cliente diferente
        response_template = f"""⚠️ **{entity} encontrada em {found_client}, mas você perguntou sobre {requested_client}**

**🔍 SITUAÇÃO IDENTIFICADA:**
A entidade técnica **{entity}** foi encontrada na base de conhecimento,
porém nos vídeos de KT do cliente **{found_client}**, não do **{requested_client}** que você mencionou.

**📋 INFORMAÇÕES DISPONÍVEIS SOBRE {entity}:**
"""

        # Extrair informações sobre a entidade dos resultados
        entity_info = []
        for result in results:
            content = ""
            if isinstance(result, dict):
                content = result.get("text", result.get("content", ""))
            elif hasattr(result, "content"):
                content = getattr(result, "content", "")

            if entity.upper() in content.upper():
                # Extrair trecho relevante (primeiro parágrafo que menciona a entidade)
                paragraphs = content.split("\n")
                for para in paragraphs:
                    if entity.upper() in para.upper():
                        entity_info.append(para.strip())
                        break

        # Adicionar informações encontradas
        if entity_info:
            for i, info in enumerate(entity_info[:3], 1):  # Máximo 3 informações
                response_template += f"\n{i}. {info}"
        else:
            response_template += f"\nDetalhes técnicos sobre {entity} identificados nos vídeos de {found_client}."

        # Adicionar orientação clara
        response_template += f"""

**💡 RECOMENDAÇÃO:**
- As informações sobre **{entity}** estão disponíveis nos KTs do **{found_client}**
- Se você precisa de **{entity}** especificamente para **{requested_client}**, pode não estar documentado ainda
- Considere verificar se **{entity}** se aplica também ao contexto **{requested_client}**

**🔗 FONTE:** Vídeos de Knowledge Transfer do cliente {found_client}"""

        return DirectInsightResult(
            insight=response_template,
            confidence=0.85,  # Alta confiança - sabemos exatamente o que aconteceu
            sources_used=len(results),
            processing_time=0.1,  # Rápida - template direto
            fallback_used=False,
        )

    def _generate_fast_metadata_response(
        self, query: str, search_results: list[Any], start_time: float
    ) -> DirectInsightResult:
        """🚀 FASE 3: Geração rápida de resposta para queries de listagem de KTs únicos"""

        # Extrair informações de KTs únicos dos metadados
        unique_kts = {}  # {video_name: {client_name, original_url, meeting_date}}
        client_filter = None

        # Detectar filtro de cliente na query primeiro
        query_upper = query.upper()
        known_clients = ["DEXCO", "ARCO", "VISSIMO", "VÍSSIMO"]
        for client in known_clients:
            if client in query_upper:
                client_filter = client.replace("VÍSSIMO", "VISSIMO")  # Normalizar
                break

        for result in search_results:
            # Acessar metadata do resultado ChromaDB
            metadata = result.get("metadata", {}) if isinstance(result, dict) else {}

            # Extrair informações essenciais
            video_name = metadata.get("video_name", "")
            client_name = metadata.get("client_name", "")
            original_url = metadata.get("original_url", "")
            meeting_date = metadata.get("meeting_date", "")

            if video_name and video_name not in unique_kts:
                unique_kts[video_name] = {
                    "client_name": client_name,
                    "original_url": original_url,
                    "meeting_date": meeting_date,
                }

        # Gerar resposta formatada com KTs únicos
        if not unique_kts:
            client_suffix = f"para o cliente {client_filter}" if client_filter else ""
            response_text = f"Não foram encontrados KTs {client_suffix} na base de conhecimento."
            confidence = 0.60
        else:
            # Organizar KTs por cliente
            kts_by_client: dict[str, list[dict[str, str]]] = {}
            for video_name, info in unique_kts.items():
                client = info["client_name"]
                if client not in kts_by_client:
                    kts_by_client[client] = []
                kts_by_client[client].append(
                    {"video_name": video_name, "url": info["original_url"], "date": info["meeting_date"]}
                )

            # Debug: Log client filter vs available clients
            logger.debug(f"CLIENT FILTER: '{client_filter}' | AVAILABLE CLIENTS: {list(kts_by_client.keys())}")
            logger.debug(f"CLIENT MATCH: {client_filter in kts_by_client if client_filter else 'No filter'}")

            # Construir resposta formatada
            if client_filter and client_filter in kts_by_client:
                # Resposta específica para um cliente
                client_kts = kts_by_client[client_filter]
                response_text = f"**KTs DO CLIENTE {client_filter}:**\n\n"

                for _i, kt in enumerate(client_kts, 1):
                    kt_title = kt["video_name"]
                    # Limpar título para exibição
                    if kt_title.startswith("[") and "] " in kt_title:
                        kt_title = kt_title.split("] ", 1)[1]
                    if "Gravação de Reunião" in kt_title:
                        kt_title = kt_title.replace("-Gravação de Reunião", "").strip()
                        if kt_title.endswith("_150"):
                            kt_title = kt_title.rsplit("_", 1)[0]

                    response_text += f"• **{kt_title}**\n"
                    if kt["url"]:
                        response_text += f"  Link: {kt['url']}\n"
                    if kt["date"]:
                        response_text += f"  Data: {kt['date']}\n"
                    response_text += "\n"

                confidence = 0.90
            else:
                # Resposta geral para todos os clientes
                response_text = "**KTs REGISTRADOS NA BASE DE CONHECIMENTO:**\n\n"

                for client, client_kts in kts_by_client.items():
                    response_text += f"**{client}:**\n"
                    for kt in client_kts:
                        kt_title = kt["video_name"]
                        # Limpar título para exibição
                        if kt_title.startswith("[") and "] " in kt_title:
                            kt_title = kt_title.split("] ", 1)[1]
                        if "Gravação de Reunião" in kt_title:
                            kt_title = kt_title.replace("-Gravação de Reunião", "").strip()
                            if kt_title.endswith("_150"):
                                kt_title = kt_title.rsplit("_", 1)[0]

                        response_text += f"  • {kt_title}\n"
                        if kt["url"]:
                            response_text += f"    Link: {kt['url']}\n"
                    response_text += "\n"

                confidence = 0.85

            # Adicionar resumo estatístico
            total_kts = len(unique_kts)
            total_clients = len(kts_by_client)
            kts_s = "s" if total_kts != 1 else ""
            clients_s = "s" if total_clients != 1 else ""
            disp_s = "is" if total_kts != 1 else ""
            response_text += (
                f"**Resumo:** {total_kts} KT{kts_s} de {total_clients} cliente{clients_s} disponível{disp_s}."
            )

        analysis_time = time.time() - start_time
        logger.info(f"⚡ Resposta FAST-TRACK gerada em {analysis_time:.3f}s - {len(unique_kts)} KTs únicos")

        return DirectInsightResult(
            insight=response_text,
            confidence=confidence,
            sources_used=len(unique_kts),
            processing_time=analysis_time,
            fallback_used=False,
        )

    def _extract_client_from_query(self, query_lower: str) -> str:
        """Extrai nome do cliente mencionado na query"""
        import re

        # Padrões para extrair cliente após palavras-chave
        client_patterns = [
            r"cliente\s+([A-Za-z][A-Za-z0-9_]*)",  # "cliente XPTO"
            r"sobre\s+o\s+cliente\s+([A-Za-z][A-Za-z0-9_]*)",  # "sobre o cliente XPTO"
            r"informações\s+.*cliente\s+([A-Za-z][A-Za-z0-9_]*)",  # "informações do cliente XPTO"
        ]

        for pattern in client_patterns:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                return match.group(1).upper()

        return ""

    def _client_exists_in_base(self, client_name: str) -> bool:
        """Verifica se cliente existe na base de conhecimento consultando diretamente a base"""
        try:
            # Importar DynamicClientManager
            from .dynamic_client_manager import DynamicClientManager

            # Inicializar o client manager se não existir
            if not hasattr(self, "_client_manager"):
                self._client_manager = DynamicClientManager()

            # Descobrir clientes disponíveis na base
            available_clients = self._client_manager.discover_clients()

            # Normalizar nome do cliente
            client_normalized = client_name.upper().strip()

            # Verificar se está na lista de clientes descobertos
            for client_info in available_clients.values():
                # Verificar nome principal
                if client_info.name.upper() == client_normalized:
                    return True

                # Verificar variações registradas
                for variation in client_info.variations:
                    if variation.upper() == client_normalized:
                        return True

            logger.info(
                f"🔍 Cliente '{client_name}' não encontrado na base."
                f" Disponíveis: {list(available_clients.keys())}"
            )
            return False

        except Exception as e:
            logger.warning(f"Erro ao verificar existência do cliente {client_name}: {e}")
            return True  # Em caso de erro, assumir que existe para não bloquear

    def _generate_client_not_found_response(self, original_query: str, start_time: float) -> DirectInsightResult:
        """Gera resposta específica para cliente inexistente"""
        import time

        # Extrair nome do cliente da query
        client_mentioned = self._extract_client_from_query(original_query.lower())

        # Descobrir clientes disponíveis
        try:
            if not hasattr(self, "_client_manager"):
                from .dynamic_client_manager import DynamicClientManager

                self._client_manager = DynamicClientManager()

            available_clients = self._client_manager.discover_clients()
            client_names = list(available_clients.keys())

            response_text = f"**Cliente '{client_mentioned}' não encontrado na base de conhecimento.**\n\n"
            response_text += "**Clientes disponíveis:**\n"
            for client in sorted(client_names):
                response_text += f"• {client}\n"

            response_text += (
                "\n**Sugestão:** Verifique a grafia do nome do cliente ou escolha um dos clientes listados acima."
            )

        except Exception as e:
            logger.warning(f"Erro ao listar clientes disponíveis: {e}")
            response_text = f"**Cliente '{client_mentioned}' não foi encontrado na base de conhecimento.**\n\n"
            response_text += "**Sugestão:** Verifique a grafia do nome do cliente e tente novamente."

        analysis_time = time.time() - start_time
        logger.info(f"🚫 Resposta cliente inexistente gerada em {analysis_time:.3f}s para cliente: {client_mentioned}")

        return DirectInsightResult(
            insight=response_text,
            confidence=0.95,  # Alta confiança que cliente não existe
            sources_used=0,
            processing_time=analysis_time,
            fallback_used=False,
        )
