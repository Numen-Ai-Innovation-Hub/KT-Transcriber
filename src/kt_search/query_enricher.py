"""Query Enricher — Enriquecimento universal de queries.

Implementa enriquecimento de queries para classificação contextual.
Detecta entidades, normaliza termos e expande semanticamente.

Pipeline: Query Natural → **QueryEnricher** → QueryClassifier
"""

import re
import time
from dataclasses import dataclass
from typing import Any

from utils.logger_setup import LoggerManager

from .kt_search_constants import ENTITY_PATTERNS, SEARCH_CONFIG

logger = LoggerManager.get_logger(__name__)


@dataclass
class EnrichmentResult:
    """Resultado do processo de enriquecimento de query."""

    original_query: str
    cleaned_query: str
    enriched_query: str
    entities: dict[str, Any]
    context: dict[str, Any]
    confidence: float
    processing_time: float


class QueryEnricher:
    """Enriquecedor universal de queries para busca semântica KT.

    Funções:
    - Detecção de entidades (clientes, transações, módulos, participantes, temporal)
    - Normalização e expansão de termos
    - Construção de contexto semântico
    - Validação e limpeza de queries

    Fornece máximo contexto para classificação precisa pelo QueryClassifier.
    """

    def __init__(self) -> None:
        """Inicializa QueryEnricher com padrões e regras."""
        self.entity_patterns = ENTITY_PATTERNS
        self.semantic_expansions = self._load_semantic_expansions()
        self.client_variations = self._load_client_variations()
        self.normalization_rules = self._load_normalization_rules()

        self._video_names_cache: list[str] = []
        self._video_names_cache_time: float = 0.0
        self._video_names_cache_ttl: float = 300.0

        logger.info("QueryEnricher inicializado com padrões de entidade e expansões semânticas")

    def enrich_query_universal(self, query: str) -> EnrichmentResult:
        """Enriquecimento universal — detecta entidades, normaliza e expande semanticamente.

        Args:
            query: Query em linguagem natural.

        Returns:
            EnrichmentResult com todos os dados de enriquecimento para classificação.
        """
        start_time = time.time()

        try:
            if query is None:
                raise ValueError("Query não pode ser None")

            if not isinstance(query, str):
                query = str(query)

            logger.info(f"Enriquecendo query: '{query[:100]}{'...' if len(query) > 100 else ''}'")

            cleaned_query = self._clean_query(query)
            if not self._validate_query(cleaned_query):
                raise ValueError(f"Query inválida após limpeza: {cleaned_query}")

            entities = self._detect_entities(cleaned_query)
            context = self._build_context(cleaned_query, entities)
            enriched_query = self._generate_enriched_query(cleaned_query, entities, context)
            confidence = self._calculate_enrichment_confidence(entities, context)

            processing_time = time.time() - start_time

            result = EnrichmentResult(
                original_query=str(query),
                cleaned_query=cleaned_query,
                enriched_query=enriched_query,
                entities=entities,
                context=context,
                confidence=confidence,
                processing_time=processing_time,
            )

            logger.info(
                f"Query enriquecida em {processing_time:.3f}s — entidades: {len(entities)}, confiança: {confidence:.2f}"
            )

            return result

        except Exception as e:
            logger.error(f"Enriquecimento de query falhou: {e}")
            fallback_query = str(query) if query is not None else ""
            return EnrichmentResult(
                original_query=fallback_query,
                cleaned_query=fallback_query.strip() if fallback_query else "",
                enriched_query=fallback_query.strip() if fallback_query else "",
                entities={},
                context={"enrichment_error": str(e)},
                confidence=0.1,
                processing_time=time.time() - start_time,
            )

    def _clean_query(self, query: str) -> str:
        """Limpa e normaliza o texto da query."""
        if not query:
            return ""

        cleaned = re.sub(r"\s+", " ", query.strip())
        cleaned = re.sub(r'["""]', '"', cleaned)
        cleaned = re.sub(r"[^\w\s\-\.\?\!\"\/\(\)\[\]]", "", cleaned)

        if len(cleaned) > SEARCH_CONFIG["max_query_length"]:
            cleaned = cleaned[: SEARCH_CONFIG["max_query_length"]].strip()
            logger.warning(f"Query truncada para {SEARCH_CONFIG['max_query_length']} caracteres")

        return cleaned

    def _validate_query(self, query: str) -> bool:
        """Valida se query atende requisitos mínimos."""
        if not query:
            return False

        if len(query) < SEARCH_CONFIG["min_query_length"]:
            return False

        meaningful_chars = re.sub(r"[^\w]", "", query)
        if len(meaningful_chars) < 3:
            return False

        return True

    def _detect_entities(self, query: str) -> dict[str, Any]:
        """Detecta todos os tipos de entidades na query."""
        entities: dict[str, Any] = {}
        query_lower = query.lower()
        query_upper = query.upper()

        for entity_type, config in self.entity_patterns.items():
            detected = []

            if entity_type == "clients":
                detected = self._detect_clients(query)

            elif entity_type == "transactions":
                for pattern in config["patterns"]:
                    matches = re.findall(pattern, query_upper)
                    detected.extend(matches)

                additional_patterns = [
                    r"\b([A-Z]{1,2}\d{2,3}[A-Z]?)\b",
                    r"\b(ZEWM\d{4})\b",
                    r"\b(F110|VA01|VF01|ME21N|MM01|FB01|VL01N)\b",
                ]
                for pattern in additional_patterns:
                    matches = re.findall(pattern, query_upper)
                    detected.extend(matches)

            elif entity_type == "sap_modules":
                for pattern in config["patterns"]:
                    matches = re.findall(pattern, query_upper)
                    detected.extend(matches)

            elif entity_type == "participants":
                for pattern in config["patterns"]:
                    matches = re.findall(pattern, query)
                    filtered_matches = []
                    for match in matches:
                        if "clients" in entities and any(
                            match.lower() in client.lower() for client in entities["clients"]["values"]
                        ):
                            continue
                        if match.lower() in ["que", "para", "como", "onde", "qual", "factory"]:
                            continue
                        if self._is_part_of_client_name(match, query):
                            continue
                        filtered_matches.append(match)
                    detected.extend(filtered_matches)

            elif entity_type == "temporal":
                detected = self._detect_temporal_expressions(query_lower)

            if detected:
                entities[entity_type] = {
                    "values": list(set(detected)),
                    "target_column": config.get("target_column", entity_type),
                    "normalized": self._normalize_entities(detected, config.get("normalization", {})),
                }

        has_sap_transaction = "transactions" in entities and entities["transactions"]["values"]
        is_technical_query = self._is_technical_content_query(query)

        if not (has_sap_transaction or is_technical_query):
            video_references = self._detect_video_references(query)
            if video_references:
                entities["video_references"] = {
                    "values": video_references,
                    "target_column": "video_name",
                    "phrases": self._extract_phrases_from_text(query),
                }
        else:
            logger.debug(f"SAP TRANSACTION OVERRIDE: ignorando filtro de vídeo para query técnica: {query[:50]}...")

        return entities

    def _detect_clients(self, query: str) -> list[str]:
        """Detecta nomes de clientes usando padrões e normalização da config."""
        detected_clients = []

        config = self.entity_patterns["clients"]
        patterns = config["patterns"]
        normalization = config.get("normalization", {})

        for pattern in patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                normalized_client = normalization.get(match.lower(), match.upper())
                if normalized_client not in detected_clients:
                    detected_clients.append(normalized_client)

        return detected_clients

    def _detect_temporal_expressions(self, query_lower: str) -> list[str]:
        """Detecta expressões temporais e converte para formato estruturado."""
        temporal_expressions = []

        pattern_recent = r"últimos?\s+(\d+)\s+(dias?|semanas?|meses?)"
        matches = re.findall(pattern_recent, query_lower)
        for match in matches:
            number, period = match
            temporal_expressions.append(f"recent_{number}_{period}")

        pattern_specific = (
            r"(janeiro|fevereiro|março|abril|maio|junho|julho|agosto"
            r"|setembro|outubro|novembro|dezembro)\s+(de\s+)?(\d{4})"
        )
        matches = re.findall(pattern_specific, query_lower)
        for match in matches:
            month, _, year = match
            temporal_expressions.append(f"specific_{month}_{year}")

        pattern_relative = r"(recentes?|ontem|hoje|semana|mês)"
        matches = re.findall(pattern_relative, query_lower)
        temporal_expressions.extend(matches)

        return temporal_expressions

    def _build_context(self, query: str, entities: dict[str, Any]) -> dict[str, Any]:
        """Constrói informações contextuais para classificação."""
        context: dict[str, Any] = {
            "query_length": len(query),
            "has_entities": len(entities) > 0,
            "entity_types": list(entities.keys()),
            "query_complexity": self._assess_query_complexity(query, entities),
        }

        if "clients" in entities:
            context["has_specific_client"] = True
            context["detected_client"] = entities["clients"]["values"][0] if entities["clients"]["values"] else None
        else:
            context["has_specific_client"] = False
            context["detected_client"] = None

        if "transactions" in entities:
            context["has_technical_terms"] = True
            context["technical_complexity"] = "high"
        else:
            context["has_technical_terms"] = False
            context["technical_complexity"] = "low"

        if "temporal" in entities:
            context["has_temporal"] = True
            context["temporal_scope"] = self._assess_temporal_scope(entities["temporal"]["values"])
        else:
            context["has_temporal"] = False
            context["temporal_scope"] = None

        context["is_listing_request"] = self._detect_listing_intent(query)
        context["is_comparison_request"] = self._detect_comparison_intent(query)
        context["is_broad_request"] = self._detect_broad_intent(query)

        return context

    def _generate_enriched_query(self, query: str, entities: dict[str, Any], context: dict[str, Any]) -> str:
        """Gera query semanticamente enriquecida para embedding."""
        parts = [self._apply_semantic_expansion(query)]

        if "clients" in entities:
            client_variations = self._get_client_variations(entities["clients"]["values"])
            parts.extend(client_variations)

        if "transactions" in entities:
            parts.extend(entities["transactions"]["values"])

        if "sap_modules" in entities:
            parts.extend(entities["sap_modules"]["values"])

        domain_terms = self._get_domain_terms(context)
        if domain_terms:
            parts.extend(domain_terms)

        if context.get("is_listing_request"):
            parts.append("listagem informações")
        elif context.get("is_comparison_request"):
            parts.append("comparação análise")

        return " ".join(parts)

    def _apply_semantic_expansion(self, query: str) -> str:
        """Aplica expansão semântica aos termos da query."""
        expanded_terms = []
        words = query.lower().split()

        for word in words:
            expanded_terms.append(word)
            if word in self.semantic_expansions:
                expanded_terms.extend(self.semantic_expansions[word][:2])

        return " ".join(expanded_terms)

    def _get_client_variations(self, clients: list[str]) -> list[str]:
        """Retorna todas as variações para os clientes detectados."""
        all_variations = []

        for client in clients:
            if client.upper() in self.client_variations:
                all_variations.extend(self.client_variations[client.upper()])
            else:
                all_variations.append(client)

        return all_variations

    def _generate_client_variations(self, client: str) -> list[str]:
        """Gera todas as variações para um nome de cliente específico."""
        client_upper = client.upper()

        if client_upper in self.client_variations:
            return self.client_variations[client_upper]

        base_variations = [client.upper(), client.lower(), client.capitalize(), client.title()]
        return list(set(base_variations))

    def _get_domain_terms(self, context: dict[str, Any]) -> list[str]:
        """Retorna termos de domínio relevantes baseados no contexto."""
        domain_terms = ["KT", "reunião", "consultoria"]

        if context.get("has_technical_terms"):
            domain_terms.extend(["SAP", "transação", "módulo", "sistema"])

        if context.get("has_temporal"):
            domain_terms.extend(["período", "data", "histórico"])

        return domain_terms

    def _assess_query_complexity(self, query: str, entities: dict[str, Any]) -> str:
        """Avalia complexidade da query para processamento adaptativo."""
        complexity_score = 0

        if len(query) > 100:
            complexity_score += 2
        elif len(query) > 50:
            complexity_score += 1

        complexity_score += len(entities)

        word_count = len(query.split())
        if word_count > 10:
            complexity_score += 2
        elif word_count > 5:
            complexity_score += 1

        if complexity_score >= 6:
            return "complex"
        elif complexity_score >= 3:
            return "medium"
        else:
            return "simple"

    def _assess_temporal_scope(self, temporal_values: list[str]) -> str:
        """Avalia escopo temporal da query."""
        if any("recent" in val for val in temporal_values):
            return "recent"
        elif any("specific" in val for val in temporal_values):
            return "specific_date"
        else:
            return "general"

    def _is_part_of_client_name(self, word: str, query: str) -> bool:
        """Verifica se palavra faz parte de um nome de cliente na query."""
        client_patterns = [r"\bpc\s+factory\b", r"\bpc\s*factory\b", r"\bpc_factory\b", r"\bgran\s+cru\b"]

        for pattern in client_patterns:
            if re.search(pattern, query.lower()) and word.lower() in pattern.lower():
                return True

        return False

    def _detect_listing_intent(self, query: str) -> bool:
        """Detecta se query solicita listagem/enumeração."""
        listing_indicators = ["liste", "quais", "quantos", "temos", "disponíveis", "mostre", "exiba", "apresente"]
        query_lower = query.lower()
        return any(indicator in query_lower for indicator in listing_indicators)

    def _detect_comparison_intent(self, query: str) -> bool:
        """Detecta se query solicita comparação."""
        comparison_indicators = [
            "diferença",
            "comparar",
            "compare",
            "versus",
            "vs",
            "entre",
            "melhor",
            "pior",
            "maior",
            "menor",
            "contra",
            " e ",
        ]
        query_lower = query.lower()

        if any(indicator in query_lower for indicator in comparison_indicators):
            return True

        if " e " in query_lower:
            words = query_lower.split()
            client_count = 0
            for word in words:
                if word in ["víssimo", "vissimo", "arco", "dexco", "gran"]:
                    client_count += 1
            if client_count >= 2:
                return True

        return False

    def _detect_broad_intent(self, query: str) -> bool:
        """Detecta se query é ampla e necessita resultados abrangentes."""
        broad_indicators = [
            "tudo",
            "todas",
            "todos",
            "geral",
            "gerais",
            "completo",
            "abrangente",
            "overview",
            "visão geral",
            "dados gerais",
            "amplo",
            "total",
            "global",
        ]
        query_lower = query.lower()
        return any(indicator in query_lower for indicator in broad_indicators)

    def _normalize_for_client_matching(self, text: str) -> str:
        """Normaliza texto para matching de clientes."""
        import unicodedata

        normalized = unicodedata.normalize("NFD", text.lower())
        normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
        return normalized

    def _normalize_entities(self, entities: list[str], normalization_rules: dict[str, str]) -> list[str]:
        """Aplica regras de normalização às entidades detectadas."""
        normalized = []

        for entity in entities:
            if entity.lower() in normalization_rules:
                normalized.append(normalization_rules[entity.lower()])
            else:
                normalized.append(entity.upper())

        return normalized

    def _calculate_enrichment_confidence(self, entities: dict[str, Any], context: dict[str, Any]) -> float:
        """Calcula score de confiança para o processo de enriquecimento."""
        confidence = 0.5

        query_complexity = context.get("query_complexity", "simple")
        if query_complexity == "simple" and len(entities) == 0:
            confidence = 0.3

        confidence += len(entities) * 0.1

        if "clients" in entities:
            confidence += 0.2
        if "transactions" in entities:
            confidence += 0.15
        if "temporal" in entities:
            confidence += 0.1

        if context.get("query_complexity") == "complex":
            confidence += 0.1
        elif context.get("query_complexity") == "medium":
            confidence += 0.05

        if context.get("has_specific_client"):
            confidence += 0.1

        if context.get("query_length", 0) < 10 and len(entities) == 0:
            confidence -= 0.2

        return max(0.1, min(1.0, confidence))

    def _load_semantic_expansions(self) -> dict[str, list[str]]:
        """Carrega regras de expansão semântica."""
        return {
            "principais": ["importantes", "relevantes", "críticos", "decisivos"],
            "informação": ["dados", "detalhes", "conteúdo", "pontos"],
            "informações": ["dados", "detalhes", "conteúdo", "pontos"],
            "integrações": ["integração", "RFC", "EDI", "API", "interface"],
            "integração": ["integrações", "RFC", "EDI", "API", "interface"],
            "problemas": ["erro", "falha", "issue", "bug", "dificuldade"],
            "problema": ["erro", "falha", "issue", "bug", "dificuldade"],
            "processo": ["procedimento", "fluxo", "workflow", "etapa"],
            "transação": ["código", "tcode", "transaction"],
            "módulo": ["component", "área", "funcionalidade"],
            "sistema": ["SAP", "ERP", "aplicação"],
            "reunião": ["meeting", "encontro", "sessão"],
            "participantes": ["pessoas", "attendees", "presentes"],
            "decisão": ["resolução", "definição", "acordo"],
            "recente": ["último", "atual", "novo"],
            "antigo": ["anterior", "passado", "histórico"],
            "dados": ["informação", "detalhes", "conteúdo"],
            "gerais": ["amplo", "abrangente", "geral", "completo"],
            "todos": ["completo", "total", "abrangente"],
            "tudo": ["completo", "total", "abrangente"],
        }

    def _load_client_variations(self) -> dict[str, list[str]]:
        """Carrega variações de nomes de clientes para matching."""
        return {
            "VÍSSIMO": ["VÍSSIMO", "VISSIMO", "Víssimo", "víssimo", "vissimo", "Vissimo"],
            "ARCO": ["ARCO", "Arco", "arco"],
            "DEXCO": ["DEXCO", "Dexco", "dexco"],
            "GRAN CRU": ["GRAN CRU", "Gran Cru", "gran cru", "GranCru", "grancru"],
        }

    def _load_normalization_rules(self) -> dict[str, str]:
        """Carrega regras de normalização de texto."""
        return {
            "víssimo": "VÍSSIMO",
            "vissimo": "VÍSSIMO",
            "arco": "ARCO",
            "dexco": "DEXCO",
            "gran cru": "GRAN CRU",
            "sd": "SD",
            "mm": "MM",
            "fi": "FI",
            "co": "CO",
            "ewm": "EWM",
            "btp": "BTP",
        }

    def _detect_video_references(self, query: str) -> list[str]:
        """Detecta referências a vídeos por fuzzy matching contra nomes disponíveis no ChromaDB.

        Returns:
            Lista de nomes de vídeos que fazem match, ou lista vazia se nenhum encontrado.
            Retorna lista vazia em caso de erro (ChromaDB indisponível na inicialização).
        """
        try:
            available_videos = self._get_available_video_names()
            if not available_videos:
                return []

            matches = self._find_video_matches_dynamic(query, available_videos)
            high_confidence_matches = []

            if matches:
                top_match_name, top_score = matches[0]

                if len(matches) == 1:
                    if top_score >= 0.8:
                        high_confidence_matches = [top_match_name]
                else:
                    second_score = matches[1][1]
                    gap_ratio = top_score / second_score if second_score > 0 else float("inf")

                    if gap_ratio >= 5.0 and top_score >= 2.0:
                        high_confidence_matches = [top_match_name]
                        logger.debug(f"Vencedor dominante detectado: {top_match_name} (gap ratio: {gap_ratio:.1f})")
                    elif gap_ratio >= 3.0 and top_score >= 1.5:
                        high_confidence_matches = [top_match_name]
                        logger.debug(f"Vencedor claro detectado: {top_match_name} (gap ratio: {gap_ratio:.1f})")
                    elif gap_ratio >= 2.0 and top_score >= 1.0:
                        high_confidence_matches = [top_match_name]
                        logger.debug(f"Vencedor moderado detectado: {top_match_name} (gap ratio: {gap_ratio:.1f})")
                    elif top_score >= 0.8:
                        close_matches = [match for match in matches if match[1] >= top_score * 0.7]
                        high_confidence_matches = [match[0] for match in close_matches[:3]]
                        logger.debug(f"Campo competitivo: {len(high_confidence_matches)} vídeos selecionados")
                    elif top_score >= 0.5:
                        high_confidence_matches = [top_match_name]
                        logger.debug(f"Match fraco fallback: {top_match_name}")

                if len(matches) > 1:
                    logger.debug(
                        f"Gap analysis: top={top_score:.2f}, segundo={second_score:.2f}, ratio={gap_ratio:.1f}"
                    )
                else:
                    logger.debug(f"Match único: score={top_score:.2f}")

            if high_confidence_matches:
                logger.debug(f"Referências de vídeo detectadas: {high_confidence_matches}")

            return high_confidence_matches

        except Exception as e:
            logger.warning(f"Erro ao detectar referências de vídeo: {e}")
            return []

    def _get_available_video_names(self) -> list[str]:
        """Obtém todos os nomes de vídeos disponíveis no ChromaDB dinamicamente.

        Returns:
            Lista de nomes de vídeos, ou lista vazia se ChromaDB indisponível.
            O caller trata lista vazia e continua sem filtro de vídeo.
        """
        now = time.time()
        if self._video_names_cache and (now - self._video_names_cache_time) < self._video_names_cache_ttl:
            return self._video_names_cache

        try:
            from src.kt_indexing.chromadb_store import ChromaDBStore

            store = ChromaDBStore()
            results = store.collection.get(include=["metadatas"])

            video_names = set()
            for metadata in results["metadatas"]:
                if metadata and "video_name" in metadata:
                    video_names.add(metadata["video_name"])

            video_names_list = list(video_names)
            self._video_names_cache = video_names_list
            self._video_names_cache_time = now
            return video_names_list

        except Exception as e:
            logger.warning(f"Não foi possível obter nomes de vídeo do ChromaDB: {e}")
            return []

    def _find_video_matches_dynamic(self, query: str, video_names: list[str]) -> list[tuple[str, float]]:
        """Encontra matches de vídeo por fuzzy matching puro.

        Returns:
            Lista de (nome_vídeo, score) ordenada por score decrescente.
        """
        from difflib import SequenceMatcher

        query_lower = query.lower()
        query_words = set(re.findall(r"\b\w+\b", query_lower))

        matches = []

        for video_name in video_names:
            score = 0.0
            video_lower = video_name.lower()

            video_words = set(re.findall(r"\b\w+\b", video_lower))
            word_overlap = len(query_words & video_words)
            if word_overlap > 0:
                score += word_overlap * 0.4

            for word in query_words:
                if len(word) > 3 and word in video_lower:
                    word_specificity = min(len(word) / 10.0, 1.0)
                    score += 0.5 + word_specificity

            if len(query_lower) > 5:
                similarity = SequenceMatcher(None, query_lower, video_lower).ratio()
                if similarity > 0.2:
                    score += similarity * 2.0

            video_phrases = self._extract_phrases_from_text(video_name)
            query_phrases = self._extract_phrases_from_text(query)

            phrase_overlap = len(set(video_phrases) & set(query_phrases))
            if phrase_overlap > 0:
                phrase_score = phrase_overlap * 0.8
                if phrase_overlap >= 2:
                    phrase_score *= 1.8
                score += phrase_score

            if score > 0.3:
                matches.append((video_name, score))

        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

    def _extract_phrases_from_text(self, text: str) -> list[str]:
        """Extrai frases significativas de qualquer texto (query ou nome de vídeo)."""
        phrases = []

        clean_text = re.sub(r"\[([^\]]+)\]", "", text).strip()
        clean_text = re.sub(r"-\d{8}_\d{6}-.*", "", clean_text).strip()

        separators = ["-", "–", ":", "|", "(", ")", "[", "]"]
        parts = [clean_text]

        for sep in separators:
            new_parts = []
            for part in parts:
                new_parts.extend(part.split(sep))
            parts = new_parts

        for part in parts:
            part = part.strip()
            if len(part) > 3:
                noise_words = {"gravação", "reunião", "meeting", "de", "da", "do", "para", "com", "em", "no", "na"}
                words = part.lower().split()
                clean_words = [w for w in words if w not in noise_words and len(w) > 2]
                if clean_words:
                    phrases.append(" ".join(clean_words))

        all_words = re.findall(r"\b\w+\b", clean_text.lower())
        for word in all_words:
            if len(word) > 3:
                phrases.append(word)

        return list(set(phrases))

    def _is_technical_content_query(self, query: str) -> bool:
        """Detecta se query busca conteúdo técnico específico (transações, processos, etc.)."""
        query_lower = query.lower()

        technical_patterns = [
            r"transaç[aã]o\s+\w+",
            r"processo\s+\w+",
            r"funcionalidade\s+\w+",
            r"tcode\s+\w+",
            r"[a-z]+\d{3,}",
            r"config\w*\s+\w+",
            r"parametr\w+\s+\w+",
        ]

        for pattern in technical_patterns:
            if re.search(pattern, query_lower):
                return True

        technical_keywords = [
            "transação",
            "tcode",
            "configuração",
            "parametro",
            "funcionalidade",
            "customização",
            "enhancement",
            "desenvolvimento",
            "implementação",
            "processo técnico",
        ]

        for keyword in technical_keywords:
            if keyword in query_lower:
                return True

        return False


def enrich_query(query: str) -> EnrichmentResult:
    """Função de conveniência para enriquecimento de query."""
    enricher = QueryEnricher()
    return enricher.enrich_query_universal(query)


def extract_entities(query: str) -> dict[str, Any]:
    """Extrai entidades da query sem enriquecimento completo."""
    enricher = QueryEnricher()
    return enricher._detect_entities(enricher._clean_query(query))
