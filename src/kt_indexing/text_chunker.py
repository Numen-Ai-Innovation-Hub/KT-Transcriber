"""Text Chunker — Transcrição de KT.

Divide segmentos de transcrição em chunks menores com sobreposição controlada.
"""

import re
from dataclasses import dataclass

from src.kt_indexing.kt_indexing_constants import CHUNK_CONFIG, SENTENCE_PATTERNS
from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)


@dataclass
class ChunkPart:
    """Parte de um segmento de transcrição após chunking."""

    text: str
    char_start: int
    char_end: int
    part_index: int
    total_parts: int


class TextChunker:
    """Divide textos longos em chunks menores com sobreposição.

    Estratégia:
    - Chunks de no máximo max_chars caracteres.
    - Sobreposição de overlap_chars entre chunks consecutivos.
    - Respeita fronteiras de sentenças quando possível.
    - Chunks muito curtos (< min_chars) são ignorados.
    """

    def __init__(self, config: dict | None = None):
        """Inicializa o chunker com configuração.

        Args:
            config: Configuração de chunking. Default: CHUNK_CONFIG.
        """
        self.config = config or CHUNK_CONFIG
        self.max_chars = self.config["max_chars"]
        self.overlap_chars = self.config["overlap_chars"]
        self.min_chars = self.config.get("min_chars", 50)
        self._sentence_pattern = re.compile("|".join(SENTENCE_PATTERNS))
        logger.debug(f"TextChunker inicializado — max_chars={self.max_chars}, overlap_chars={self.overlap_chars}")

    def split_segment_into_parts(self, text: str) -> list[ChunkPart]:
        """Divide texto em partes com sobreposição controlada.

        Args:
            text: Texto do segmento a dividir.

        Returns:
            Lista de ChunkPart com texto e posições.
        """
        if not text or len(text.strip()) < self.min_chars:
            if text and len(text.strip()) >= self.min_chars:
                return [ChunkPart(text=text.strip(), char_start=0, char_end=len(text), part_index=0, total_parts=1)]
            return []

        text = text.strip()

        # Texto curto o suficiente: retornar como chunk único
        if len(text) <= self.max_chars:
            return [ChunkPart(text=text, char_start=0, char_end=len(text), part_index=0, total_parts=1)]

        # Dividir em sentenças para respeitar fronteiras
        sentences = self._split_into_sentences(text)
        parts = self._build_chunks_from_sentences(sentences, text)

        # Atualizar total_parts
        total = len(parts)
        for part in parts:
            part.total_parts = total

        logger.debug(f"Texto dividido em {total} chunks (total {len(text)} chars)")
        return parts

    def _split_into_sentences(self, text: str) -> list[str]:
        """Divide texto em sentenças usando padrões regex.

        Args:
            text: Texto para dividir.

        Returns:
            Lista de sentenças.
        """
        sentences = self._sentence_pattern.split(text)
        return [s.strip() for s in sentences if s and s.strip()]

    def _build_chunks_from_sentences(self, sentences: list[str], original_text: str) -> list[ChunkPart]:
        """Constrói chunks a partir de sentenças com sobreposição.

        Args:
            sentences: Lista de sentenças.
            original_text: Texto original para cálculo de posições.

        Returns:
            Lista de ChunkPart.
        """
        parts: list[ChunkPart] = []
        current_chunk = ""
        char_offset = 0

        for sentence in sentences:
            # Se adicionar esta sentença não excede o limite
            if len(current_chunk) + len(sentence) + 1 <= self.max_chars:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
            else:
                # Salvar chunk atual se tiver tamanho mínimo
                if len(current_chunk) >= self.min_chars:
                    start = original_text.find(current_chunk, char_offset)
                    if start == -1:
                        start = char_offset
                    parts.append(
                        ChunkPart(
                            text=current_chunk,
                            char_start=start,
                            char_end=start + len(current_chunk),
                            part_index=len(parts),
                            total_parts=0,
                        )
                    )
                    char_offset = max(0, start + len(current_chunk) - self.overlap_chars)

                # Iniciar novo chunk com sobreposição
                if len(current_chunk) > self.overlap_chars:
                    # Pegar últimos overlap_chars como início do próximo chunk
                    overlap_text = current_chunk[-self.overlap_chars :]
                    current_chunk = overlap_text + " " + sentence
                else:
                    current_chunk = sentence

        # Adicionar último chunk
        if current_chunk and len(current_chunk) >= self.min_chars:
            start = original_text.find(current_chunk, char_offset)
            if start == -1:
                start = char_offset
            parts.append(
                ChunkPart(
                    text=current_chunk,
                    char_start=start,
                    char_end=start + len(current_chunk),
                    part_index=len(parts),
                    total_parts=0,
                )
            )

        # Se nenhum chunk foi criado, retornar texto completo truncado
        if not parts and original_text:
            parts.append(
                ChunkPart(
                    text=original_text[: self.max_chars],
                    char_start=0,
                    char_end=min(self.max_chars, len(original_text)),
                    part_index=0,
                    total_parts=1,
                )
            )

        return parts


def chunk_text(text: str, max_chars: int = 1000, overlap_chars: int = 200) -> list[str]:
    """Função de conveniência para chunking de texto.

    Args:
        text: Texto a dividir em chunks.
        max_chars: Tamanho máximo de cada chunk.
        overlap_chars: Sobreposição entre chunks consecutivos.

    Returns:
        Lista de strings (chunks de texto).
    """
    config = {"max_chars": max_chars, "overlap_chars": overlap_chars, "min_chars": 50}
    chunker = TextChunker(config=config)
    parts = chunker.split_segment_into_parts(text)
    return [part.text for part in parts]
