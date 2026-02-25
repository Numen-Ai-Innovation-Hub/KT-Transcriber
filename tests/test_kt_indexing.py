"""Testes unitários para kt_indexing — TextChunker, ChromaDBStore, IndexingEngine."""

from pathlib import Path
from unittest.mock import patch

# ════════════════════════════════════════════════════════════════════════════
# TextChunker
# ════════════════════════════════════════════════════════════════════════════


class TestTextChunker:
    """Testa TextChunker — lógica de chunking sem I/O externo."""

    def test_texto_abaixo_min_chars_retorna_lista_vazia(self) -> None:
        """Textos com menos de min_chars (50) retornam lista vazia."""
        from src.kt_indexing.text_chunker import TextChunker

        chunker = TextChunker()
        result = chunker.split_segment_into_parts("Texto curto.")
        assert result == []

    def test_texto_vazio_retorna_lista_vazia(self) -> None:
        """String vazia retorna lista vazia."""
        from src.kt_indexing.text_chunker import TextChunker

        chunker = TextChunker()
        result = chunker.split_segment_into_parts("")
        assert result == []

    def test_texto_abaixo_max_chars_retorna_chunk_unico(self) -> None:
        """Texto com menos de max_chars retorna exatamente um chunk."""
        from src.kt_indexing.text_chunker import TextChunker

        chunker = TextChunker()
        text = "Este é um texto de tamanho médio que tem mais de cinquenta caracteres para passar no filtro mínimo."
        result = chunker.split_segment_into_parts(text)

        assert len(result) == 1
        assert result[0].text == text.strip()
        assert result[0].part_index == 0
        assert result[0].total_parts == 1

    def test_texto_longo_gera_multiplos_chunks(self) -> None:
        """Texto maior que max_chars gera múltiplos chunks."""
        from src.kt_indexing.text_chunker import TextChunker

        config = {"max_chars": 200, "overlap_chars": 50, "min_chars": 50}
        chunker = TextChunker(config=config)

        # Texto de ~600 chars para forçar múltiplos chunks
        sentence = "Este é um segmento de texto longo que vai gerar múltiplos chunks no processamento. "
        text = sentence * 7

        result = chunker.split_segment_into_parts(text)
        assert len(result) > 1

    def test_chunks_tem_part_index_sequencial(self) -> None:
        """Chunks têm part_index sequencial começando em 0."""
        from src.kt_indexing.text_chunker import TextChunker

        config = {"max_chars": 200, "overlap_chars": 50, "min_chars": 50}
        chunker = TextChunker(config=config)
        sentence = "Segmento de texto bem longo para forçar divisão em partes menores. "
        text = sentence * 7

        result = chunker.split_segment_into_parts(text)
        indices = [p.part_index for p in result]
        assert indices == list(range(len(result)))

    def test_chunks_tem_total_parts_correto(self) -> None:
        """Todos os chunks têm total_parts igual ao número total de chunks."""
        from src.kt_indexing.text_chunker import TextChunker

        config = {"max_chars": 200, "overlap_chars": 50, "min_chars": 50}
        chunker = TextChunker(config=config)
        sentence = "Segmento de texto bem longo para forçar divisão em partes menores. "
        text = sentence * 7

        result = chunker.split_segment_into_parts(text)
        total = len(result)
        for part in result:
            assert part.total_parts == total

    def test_chunk_text_funcao_conveniencia(self) -> None:
        """chunk_text retorna lista de strings com texto dos chunks."""
        from src.kt_indexing.text_chunker import chunk_text

        text = "Texto de exemplo para teste do chunker. " * 10
        result = chunk_text(text, max_chars=200, overlap_chars=50)

        assert isinstance(result, list)
        assert all(isinstance(chunk, str) for chunk in result)
        assert len(result) >= 1

    def test_chunk_unico_tem_char_start_zero(self) -> None:
        """Chunk único tem char_start=0."""
        from src.kt_indexing.text_chunker import TextChunker

        chunker = TextChunker()
        text = "Este é um texto de tamanho médio que tem mais de cinquenta caracteres para passar no filtro mínimo."
        result = chunker.split_segment_into_parts(text)

        assert result[0].char_start == 0

    def test_configuracao_customizada_e_respeitada(self) -> None:
        """Configuração customizada de max_chars é respeitada."""
        from src.kt_indexing.text_chunker import TextChunker

        # max_chars muito pequeno para forçar múltiplos chunks
        config = {"max_chars": 100, "overlap_chars": 20, "min_chars": 30}
        chunker = TextChunker(config=config)

        text = ("Texto de teste com sentenças longas para garantir que o chunker divida corretamente. " * 5).strip()
        result = chunker.split_segment_into_parts(text)

        # Cada chunk não deve exceder max_chars
        for part in result:
            assert len(part.text) <= config["max_chars"] + config["overlap_chars"] + 50  # margem de sentença


