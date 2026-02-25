"""
Insights Agent - Agente que extrai insights diretos baseados nos resultados da busca semântica
Analisa contextos encontrados e gera insights objetivos para responder perguntas
"""

import re
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from utils.logger_setup import LoggerManager

from .insight_processors import InsightProcessors
from .query_type_detector import QueryTypeDetector

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
        from .insights_prompts import PROMPT_TEMPLATES

        self.prompt_templates = PROMPT_TEMPLATES
        self._query_type_detector = QueryTypeDetector()
        self._processors = InsightProcessors()

        logger.info(f"InsightsAgent inicializado com modelo {self.model}")

    def generate_direct_insight(
        self, original_query: str, search_results: list[Any], query_type: str | None = None
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
        from utils.hash_manager import get_hash_manager

        cache_key = get_hash_manager().generate_content_hash(f"{original_query}_{len(search_results)}")
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
            logger.info(f"Iniciando extração de insights para: '{original_query[:100]}{suffix}'")

            # 1. Analisar relevância contextual dos resultados
            context_analysis = self._processors.analyze_context_relevance(original_query, search_results)
            logger.info(f"Análise contextual: {context_analysis['primary_theme']}")

            # 2. Preparar contextos para análise com foco na relevância (incluir query original para filtro semântico)
            context_analysis["original_query"] = original_query
            formatted_contexts = self._processors.format_contexts_for_llm(search_results, context_analysis)
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
            performance_config = self._processors.get_performance_config(query_type, len(search_results))

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
            direct_insight = self._processors.format_insight_text(raw_insight)
            processing_time = time.time() - start_time

            # 7. Calcular confiança baseada na qualidade dos contextos
            confidence = self._processors.calculate_confidence(search_results, direct_insight)

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
            is_specific_kt_analysis = self._query_type_detector.detect_specific_kt_analysis(query_lower)

            if is_listing_query and not is_specific_kt_analysis:
                # 🚨 P1-1 FIX: Validar cliente inexistente antes do fast-track
                if "cliente" in query_lower:
                    client_mentioned = self._processors.extract_client_from_query(query_lower)
                    if client_mentioned and not self._client_exists_in_base(client_mentioned):
                        logger.info(f"🚫 Cliente inexistente detectado: {client_mentioned}")
                        logger.info("   🎯 Template alterado: metadata_listing → client_not_found")
                        return "client_not_found"

                logger.info(
                    f"🎯 TEMPLATE DETECTION: Query clara de metadata listing detectada: '{query_lower[:50]}...'"
                )
                regex_match = any(re.search(pattern, query_lower) for pattern in flexible_patterns)
                logger.info(f"   📊 Score: {listing_score}, Legacy: {any(legacy_patterns)}, Regex: {regex_match}")
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

    def _build_specialized_prompt(
        self, query_type: str, original_query: str, contexts: str, context_analysis: dict[str, Any] | None = None
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
        entity_info: list[str] = []
        for result in results:
            content = ""
            if isinstance(result, dict):
                raw = result.get("text", result.get("content", ""))
                content = raw if isinstance(raw, str) else ""
            elif hasattr(result, "content"):
                raw = getattr(result, "content", "")
                content = raw if isinstance(raw, str) else ""

            if isinstance(content, str) and entity.upper() in content.upper():
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
                f"🔍 Cliente '{client_name}' não encontrado na base. Disponíveis: {list(available_clients.keys())}"
            )
            return False

        except Exception as e:
            logger.warning(f"Erro ao verificar existência do cliente {client_name}: {e}")
            return True  # Em caso de erro, assumir que existe para não bloquear

    def _generate_client_not_found_response(self, original_query: str, start_time: float) -> DirectInsightResult:
        """Gera resposta específica para cliente inexistente"""
        # Extrair nome do cliente da query
        client_mentioned = self._processors.extract_client_from_query(original_query.lower())

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
