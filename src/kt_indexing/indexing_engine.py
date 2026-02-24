"""Motor de indexação — domínio kt_indexing.

Orquestra o pipeline completo de indexação: carrega JSONs de transcrição,
normaliza nomes de vídeo, extrai metadados via LLM, gera embeddings
e indexa no ChromaDB.

Pipeline:
1. Carregar e validar JSON de transcrição
2. Normalizar nome do vídeo
3. Para cada segmento:
   - Dividir em partes com overlap
   - Extrair metadados via GPT
   - Gerar embedding e indexar no ChromaDB
   - (Opcional) Gerar arquivo TXT para auditoria
"""

import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config.settings import DIRECTORY_PATHS
from src.kt_indexing.chromadb_store import ChromaDBStore, EmbeddingGenerator
from src.kt_indexing.file_generator import FileGenerator
from src.kt_indexing.kt_indexing_constants import METADATA_DEFAULTS, PERFORMANCE_CONFIG
from src.kt_indexing.kt_indexing_utils import (
    calculate_estimated_processing_time,
    create_client_variations,
    extract_client_name_smart,
    extract_enriched_tldv_fields,
    extract_sap_modules_from_title,
    format_datetime,
    handle_processing_error,
    load_and_validate_json,
)
from src.kt_indexing.llm_metadata_extractor import LLMMetadataExtractor
from src.kt_indexing.text_chunker import TextChunker
from src.kt_indexing.video_normalizer import EnhancedVideoNormalizer
from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)


