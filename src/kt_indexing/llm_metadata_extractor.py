"""LLM Metadata Extractor — Transcrição de KT.

Extrai metadados estruturados de chunks de transcrição usando LLM (GPT-4o-mini).
"""

import ast
import re
import time
from typing import Any

import openai

from src.config.settings import OPENAI_API_KEY, OPENAI_MODEL
from src.kt_indexing.kt_indexing_constants import ENHANCED_METADATA_EXTRACTION_PROMPT, LLM_CONFIG, METADATA_DEFAULTS
from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)


class LLMMetadataExtractor:
    """Extrai metadados estruturados de chunks de transcrição via LLM.

    Usa GPT-4o-mini para identificar:
    - Fase da reunião (apresentacao, demo, discussao, qa, encerramento)
    - Tipo de KT (sustentacao, implementacao, treinamento, etc.)
    - Módulos SAP mencionados
    - Transações SAP
    - Termos técnicos
    - Participantes mencionados
    - Sistemas integrados
    - Decisões e problemas
    - Tags para busca semântica
    """

    def __init__(self, config: dict | None = None):
        """Inicializa o extrator com cliente OpenAI.

        Args:
            config: Configuração LLM. Default: LLM_CONFIG.
        """
        self.config = config or LLM_CONFIG
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY)
        self.model = self.config.get("model", OPENAI_MODEL)
        logger.info(f"LLMMetadataExtractor inicializado com modelo: {self.model}")

    def extract_metadata_for_chunk(
        self,
        chunk_text: str,
        video_name: str = "",
        client_name: str = "",
    ) -> dict[str, Any]:
        """Extrai metadados para um chunk individual.

        Args:
            chunk_text: Texto do chunk de transcrição.
            video_name: Nome do vídeo/reunião para contexto.
            client_name: Nome do cliente para contexto.

        Returns:
            Dict com metadados extraídos. Usa defaults se extração falhar.
        """
        if not chunk_text or len(chunk_text.strip()) < 20:
            logger.debug("Chunk muito curto para extração LLM — usando defaults")
            return METADATA_DEFAULTS.copy()

        prompt = ENHANCED_METADATA_EXTRACTION_PROMPT.format(
            chunk_text=chunk_text[:2000],  # Limitar para não exceder tokens
            video_name=video_name,
            client_name=client_name,
        )

        max_retries = self.config.get("max_retries", 3)
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.config.get("temperature", 0.1),
                    max_tokens=self.config.get("max_tokens", 1000),
                )
                raw_response = (response.choices[0].message.content or "").strip()
                return self._parse_gpt_response(raw_response)

            except openai.RateLimitError as e:
                logger.warning(f"Rate limit atingido (tentativa {attempt + 1}): {e}")
                time.sleep(2**attempt)

            except openai.APIError as e:
                logger.error(f"Erro de API OpenAI (tentativa {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    break
                time.sleep(1)

            except Exception as e:
                logger.error(f"Erro ao extrair metadados (tentativa {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    break

        logger.warning("Extração LLM falhou — retornando defaults")
        return METADATA_DEFAULTS.copy()

    def _parse_gpt_response(self, raw_response: str) -> dict[str, Any]:
        """Analisa resposta do GPT e extrai variáveis Python.

        Suporta dois formatos:
        1. Formato de atribuição Python: `variavel = valor`
        2. Formato de dois pontos: `variavel: valor`

        Args:
            raw_response: Resposta bruta do GPT.

        Returns:
            Dict com metadados extraídos e validados.
        """
        metadata = METADATA_DEFAULTS.copy()

        if not raw_response:
            return metadata

        lines = raw_response.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Tentar formato de atribuição Python: variavel = valor
            if "=" in line:
                parts = line.split("=", 1)
            # Tentar formato de dois pontos: variavel: valor
            elif ":" in line:
                parts = line.split(":", 1)
            else:
                continue

            if len(parts) != 2:
                continue

            key = parts[0].strip().strip("\"'")
            value_str = parts[1].strip()

            if not key or key not in metadata:
                continue

            parsed_value = self._parse_value(value_str)
            if parsed_value is not None:
                metadata[key] = parsed_value

        return metadata

    def _parse_value(self, value_str: str) -> Any:
        """Analisa string de valor para tipo Python apropriado.

        Args:
            value_str: String com o valor a analisar.

        Returns:
            Valor analisado (str, list) ou None se inválido.
        """
        value_str = value_str.strip().strip("\"'")

        # Tentar como literal Python (listas, etc.)
        if value_str.startswith("["):
            try:
                result = ast.literal_eval(value_str)
                if isinstance(result, list):
                    return [str(item).strip().strip("\"'") for item in result if item]
                return result
            except Exception:
                # Tentar parse manual de lista simples: ["item1", "item2"]
                items = re.findall(r'"([^"]+)"|\'([^\']+)\'|([^,\[\]]+)', value_str)
                cleaned = []
                for groups in items:
                    item = next((g.strip() for g in groups if g.strip()), None)
                    if item:
                        cleaned.append(item)
                return cleaned if cleaned else []

        return value_str if value_str else None

    def process_chunks_batch(
        self,
        chunks: list[dict[str, Any]],
        rate_limit_delay: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Processa lista de chunks em batch com extração de metadados.

        Args:
            chunks: Lista de dicts com chaves: text, video_name, client_name.
            rate_limit_delay: Delay entre chamadas de API em segundos.

        Returns:
            Lista de dicts com metadados extraídos adicionados.
        """
        results = []

        for i, chunk in enumerate(chunks):
            chunk_text = chunk.get("text", "")
            video_name = chunk.get("video_name", "")
            client_name = chunk.get("client_name", "")

            metadata = self.extract_metadata_for_chunk(
                chunk_text=chunk_text,
                video_name=video_name,
                client_name=client_name,
            )

            result = chunk.copy()
            result["extracted_metadata"] = metadata
            results.append(result)

            if (i + 1) % 10 == 0:
                logger.info(f"Metadados extraídos: {i + 1}/{len(chunks)} chunks")

            if rate_limit_delay > 0:
                time.sleep(rate_limit_delay)

        logger.info(f"Extração de metadados concluída: {len(results)} chunks processados")
        return results
