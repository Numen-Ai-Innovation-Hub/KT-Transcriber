"""ChromaDB Store — Transcrição de KT.

Unifica ChromaDBManager + EmbeddingGenerator do projeto legado em um único módulo.
Responsável por toda persistência vetorial: embeddings e operações na coleção ChromaDB.

Eliminado: cache pickle de embeddings (era anti-pattern — sem TTL, sem invalidação).
Eliminado: from chromadb.config import Settings (deprecated).
"""

import time
from datetime import datetime
from typing import Any, cast

import chromadb
import openai
from chromadb.api.types import Include, Metadatas, PyEmbeddings

from src.config.settings import DIRECTORY_PATHS, OPENAI_API_KEY
from src.kt_indexing.kt_indexing_constants import CHROMADB_CONFIG, OPENAI_CONFIG
from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# EMBEDDING GENERATOR
# ════════════════════════════════════════════════════════════════════════════


class EmbeddingGenerator:
    """Gera embeddings híbridos para chunks de transcrição KT.

    Estratégia híbrida (80/20):
    - 80% peso: conteúdo do CHUNK (texto principal da transcrição)
    - 20% peso: contexto de METADADOS (cliente, módulos, entidades, tags)
    """

    def __init__(self, config: dict | None = None):
        """Inicializa gerador com cliente OpenAI.

        Args:
            config: Configuração de embedding. Default: OPENAI_CONFIG.
        """
        self.config = config or OPENAI_CONFIG
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY)
        self._last_input_text = ""
        self._last_embedding: list[float] | None = None
        logger.info(f"EmbeddingGenerator inicializado com modelo: {self.config['model']}")

    def generate_chunk_embedding(self, chunk_text: str, metadata: dict) -> list[float]:
        """Gera embedding para chunk com abordagem híbrida conteúdo + contexto.

        Args:
            chunk_text: Texto principal da transcrição (seção CHUNK).
            metadata: Metadados com informações de contexto.

        Returns:
            Vetor de embedding (1536 dimensões).
        """
        try:
            embedding_input = self._build_hybrid_input(chunk_text, metadata)
            self._last_input_text = embedding_input
            embedding = self._generate_embedding(embedding_input)
            self._last_embedding = embedding
            return embedding
        except Exception as e:
            logger.error(f"Falha ao gerar embedding de chunk: {e}")
            return [0.0] * self.config["dimensions"]

    def _build_hybrid_input(self, chunk_text: str, metadata: dict) -> str:
        """Constrói input híbrido priorizando conteúdo do chunk (80%) com contexto (20%).

        Estrutura:
            CHUNK: {texto}

            CONTEXTO: {cliente} | {módulos} | {fase}
            ENTIDADES: {participantes} | {sistemas}
            TRANSAÇÕES: {transações}
            TAGS: {tags}

        Args:
            chunk_text: Texto principal do chunk.
            metadata: Metadados com contexto.

        Returns:
            String de input para geração de embedding.
        """
        main_content = f"CHUNK: {chunk_text.strip()}"

        context_parts = []
        client = metadata.get("client_name", "")
        modules = metadata.get("sap_modules_title", "")
        phase = metadata.get("meeting_phase", "")
        context_parts.append(f"CONTEXTO: {client} | {modules} | {phase}")

        participants = ", ".join(metadata.get("participants_mentioned", []))
        systems = ", ".join(metadata.get("systems", []))
        if participants or systems:
            context_parts.append(f"ENTIDADES: {participants} | {systems}")

        transactions = ", ".join(metadata.get("transactions", []))
        if transactions:
            context_parts.append(f"TRANSAÇÕES: {transactions}")

        tags = ", ".join(metadata.get("searchable_tags", []))
        if tags:
            context_parts.append(f"TAGS: {tags}")

        context_section = "\n".join(filter(None, context_parts))
        if context_section:
            return f"{main_content}\n\n{context_section}"
        return main_content

    def _generate_embedding(self, text: str) -> list[float]:
        """Gera embedding via OpenAI API com retry automático.

        Args:
            text: Texto para geração de embedding.

        Returns:
            Vetor de embedding.
        """
        max_retries = self.config["max_retries"]
        rate_limit_delay = self.config["rate_limit_delay"]

        for attempt in range(max_retries):
            try:
                # Truncar texto se muito longo (~4 chars por token)
                max_chars = self.config["max_tokens"] * 4
                if len(text) > max_chars:
                    text = text[:max_chars]
                    logger.debug("Texto truncado por exceder limite de tokens")

                if attempt > 0:
                    time.sleep(rate_limit_delay * attempt)

                response = self.client.embeddings.create(
                    model=self.config["model"],
                    input=text,
                    dimensions=self.config["dimensions"],
                )

                embedding = response.data[0].embedding

                if len(embedding) != self.config["dimensions"]:
                    raise ValueError(f"Dimensões inesperadas: {len(embedding)}")

                logger.debug(f"Embedding gerado com sucesso (tentativa {attempt + 1})")
                return embedding

            except openai.RateLimitError as e:
                logger.warning(f"Rate limit atingido (tentativa {attempt + 1}): {e}")
                time.sleep(rate_limit_delay * (attempt + 1) * 2)

            except openai.APIError as e:
                logger.error(f"Erro de API OpenAI (tentativa {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(rate_limit_delay)

            except Exception as e:
                logger.error(f"Erro inesperado ao gerar embedding (tentativa {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(rate_limit_delay)

        raise RuntimeError(f"Falha ao gerar embedding após {max_retries} tentativas")

    def generate_query_embedding(self, query: str) -> list[float]:
        """Gera embedding para queries de busca (sem prefixo CHUNK).

        Args:
            query: Texto da query de busca.

        Returns:
            Vetor de embedding.
        """
        try:
            return self._generate_embedding(query.strip())
        except Exception as e:
            logger.error(f"Falha ao gerar embedding de query: {e}")
            return [0.0] * self.config["dimensions"]

    def generate_batch_embeddings(self, chunks_data: list[dict]) -> list[dict]:
        """Gera embeddings para múltiplos chunks.

        Args:
            chunks_data: Lista de dicts com chaves 'text' e 'metadata'.

        Returns:
            Lista de dicts com 'embedding' adicionado.
        """
        results = []
        rate_limit_delay = self.config["rate_limit_delay"]

        for i, chunk_data in enumerate(chunks_data):
            try:
                embedding = self.generate_chunk_embedding(
                    chunk_text=chunk_data["text"],
                    metadata=chunk_data["metadata"],
                )
                result = chunk_data.copy()
                result["embedding"] = embedding
                results.append(result)

                if (i + 1) % 10 == 0:
                    logger.info(f"Embeddings gerados: {i + 1}/{len(chunks_data)}")

                time.sleep(rate_limit_delay)

            except Exception as e:
                logger.error(f"Falha ao gerar embedding para chunk {i}: {e}")
                result = chunk_data.copy()
                result["embedding"] = [0.0] * self.config["dimensions"]
                result["embedding_error"] = str(e)
                results.append(result)

        return results

    def validate_embedding(self, embedding: list[float]) -> bool:
        """Valida formato e dimensões do embedding.

        Args:
            embedding: Vetor de embedding a validar.

        Returns:
            True se válido.
        """
        if not isinstance(embedding, list):
            return False
        if len(embedding) != self.config["dimensions"]:
            return False
        if not all(isinstance(x, int | float) for x in embedding):
            return False
        if any(x != x for x in embedding):  # NaN check
            return False
        return True


# ════════════════════════════════════════════════════════════════════════════
# CHROMADB STORE
# ════════════════════════════════════════════════════════════════════════════


class ChromaDBStore:
    """Interface completa para operações ChromaDB.

    Responsável por:
    - Gerenciamento da coleção (criação, reset)
    - Indexação de chunks (individual e em batch)
    - Busca por similaridade semântica
    - Busca por metadados
    - Operações utilitárias (distinct values, stats)
    """

    def __init__(self, config: dict | None = None):
        """Inicializa ChromaDBStore com cliente persistente.

        Args:
            config: Configuração ChromaDB. Default: CHROMADB_CONFIG.
        """
        self.config = config or CHROMADB_CONFIG
        self.client = self._initialize_client()
        self.collection = self._get_or_create_collection()
        logger.info(f"ChromaDBStore inicializado — coleção: {self.config['collection_name']}")

    def _initialize_client(self) -> chromadb.ClientAPI:
        """Inicializa cliente ChromaDB com persistência em disco."""
        try:
            persist_dir = str(DIRECTORY_PATHS["vector_db"])
            client = chromadb.PersistentClient(path=persist_dir)
            logger.info(f"ChromaDB client inicializado em: {persist_dir}")
            return client
        except Exception as e:
            logger.error(f"Falha ao inicializar ChromaDB client: {e}")
            raise

    def _get_or_create_collection(self) -> chromadb.Collection:
        """Obtém coleção existente ou cria uma nova."""
        collection_name = self.config["collection_name"]
        try:
            try:
                collection = self.client.get_collection(name=collection_name)
                logger.info(f"Coleção existente obtida: {collection_name}")
                return collection
            except Exception:
                collection = self.client.create_collection(
                    name=collection_name,
                    metadata={"description": "KT transcription chunks with semantic search"},
                )
                logger.info(f"Nova coleção criada: {collection_name}")
                return collection
        except Exception as e:
            logger.error(f"Falha ao obter/criar coleção: {e}")
            raise

    def add_chunk(self, chunk_id: str, content: str, metadata: dict, embedding: list[float]) -> bool:
        """Adiciona chunk individual à coleção ChromaDB.

        Args:
            chunk_id: Identificador único do chunk.
            content: Conteúdo textual do chunk.
            metadata: Metadados do chunk.
            embedding: Vetor de embedding pré-computado.

        Returns:
            True se bem-sucedido.
        """
        try:
            if not chunk_id:
                raise ValueError("chunk_id é obrigatório")
            if content is None:
                content = ""

            expected_dims = self.config["embedding_dimensions"]
            if len(embedding) != expected_dims:
                raise ValueError(f"Dimensões inválidas: esperado {expected_dims}, obtido {len(embedding)}")

            clean_metadata = self._clean_metadata(metadata)
            clean_metadata["indexed_at"] = datetime.now().isoformat()
            clean_metadata["content_length"] = len(content)

            self.collection.add(
                ids=[chunk_id],
                documents=[content],
                embeddings=cast(PyEmbeddings, [embedding]),
                metadatas=[clean_metadata],
            )

            logger.debug(f"Chunk adicionado: {chunk_id}")
            return True

        except Exception as e:
            logger.error(f"Falha ao adicionar chunk {chunk_id}: {e}")
            return False

    def add_chunks_batch(self, chunks: list[dict[str, Any]]) -> dict[str, int]:
        """Adiciona múltiplos chunks em batch.

        Args:
            chunks: Lista de dicts com chaves: id, content, metadata, embedding.

        Returns:
            Dict com contagens: total, success, failure.
        """
        batch_size = int(self.config["max_batch_size"])
        total_chunks = len(chunks)
        success_count = 0
        failure_count = 0

        for i in range(0, total_chunks, batch_size):
            batch = chunks[i : i + batch_size]
            try:
                ids = []
                documents = []
                embeddings = []
                metadatas: Metadatas = []

                for chunk in batch:
                    ids.append(chunk["id"])
                    documents.append(chunk["content"])
                    embeddings.append(chunk["embedding"])

                    clean_metadata = self._clean_metadata(chunk["metadata"])
                    clean_metadata["indexed_at"] = datetime.now().isoformat()
                    clean_metadata["content_length"] = len(chunk["content"])
                    metadatas.append(clean_metadata)

                self.collection.add(
                    ids=ids,
                    documents=documents,
                    embeddings=cast(PyEmbeddings, embeddings),
                    metadatas=metadatas,
                )
                success_count += len(batch)
                logger.info(f"Batch {i // batch_size + 1}: {len(batch)} chunks adicionados")

            except Exception as e:
                logger.error(f"Batch {i // batch_size + 1} falhou: {e}")
                failure_count += len(batch)

        return {"total": total_chunks, "success": success_count, "failure": failure_count}

    def query_similarity(
        self,
        query_embedding: list[float],
        limit: int = 10,
        where_filter: dict | None = None,
        include_metadata: bool = True,
    ) -> dict[str, Any]:
        """Busca por similaridade usando embedding.

        Args:
            query_embedding: Vetor de embedding da query.
            limit: Número máximo de resultados.
            where_filter: Filtros de metadados.
            include_metadata: Se True, inclui metadados nos resultados.

        Returns:
            Dict com resultados e estatísticas.
        """
        try:
            include_fields: Include = ["documents", "distances"]
            if include_metadata:
                include_fields.append("metadatas")

            results = self.collection.query(
                query_embeddings=cast(PyEmbeddings, [query_embedding]),
                n_results=limit,
                where=where_filter,
                include=include_fields,
            )

            ids_list = results["ids"][0] if results["ids"] else []
            docs_list = results["documents"][0] if results["documents"] else []
            dists_list = results["distances"][0] if results["distances"] else []
            raw_metas = results["metadatas"]
            metas_list = raw_metas[0] if raw_metas else []

            formatted_results = []
            for i in range(len(ids_list)):
                result: dict[str, Any] = {
                    "chunk_id": ids_list[i],
                    "content": docs_list[i],
                    "similarity_score": 1 - dists_list[i],
                }
                if include_metadata and metas_list:
                    result["metadata"] = metas_list[i]
                formatted_results.append(result)

            return {
                "results": formatted_results,
                "total_found": len(formatted_results),
                "query_type": "similarity",
                "filter_applied": where_filter is not None,
            }

        except Exception as e:
            logger.error(f"Busca por similaridade falhou: {e}")
            return {"results": [], "total_found": 0, "error": str(e)}

    def query_metadata(
        self,
        where_filter: dict[str, Any] | None = None,
        limit: int = 10,
        include_content: bool = True,
    ) -> dict[str, Any]:
        """Busca documentos por filtros de metadados.

        Args:
            where_filter: Filtros de metadados.
            limit: Número máximo de resultados.
            include_content: Se True, inclui conteúdo dos documentos.

        Returns:
            Dict com resultados e estatísticas.
        """
        try:
            include_fields_get: Include = ["metadatas"]
            if include_content:
                include_fields_get.append("documents")

            results = self.collection.get(where=where_filter, limit=limit, include=include_fields_get)

            ids_list = results["ids"] or []
            metas_list = results["metadatas"] or []
            docs_list = results["documents"] or []

            formatted_results = []
            for i in range(len(ids_list)):
                result: dict[str, Any] = {
                    "chunk_id": ids_list[i],
                    "metadata": metas_list[i] if metas_list else {},
                }
                if include_content and docs_list:
                    result["content"] = docs_list[i]
                formatted_results.append(result)

            return {
                "results": formatted_results,
                "total_found": len(formatted_results),
                "query_type": "metadata",
                "filter_applied": True,
            }

        except Exception as e:
            logger.error(f"Busca por metadados falhou: {e}")
            return {"results": [], "total_found": 0, "error": str(e)}

    def similarity_search(self, query_text: str, limit: int = 10, filters: dict | None = None) -> list[dict[str, Any]]:
        """Busca por similaridade usando texto (gera embedding internamente).

        Args:
            query_text: Texto da query.
            limit: Número máximo de resultados.
            filters: Filtros de metadados.

        Returns:
            Lista de resultados com scores de similaridade.
        """
        try:
            embedding_gen = EmbeddingGenerator()
            query_embedding = embedding_gen.generate_query_embedding(query_text)

            if not query_embedding or len(query_embedding) != 1536:
                logger.error("Falha ao gerar embedding de query válido")
                return []

            include_sim: Include = ["documents", "distances", "metadatas"]
            results = self.collection.query(
                query_embeddings=cast(PyEmbeddings, [query_embedding]),
                n_results=limit,
                where=filters,
                include=include_sim,
            )

            formatted_results = []
            if results.get("ids") and len(results["ids"]) > 0:
                ids_row = results["ids"][0]
                docs_row = results["documents"][0] if results["documents"] else []
                dists_row = results["distances"][0] if results["distances"] else []
                raw_metas_sim = results["metadatas"]
                metas_row = raw_metas_sim[0] if raw_metas_sim else []
                for i in range(len(ids_row)):
                    formatted_results.append(
                        {
                            "chunk_id": ids_row[i],
                            "content": docs_row[i],
                            "similarity_score": 1 - dists_row[i],
                            "metadata": metas_row[i] if metas_row else {},
                        }
                    )

            return formatted_results

        except Exception as e:
            logger.error(f"similarity_search falhou: {e}")
            return []

    def search_by_metadata(self, filters: dict[str, Any], limit: int = 50) -> list[dict[str, Any]]:
        """Busca documentos apenas por filtros de metadados.

        Args:
            filters: Condições de filtro de metadados.
            limit: Número máximo de resultados.

        Returns:
            Lista de documentos correspondentes.
        """
        try:
            processed_filters = self._process_temporal_filters(filters)
            include_meta: Include = ["documents", "metadatas"]

            if processed_filters is None:
                raw = self.collection.get(limit=limit, include=include_meta)
                return self._post_process_temporal_results(dict(raw), filters)

            results = self.collection.get(where=processed_filters, limit=limit, include=include_meta)

            ids_list = results["ids"] or []
            docs_list = results["documents"] or []
            metas_list = results["metadatas"] or []

            formatted_results = []
            for i in range(len(ids_list)):
                formatted_results.append(
                    {
                        "chunk_id": ids_list[i],
                        "content": docs_list[i],
                        "metadata": metas_list[i] if metas_list else {},
                    }
                )

            return formatted_results

        except Exception as e:
            logger.error(f"search_by_metadata falhou: {e}")
            return []

    def delete_chunk(self, chunk_id: str) -> bool:
        """Remove chunk específico por ID.

        Args:
            chunk_id: ID do chunk a remover.

        Returns:
            True se removido com sucesso.
        """
        try:
            self.collection.delete(ids=[chunk_id])
            logger.info(f"Chunk removido: {chunk_id}")
            return True
        except Exception as e:
            logger.error(f"Falha ao remover chunk {chunk_id}: {e}")
            return False

    def reset_collection(self) -> bool:
        """Reseta coleção (remove todos os documentos) — USE COM CAUTELA.

        Returns:
            True se resetada com sucesso. False se reset desabilitado.
        """
        if not self.config.get("allow_reset", False):
            logger.warning("Reset de coleção desabilitado em configuração")
            return False

        try:
            self.client.delete_collection(name=self.config["collection_name"])
            self.collection = self._get_or_create_collection()
            logger.warning(f"Coleção resetada: {self.config['collection_name']}")
            return True
        except Exception as e:
            logger.error(f"Falha ao resetar coleção: {e}")
            return False

    def get_collection_info(self) -> dict[str, Any]:
        """Obtém informações e estatísticas da coleção.

        Returns:
            Dict com estatísticas da coleção.
        """
        try:
            count = self.collection.count()
            sample_results = self.collection.get(limit=10, include=["metadatas"])

            metadata_fields: set[str] = set()
            clients: set[str] = set()

            raw_sample_metas = sample_results["metadatas"]
            for metadata in raw_sample_metas or []:
                if metadata:
                    metadata_fields.update(k for k in metadata.keys() if isinstance(k, str))
                    client_val = metadata.get("client_name")
                    if isinstance(client_val, str) and client_val:
                        clients.add(client_val)

            return {
                "total_documents": count,
                "collection_name": self.config["collection_name"],
                "metadata_fields": list(metadata_fields),
                "unique_clients": list(clients),
                "sample_size": len(sample_results.get("ids", [])),
                "embedding_dimensions": self.config.get("embedding_dimensions", 1536),
                "persist_directory": str(DIRECTORY_PATHS["vector_db"]),
            }

        except Exception as e:
            logger.error(f"Falha ao obter informações da coleção: {e}")
            return {"error": str(e)}

    def get_collection_stats(self) -> dict[str, Any]:
        """Alias para get_collection_info."""
        return self.get_collection_info()

    def get_distinct_values(self, field_name: str) -> list[str]:
        """Obtém valores distintos de um campo de metadado.

        Args:
            field_name: Nome do campo de metadado.

        Returns:
            Lista de valores únicos.
        """
        try:
            include_only_meta: Include = ["metadatas"]
            results = self.collection.get(limit=1000, include=include_only_meta)
            distinct_values: set[str] = set()

            if results.get("metadatas"):
                for metadata in results["metadatas"] or []:
                    if metadata and field_name in metadata:
                        value = metadata[field_name]
                        if isinstance(value, str) and value:
                            distinct_values.add(value)

            return list(distinct_values)

        except Exception as e:
            logger.error(f"Falha ao obter valores distintos para {field_name}: {e}")
            return []

    def get_distinct_clients(self) -> list[dict[str, Any]]:
        """Obtém clientes distintos com metadados agregados.

        Returns:
            Lista de dicionários com dados agregados por cliente.
        """
        try:
            include_clients: Include = ["metadatas"]
            results = self.collection.get(include=include_clients)

            if not results.get("metadatas"):
                return []

            clients_data: dict[str, dict[str, Any]] = {}

            for metadata in results["metadatas"] or []:
                if not metadata:
                    continue

                client_name_raw = metadata.get("client_name")
                if (
                    not isinstance(client_name_raw, str)
                    or not client_name_raw
                    or client_name_raw == "CLIENTE_DESCONHECIDO"
                ):
                    continue
                client_name = client_name_raw

                if client_name not in clients_data:
                    clients_data[client_name] = {
                        "client_name": client_name,
                        "chunk_count": 0,
                        "latest_meeting_date": None,
                        "sap_modules": set(),
                        "meeting_phases": set(),
                    }

                client_data = clients_data[client_name]
                client_data["chunk_count"] += 1

                meeting_date = metadata.get("meeting_date")
                if meeting_date:
                    if not client_data["latest_meeting_date"] or meeting_date > client_data["latest_meeting_date"]:
                        client_data["latest_meeting_date"] = meeting_date

                sap_modules = metadata.get("sap_modules")
                if sap_modules:
                    if isinstance(sap_modules, str):
                        client_data["sap_modules"].add(sap_modules)
                    elif isinstance(sap_modules, list):
                        client_data["sap_modules"].update(sap_modules)

                meeting_phase = metadata.get("meeting_phase")
                if meeting_phase:
                    client_data["meeting_phases"].add(meeting_phase)

            result_data = []
            for client_data in clients_data.values():
                client_data["sap_modules"] = list(client_data["sap_modules"])
                client_data["meeting_phases"] = list(client_data["meeting_phases"])
                result_data.append(client_data)

            return sorted(result_data, key=lambda x: x["client_name"])

        except Exception as e:
            logger.error(f"Falha ao obter clientes distintos: {e}")
            return []

    def _clean_metadata(self, metadata: dict) -> dict[str, Any]:
        """Limpa metadados para compatibilidade com ChromaDB.

        Args:
            metadata: Metadados originais.

        Returns:
            Metadados compatíveis com ChromaDB (sem dicts aninhados, listas convertidas).
        """
        clean_metadata: dict[str, Any] = {}

        for key, value in metadata.items():
            if isinstance(value, list | tuple):
                clean_metadata[key] = ", ".join(str(item) for item in value if item)
            elif isinstance(value, dict):
                logger.debug(f"Campo dict ignorado (ChromaDB não suporta): {key}")
                continue
            elif value is None:
                clean_metadata[key] = None
            elif isinstance(value, str | int | float | bool):
                clean_metadata[key] = value
            else:
                clean_metadata[key] = str(value)

        return clean_metadata

    def _process_temporal_filters(self, filters: dict[str, Any]) -> dict[str, Any] | None:
        """Processa filtros temporais (datas como strings).

        Returns:
            Filtros processados ou None se pós-processamento necessário.
        """
        if not filters:
            return filters

        for key, value in filters.items():
            if key == "meeting_date" and isinstance(value, dict) and "$gte" in value:
                return None  # Requer pós-processamento

        return filters

    def _post_process_temporal_results(
        self, results: dict[str, Any], original_filters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Aplica filtros temporais em pós-processamento (strings de data).

        Args:
            results: Resultados brutos do ChromaDB.
            original_filters: Filtros originais incluindo temporais.

        Returns:
            Lista de resultados filtrados.
        """
        formatted_results = []
        date_filter = original_filters.get("meeting_date", {})
        min_date_str = date_filter.get("$gte")

        for i in range(len(results["ids"])):
            metadata = results.get("metadatas", [{}])[i] if results.get("metadatas") else {}
            meeting_date = metadata.get("meeting_date")

            include_result = True
            if min_date_str and meeting_date and meeting_date < min_date_str:
                include_result = False

            if include_result:
                for key, value in original_filters.items():
                    if key != "meeting_date" and key in metadata:
                        if isinstance(value, str) and metadata[key] != value:
                            include_result = False
                            break

            if include_result:
                formatted_results.append(
                    {
                        "chunk_id": results["ids"][i],
                        "content": results["documents"][i] if results.get("documents") else "",
                        "metadata": metadata,
                    }
                )

        return formatted_results