class IndexingEngine:
    """Motor de indexação de transcrições KT para ChromaDB.

    Pipeline:
    1. Carrega e valida arquivos JSON de transcrição
    2. Para cada vídeo:
       - Normaliza nome do vídeo
       - Processa cada segmento:
         * Divide em partes com overlap
         * Extrai metadados via GPT
         * Indexa no ChromaDB com embedding híbrido
         * (Opcional) Gera TXT para auditoria
    3. Valida e reporta estatísticas finais
    """

    def __init__(
        self,
        input_dir: Path | None = None,
        output_dir: Path | None = None,
        enable_chromadb: bool = True,
        generate_txt_files: bool = True,
    ):
        """Inicializa o motor de indexação.

        Args:
            input_dir: Diretório de entrada com arquivos JSON. Default: DIRECTORY_PATHS["transcriptions"].
            output_dir: Diretório de saída para arquivos TXT. Default: transcriptions/chunks.
            enable_chromadb: Habilitar indexação ChromaDB. Default: True.
            generate_txt_files: Gerar arquivos TXT de auditoria. Default: True.
        """
        self.enable_chromadb = enable_chromadb
        self.generate_txt_files = generate_txt_files
        self.input_dir = Path(input_dir) if input_dir else DIRECTORY_PATHS["transcriptions"]
        self.output_dir = Path(output_dir) if output_dir else DIRECTORY_PATHS["transcriptions"] / "chunks"

        logger.info(f"Diretório de entrada: {self.input_dir}")
        logger.info(f"Diretório de saída: {self.output_dir}")
        logger.info(f"ChromaDB habilitado: {self.enable_chromadb}")
        logger.info(f"Geração de TXT: {self.generate_txt_files}")

        self.video_normalizer = EnhancedVideoNormalizer()
        self.text_chunker = TextChunker()

        try:
            self.metadata_extractor: LLMMetadataExtractor | None = LLMMetadataExtractor()
            self.llm_available = True
        except Exception as e:
            logger.warning(f"Extrator LLM não disponível: {e}")
            self.llm_available = False
            self.metadata_extractor = None

        self.file_generator = FileGenerator()

        self.chromadb_store: ChromaDBStore | None = None
        self.embedding_generator: EmbeddingGenerator | None = None
        if self.enable_chromadb:
            try:
                self.chromadb_store = ChromaDBStore()
                self.embedding_generator = EmbeddingGenerator()
                logger.info("Componentes ChromaDB inicializados")
            except Exception as e:
                logger.error(f"Falha ao inicializar ChromaDB: {e}")
                self.enable_chromadb = False

        self.global_stats: dict[str, Any] = {
            "start_time": None,
            "end_time": None,
            "total_processing_time": 0,
            "videos_processed": 0,
            "videos_failed": 0,
            "segments_processed": 0,
            "parts_created": 0,
            "files_generated": 0,
            "chunks_indexed": 0,
            "embeddings_generated": 0,
            "llm_calls_made": 0,
            "errors_encountered": 0,
            "total_input_size_mb": 0,
            "total_output_size_mb": 0,
        }

    def process_all_videos(self) -> dict[str, Any]:
        """Processa todos os arquivos JSON no diretório de entrada.

        Returns:
            Estatísticas globais de processamento.
        """
        logger.info("Iniciando pipeline completo de indexação")
        self.global_stats["start_time"] = time.time()

        json_files = self._find_input_files()
        if not json_files:
            logger.error("Nenhum arquivo JSON encontrado para processamento")
            return self.global_stats

        logger.info(f"Encontrados {len(json_files)} arquivos JSON para processamento")
        self._log_processing_estimates(json_files)

        for i, json_file in enumerate(json_files):
            try:
                logger.info(f"Processando vídeo {i + 1}/{len(json_files)}: {json_file.name}")
                video_stats = self.process_single_video(json_file)
                self._update_global_stats(video_stats)
                logger.info(f"Vídeo {i + 1} concluído: {video_stats['files_generated']} arquivos gerados")
            except Exception as e:
                logger.error(f"Erro processando {json_file.name}: {e}")
                self.global_stats["videos_failed"] += 1
                handle_processing_error(e, f"video_processing: {json_file.name}")

        self._finalize_processing()
        return self.global_stats

    def process_single_video(self, json_file: Path) -> dict[str, Any]:
        """Processa um único arquivo JSON de transcrição.

        Args:
            json_file: Caminho para o arquivo JSON.

        Returns:
            Estatísticas de processamento do vídeo.
        """
        self.video_file = json_file
        video_stats: dict[str, Any] = {
            "video_file": str(json_file),
            "segments_processed": 0,
            "parts_created": 0,
            "files_generated": 0,
            "llm_calls_made": 0,
            "processing_time": 0,
            "errors": [],
        }

        start_time = time.time()
        try:
            video_data = load_and_validate_json(json_file)
            video_metadata = video_data["metadata"]
            segments = video_data["transcript"]["segments"]

            logger.info(f"   {len(segments)} segmentos carregados")

            normalized_name = self.video_normalizer.normalize(video_metadata["video_name"])["slug"]
            logger.info(f"   Nome normalizado: {normalized_name}")

            video_stats.update(
                self._process_video_segments(
                    segments=segments,
                    video_metadata=video_metadata,
                    normalized_name=normalized_name,
                    video_data=video_data,
                )
            )

            video_stats["processing_time"] = time.time() - start_time
            self.global_stats["videos_processed"] += 1

        except Exception as e:
            video_stats["errors"].append(str(e))
            video_stats["processing_time"] = time.time() - start_time
            raise

        return video_stats

    def process_json_file(self, json_file: Path) -> list[dict[str, Any]]:
        """Processa um JSON de transcrição e retorna lista de chunks para indexação externa.

        Processa o arquivo sem executar ChromaDB internamente, retornando os dados
        para que o chamador (ex: arq_worker) possa gerar embeddings e indexar.

        Args:
            json_file: Caminho para o arquivo JSON normalizado.

        Returns:
            Lista de dicts com keys: id, content, text, metadata.
        """
        chunks: list[dict[str, Any]] = []

        video_data = load_and_validate_json(json_file)
        video_metadata = video_data["metadata"]
        segments = video_data["transcript"]["segments"]

        self.video_file = json_file
        normalized_name = self.video_normalizer.normalize(video_metadata["video_name"])["slug"]

        for segment in segments:
            segment_text = segment.get("text", "")
            if not segment_text:
                continue

            parts = self.text_chunker.split_segment_into_parts(segment_text)

            for part in parts:
                if self.llm_available and self.metadata_extractor:
                    extracted_metadata = self.metadata_extractor.extract_metadata_for_chunk(
                        chunk_text=part.text,
                        video_name=video_metadata.get("video_name", ""),
                        client_name=video_metadata.get("client_name", ""),
                    )
                else:
                    extracted_metadata = self._create_simple_fallback_metadata(part.text, video_metadata, segment)

                tldv_metadata = self._build_tldv_metadata(
                    video_metadata, segment, normalized_name, video_data, str(json_file.name)
                )

                chunk_id = f"{normalized_name}_segments_{segment['id']:03d}_part_{part.part_index}"

                chunks.append(
                    {
                        "id": chunk_id,
                        "content": part.text,
                        "text": part.text,
                        "metadata": {**tldv_metadata, **extracted_metadata},
                    }
                )

        logger.info(f"[process_json_file] {len(chunks)} chunks gerados de {json_file.name}")
        return chunks

    def _process_video_segments(
        self,
        segments: list[dict],
        video_metadata: dict[str, Any],
        normalized_name: str,
        video_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Processa todos os segmentos de um vídeo.

        Args:
            segments: Lista de segmentos.
            video_metadata: Metadados do vídeo.
            normalized_name: Nome normalizado do vídeo.
            video_data: Dados completos do vídeo.

        Returns:
            Estatísticas de processamento dos segmentos.
        """
        stats = {
            "segments_processed": 0,
            "parts_created": 0,
            "files_generated": 0,
            "llm_calls_made": 0,
            "chunks_indexed": 0,
            "embeddings_generated": 0,
        }

        video_output_dir = self.output_dir / normalized_name
        if self.generate_txt_files:
            video_output_dir.mkdir(parents=True, exist_ok=True)

        for segment in segments:
            try:
                segment_id = segment["id"]
                segment_text = segment["text"]

                parts = self.text_chunker.split_segment_into_parts(segment_text)

                for part in parts:
                    part_stats = self._process_single_part(
                        part=part,
                        segment=segment,
                        video_metadata=video_metadata,
                        normalized_name=normalized_name,
                        video_output_dir=video_output_dir,
                        video_data=video_data,
                    )

                    stats["parts_created"] += 1
                    stats["files_generated"] += part_stats["file_created"]
                    stats["llm_calls_made"] += part_stats["llm_call_made"]
                    stats["chunks_indexed"] += part_stats.get("chunks_indexed", 0)
                    stats["embeddings_generated"] += part_stats.get("embeddings_generated", 0)

                stats["segments_processed"] += 1

                log_every = PERFORMANCE_CONFIG.get("batch_size", 10)
                if segment_id % log_every == 0:
                    logger.debug(f"Segmento {segment_id} processado")

            except Exception as e:
                logger.error(f"Erro processando segmento {segment.get('id', 'unknown')}: {e}")
                handle_processing_error(e, f"segment_processing: {segment.get('id')}")
                continue

        return stats

    def _process_single_part(
        self,
        part: Any,
        segment: dict[str, Any],
        video_metadata: dict[str, Any],
        normalized_name: str,
        video_output_dir: Path,
        video_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Processa uma única parte de um segmento.

        Args:
            part: Objeto ChunkPart.
            segment: Metadados do segmento.
            video_metadata: Metadados do vídeo.
            normalized_name: Nome normalizado do vídeo.
            video_output_dir: Diretório de saída do vídeo.
            video_data: Dados completos do vídeo.

        Returns:
            Estatísticas de processamento da parte.
        """
        part_stats = {"file_created": 0, "llm_call_made": 0, "chunks_indexed": 0, "embeddings_generated": 0}

        try:
            if self.llm_available and self.metadata_extractor:
                extracted_metadata = self.metadata_extractor.extract_metadata_for_chunk(
                    chunk_text=part.text,
                    video_name=video_metadata.get("video_name", ""),
                    client_name=video_metadata.get("client_name", ""),
                )
                part_stats["llm_call_made"] = 1
            else:
                extracted_metadata = self._create_simple_fallback_metadata(part.text, video_metadata, segment)

            tldv_metadata = self._build_tldv_metadata(
                video_metadata, segment, normalized_name, video_data, str(self.video_file.name)
            )

            filename = f"{normalized_name}_segments_{segment['id']:03d}_part_{part.part_index}.txt"
            chunk_id = f"{normalized_name}_segments_{segment['id']:03d}_part_{part.part_index}"

            if self.enable_chromadb:
                try:
                    self._index_chunk_to_chromadb(
                        chunk_id=chunk_id,
                        chunk_text=part.text,
                        tldv_metadata=tldv_metadata,
                        customized_metadata=extracted_metadata,
                    )
                    part_stats["chunks_indexed"] = 1
                    part_stats["embeddings_generated"] = 1
                except Exception as e:
                    logger.error(f"Falha ao indexar chunk {chunk_id} no ChromaDB: {e}")

            if self.generate_txt_files:
                try:
                    self.file_generator.create_chunk_txt_file(
                        filename=filename,
                        output_dir=video_output_dir,
                        tldv_metadata=tldv_metadata,
                        customized_metadata=extracted_metadata,
                        chunk_text=part.text,
                    )
                    part_stats["file_created"] = 1
                except Exception as e:
                    logger.warning(f"Falha ao gerar TXT {filename}: {e}")

        except Exception as e:
            logger.error(f"Falha ao processar parte {part.part_index}: {e}")
            raise

        return part_stats

    def _build_tldv_metadata(
        self,
        video_metadata: dict[str, Any],
        segment: dict[str, Any],
        normalized_name: str,
        video_data: dict[str, Any],
        original_filename: str | None = None,
    ) -> dict[str, Any]:
        """Constrói seção de metadados TLDV com campos enriquecidos.

        Args:
            video_metadata: Metadados originais do vídeo.
            segment: Dados do segmento.
            normalized_name: Nome normalizado do vídeo.
            video_data: Dados completos do vídeo.
            original_filename: Nome do arquivo original.

        Returns:
            Dicionário de metadados TLDV.
        """
        client_name = extract_client_name_smart(video_name=video_metadata.get("video_name", ""))
        sap_modules_list = extract_sap_modules_from_title(video_metadata.get("video_name", ""))
        sap_modules_title = ", ".join(sap_modules_list) if sap_modules_list else ""
        enriched_fields = extract_enriched_tldv_fields(video_data)

        tldv_metadata: dict[str, Any] = {
            "video_name": video_metadata.get("video_name", ""),
            "meeting_id": video_metadata.get("meeting_id", ""),
            "original_url": video_metadata.get("original_url", ""),
            "video_folder": normalized_name,
            "speaker": segment.get("speaker", ""),
            "start_time_formatted": segment.get("start_time_formatted", ""),
            "end_time_formatted": segment.get("end_time_formatted", ""),
            "processing_date": format_datetime(),
            "client_name": client_name,
            "sap_modules_title": sap_modules_title,
        }

        tldv_metadata.update(enriched_fields)
        return tldv_metadata

    def _create_simple_fallback_metadata(
        self, chunk_text: str, video_metadata: dict[str, Any], segment: dict[str, Any]
    ) -> dict[str, Any]:
        """Cria metadados de fallback quando LLM não está disponível.

        Args:
            chunk_text: Texto do chunk.
            video_metadata: Metadados do vídeo.
            segment: Metadados do segmento.

        Returns:
            Metadados simples.
        """
        metadata = METADATA_DEFAULTS.copy()
        video_name = video_metadata.get("video_name", "")
        client_name = extract_client_name_smart(video_name=video_name)

        if client_name and client_name != "CLIENTE_DESCONHECIDO":
            metadata["client_variations"] = create_client_variations(client_name)
            metadata["searchable_tags"] = [client_name]

        sap_modules = extract_sap_modules_from_title(video_name)
        if sap_modules:
            metadata["sap_modules"] = sap_modules

        return metadata

    def _find_input_files(self) -> list[Path]:
        """Localiza todos os arquivos JSON consolidados no diretório de entrada."""
        json_files = list(self.input_dir.glob("*_consolidado.json"))
        json_files.sort()
        return json_files

    def _log_processing_estimates(self, json_files: list[Path]) -> None:
        """Registra estimativas de processamento."""
        total_size_mb = sum(f.stat().st_size for f in json_files) / (1024 * 1024)
        self.global_stats["total_input_size_mb"] = total_size_mb

        avg_segments_per_file = 200
        total_estimated_segments = len(json_files) * avg_segments_per_file
        estimated_seconds = calculate_estimated_processing_time(total_estimated_segments)

        logger.info(f"Tamanho total de entrada: {total_size_mb:.1f} MB")
        logger.info(f"Segmentos estimados: ~{total_estimated_segments}")
        logger.info(f"Tempo estimado: ~{estimated_seconds / 60:.1f} minutos")

        if not self.llm_available:
            logger.warning("LLM não disponível — usando metadados de fallback")

    def _update_global_stats(self, video_stats: dict[str, Any]) -> None:
        """Atualiza estatísticas globais com estatísticas do vídeo."""
        self.global_stats["segments_processed"] += video_stats["segments_processed"]
        self.global_stats["parts_created"] += video_stats["parts_created"]
        self.global_stats["files_generated"] += video_stats["files_generated"]
        self.global_stats["llm_calls_made"] += video_stats["llm_calls_made"]
        self.global_stats["chunks_indexed"] += video_stats.get("chunks_indexed", 0)
        self.global_stats["embeddings_generated"] += video_stats.get("embeddings_generated", 0)
        self.global_stats["errors_encountered"] += len(video_stats.get("errors", []))

    def _finalize_processing(self) -> None:
        """Finaliza processamento com estatísticas finais."""
        self.global_stats["end_time"] = time.time()
        self.global_stats["total_processing_time"] = self.global_stats["end_time"] - self.global_stats["start_time"]

        try:
            total_output_size = sum(f.stat().st_size for f in self.output_dir.rglob("*.txt"))
            self.global_stats["total_output_size_mb"] = total_output_size / (1024 * 1024)
        except Exception:
            self.global_stats["total_output_size_mb"] = 0

        logger.info("Pipeline de indexação concluído!")
        logger.info(f"Vídeos processados: {self.global_stats['videos_processed']}")
        logger.info(f"Vídeos com falha: {self.global_stats['videos_failed']}")
        logger.info(f"Segmentos processados: {self.global_stats['segments_processed']}")
        logger.info(f"Partes criadas: {self.global_stats['parts_created']}")
        logger.info(f"Arquivos TXT gerados: {self.global_stats['files_generated']}")
        logger.info(f"Chunks indexados: {self.global_stats['chunks_indexed']}")
        logger.info(f"LLM calls: {self.global_stats['llm_calls_made']}")
        logger.info(f"Erros: {self.global_stats['errors_encountered']}")
        logger.info(f"Tempo total: {self.global_stats['total_processing_time']:.1f}s")

    def _index_chunk_to_chromadb(
        self, chunk_id: str, chunk_text: str, tldv_metadata: dict[str, Any], customized_metadata: dict[str, Any]
    ) -> bool:
        """Indexa chunk no ChromaDB com geração de embedding.

        Args:
            chunk_id: Identificador único do chunk.
            chunk_text: Conteúdo textual do chunk.
            tldv_metadata: Metadados TLDV.
            customized_metadata: Metadados extraídos pelo GPT.

        Returns:
            True se indexado com sucesso.
        """
        if not self.chromadb_store or not self.embedding_generator:
            return False

        try:
            normalized_chunk_text = self._normalize_utf8_text(chunk_text)

            combined_metadata: dict[str, Any] = {}
            combined_metadata.update(tldv_metadata)
            combined_metadata.update(customized_metadata)

            if "client_name" in tldv_metadata and tldv_metadata["client_name"] != "CLIENTE_DESCONHECIDO":
                combined_metadata["client_name"] = tldv_metadata["client_name"]

            combined_metadata["processing_date"] = datetime.now().isoformat()

            normalized_metadata = self._normalize_utf8_metadata(combined_metadata)
            cleaned_metadata = self.chromadb_store._clean_metadata(normalized_metadata)

            embedding = self.embedding_generator.generate_chunk_embedding(
                chunk_text=normalized_chunk_text, metadata=cleaned_metadata
            )

            if not embedding or len(embedding) != 1536:
                logger.error(f"Embedding inválido gerado para {chunk_id}")
                return False

            success = self.chromadb_store.add_chunk(
                chunk_id=chunk_id,
                content=normalized_chunk_text,
                metadata=cleaned_metadata,
                embedding=embedding,
            )

            if success:
                self.global_stats["chunks_indexed"] += 1
                self.global_stats["embeddings_generated"] += 1

            return success

        except Exception as e:
            logger.error(f"Falha ao indexar chunk {chunk_id}: {e}")
            return False

    def _normalize_utf8_text(self, text: str) -> str:
        """Normaliza texto UTF-8 para evitar corrupção de encoding.

        Args:
            text: Texto de entrada.

        Returns:
            Texto normalizado em UTF-8.
        """
        if not isinstance(text, str):
            text = str(text)
        try:
            normalized = unicodedata.normalize("NFKC", text)
            normalized = normalized.replace("\uFFFD", "?")
            normalized = normalized.encode("utf-8", errors="replace").decode("utf-8")
            return normalized
        except Exception as e:
            logger.warning(f"Falha na normalização UTF-8: {e}")
            return text.encode("utf-8", errors="replace").decode("utf-8")

    def _normalize_utf8_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Normaliza encoding UTF-8 em dicionário de metadados.

        Args:
            metadata: Dicionário de metadados.

        Returns:
            Metadados com strings normalizadas.
        """
        normalized_metadata: dict[str, Any] = {}
        for key, value in metadata.items():
            normalized_key = self._normalize_utf8_text(key) if isinstance(key, str) else key
            if isinstance(value, str):
                normalized_value: Any = self._normalize_utf8_text(value)
            elif isinstance(value, list):
                normalized_value = [
                    self._normalize_utf8_text(item) if isinstance(item, str) else item for item in value
                ]
            elif isinstance(value, dict):
                normalized_value = self._normalize_utf8_metadata(value)
            else:
                normalized_value = value
            normalized_metadata[normalized_key] = normalized_value
        return normalized_metadata
