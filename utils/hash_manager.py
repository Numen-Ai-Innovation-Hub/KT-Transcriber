"""
Hash Manager - Controle de Cache por Conteúdo via SQLite
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

Gerencia cache inteligente de hashes de arquivos usando SQLite como storage.
Um banco único (`data/sqlite_db/hashes.db`) armazena todos os hashes — sem arquivos JSON por documento.

Funcionalidades:
- Geração de hash de conteúdo (strings, arquivos)
- Armazenamento/consulta de hash via SQLite (INSERT OR REPLACE atômico)
- Validação de freshness de cache (should_reprocess)
- Limpeza de entradas órfãs

Reutilizável em outras soluções!
"""

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class HashManager:
    """
    Gerenciador de hash para controle de cache inteligente via SQLite.

    Usa um banco SQLite único em vez de arquivos JSON individuais por documento.
    Storage: FILE_PATHS["hashes_db"] → data/sqlite_db/hashes.db
    """

    def __init__(self, db_path: str | Path) -> None:
        """
        Inicializa o gerenciador de hash.

        Args:
            db_path: Caminho do banco SQLite (injetado via FILE_PATHS["hashes_db"])
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Cria a tabela de hashes se não existir."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS document_hashes (
                    source_file  TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    updated_at   TEXT NOT NULL
                )
            """)
            conn.commit()

    def generate_content_hash(self, content: str | bytes, algorithm: str = "sha256") -> str:
        """
        Gera hash de conteúdo (string ou bytes).

        Args:
            content: Conteúdo para gerar hash
            algorithm: Algoritmo de hash (sha256, md5, sha1)

        Returns:
            Hash hexadecimal do conteúdo
        """
        content_bytes = content.encode("utf-8") if isinstance(content, str) else content
        hash_obj = hashlib.new(algorithm)
        hash_obj.update(content_bytes)
        return hash_obj.hexdigest()

    def generate_file_hash(self, file_path: str | Path, algorithm: str = "sha256") -> str:
        """
        Gera hash do conteúdo de um arquivo (leitura em chunks).

        Args:
            file_path: Caminho do arquivo
            algorithm: Algoritmo de hash

        Returns:
            Hash hexadecimal do arquivo

        Raises:
            FileNotFoundError: Se o arquivo não existir
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

        hash_obj = hashlib.new(algorithm)
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_obj.update(chunk)

        return hash_obj.hexdigest()

    def should_reprocess(self, source_file: str, current_hash: str) -> bool:
        """
        Determina se o arquivo deve ser reprocessado comparando o hash atual com o armazenado.

        Retorna True (reprocessar) se o arquivo não tem entrada no banco ou o hash mudou.
        Retorna True em caso de erro (safe default: garante reprocessamento).

        Args:
            source_file: Identificador único do arquivo (ex: caminho relativo ou nome)
            current_hash: Hash atual do arquivo

        Returns:
            True se deve reprocessar, False se pode usar cache
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT content_hash FROM document_hashes WHERE source_file = ?",
                    (source_file,),
                ).fetchone()

            if row is None:
                return True  # Nunca processado

            return row[0] != current_hash

        except Exception:
            return True  # Safe default

    def update_cache_hash(self, source_file: str, content_hash: str) -> None:
        """
        Insere ou atualiza o hash de um arquivo no banco (INSERT OR REPLACE atômico).

        Args:
            source_file: Identificador único do arquivo
            content_hash: Hash do conteúdo processado
        """
        updated_at = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO document_hashes (source_file, content_hash, updated_at) VALUES (?, ?, ?)",
                (source_file, content_hash, updated_at),
            )
            conn.commit()

    def load_hash_metadata(self, source_file: str) -> dict[str, Any] | None:
        """
        Carrega os metadados de hash de um arquivo.

        Retorna None se o arquivo não tem entrada no banco ou em caso de erro.

        Args:
            source_file: Identificador único do arquivo

        Returns:
            Dicionário com source_file, content_hash, updated_at — ou None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT source_file, content_hash, updated_at FROM document_hashes WHERE source_file = ?",
                    (source_file,),
                ).fetchone()

            if row is None:
                return None

            return {"source_file": row[0], "content_hash": row[1], "updated_at": row[2]}

        except Exception:
            return None

    def cleanup_orphaned_entries(self, valid_source_files: list[str]) -> int:
        """
        Remove entradas do banco para arquivos que não existem mais.

        Retorna 0 em caso de erro (cleanup não é operação crítica).

        Args:
            valid_source_files: Lista de source_file válidos no momento

        Returns:
            Número de entradas removidas
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                placeholders = ",".join("?" * len(valid_source_files))
                cursor = conn.execute(
                    f"DELETE FROM document_hashes WHERE source_file NOT IN ({placeholders})",
                    valid_source_files,
                )
                conn.commit()
                return cursor.rowcount
        except Exception:
            return 0

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Retorna estatísticas do banco de hashes.

        Retorna dict com "error" em caso de falha (não crítico).

        Returns:
            Dicionário com total de entradas, mais antiga, mais recente
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                total = conn.execute("SELECT COUNT(*) FROM document_hashes").fetchone()[0]
                oldest = conn.execute(
                    "SELECT source_file, updated_at FROM document_hashes ORDER BY updated_at ASC LIMIT 1"
                ).fetchone()
                newest = conn.execute(
                    "SELECT source_file, updated_at FROM document_hashes ORDER BY updated_at DESC LIMIT 1"
                ).fetchone()

            return {
                "total_caches": total,
                "oldest_cache": oldest[0] if oldest else None,
                "newest_cache": newest[0] if newest else None,
            }

        except Exception as e:
            return {"error": str(e)}


# Instância global reutilizável
_hash_manager: HashManager | None = None


def get_hash_manager() -> HashManager:
    """Retorna instância singleton do HashManager (thread-safe para leitura)."""
    global _hash_manager
    if _hash_manager is None:
        from src.config.settings import FILE_PATHS

        _hash_manager = HashManager(db_path=FILE_PATHS["hashes_db"])
    return _hash_manager
