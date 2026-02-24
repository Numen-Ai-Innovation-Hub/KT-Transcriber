"""
Dynamic Client Manager - Descoberta automática de clientes ChromaDB
=====================================================================

Gerencia descoberta dinâmica de clientes disponíveis no ChromaDB sem hardcoding,
implementando cache inteligente e variações de nomes para matching fuzzy.

Características:
- Descoberta em tempo real via ChromaDB queries
- Cache TTL configurável
- Fuzzy matching automático para variações de nomes
- Integração com search_engine para filtros dinâmicos
"""

import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.kt_indexing.chromadb_store import ChromaDBStore
from utils.logger_setup import LoggerManager

from .kt_search_constants import DYNAMIC_CONFIG

logger = LoggerManager.get_logger(__name__)


@dataclass
class ClientInfo:
    """Informações sobre um cliente descoberto dinamicamente"""

    name: str
    normalized_name: str
    variations: list[str]
    chunk_count: int
    latest_meeting_date: str | None
    sap_modules: set[str]
    meeting_phases: set[str]
    first_discovered: datetime
    last_updated: datetime


class DynamicClientManager:
    """Gerenciador dinâmico de descoberta de clientes"""

    def __init__(self):
        self.chromadb_manager = ChromaDBStore()
        self.cache: dict[str, ClientInfo] = {}
        self.cache_timestamp = None
        self.cache_ttl = DYNAMIC_CONFIG["auto_discovery"]["cache_ttl"]
        self.min_chunks_threshold = DYNAMIC_CONFIG["auto_discovery"]["min_chunks_per_client"]

        # Padrões para normalização de nomes
        self.normalization_patterns = {
            # Remover acentos
            "À": "A",
            "Á": "A",
            "Â": "A",
            "Ã": "A",
            "Ä": "A",
            "È": "E",
            "É": "E",
            "Ê": "E",
            "Ë": "E",
            "Ì": "I",
            "Í": "I",
            "Î": "I",
            "Ï": "I",
            "Ò": "O",
            "Ó": "O",
            "Ô": "O",
            "Õ": "O",
            "Ö": "O",
            "Ù": "U",
            "Ú": "U",
            "Û": "U",
            "Ü": "U",
            "Ç": "C",
            "Ñ": "N",
            # Lowercase versions
            "à": "a",
            "á": "a",
            "â": "a",
            "ã": "a",
            "ä": "a",
            "è": "e",
            "é": "e",
            "ê": "e",
            "ë": "e",
            "ì": "i",
            "í": "i",
            "î": "i",
            "ï": "i",
            "ò": "o",
            "ó": "o",
            "ô": "o",
            "õ": "o",
            "ö": "o",
            "ù": "u",
            "ú": "u",
            "û": "u",
            "ü": "u",
            "ç": "c",
            "ñ": "n",
        }

    def discover_clients(self, force_refresh: bool = False) -> dict[str, ClientInfo]:
        """
        Descobre clientes disponíveis no ChromaDB

        Args:
            force_refresh: Forçar refresh do cache

        Returns:
            Dicionário de clientes descobertos {nome_normalizado: ClientInfo}
        """

        # Verificar se cache ainda é válido
        if not force_refresh and self._is_cache_valid():
            logger.debug(f"Retornando {len(self.cache)} clientes do cache")
            return self.cache

        logger.info("🔍 Descobrindo clientes disponíveis no ChromaDB...")
        start_time = time.time()

        try:
            # Query todos os chunks para extrair client_name únicos
            all_clients_data = self.chromadb_manager.get_distinct_clients()

            discovered_clients = {}
            current_time = datetime.now()

            for client_data in all_clients_data:
                client_name = client_data.get("client_name", "UNKNOWN")

                # Filtrar clientes inválidos
                if self._should_ignore_client(client_name):
                    continue

                # Extrair informações adicionais do cliente
                client_info = self._build_client_info(client_name, client_data, current_time)

                # Aplicar threshold mínimo de chunks
                if client_info.chunk_count < self.min_chunks_threshold:
                    logger.debug(f"Cliente '{client_name}' ignorado: apenas {client_info.chunk_count} chunks")
                    continue

                discovered_clients[client_info.normalized_name] = client_info
                logger.debug(f"Cliente descoberto: {client_name} → {client_info.chunk_count} chunks")

            # Atualizar cache
            self.cache = discovered_clients
            self.cache_timestamp = current_time

            discovery_time = time.time() - start_time
            logger.info(f"✅ {len(discovered_clients)} clientes descobertos em {discovery_time:.2f}s")

            # Log detalhado dos clientes encontrados
            for client_info in discovered_clients.values():
                logger.info(
                    f"   📋 {client_info.name}: {client_info.chunk_count} chunks, "
                    f"módulos: {list(client_info.sap_modules)[:3]}, "
                    f"última reunião: {client_info.latest_meeting_date}"
                )

            return discovered_clients

        except Exception as e:
            logger.error(f"❌ Erro descobrindo clientes: {e}")
            # Retornar cache existente em caso de erro
            return self.cache if self.cache else {}

    def find_client_matches(self, query_term: str, fuzzy: bool = True) -> list[tuple[str, float]]:
        """
        Encontra clientes que fazem match com termo da query

        Args:
            query_term: Termo a ser buscado
            fuzzy: Aplicar matching fuzzy

        Returns:
            Lista de (cliente_normalizado, confidence_score) ordenada por relevância
        """

        clients = self.discover_clients()
        matches = []

        query_normalized = self._normalize_text(query_term)
        query_lower = query_term.lower()

        for client_info in clients.values():
            # Testar match exato primeiro
            exact_score = self._calculate_exact_match_score(query_term, client_info)
            if exact_score > 0:
                matches.append((client_info.normalized_name, exact_score))
                continue

            # Fuzzy matching se habilitado
            if fuzzy:
                fuzzy_score = self._calculate_fuzzy_match_score(query_normalized, query_lower, client_info)
                if fuzzy_score > 0.3:  # Threshold mínimo para fuzzy match
                    matches.append((client_info.normalized_name, fuzzy_score))

        # Ordenar por score decrescente
        matches.sort(key=lambda x: x[1], reverse=True)

        if matches:
            logger.debug(f"Cliente matches para '{query_term}': {matches[:3]}")

        return matches

    def get_client_info(self, client_name: str) -> ClientInfo | None:
        """
        Retorna informações detalhadas de um cliente específico

        Args:
            client_name: Nome ou nome normalizado do cliente

        Returns:
            ClientInfo se encontrado, None caso contrário
        """

        clients = self.discover_clients()

        # Buscar por nome normalizado primeiro
        if client_name in clients:
            return clients[client_name]

        # Buscar por variações
        for client_info in clients.values():
            if client_name.upper() in [var.upper() for var in client_info.variations]:
                return client_info

        return None

    def get_client_variations(self, client_name: str) -> list[str]:
        """
        Gera todas as variações possíveis de um nome de cliente

        Args:
            client_name: Nome do cliente

        Returns:
            Lista de variações para fuzzy matching
        """

        if not client_name or client_name == "UNKNOWN":
            return []

        variations = set()

        # Nome original
        variations.add(client_name)

        # Versão normalizada (sem acentos)
        normalized = self._normalize_text(client_name)
        variations.add(normalized)

        # Variações de case
        variations.add(client_name.upper())
        variations.add(client_name.lower())
        variations.add(client_name.capitalize())
        variations.add(normalized.upper())
        variations.add(normalized.lower())
        variations.add(normalized.capitalize())

        # Remover caracteres especiais
        clean_version = re.sub(r"[^\w]", "", client_name)
        if clean_version:
            variations.add(clean_version)
            variations.add(clean_version.upper())
            variations.add(clean_version.lower())

        # Variações específicas conhecidas
        specific_variations = {
            "VÍSSIMO": ["VISSIMO", "Víssimo", "víssimo", "vissimo", "Vissimo"],
            "ARCO": ["Arco", "arco"],
            "DEXCO": ["Dexco", "dexco"],
            "KT_SUSTENTACAO": ["KT SUSTENTAÇÃO", "SUSTENTACAO", "SUSTENTAÇÃO"],
        }

        for standard_name, vars_list in specific_variations.items():
            if client_name.upper() == standard_name or any(v.upper() == client_name.upper() for v in vars_list):
                variations.update(vars_list)
                variations.add(standard_name)

        return sorted(variations)

    def invalidate_cache(self):
        """Invalida cache forçando próxima descoberta"""
        self.cache_timestamp = None
        logger.info("Cache de clientes invalidado")

    def get_cache_stats(self) -> dict:
        """Retorna estatísticas do cache para debugging"""
        return {
            "cache_size": len(self.cache),
            "cache_timestamp": self.cache_timestamp.isoformat() if self.cache_timestamp else None,
            "cache_valid": self._is_cache_valid(),
            "cache_ttl": self.cache_ttl,
            "clients_cached": list(self.cache.keys()) if self.cache else [],
        }

    # Métodos privados auxiliares

    def _is_cache_valid(self) -> bool:
        """Verifica se cache ainda é válido"""
        if not self.cache_timestamp:
            return False

        age_seconds = (datetime.now() - self.cache_timestamp).total_seconds()
        return age_seconds < self.cache_ttl

    def _should_ignore_client(self, client_name: str) -> bool:
        """Verifica se cliente deve ser ignorado"""
        if not client_name or not client_name.strip():
            return True

        ignore_patterns = ["UNKNOWN", "CLIENTE_DESCONHECIDO", "NULL", "NONE", "TEST", "TESTE", "DEBUG"]

        client_upper = client_name.upper()
        return any(pattern in client_upper for pattern in ignore_patterns)

    def _normalize_text(self, text: str) -> str:
        """Normaliza texto removendo acentos e caracteres especiais"""
        if not text:
            return ""

        # Aplicar mapeamento de caracteres
        normalized = text
        for old_char, new_char in self.normalization_patterns.items():
            normalized = normalized.replace(old_char, new_char)

        return normalized

    def _build_client_info(self, client_name: str, client_data: dict, current_time: datetime) -> ClientInfo:
        """Constrói objeto ClientInfo a partir dos dados do ChromaDB"""

        normalized_name = self._normalize_text(client_name).upper()
        variations = self.get_client_variations(client_name)

        # Extrair informações agregadas
        chunk_count = client_data.get("chunk_count", 0)
        latest_meeting = client_data.get("latest_meeting_date")
        sap_modules = set(client_data.get("sap_modules", []))
        meeting_phases = set(client_data.get("meeting_phases", []))

        return ClientInfo(
            name=client_name,
            normalized_name=normalized_name,
            variations=variations,
            chunk_count=chunk_count,
            latest_meeting_date=latest_meeting,
            sap_modules=sap_modules,
            meeting_phases=meeting_phases,
            first_discovered=current_time,
            last_updated=current_time,
        )

    def _calculate_exact_match_score(self, query_term: str, client_info: ClientInfo) -> float:
        """Calcula score para match exato"""

        query_upper = query_term.upper()

        # Match exato com nome principal
        if query_upper == client_info.name.upper():
            return 1.0

        # Match exato com nome normalizado
        if query_upper == client_info.normalized_name:
            return 0.95

        # Match exato com variações
        for variation in client_info.variations:
            if query_upper == variation.upper():
                return 0.9

        return 0.0

    def _calculate_fuzzy_match_score(self, query_normalized: str, query_lower: str, client_info: ClientInfo) -> float:
        """Calcula score para fuzzy matching"""

        max_score = 0.0

        # Testar substring matches
        for variation in client_info.variations:
            var_lower = variation.lower()
            var_normalized = self._normalize_text(variation).lower()

            # Substring match direto
            if query_lower in var_lower:
                score = len(query_lower) / len(var_lower) * 0.8
                max_score = max(max_score, score)

            # Substring match normalizado
            if query_normalized.lower() in var_normalized:
                score = len(query_normalized) / len(var_normalized) * 0.7
                max_score = max(max_score, score)

            # Match reverso (variação contida na query)
            if var_lower in query_lower:
                score = len(var_lower) / len(query_lower) * 0.6
                max_score = max(max_score, score)

        return max_score

    def enrich_with_client_discovery(self, raw_results: list[dict], entities: dict[str, Any]) -> list[dict]:
        """
        Enriquece resultados ChromaDB com descoberta dinâmica de clientes

        Args:
            raw_results: Resultados brutos do ChromaDB
            entities: Entidades detectadas na query

        Returns:
            Resultados enriquecidos com informações de clientes descobertos
        """

        if not raw_results:
            return raw_results

        logger.debug(f"Enriquecendo {len(raw_results)} resultados com descoberta de clientes")

        # Descobrir clientes disponíveis
        available_clients = self.discover_clients()

        # Enriquecer cada resultado
        enriched_results = []
        for result in raw_results:
            metadata = result.get("metadata", {})
            client_name = metadata.get("client_name", "UNKNOWN")

            # Verificar se cliente está na base descoberta
            if client_name != "UNKNOWN":
                client_info = self.get_client_info(client_name)
                if client_info:
                    # Adicionar informações do cliente descoberto
                    result["client_info"] = {
                        "chunk_count": client_info.chunk_count,
                        "sap_modules": list(client_info.sap_modules),
                        "meeting_phases": list(client_info.meeting_phases),
                        "latest_meeting_date": client_info.latest_meeting_date,
                        "variations": client_info.variations,
                    }

                    # Boost quality score se cliente for relevante para a query
                    if "clients" in entities:
                        query_clients = [c.upper() for c in entities["clients"]["values"]]
                        if any(var.upper() in query_clients for var in client_info.variations):
                            current_quality = result.get("quality_score", 0.5)
                            result["quality_score"] = min(1.0, current_quality + 0.1)
                            result["client_boost"] = True

            enriched_results.append(result)

        logger.debug(f"Resultados enriquecidos com dados de {len(available_clients)} clientes disponíveis")
        return enriched_results
