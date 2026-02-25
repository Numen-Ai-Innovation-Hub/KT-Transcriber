"""
DPT-2 Extractor - 100% Standalone e Reutilizável.

NÃO usa logging interno - retorna resultados ou lança exceções built-in.
NÃO usa exceções customizadas - apenas stdlib.
NÃO depende de configurações - tudo via parâmetros.
NÃO gerencia cache - responsabilidade da camada de aplicação.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass
class DocumentContent:
    """Estrutura clara do conteúdo extraído"""

    text_content: str
    metadata: dict[str, Any]
    extraction_stats: dict[str, int]
    extraction_method: str
    duration_seconds: float


def _build_retry_session(
    max_retries: int,
    backoff_factor: float,
) -> requests.Session:
    """
    Cria sessão requests com retry automático e backoff exponencial.

    Args:
        max_retries: Número máximo de tentativas por request
        backoff_factor: Factor de espera entre retries (segundos × 2^n)

    Returns:
        requests.Session configurada com HTTPAdapter e Retry
    """
    retry_strategy = Retry(
        total=max_retries,
        connect=max_retries,
        read=max_retries,
        status=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"],
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class DPT2Extractor:
    """
    Extrator de PDFs usando Landing.AI DPT-2 API.

    100% reutilizável - sem logging interno, sem lógica de negócio.
    """

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        model: str,
        connect_timeout: int = 15,
        read_timeout: int = 120,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        """
        Inicializa o extrator DPT-2 com todos os parâmetros injectados.

        Args:
            api_key: API key da Landing.AI (obrigatório)
            endpoint: URL do endpoint da API
            model: Modelo DPT-2 a usar (ex: "dpt-2-latest")
            connect_timeout: Timeout de conexão em segundos
            read_timeout: Timeout de leitura em segundos
            max_retries: Número máximo de tentativas em caso de falha
            backoff_factor: Factor de backoff entre tentativas

        Raises:
            ValueError: Se api_key for vazio
        """
        if not api_key:
            raise ValueError("api_key é obrigatório para o DPT2Extractor")

        self.api_key = api_key
        self.endpoint = endpoint
        self.model = model
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.provider_name = "dpt-2"

        self._session = _build_retry_session(max_retries=max_retries, backoff_factor=backoff_factor)

    def extract_document_complete(self, file_path: str) -> DocumentContent:
        """
        Extrai PDF usando DPT-2 API.

        Args:
            file_path: Caminho absoluto para o arquivo PDF

        Returns:
            DocumentContent com texto extraído e metadados

        Raises:
            FileNotFoundError: Se arquivo não existe
            ValueError: Se arquivo é inválido (vazio, não-PDF)
            ConnectionError: Se falha na comunicação com a API
            OSError: Se falha inesperada ao processar resposta
        """
        start_time = time.time()
        pdf_path = Path(file_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        if pdf_path.stat().st_size <= 0:
            raise ValueError(f"Arquivo está vazio (0 bytes): {file_path}")
        if not file_path.lower().endswith(".pdf"):
            raise ValueError(f"Apenas arquivos .pdf são suportados: {file_path}")

        try:
            with open(file_path, "rb") as f:
                files = {"document": f}
                data = {"model": self.model, "split": "page"}
                headers = {"Authorization": f"Bearer {self.api_key}"}

                response = self._session.post(
                    self.endpoint,
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=(self.connect_timeout, self.read_timeout),
                )
                response.raise_for_status()
                result = response.json()

        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Erro na API DPT-2: {e}") from e

        try:
            text_content = self._extract_text_from_result(result)
            api_metadata = result.get("metadata", {})
            extraction_stats: dict[str, int] = {
                "pages": api_metadata.get("page_count", 0),
                "chunks": len(result.get("chunks", [])),
                "splits": len(result.get("splits", [])),
                "api_duration_ms": api_metadata.get("duration_ms", 0),
                "credit_usage": api_metadata.get("credit_usage", 0),
            }
            duration = time.time() - start_time

            return DocumentContent(
                text_content=text_content,
                metadata={
                    "pages": api_metadata.get("page_count"),
                    "filename": api_metadata.get("filename"),
                    "job_id": api_metadata.get("job_id"),
                    "version": api_metadata.get("version"),
                    "chunks_count": len(result.get("chunks", [])),
                    "splits_count": len(result.get("splits", [])),
                    "raw_result": result,
                    "native_chunks": self._extract_native_chunks(result),
                },
                extraction_stats=extraction_stats,
                extraction_method="Landing.AI DPT-2",
                duration_seconds=duration,
            )

        except Exception as e:
            raise OSError(f"Erro ao processar resposta DPT-2: {e}") from e

    def get_chunks_with_grounding(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Retorna chunks com informação de grounding (posição na página).

        Funcionalidade adicional do DPT-2 não disponível no pdfplumber.

        Args:
            result: Resposta completa da API DPT-2

        Returns:
            Lista de chunks com posicionamento
        """
        return [
            {
                "id": chunk_data.get("id"),
                "markdown": chunk_data.get("markdown"),
                "type": chunk_data.get("type"),
                "grounding": chunk_data.get("grounding", {}),
            }
            for chunk_data in result.get("chunks", [])
        ]

    def _extract_text_from_result(self, result: dict[str, Any]) -> str:
        """
        Extrai texto estruturado do resultado DPT-2.

        Mantém formato compatível com chunking service:
        - Marcadores de página "--- Página X ---"
        - Preserva estrutura markdown
        """
        splits = result.get("splits", [])
        if splits:
            pages_text = []
            for split in splits:
                pages = split.get("pages", [])
                page_num = pages[0] if pages else 0
                page_markdown = split.get("markdown", "")
                pages_text.append(f"--- Página {page_num} ---\n{page_markdown}")
            return "\n\n".join(pages_text)
        return result.get("markdown", "")

    def _extract_native_chunks(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extrai chunks nativos da API DPT-2 com metadados completos.

        Args:
            result: Resposta completa da API DPT-2

        Returns:
            Lista de chunks com grounding e tipos semânticos
        """
        native_chunks = []
        for chunk_data in result.get("chunks", []):
            chunk = {
                "id": chunk_data.get("id"),
                "text": chunk_data.get("markdown", ""),
                "type": chunk_data.get("type", "unknown"),
                "grounding": chunk_data.get("grounding", {}),
                "metadata": {
                    "semantic_type": chunk_data.get("type"),
                    "confidence": chunk_data.get("metadata", {}).get("confidence", 1.0)
                    if isinstance(chunk_data.get("metadata"), dict)
                    else 1.0,
                },
            }
            native_chunks.append(chunk)
        return native_chunks