# ════════════════════════════════════════════════════════════════════════════
# IndexingEngine
# ════════════════════════════════════════════════════════════════════════════


class TestIndexingEngineInit:
    """Testa inicialização do IndexingEngine com ChromaDB desativado."""

    def test_init_sem_chromadb_nao_inicializa_store(self, tmp_path: Path) -> None:
        """enable_chromadb=False → chromadb_store permanece None."""
        from src.kt_indexing.indexing_engine import IndexingEngine

        engine = IndexingEngine(
            input_dir=tmp_path,
            output_dir=tmp_path / "chunks",
            enable_chromadb=False,
            generate_txt_files=False,
        )

        assert engine.chromadb_store is None
        assert engine.embedding_generator is None
        assert engine.enable_chromadb is False

    def test_init_configura_diretorios_corretamente(self, tmp_path: Path) -> None:
        """Diretórios de entrada e saída são configurados conforme passados."""
        from src.kt_indexing.indexing_engine import IndexingEngine

        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()

        engine = IndexingEngine(
            input_dir=input_dir,
            output_dir=output_dir,
            enable_chromadb=False,
            generate_txt_files=False,
        )

        assert engine.input_dir == input_dir
        assert engine.output_dir == output_dir

    def test_global_stats_inicializado_com_zeros(self, tmp_path: Path) -> None:
        """global_stats é inicializado com valores nulos/zeros."""
        from src.kt_indexing.indexing_engine import IndexingEngine

        engine = IndexingEngine(
            input_dir=tmp_path,
            output_dir=tmp_path,
            enable_chromadb=False,
            generate_txt_files=False,
        )

        assert engine.global_stats["videos_processed"] == 0
        assert engine.global_stats["chunks_indexed"] == 0
        assert engine.global_stats["errors_encountered"] == 0


class TestIndexingEngineProcessAllVideos:
    """Testa process_all_videos com diretório vazio."""

    def test_diretorio_vazio_retorna_stats_sem_processar(self, tmp_path: Path) -> None:
        """Diretório sem JSONs retorna stats com videos_processed=0."""
        from src.kt_indexing.indexing_engine import IndexingEngine

        engine = IndexingEngine(
            input_dir=tmp_path,
            output_dir=tmp_path / "chunks",
            enable_chromadb=False,
            generate_txt_files=False,
        )

        stats = engine.process_all_videos()
        assert stats["videos_processed"] == 0


# ════════════════════════════════════════════════════════════════════════════
# EmbeddingGenerator (sem I/O real — teste apenas construção híbrida)
# ════════════════════════════════════════════════════════════════════════════


class TestEmbeddingGeneratorHybridInput:
    """Testa _build_hybrid_input — método puro de construção de texto."""

    def _make_generator(self) -> object:
        """Cria EmbeddingGenerator com OpenAI mockado."""
        with patch("src.kt_indexing.chromadb_store.openai.OpenAI"):
            from src.kt_indexing.chromadb_store import EmbeddingGenerator

            return EmbeddingGenerator()

    def test_build_hybrid_input_contem_chunk(self) -> None:
        """Input híbrido começa com 'CHUNK:' e contém texto do chunk."""
        gen = self._make_generator()
        metadata: dict = {"client_name": "ClienteX", "sap_modules_title": "FI", "meeting_phase": "AS-IS"}

        result = gen._build_hybrid_input("Texto do chunk de exemplo.", metadata)  # type: ignore[attr-defined]

        assert result.startswith("CHUNK:")
        assert "Texto do chunk de exemplo." in result

    def test_build_hybrid_input_contem_contexto(self) -> None:
        """Input híbrido inclui bloco CONTEXTO com cliente e módulo."""
        gen = self._make_generator()
        metadata: dict = {"client_name": "Empresa ABC", "sap_modules_title": "MM", "meeting_phase": "TO-BE"}

        result = gen._build_hybrid_input("Texto.", metadata)  # type: ignore[attr-defined]

        assert "CONTEXTO:" in result
        assert "Empresa ABC" in result

    def test_build_hybrid_input_sem_metadata_retorna_apenas_chunk(self) -> None:
        """Sem metadados relevantes, retorna apenas a seção CHUNK."""
        gen = self._make_generator()
        result = gen._build_hybrid_input("Texto simples.", {})  # type: ignore[attr-defined]

        assert "CHUNK:" in result
        # Sem participantes/transações/tags → sem seções extras
        assert "ENTIDADES:" not in result
        assert "TRANSAÇÕES:" not in result
