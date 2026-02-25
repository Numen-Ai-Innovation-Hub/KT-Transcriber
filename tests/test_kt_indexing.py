"""Testes unitários para kt_indexing — TextChunker, ChromaDBStore, IndexingEngine."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

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


# ════════════════════════════════════════════════════════════════════════════
# EmbeddingGenerator — validate_embedding (puro, sem I/O)
# ════════════════════════════════════════════════════════════════════════════


class TestEmbeddingGeneratorValidation:
    """Testa validate_embedding — método puro de validação de vetores."""

    def _make_generator(self) -> object:
        """Cria EmbeddingGenerator com OpenAI mockado."""
        with patch("src.kt_indexing.chromadb_store.openai.OpenAI"):
            from src.kt_indexing.chromadb_store import EmbeddingGenerator

            return EmbeddingGenerator()

    def test_validate_embedding_lista_valida_retorna_verdadeiro(self) -> None:
        """Vetor de dimensão correta (1536) retorna True."""
        gen = self._make_generator()
        assert gen.validate_embedding([0.1] * 1536) is True  # type: ignore[attr-defined]

    def test_validate_embedding_tamanho_errado_retorna_falso(self) -> None:
        """Vetor com dimensão errada retorna False."""
        gen = self._make_generator()
        assert gen.validate_embedding([0.1] * 10) is False  # type: ignore[attr-defined]

    def test_validate_embedding_nao_lista_retorna_falso(self) -> None:
        """Argumento que não é lista retorna False."""
        gen = self._make_generator()
        assert gen.validate_embedding("not-a-list") is False  # type: ignore[attr-defined]


# ════════════════════════════════════════════════════════════════════════════
# KTIndexingUtils — funções puras (sem I/O externo)
# ════════════════════════════════════════════════════════════════════════════


class TestKTIndexingUtils:
    """Testa funções puras de kt_indexing_utils — sem mocking necessário."""

    def test_normalize_client_name_remove_acentos(self) -> None:
        """Acentos são removidos e resultado é uppercase."""
        from src.kt_indexing.kt_indexing_utils import normalize_client_name

        assert normalize_client_name("Café") == "CAFE"

    def test_normalize_client_name_vazio_retorna_desconhecido(self) -> None:
        """String vazia retorna CLIENTE_DESCONHECIDO."""
        from src.kt_indexing.kt_indexing_utils import normalize_client_name

        assert normalize_client_name("") == "CLIENTE_DESCONHECIDO"

    def test_normalize_client_name_espacos_viram_underscore(self) -> None:
        """Espaços são convertidos para underscore."""
        from src.kt_indexing.kt_indexing_utils import normalize_client_name

        assert normalize_client_name("ABC DEF") == "ABC_DEF"

    def test_extract_client_name_smart_heuristica(self) -> None:
        """Primeira palavra não-stopword é extraída como nome do cliente."""
        from src.kt_indexing.kt_indexing_utils import extract_client_name_smart

        result = extract_client_name_smart("KT Vissimo MM")
        assert result == "VISSIMO"

    def test_extract_sap_modules_from_title_encontra_multiplos(self) -> None:
        """Múltiplos módulos SAP no título são detectados."""
        from src.kt_indexing.kt_indexing_utils import extract_sap_modules_from_title

        result = extract_sap_modules_from_title("KT MM-SD FI")
        assert "MM" in result
        assert "SD" in result
        assert "FI" in result

    def test_extract_sap_modules_from_title_titulo_vazio(self) -> None:
        """Título vazio retorna lista vazia."""
        from src.kt_indexing.kt_indexing_utils import extract_sap_modules_from_title

        assert extract_sap_modules_from_title("") == []

    def test_format_datetime_sem_argumento_retorna_iso(self) -> None:
        """Chamada sem argumento retorna data/hora atual em formato ISO."""
        from src.kt_indexing.kt_indexing_utils import format_datetime

        result = format_datetime()
        assert "T" in result  # Formato ISO 8601

    def test_format_datetime_com_objeto_datetime(self) -> None:
        """Objeto datetime é convertido para isoformat."""
        from src.kt_indexing.kt_indexing_utils import format_datetime

        dt = datetime(2024, 6, 15, 10, 30, 0)
        assert format_datetime(dt) == "2024-06-15T10:30:00"

    def test_safe_filename_remove_caracteres_invalidos(self) -> None:
        """Barras e caracteres inválidos são substituídos por underscore."""
        from src.kt_indexing.kt_indexing_utils import safe_filename

        result = safe_filename("arquivo/com:caracteres?invalidos")
        assert "/" not in result
        assert ":" not in result

    def test_create_client_variations_gera_formas(self) -> None:
        """Variações incluem versões uppercase, lowercase e sem underscore."""
        from src.kt_indexing.kt_indexing_utils import create_client_variations

        result = create_client_variations("EMPRESA_X")
        result_lower = [v.lower() for v in result]
        assert "empresa_x" in result_lower
        assert "empresa x" in result_lower or any("empresa" in v.lower() for v in result)

    def test_extract_enriched_tldv_fields_mapeia_campos(self) -> None:
        """Campos do formato flat são mapeados corretamente."""
        from src.kt_indexing.kt_indexing_utils import extract_enriched_tldv_fields

        data: dict[str, Any] = {
            "meeting_url": "https://example.com/kt",
            "happened_at": "2024-01-15T10:00:00Z",
            "duration": 3600,
            "highlights": [],
        }
        result = extract_enriched_tldv_fields(data)

        assert result["original_url"] == "https://example.com/kt"
        assert result["meeting_date"] == "2024-01-15"
        assert result["duration_seconds"] == 3600

    def test_extract_participants_list_sem_invitees_retorna_vazio(self) -> None:
        """Dict sem campo meeting.invitees retorna lista vazia."""
        from src.kt_indexing.kt_indexing_utils import extract_participants_list

        assert extract_participants_list({}) == []


# ════════════════════════════════════════════════════════════════════════════
# FileGenerator — construção de arquivos (puro + tmp_path)
# ════════════════════════════════════════════════════════════════════════════


class TestFileGenerator:
    """Testa FileGenerator — métodos de construção e validação de arquivos TXT."""

    def test_build_tldv_section_primeira_linha(self) -> None:
        """Primeira linha da seção TLDV é 'TLDV:'."""
        from src.kt_indexing.file_generator import FileGenerator

        gen = FileGenerator()
        lines = gen._build_tldv_section({})
        assert lines[0] == "TLDV:"

    def test_build_tldv_section_contem_campos_obrigatorios(self) -> None:
        """Seção TLDV contém campos obrigatórios com valores do metadata."""
        from src.kt_indexing.file_generator import FileGenerator

        gen = FileGenerator()
        metadata: dict[str, Any] = {"video_name": "KT Finance", "client_name": "ClienteX"}
        lines = gen._build_tldv_section(metadata)
        content = "\n".join(lines)

        assert "video_name: KT Finance" in content
        assert "client_name: ClienteX" in content

    def test_build_customized_section_primeira_linha(self) -> None:
        """Primeira linha da seção CUSTOMIZADOS é 'CUSTOMIZADOS:'."""
        from src.kt_indexing.file_generator import FileGenerator

        gen = FileGenerator()
        lines = gen._build_customized_section({})
        assert lines[0] == "CUSTOMIZADOS:"

    def test_build_chunk_section_contem_texto(self) -> None:
        """Seção CHUNK contém o texto do chunk."""
        from src.kt_indexing.file_generator import FileGenerator

        gen = FileGenerator()
        lines = gen._build_chunk_section("conteúdo do chunk de teste")
        content = "\n".join(lines)

        assert "CHUNK:" in content
        assert "conteúdo do chunk de teste" in content

    def test_build_file_content_todas_secoes_presentes(self) -> None:
        """Conteúdo do arquivo contém as três seções separadas pelo separador."""
        from src.kt_indexing.file_generator import FileGenerator

        gen = FileGenerator()
        content = gen._build_file_content(
            tldv_metadata={"video_name": "KT Test"},
            customized_metadata={},
            chunk_text="texto de chunk",
        )

        assert "TLDV:" in content
        assert "CUSTOMIZADOS:" in content
        assert "CHUNK:" in content
        assert gen.separator in content

    def test_create_chunk_txt_file_cria_arquivo_em_disco(self, tmp_path: Path) -> None:
        """create_chunk_txt_file cria arquivo no diretório especificado."""
        from src.kt_indexing.file_generator import FileGenerator

        gen = FileGenerator()
        file_path = gen.create_chunk_txt_file(
            filename="test_chunk.txt",
            output_dir=tmp_path,
            tldv_metadata={"video_name": "KT Test", "client_name": "ClienteX"},
            customized_metadata={},
            chunk_text="Texto do chunk para teste de criação de arquivo.",
        )

        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8").startswith("TLDV:")

    def test_parse_file_sections_divide_em_tres_secoes(self, tmp_path: Path) -> None:
        """_parse_file_sections identifica seções TLDV, CUSTOMIZADOS e CHUNK."""
        from src.kt_indexing.file_generator import FileGenerator

        gen = FileGenerator()
        content = gen._build_file_content(
            tldv_metadata={"video_name": "KT"},
            customized_metadata={},
            chunk_text="texto aqui",
        )
        sections = gen._parse_file_sections(content)

        assert "tldv" in sections
        assert "customizados" in sections
        assert "chunk" in sections

    def test_validate_chunk_section_vazio_retorna_erro(self) -> None:
        """Seção CHUNK vazia gera erro de validação."""
        from src.kt_indexing.file_generator import FileGenerator

        gen = FileGenerator()
        result = gen._validate_chunk_section("")

        assert len(result["errors"]) > 0
        assert any("vazia" in e.lower() or "chunk" in e.lower() for e in result["errors"])


# ════════════════════════════════════════════════════════════════════════════
# LLMMetadataExtractor — parsing puro + mock OpenAI
# ════════════════════════════════════════════════════════════════════════════


class TestLLMMetadataExtractor:
    """Testa LLMMetadataExtractor — parsing puro e comportamento com mock OpenAI."""

    def _make_extractor(self) -> object:
        """Cria LLMMetadataExtractor com OpenAI mockado."""
        with patch("src.kt_indexing.llm_metadata_extractor.openai.OpenAI"):
            from src.kt_indexing.llm_metadata_extractor import LLMMetadataExtractor

            return LLMMetadataExtractor()

    def test_init_com_openai_mockado_nao_crasha(self) -> None:
        """Instanciar com OpenAI mockado não levanta exceção."""
        extractor = self._make_extractor()
        assert extractor is not None

    def test_parse_gpt_response_formato_atribuicao_python(self) -> None:
        """Formato 'variavel = valor' é parseado corretamente."""
        extractor = self._make_extractor()
        result = extractor._parse_gpt_response(  # type: ignore[attr-defined]
            "sap_modules = ['MM', 'SD']"
        )
        assert "MM" in result["sap_modules"]
        assert "SD" in result["sap_modules"]

    def test_parse_gpt_response_formato_dois_pontos(self) -> None:
        """Formato 'variavel: valor' é parseado corretamente."""
        extractor = self._make_extractor()
        result = extractor._parse_gpt_response(  # type: ignore[attr-defined]
            "meeting_phase: DEMO"
        )
        assert result["meeting_phase"] == "DEMO"

    def test_parse_gpt_response_vazio_retorna_defaults(self) -> None:
        """Resposta vazia retorna METADATA_DEFAULTS sem modificações."""
        from src.kt_indexing.kt_indexing_constants import METADATA_DEFAULTS

        extractor = self._make_extractor()
        result = extractor._parse_gpt_response("")  # type: ignore[attr-defined]
        assert result["meeting_phase"] == METADATA_DEFAULTS["meeting_phase"]
        assert result["sap_modules"] == METADATA_DEFAULTS["sap_modules"]

    def test_parse_gpt_response_chave_invalida_ignorada(self) -> None:
        """Chave que não existe em METADATA_DEFAULTS é ignorada."""
        from src.kt_indexing.kt_indexing_constants import METADATA_DEFAULTS

        extractor = self._make_extractor()
        result = extractor._parse_gpt_response("chave_inexistente = valor_qualquer")  # type: ignore[attr-defined]
        assert "chave_inexistente" not in result
        assert result["meeting_phase"] == METADATA_DEFAULTS["meeting_phase"]

    def test_extract_metadata_chunk_muito_curto_retorna_defaults(self) -> None:
        """Chunk com menos de 20 chars retorna defaults sem chamar OpenAI."""
        from src.kt_indexing.kt_indexing_constants import METADATA_DEFAULTS

        with patch("src.kt_indexing.llm_metadata_extractor.openai.OpenAI") as mock_openai_cls:
            from src.kt_indexing.llm_metadata_extractor import LLMMetadataExtractor

            extractor = LLMMetadataExtractor()
            mock_client = mock_openai_cls.return_value

        result = extractor.extract_metadata_for_chunk("curto")
        # API não deve ter sido chamada
        mock_client.chat.completions.create.assert_not_called()
        assert result["meeting_phase"] == METADATA_DEFAULTS["meeting_phase"]


# ════════════════════════════════════════════════════════════════════════════
# KTIndexingService — unidade (sem stack real)
# ════════════════════════════════════════════════════════════════════════════


class TestKTIndexingServiceUnit:
    """Testa KTIndexingService — singleton e operações sem ChromaDB real."""

    def _make_service(self, isolated_test_dirs: Path) -> object:
        """Cria KTIndexingService via __new__ com diretórios temporários."""
        from src.services.kt_indexing_service import KTIndexingService

        service = KTIndexingService.__new__(KTIndexingService)
        service._transcriptions_dir = isolated_test_dirs / "transcriptions"
        service._vector_db_dir = isolated_test_dirs / "vector_db_nonexistent"
        return service

    def test_singleton_retorna_mesma_instancia(self) -> None:
        """get_kt_indexing_service() retorna sempre a mesma instância."""
        from tests.conftest import _reset_all_singletons
        from src.services.kt_indexing_service import get_kt_indexing_service

        _reset_all_singletons()
        s1 = get_kt_indexing_service()
        s2 = get_kt_indexing_service()
        _reset_all_singletons()  # cleanup

        assert s1 is s2

    def test_force_clean_remove_e_recria_diretorio(self, isolated_test_dirs: Path) -> None:
        """force_clean() remove o conteúdo de vector_db e recria o diretório vazio."""
        from src.services.kt_indexing_service import KTIndexingService

        service = KTIndexingService.__new__(KTIndexingService)
        service._transcriptions_dir = isolated_test_dirs / "transcriptions"
        service._vector_db_dir = isolated_test_dirs / "vector_db"
        # Adicionar arquivo no dir para verificar remoção
        (service._vector_db_dir / "dados.txt").write_text("conteúdo")

        service.force_clean()

        assert service._vector_db_dir.exists()
        assert list(service._vector_db_dir.iterdir()) == []

    def test_run_indexing_sem_jsons_retorna_zero_indexados(self, isolated_test_dirs: Path) -> None:
        """run_indexing() com diretório de transcrições vazio retorna videos_indexed=0."""
        service = self._make_service(isolated_test_dirs)
        stats = service.run_indexing()  # type: ignore[attr-defined]

        assert stats["videos_indexed"] == 0
        assert stats["videos_failed"] == 0

    def test_get_new_json_files_sem_arquivos_retorna_vazio(self, isolated_test_dirs: Path) -> None:
        """_get_new_json_files com dir vazio retorna lista vazia."""
        service = self._make_service(isolated_test_dirs)
        stats: dict[str, Any] = {"videos_already_indexed": 0}

        result = service._get_new_json_files(stats)  # type: ignore[attr-defined]
        assert result == []

    def test_get_new_json_files_sem_chromadb_todos_sao_novos(self, isolated_test_dirs: Path) -> None:
        """Com vector_db inexistente, todos os JSONs são considerados novos."""
        from src.services.kt_indexing_service import KTIndexingService

        transcriptions = isolated_test_dirs / "transcriptions"
        (transcriptions / "reuniao.json").write_text(
            json.dumps({"meeting_id": "id-123", "metadata": {"meeting_id": "id-123"}}),
            encoding="utf-8",
        )

        service = KTIndexingService.__new__(KTIndexingService)
        service._transcriptions_dir = transcriptions
        service._vector_db_dir = isolated_test_dirs / "vector_db_nao_existe"

        stats: dict[str, Any] = {"videos_already_indexed": 0}
        result = service._get_new_json_files(stats)  # type: ignore[attr-defined]

        assert len(result) == 1
        assert result[0].name == "reuniao.json"


# ════════════════════════════════════════════════════════════════════════════
# EmbeddingGenerator — generate_chunk/query_embedding (mock API)
# ════════════════════════════════════════════════════════════════════════════


class TestEmbeddingGeneratorAPI:
    """Testa generate_chunk_embedding e generate_query_embedding com OpenAI mockado."""

    def _make_generator(self) -> object:
        """Cria EmbeddingGenerator com OpenAI mockado."""
        with patch("src.kt_indexing.chromadb_store.openai.OpenAI"):
            from src.kt_indexing.chromadb_store import EmbeddingGenerator

            return EmbeddingGenerator()

    def _configure_mock_embedding(self, gen: object, values: list[float]) -> None:
        """Configura o mock do cliente OpenAI para retornar vetor específico."""
        mock_data = MagicMock()
        mock_data.embedding = values
        gen.client.embeddings.create.return_value.data = [mock_data]  # type: ignore[attr-defined]

    def test_generate_chunk_embedding_retorna_vetor_de_1536(self) -> None:
        """generate_chunk_embedding retorna vetor com 1536 dimensões quando OpenAI responde."""
        from src.kt_indexing.kt_indexing_constants import OPENAI_CONFIG

        gen = self._make_generator()
        mock_embedding = [0.1] * OPENAI_CONFIG["dimensions"]
        self._configure_mock_embedding(gen, mock_embedding)

        result = gen.generate_chunk_embedding(  # type: ignore[attr-defined]
            "Texto do chunk de transcrição", {"client_name": "ClienteX"}
        )

        assert len(result) == OPENAI_CONFIG["dimensions"]
        assert result[0] == 0.1

    def test_generate_query_embedding_delega_para_generate_embedding(self) -> None:
        """generate_query_embedding retorna vetor com 1536 dimensões."""
        from src.kt_indexing.kt_indexing_constants import OPENAI_CONFIG

        gen = self._make_generator()
        mock_embedding = [0.3] * OPENAI_CONFIG["dimensions"]
        self._configure_mock_embedding(gen, mock_embedding)

        result = gen.generate_query_embedding("query de busca FI")  # type: ignore[attr-defined]

        assert len(result) == OPENAI_CONFIG["dimensions"]
        assert result[0] == 0.3

    def test_generate_chunk_embedding_erro_retorna_zeros(self) -> None:
        """Em caso de erro persistente na API, retorna vetor de zeros."""
        from src.kt_indexing.kt_indexing_constants import OPENAI_CONFIG

        gen = self._make_generator()
        gen.client.embeddings.create.side_effect = Exception("API indisponível")  # type: ignore[attr-defined]

        result = gen.generate_chunk_embedding("Texto", {})  # type: ignore[attr-defined]

        assert result == [0.0] * OPENAI_CONFIG["dimensions"]

    def test_generate_query_embedding_erro_retorna_zeros(self) -> None:
        """Em caso de erro na API de query, retorna vetor de zeros."""
        from src.kt_indexing.kt_indexing_constants import OPENAI_CONFIG

        gen = self._make_generator()
        gen.client.embeddings.create.side_effect = Exception("Timeout")  # type: ignore[attr-defined]

        result = gen.generate_query_embedding("query com erro")  # type: ignore[attr-defined]

        assert result == [0.0] * OPENAI_CONFIG["dimensions"]


# ════════════════════════════════════════════════════════════════════════════
# IndexingEngine — métodos de metadata (puro, enable_chromadb=False)
# ════════════════════════════════════════════════════════════════════════════


class TestIndexingEngineMetadata:
    """Testa _build_tldv_metadata, _create_simple_fallback_metadata e _find_input_files."""

    def _make_engine(self, tmp_path: Path) -> object:
        """Cria IndexingEngine com ChromaDB desativado."""
        from src.kt_indexing.indexing_engine import IndexingEngine

        return IndexingEngine(
            input_dir=tmp_path,
            output_dir=tmp_path / "chunks",
            enable_chromadb=False,
            generate_txt_files=False,
        )

    def test_build_tldv_metadata_retorna_video_name_correto(self, tmp_path: Path) -> None:
        """_build_tldv_metadata inclui video_name e speaker nos metadados retornados."""
        engine = self._make_engine(tmp_path)

        video_metadata = {"video_name": "KT MM FI", "meeting_id": "123", "original_url": "https://x.com"}
        segment = {"speaker": "João", "start_time_formatted": "00:00:10", "end_time_formatted": "00:01:00"}
        video_data: dict[str, Any] = {
            "meeting_url": "",
            "happened_at": "2024-01-15T10:00:00Z",
            "duration": 3600,
            "highlights": [],
        }

        result = engine._build_tldv_metadata(  # type: ignore[attr-defined]
            video_metadata=video_metadata,
            segment=segment,
            normalized_name="kt-mm-fi",
            video_data=video_data,
        )

        assert result["video_name"] == "KT MM FI"
        assert result["speaker"] == "João"
        assert result["video_folder"] == "kt-mm-fi"

    def test_build_tldv_metadata_extrai_modulos_sap_do_titulo(self, tmp_path: Path) -> None:
        """_build_tldv_metadata extrai módulos SAP mencionados no nome do vídeo."""
        engine = self._make_engine(tmp_path)

        video_metadata = {"video_name": "KT MM SD", "meeting_id": "", "original_url": ""}
        segment: dict[str, Any] = {"speaker": "", "start_time_formatted": "", "end_time_formatted": ""}
        video_data: dict[str, Any] = {"meeting_url": "", "happened_at": "", "duration": 0, "highlights": []}

        result = engine._build_tldv_metadata(  # type: ignore[attr-defined]
            video_metadata=video_metadata,
            segment=segment,
            normalized_name="kt-mm-sd",
            video_data=video_data,
        )

        assert "MM" in result["sap_modules_title"]
        assert "SD" in result["sap_modules_title"]

    def test_create_simple_fallback_metadata_retorna_defaults(self, tmp_path: Path) -> None:
        """_create_simple_fallback_metadata retorna cópia dos METADATA_DEFAULTS."""
        from src.kt_indexing.kt_indexing_constants import METADATA_DEFAULTS

        engine = self._make_engine(tmp_path)

        result = engine._create_simple_fallback_metadata(  # type: ignore[attr-defined]
            chunk_text="Texto do chunk",
            video_metadata={"video_name": ""},
            segment={},
        )

        assert "sap_modules" in result
        assert "meeting_phase" in result
        assert result["meeting_phase"] == METADATA_DEFAULTS["meeting_phase"]

    def test_create_simple_fallback_metadata_com_cliente_gera_tags(self, tmp_path: Path) -> None:
        """Com cliente detectável no nome do vídeo, searchable_tags contém o cliente."""
        engine = self._make_engine(tmp_path)

        result = engine._create_simple_fallback_metadata(  # type: ignore[attr-defined]
            chunk_text="Texto",
            video_metadata={"video_name": "KT Vissimo MM"},
            segment={},
        )

        assert "VISSIMO" in result["searchable_tags"]

    def test_find_input_files_encontra_apenas_consolidados(self, tmp_path: Path) -> None:
        """_find_input_files retorna apenas arquivos com sufixo _consolidado.json."""
        (tmp_path / "reuniao_consolidado.json").write_text("{}")
        (tmp_path / "arquivo_normal.json").write_text("{}")

        engine = self._make_engine(tmp_path)
        files = engine._find_input_files()  # type: ignore[attr-defined]

        assert len(files) == 1
        assert files[0].name == "reuniao_consolidado.json"
