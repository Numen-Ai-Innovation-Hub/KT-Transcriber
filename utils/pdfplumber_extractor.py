"""
PDF Extractor - 100% Standalone e Reutilizável.

NÃO usa logging interno - retorna resultados ou lança exceções built-in.
NÃO usa exceções customizadas - apenas stdlib.
NÃO depende de configurações - tudo via parâmetros.
NÃO gerencia cache - responsabilidade da camada de aplicação.
"""

import importlib
import importlib.util
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DocumentContent:
    """Estrutura clara do conteúdo extraído"""

    text_content: str
    metadata: dict[str, Any]
    extraction_stats: dict[str, int]
    extraction_method: str
    duration_seconds: float


class PDFPlumberExtractor:
    """
    Extrator genérico de PDFs com pdfplumber.

    100% reutilizável - sem logging interno, sem lógica de negócio.
    """

    def __init__(self, extracted_dir: str | Path) -> None:
        """
        Inicializa o extrator com diretório de auditoria.

        Args:
            extracted_dir: Diretório para arquivos extraídos (injetado via DIRECTORY_PATHS["extracted"])
        """
        self.extracted_dir = Path(extracted_dir)
        self.extracted_dir.mkdir(parents=True, exist_ok=True)

    def extract_document_complete(
        self,
        file_path: str,
        project_id: str,
        extracted_txt_pattern: str,
        extracted_image_pattern: str,
        delimiter: str = "─" * 120,
    ) -> DocumentContent:
        """
        Extração completa de documento PDF.

        Funcionalidades:
        - Extração de texto, tabelas e imagens
        - Auditoria automática em TXT

        Args:
            file_path: Caminho absoluto para o arquivo PDF
            project_id: ID do projeto (ex: OTC3178) - usado para criar pasta e nomear arquivos
            extracted_txt_pattern: Pattern para nome do arquivo TXT de auditoria (injetado via FILE_PATTERNS)
            extracted_image_pattern: Pattern para nome das imagens extraídas (injetado via FILE_PATTERNS)
            delimiter: Caractere delimitador para auditoria (padrão: ─ * 120)

        Returns:
            DocumentContent com texto extraído e metadados

        Raises:
            FileNotFoundError: Se arquivo não existe
            ValueError: Se arquivo é inválido (vazio, não-PDF)
            ImportError: Se pdfplumber não está instalado
            IOError: Se falha ao ler/processar PDF
        """
        start_time = time.time()

        # Validações iniciais
        self._validate_prerequisites(file_path)

        # Diretório específico para este documento (usa project_id ao invés de filename completo)
        doc_output_dir = self.extracted_dir / project_id
        doc_output_dir.mkdir(parents=True, exist_ok=True)

        # Extração com pdfplumber
        try:
            content = self._extract_with_pdfplumber(file_path, doc_output_dir, extracted_image_pattern, project_id)
            content.duration_seconds = time.time() - start_time
            content.extraction_method = "pdfplumber"

            # Validação final
            self._validate_extraction_result(content)

            # Salvar arquivo TXT de auditoria usando pattern injetado
            audit_filename = extracted_txt_pattern
            self._save_audit_txt(content, file_path, doc_output_dir, audit_filename, delimiter)

            return content

        except Exception as e:
            # Re-lança exceções built-in sem modificar
            if isinstance(e, (ValueError, FileNotFoundError, ImportError, IOError)):
                raise
            # Exceções inesperadas viram IOError
            raise OSError(f"Falha ao processar PDF {os.path.basename(file_path)}: {e}") from e

    def _validate_prerequisites(self, file_path: str) -> None:
        """
        Valida pré-requisitos antes da extração.

        Raises:
            FileNotFoundError: Se arquivo não existe
            ValueError: Se arquivo é inválido (vazio, não-PDF)
            ImportError: Se pdfplumber não está instalado
        """
        # Arquivo existe?
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

        # Arquivo tem tamanho válido?
        file_size = os.path.getsize(file_path)
        if file_size <= 0:
            raise ValueError(f"Arquivo está vazio (0 bytes): {file_path}")

        # Arquivo é .pdf?
        if not file_path.lower().endswith(".pdf"):
            raise ValueError(f"Apenas arquivos .pdf são suportados: {file_path}")

        # pdfplumber disponível?
        if importlib.util.find_spec("pdfplumber") is None:
            raise ImportError("Biblioteca pdfplumber não está instalada. Instale com: pip install pdfplumber")

    def _extract_with_pdfplumber(
        self, file_path: str, output_dir: Path, image_pattern: str, project_id: str
    ) -> DocumentContent:
        """Extração completa usando pdfplumber otimizado"""

        text = ""
        images_detected = 0
        stats = {"pages": 0, "tables": 0, "images": 0, "paragraphs": 0}

        try:
            pdfplumber_mod = importlib.import_module("pdfplumber")
            with pdfplumber_mod.open(file_path) as pdf:
                stats["pages"] = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages):
                    # Identificação de páginas
                    page_text = f"\n--- Página {page_num + 1} ---\n"

                    # Extração de tabelas com método otimizado
                    tables = page.extract_tables()
                    if tables:
                        for table_num, table in enumerate(tables):
                            page_text += f"\n### Tabela {table_num + 1}:\n"

                            # Determina número máximo de colunas
                            max_cols = 0
                            if table:
                                max_cols = max(len(row) for row in table if row) if table else 0

                            # Processa TODAS as linhas (incluindo vazias)
                            for row in table:
                                if row:  # Se a linha não é None
                                    # Limpa células (converte None para "")
                                    clean_row = [str(cell).strip() if cell is not None else "" for cell in row]

                                    # Padroniza: todas as linhas com mesmo número de colunas
                                    while len(clean_row) < max_cols:
                                        clean_row.append("")

                                    # Trunca se tiver colunas extras
                                    clean_row = clean_row[:max_cols]

                                    page_text += "| " + " | ".join(clean_row) + " |\n"
                                else:
                                    # Linha vazia - cria linha com células vazias
                                    empty_row = [""] * max_cols
                                    page_text += "| " + " | ".join(empty_row) + " |\n"

                            page_text += "\n"
                            stats["tables"] += 1

                    # Extrai texto normal
                    regular_text = page.extract_text()
                    if regular_text:
                        page_text += regular_text + "\n"
                        # Conta parágrafos aproximadamente
                        stats["paragraphs"] += len([p for p in regular_text.split("\n") if p.strip()])

                    # Identificação e salvamento de imagens
                    images = page.images
                    if images:
                        for img_index, img in enumerate(images):
                            images_detected += 1
                            stats["images"] += 1

                            # Cria nome único para a imagem usando pattern injetado
                            img_filename = image_pattern.format(
                                project_id=project_id,
                                page=page_num + 1,
                                index=img_index + 1,
                            )
                            img_path = output_dir / img_filename

                            try:
                                # Debug: verifica estrutura do objeto imagem
                                if isinstance(img, dict):
                                    # Se for dicionário, tenta diferentes chaves
                                    if "bbox" in img:
                                        bbox = img["bbox"]
                                    elif all(key in img for key in ["x0", "top", "x1", "bottom"]):
                                        bbox = (img["x0"], img["top"], img["x1"], img["bottom"])
                                    else:
                                        # Usa coordenadas padrão se não encontrar
                                        bbox = (0, 0, page.width, page.height)
                                else:
                                    # Se for objeto, tenta atributos
                                    if hasattr(img, "bbox"):
                                        bbox = img.bbox
                                    else:
                                        bbox = (0, 0, page.width, page.height)

                                # Extrai imagem com padrão profissional (300 DPI + PNG)
                                try:
                                    img_obj = page.crop(bbox).to_image(
                                        resolution=300,  # Padrão profissional
                                        antialias=True,  # Bordas suaves
                                    )
                                    img_obj.save(img_path, format="PNG", optimize=False)
                                except Exception:
                                    # Fallback: qualidade padrão se 300 DPI falhar
                                    img_obj = page.crop(bbox).to_image()
                                    img_obj.save(img_path)

                                page_text += f"\n<!-- image on page {page_num + 1}: {img_filename} -->\n"

                            except Exception:
                                # Marca presença mas não conseguiu extrair
                                page_text += f"\n<!-- image on page {page_num + 1}: detectada mas não extraída -->\n"

                    text += page_text

            # Alinha tabelas para melhor visualização
            aligned_text = self._align_tables_in_text(text)

            return DocumentContent(
                text_content=aligned_text.strip(),
                metadata={"pages": stats["pages"], "images_saved": images_detected},
                extraction_stats=stats,
                extraction_method="",  # Será preenchido depois
                duration_seconds=0.0,  # Será preenchido depois
            )

        except Exception as e:
            raise OSError(f"Erro na extração pdfplumber: {e}") from e

    def _align_tables_in_text(self, text: str) -> str:
        """Alinha as tabelas no texto para colunas padronizadas."""
        lines = text.split("\n")
        result_lines = []
        i = 0

        while i < len(lines):
            line = lines[i]

            # Detecta início de tabela
            if line.startswith("### Tabela"):
                result_lines.append(line)  # Mantém cabeçalho da tabela
                i += 1

                # Coleta todas as linhas da tabela
                table_lines = []
                while i < len(lines) and lines[i].startswith("|"):
                    table_lines.append(lines[i])
                    i += 1

                # Alinha a tabela se houver linhas
                if table_lines:
                    aligned_table = self._align_single_table(table_lines)
                    result_lines.extend(aligned_table)

                # Adiciona linha vazia após tabela se existir
                if i < len(lines) and lines[i].strip() == "":
                    result_lines.append("")
                    i += 1
            else:
                result_lines.append(line)
                i += 1

        return "\n".join(result_lines)

    def _align_single_table(self, table_lines: list[str]) -> list[str]:
        """Alinha uma única tabela com colunas padronizadas."""
        if not table_lines:
            return table_lines

        # Parse das linhas da tabela
        parsed_rows = []
        for line in table_lines:
            # Remove | do início e fim, depois divide
            clean_line = line.strip()
            if clean_line.startswith("|") and clean_line.endswith("|"):
                clean_line = clean_line[1:-1]  # Remove primeiro e último |
                cells = [cell.strip() for cell in clean_line.split("|")]
                parsed_rows.append(cells)

        if not parsed_rows:
            return table_lines

        # Determina número máximo de colunas
        max_cols = max(len(row) for row in parsed_rows)

        # Padroniza número de colunas
        for row in parsed_rows:
            while len(row) < max_cols:
                row.append("")

        # Calcula largura máxima de cada coluna
        col_widths = []
        for col_idx in range(max_cols):
            max_width = 0
            for row in parsed_rows:
                if col_idx < len(row):
                    max_width = max(max_width, len(row[col_idx]))
            col_widths.append(max(max_width, 1))  # Mínimo 1 caractere

        # Reconstrói tabela alinhada
        aligned_lines = []
        for row in parsed_rows:
            aligned_cells = []
            for col_idx, cell in enumerate(row):
                if col_idx < len(col_widths):
                    aligned_cell = cell.ljust(col_widths[col_idx])
                    aligned_cells.append(aligned_cell)
            aligned_lines.append("| " + " | ".join(aligned_cells) + " |")

        return aligned_lines

    def _validate_extraction_result(self, content: DocumentContent) -> None:
        """
        Validação final do resultado.

        Raises:
            ValueError: Se conteúdo extraído é insuficiente
        """
        # Conteúdo mínimo?
        if len(content.text_content) < 50:
            raise ValueError(f"Conteúdo extraído insuficiente: {len(content.text_content)} caracteres (mínimo: 50)")

        # Pelo menos algumas páginas?
        if content.extraction_stats.get("pages", 0) <= 0:
            raise ValueError("Nenhuma página encontrada no PDF")

    def _save_audit_txt(
        self,
        content: DocumentContent,
        file_path: str,
        output_dir: Path,
        audit_filename: str,
        delimiter: str = "─" * 120,
    ) -> None:
        """
        Salva arquivo TXT de auditoria com conteúdo extraído completo.

        Args:
            content: Conteúdo extraído
            file_path: Caminho do PDF original
            output_dir: Diretório de saída
            audit_filename: Nome do arquivo de auditoria (injetado via pattern)
            delimiter: Caractere delimitador (padrão: ─ * 120)

        Raises:
            IOError: Se falha ao salvar arquivo de auditoria
        """
        try:
            audit_filepath = output_dir / audit_filename

            # Conteúdo do arquivo de auditoria
            audit_content = f"""{delimiter}
AUDITORIA DE EXTRAÇÃO PDF
{delimiter}
Arquivo Original: {Path(file_path).name}
Data/Hora: {time.strftime("%Y-%m-%d %H:%M:%S")}
Método: {content.extraction_method}
Duração: {content.duration_seconds:.2f} segundos

ESTATÍSTICAS DE EXTRAÇÃO:
{delimiter}
"""

            # Adiciona estatísticas detalhadas
            for elemento, quantidade in content.extraction_stats.items():
                audit_content += f"• {elemento.capitalize()}: {quantidade}\n"

            audit_content += f"\nTotal de caracteres extraídos: {len(content.text_content)}\n"
            audit_content += f"Total de palavras: {len(content.text_content.split())}\n"

            # Adiciona metadados se disponíveis
            if content.metadata:
                audit_content += f"\nMETADADOS DO DOCUMENTO:\n{delimiter}\n"
                for key, value in content.metadata.items():
                    if value:  # Só inclui metadados não vazios
                        audit_content += f"• {key}: {value}\n"

            audit_content += f"\n\nCONTEÚDO EXTRAÍDO COMPLETO:\n{delimiter}\n"
            audit_content += content.text_content

            # Salva o arquivo
            with open(audit_filepath, "w", encoding="utf-8") as f:
                f.write(audit_content)

        except Exception:
            # Não levanta exceção - auditoria é opcional
            pass
