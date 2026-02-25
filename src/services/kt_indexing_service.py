"""Serviço de orquestração para indexação KT.

Singleton thread-safe. Encapsula IndexingEngine + ChromaDBStore.
Usar get_kt_indexing_service() para obter a instância.
"""

import json
import threading
from pathlib import Path
from typing import Any

from src.config.settings import DIRECTORY_PATHS
from src.kt_indexing.chromadb_store import ChromaDBStore
from src.kt_indexing.indexing_engine import IndexingEngine
from utils.exception_setup import ApplicationError
from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)


class KTIndexingService:
    """Serviço de orquestração para indexação KT no ChromaDB.

    Singleton thread-safe. Encapsula IndexingEngine e ChromaDBStore.
    Cada chamada a run_indexing() opera de forma incremental — pula vídeos já indexados.
    """

    _instance: "KTIndexingService | None" = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        """Inicializa o serviço com diretórios de dados."""
        self._transcriptions_dir: Path = DIRECTORY_PATHS["transcriptions"]
        self._vector_db_dir: Path = DIRECTORY_PATHS["vector_db"]

    @classmethod
    def get_instance(cls) -> "KTIndexingService":
        """Retorna instância singleton (double-checked locking)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ────────────────────────────────────────────────────────────────────────
    # OPERAÇÕES PÚBLICAS
    # ────────────────────────────────────────────────────────────────────────

    def force_clean(self) -> None:
        """Remove vector_db/ e chunks/ e os recria vazios."""
        import shutil

        chunks_dir = self._transcriptions_dir / "chunks"

        logger.warning(f"Iniciando limpeza de vector_db/ em {self._vector_db_dir}")
        if self._vector_db_dir.exists():
            shutil.rmtree(self._vector_db_dir)
        self._vector_db_dir.mkdir(parents=True, exist_ok=True)

        logger.warning(f"Iniciando limpeza de chunks/ em {chunks_dir}")
        if chunks_dir.exists():
            shutil.rmtree(chunks_dir)
        chunks_dir.mkdir(parents=True, exist_ok=True)

        logger.warning("Limpeza concluída — vector_db/ e chunks/ recriados vazios")

    def run_indexing(self) -> dict[str, Any]:
        """Indexa JSONs novos no ChromaDB de forma incremental.

        Pula vídeos cujo meeting_id já está no ChromaDB.
        Para cada JSON novo: chunking + extração LLM de metadados + geração de embeddings.

        Returns:
            Dicionário com estatísticas da execução (videos_indexed, chunks_indexed, etc.).

        Raises:
            ApplicationError: Se ocorrer erro crítico durante a indexação.
        """
        stats: dict[str, Any] = {
            "videos_already_indexed": 0,
            "videos_indexed": 0,
            "chunks_indexed": 0,
            "videos_failed": 0,
            "errors": [],
        }

        new_files = self._get_new_json_files(stats)

        if not new_files:
            logger.info(
                f"Nenhum JSON novo para indexar — "
                f"{stats['videos_already_indexed']} vídeo(s) já indexado(s). Concluído (incremental)"
            )
            return stats

        logger.info(f"JSONs para indexar: {len(new_files)} | já indexados: {stats['videos_already_indexed']}")

        engine = IndexingEngine(
            input_dir=self._transcriptions_dir,
            enable_chromadb=True,
            generate_txt_files=True,
        )

        for i, json_file in enumerate(new_files):
            logger.info(f"Indexando {i + 1}/{len(new_files)}: {json_file.name}")
            try:
                video_stats = engine.process_single_video(json_file)
                stats["videos_indexed"] += 1
                stats["chunks_indexed"] += video_stats.get("parts_created", 0)
                logger.info(
                    f"Vídeo indexado: {json_file.name} — "
                    f"{video_stats.get('parts_created', 0)} chunks, "
                    f"{video_stats.get('segments_processed', 0)} segmentos"
                )
            except ApplicationError as e:
                logger.error(f"Erro ao indexar '{json_file.name}': {e.message}")
                stats["videos_failed"] += 1
                stats["errors"].append(f"Indexação — {json_file.name}: {e.message}")
            except Exception as e:
                logger.error(f"Erro inesperado ao indexar '{json_file.name}': {e}")
                stats["videos_failed"] += 1
                stats["errors"].append(f"Indexação — {json_file.name}: {e!s}")

        logger.info(
            f"Indexação concluída — "
            f"indexados: {stats['videos_indexed']}, "
            f"chunks: {stats['chunks_indexed']}, "
            f"falhas: {stats['videos_failed']}"
        )
        return stats

    def get_status(self) -> dict[str, Any]:
        """Retorna status atual do ChromaDB (documentos, clientes, coleção).

        Returns:
            Dicionário com informações da coleção ChromaDB.

        Raises:
            ApplicationError: Se o vector_db não existir ou ChromaDB não estiver acessível.
        """
        if not self._vector_db_dir.exists():
            raise ApplicationError(
                message="Diretório vector_db não encontrado — indexação não foi executada",
                status_code=404,
                error_code="NOT_FOUND",
            )

        store = ChromaDBStore()
        info = store.get_collection_info()

        if "error" in info:
            raise ApplicationError(
                message=f"Erro ao consultar ChromaDB: {info['error']}",
                status_code=503,
                error_code="SERVICE_UNAVAILABLE",
            )

        return info

    # ────────────────────────────────────────────────────────────────────────
    # PRIVADOS
    # ────────────────────────────────────────────────────────────────────────

    def _get_indexed_meeting_ids(self) -> set[str]:
        """Retorna IDs de reuniões já indexadas no ChromaDB.

        Returns:
            Set com meeting_ids já presentes no ChromaDB. Vazio se DB não existe.
        """
        if not self._vector_db_dir.exists():
            return set()

        try:
            store = ChromaDBStore()
            indexed_ids = store.get_distinct_values("meeting_id")
            return set(indexed_ids)
        except Exception as e:
            logger.warning(f"Erro ao consultar meeting_ids no ChromaDB: {e}")
            return set()

    def _get_new_json_files(self, stats: dict[str, Any]) -> list[Path]:
        """Retorna JSONs de transcrição que ainda não foram indexados.

        Args:
            stats: Dicionário de estatísticas (videos_already_indexed mutado in-place).

        Returns:
            Lista de Paths de arquivos não indexados.
        """
        all_json_files = list(self._transcriptions_dir.glob("*.json"))
        if not all_json_files:
            return []

        indexed_ids = self._get_indexed_meeting_ids()
        if not indexed_ids:
            logger.info("Nenhum dado indexado ainda — processando todos os JSONs")
            return all_json_files

        new_files: list[Path] = []
        for json_file in all_json_files:
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                meeting_id = data.get("metadata", {}).get("meeting_id") or data.get("meeting_id", "")
                if meeting_id in indexed_ids:
                    stats["videos_already_indexed"] += 1
                else:
                    new_files.append(json_file)
            except Exception as e:
                logger.warning(f"Erro ao verificar {json_file.name}, incluindo no processamento: {e}")
                new_files.append(json_file)

        return new_files


def get_kt_indexing_service() -> KTIndexingService:
    """Factory para injeção de dependência nos routers."""
    return KTIndexingService.get_instance()
