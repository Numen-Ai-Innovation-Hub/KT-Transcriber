"""
Gera arquivos TXT estruturados com seções de metadados TLDV e CUSTOMIZADOS.
"""

from pathlib import Path
from typing import Any

from src.kt_indexing.kt_indexing_constants import FILE_CONFIG, VALIDATION_RULES
from src.kt_indexing.kt_indexing_utils import format_datetime, safe_filename
from utils.exception_setup import ApplicationError
from utils.logger_setup import LoggerManager


class FileGenerator:
    """
    Responsável pela geração de arquivos TXT estruturados com seções de metadados.

    Estrutura do arquivo gerado:
    - Seção TLDV: Dados originais da transcrição
    - Seção CUSTOMIZADOS: Metadados extraídos via GPT
    - Seção CHUNK: Conteúdo textual com sobreposição
    """

    def __init__(self) -> None:
        self.logger = LoggerManager.get_logger(__name__)
        self.encoding = FILE_CONFIG["encoding"]
        self.separator = FILE_CONFIG["separator"]

    def create_chunk_txt_file(
        self,
        filename: str,
        output_dir: Path,
        tldv_metadata: dict[str, Any],
        customized_metadata: dict[str, Any],
        chunk_text: str,
    ) -> Path:
        """
        Cria um arquivo TXT estruturado para um chunk de transcrição.

        Args:
            filename: Nome do arquivo a ser criado.
            output_dir: Diretório de destino para o arquivo.
            tldv_metadata: Metadados originais da transcrição TLDV.
            customized_metadata: Metadados extraídos via GPT.
            chunk_text: Conteúdo textual do chunk.

        Returns:
            Caminho do arquivo criado.

        Raises:
            ApplicationError: Se a escrita do arquivo falhar.
        """
        safe_name = safe_filename(filename, FILE_CONFIG["max_filename_length"])
        file_path = output_dir / safe_name

        content = self._build_file_content(tldv_metadata, customized_metadata, chunk_text)

        try:
            with open(file_path, "w", encoding=self.encoding) as f:
                f.write(content)

            self.logger.debug(f"Arquivo TXT criado: {file_path}")
            return file_path

        except Exception as e:
            raise ApplicationError(
                f"Falha ao criar arquivo {file_path}",
                status_code=500,
                error_code="INTERNAL_ERROR",
                context={"file": str(file_path)},
            ) from e

    def _build_file_content(
        self, tldv_metadata: dict[str, Any], customized_metadata: dict[str, Any], chunk_text: str
    ) -> str:
        """
        Monta o conteúdo completo do arquivo combinando todas as seções.

        Args:
            tldv_metadata: Metadados originais da transcrição TLDV.
            customized_metadata: Metadados extraídos via GPT.
            chunk_text: Conteúdo textual do chunk.

        Returns:
            Conteúdo completo do arquivo como string.
        """
        content_lines: list[str] = []

        content_lines.extend(self._build_tldv_section(tldv_metadata))
        content_lines.append(self.separator)
        content_lines.extend(self._build_customized_section(customized_metadata))
        content_lines.append(self.separator)
        content_lines.extend(self._build_chunk_section(chunk_text))

        return "\n".join(content_lines)

    def _build_tldv_section(self, metadata: dict[str, Any]) -> list[str]:
        """
        Constrói as linhas da seção TLDV com os campos de metadados originais.

        Args:
            metadata: Dicionário com metadados da transcrição TLDV.

        Returns:
            Lista de linhas formatadas para a seção TLDV.
        """
        lines = ["TLDV:"]

        tldv_fields: list[tuple[str, Any]] = [
            ("video_name", ""),
            ("meeting_id", ""),
            ("original_url", ""),
            ("video_folder", ""),
            ("speaker", ""),
            ("start_time_formatted", ""),
            ("end_time_formatted", ""),
            ("processing_date", format_datetime()),
            ("client_name", ""),
            ("sap_modules_title", ""),
            ("participants_list", []),
            ("highlights_summary", []),
            ("decisions_summary", []),
        ]

        for field_name, default_value in tldv_fields:
            value = metadata.get(field_name, default_value)
            formatted_value = str(value)
            lines.append(f"{field_name}: {formatted_value}")

        return lines

    def _build_customized_section(self, metadata: dict[str, Any]) -> list[str]:
        """
        Constrói as linhas da seção CUSTOMIZADOS com os metadados extraídos via GPT.

        Args:
            metadata: Dicionário com metadados extraídos via GPT.

        Returns:
            Lista de linhas formatadas para a seção CUSTOMIZADOS.
        """
        lines = ["CUSTOMIZADOS:"]

        customized_fields: list[tuple[str, Any]] = [
            ("sap_modules", []),
            ("systems", []),
            ("transactions", []),
            ("integrations", []),
            ("technical_terms", []),
            ("participants_mentioned", []),
            ("speaker_role", "Participante"),
            ("meeting_phase", "DISCUSSAO_GERAL"),
            ("meeting_date", ""),
            ("topics", []),
            ("content_type", "EXPLICAÇÃO"),
            ("business_impact", "MEDIUM"),
            ("knowledge_area", "BUSINESS"),
            ("key_decisions", []),
            ("client_variations", []),
            ("searchable_tags", []),
        ]

        for field_name, default_value in customized_fields:
            value = metadata.get(field_name, default_value)
            formatted_value = str(value)
            lines.append(f"{field_name}: {formatted_value}")

        return lines

    def _build_chunk_section(self, chunk_text: str) -> list[str]:
        """
        Constrói as linhas da seção CHUNK com o conteúdo textual do trecho.

        Args:
            chunk_text: Texto do chunk de transcrição.

        Returns:
            Lista de linhas para a seção CHUNK.
        """
        lines = ["CHUNK:"]
        chunk_lines = chunk_text.strip().split("\n")
        lines.extend(chunk_lines)
        return lines

    def create_batch_files(
        self, chunks_data: list[dict[str, Any]], output_base_dir: Path, video_folder_name: str
    ) -> list[Path]:
        """
        Cria múltiplos arquivos TXT para um lote de chunks de um vídeo.

        Erros individuais são logados como warnings e não interrompem o lote.

        Args:
            chunks_data: Lista de dicionários com dados de cada chunk.
            output_base_dir: Diretório base para os arquivos gerados.
            video_folder_name: Nome da subpasta do vídeo dentro do diretório base.

        Returns:
            Lista de caminhos dos arquivos criados com sucesso.
        """
        created_files: list[Path] = []
        video_output_dir = output_base_dir / video_folder_name

        self.logger.info(f"Criando {len(chunks_data)} arquivos TXT em {video_output_dir}")

        for chunk_data in chunks_data:
            try:
                file_path = self.create_chunk_txt_file(
                    filename=chunk_data["filename"],
                    output_dir=video_output_dir,
                    tldv_metadata=chunk_data["tldv_metadata"],
                    customized_metadata=chunk_data["customized_metadata"],
                    chunk_text=chunk_data["chunk_text"],
                )
                created_files.append(file_path)

            except Exception as e:
                self.logger.warning(f"Falha ao criar arquivo {chunk_data.get('filename', 'desconhecido')}: {e}")
                continue

        self.logger.info(f"Arquivos criados com sucesso: {len(created_files)}")
        return created_files

    def validate_generated_file(self, file_path: Path) -> dict[str, Any]:
        """
        Valida a estrutura e o conteúdo de um arquivo TXT gerado.

        Args:
            file_path: Caminho do arquivo a ser validado.

        Returns:
            Dicionário com resultado da validação contendo as chaves:
            ``is_valid``, ``file_path``, ``errors``, ``warnings``, ``metadata``.
        """
        validation: dict[str, Any] = {
            "is_valid": False,
            "file_path": str(file_path),
            "errors": [],
            "warnings": [],
            "metadata": {},
        }

        try:
            if not file_path.exists():
                validation["errors"].append("Arquivo não encontrado")
                return validation

            with open(file_path, encoding=self.encoding) as f:
                content = f.read()

            for section in VALIDATION_RULES["required_sections"]:
                if section not in content:
                    validation["errors"].append(f"Seção obrigatória ausente: {section}")

            sections = self._parse_file_sections(content)

            tldv_validation = self._validate_tldv_section(sections.get("tldv", ""))
            validation["errors"].extend(tldv_validation["errors"])
            validation["warnings"].extend(tldv_validation["warnings"])

            customized_validation = self._validate_customized_section(sections.get("customizados", ""))
            validation["errors"].extend(customized_validation["errors"])
            validation["warnings"].extend(customized_validation["warnings"])

            chunk_validation = self._validate_chunk_section(sections.get("chunk", ""))
            validation["errors"].extend(chunk_validation["errors"])
            validation["warnings"].extend(chunk_validation["warnings"])

            validation["is_valid"] = len(validation["errors"]) == 0

            validation["metadata"] = {
                "file_size_bytes": file_path.stat().st_size,
                "content_length": len(content),
                "chunk_length": len(sections.get("chunk", "")),
                "sections_found": list(sections.keys()),
            }

        except Exception as e:
            validation["errors"].append(f"Erro de validação: {str(e)}")

        return validation

    def _parse_file_sections(self, content: str) -> dict[str, str]:
        """
        Divide o conteúdo do arquivo nas seções TLDV, CUSTOMIZADOS e CHUNK.

        Args:
            content: Conteúdo completo do arquivo TXT.

        Returns:
            Dicionário mapeando nome da seção para seu conteúdo.
        """
        sections: dict[str, str] = {}
        parts = content.split(self.separator)

        for part in parts:
            part = part.strip()
            if part.startswith("TLDV:"):
                sections["tldv"] = part
            elif part.startswith("CUSTOMIZADOS:"):
                sections["customizados"] = part
            elif part.startswith("CHUNK:"):
                sections["chunk"] = part[6:].strip()

        return sections

    def _validate_tldv_section(self, section_content: str) -> dict[str, list[str]]:
        """
        Valida a presença dos campos obrigatórios na seção TLDV.

        Args:
            section_content: Conteúdo textual da seção TLDV.

        Returns:
            Dicionário com listas ``errors`` e ``warnings``.
        """
        validation: dict[str, list[str]] = {"errors": [], "warnings": []}

        for field in VALIDATION_RULES["required_tldv_fields"]:
            if f"{field}:" not in section_content:
                validation["errors"].append(f"Campo TLDV ausente: {field}")

        return validation

    def _validate_customized_section(self, section_content: str) -> dict[str, list[str]]:
        """
        Valida a presença dos campos obrigatórios na seção CUSTOMIZADOS.

        Args:
            section_content: Conteúdo textual da seção CUSTOMIZADOS.

        Returns:
            Dicionário com listas ``errors`` e ``warnings``.
        """
        validation: dict[str, list[str]] = {"errors": [], "warnings": []}

        for field in VALIDATION_RULES["required_customized_fields"]:
            if f"{field}:" not in section_content:
                validation["errors"].append(f"Campo CUSTOMIZADOS ausente: {field}")

        return validation

    def _validate_chunk_section(self, chunk_content: str) -> dict[str, list[str]]:
        """
        Valida o tamanho e conteúdo da seção CHUNK.

        Args:
            chunk_content: Texto da seção CHUNK.

        Returns:
            Dicionário com listas ``errors`` e ``warnings``.
        """
        validation: dict[str, list[str]] = {"errors": [], "warnings": []}

        chunk_length = len(chunk_content)

        if chunk_length < VALIDATION_RULES["min_chunk_length"]:
            validation["warnings"].append(
                f"Chunk muito curto: {chunk_length} chars (mínimo: {VALIDATION_RULES['min_chunk_length']})"
            )

        if chunk_length > VALIDATION_RULES["max_chunk_length"]:
            validation["warnings"].append(
                f"Chunk muito longo: {chunk_length} chars (máximo: {VALIDATION_RULES['max_chunk_length']})"
            )

        if not chunk_content.strip():
            validation["errors"].append("Seção CHUNK está vazia")

        return validation

    def get_generation_stats(self, created_files: list[Path | str]) -> dict[str, Any]:
        """
        Calcula estatísticas de geração para um lote de arquivos criados.

        Args:
            created_files: Lista de caminhos dos arquivos gerados.

        Returns:
            Dicionário com estatísticas do lote: total de arquivos, tamanho,
            arquivos válidos, erros de validação e taxa de sucesso.
        """
        if not created_files:
            return {
                "total_files": 0,
                "total_size_bytes": 0,
                "avg_file_size": 0,
                "valid_files": 0,
                "validation_errors": 0,
            }

        total_size = 0
        valid_files = 0
        total_errors = 0

        for file_path in created_files:
            try:
                if isinstance(file_path, str):
                    file_path = Path(file_path)

                if file_path.exists():
                    total_size += file_path.stat().st_size

                    validation = self.validate_generated_file(file_path)
                    if validation["is_valid"]:
                        valid_files += 1
                    total_errors += len(validation["errors"])

            except Exception as e:
                self.logger.warning(f"Não foi possível processar estatísticas para {file_path}: {e}")
                continue

        return {
            "total_files": len(created_files),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "avg_file_size": total_size / len(created_files) if created_files else 0,
            "valid_files": valid_files,
            "validation_errors": total_errors,
            "success_rate": (valid_files / len(created_files) * 100) if created_files else 0,
        }


def create_txt_file(
    filename: str,
    output_dir: Path,
    tldv_metadata: dict[str, Any],
    customized_metadata: dict[str, Any],
    chunk_text: str,
) -> Path:
    """
    Função de conveniência para criar um arquivo TXT de chunk sem instanciar FileGenerator diretamente.

    Args:
        filename: Nome do arquivo a ser criado.
        output_dir: Diretório de destino para o arquivo.
        tldv_metadata: Metadados originais da transcrição TLDV.
        customized_metadata: Metadados extraídos via GPT.
        chunk_text: Conteúdo textual do chunk.

    Returns:
        Caminho do arquivo criado.
    """
    generator = FileGenerator()
    return generator.create_chunk_txt_file(
        filename=filename,
        output_dir=output_dir,
        tldv_metadata=tldv_metadata,
        customized_metadata=customized_metadata,
        chunk_text=chunk_text,
    )
