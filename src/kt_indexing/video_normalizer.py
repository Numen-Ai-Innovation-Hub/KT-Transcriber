"""Video Normalizer — Transcrição de KT.

Normaliza nomes de vídeos/reuniões para formato padronizado.
Usa LLM para extração de módulos SAP e descrição inteligente do nome.
"""

import re
import unicodedata
from typing import Any

import openai

from src.config.settings import OPENAI_API_KEY, OPENAI_MODEL
from src.kt_indexing.kt_indexing_constants import CHAR_REPLACEMENTS
from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)

_NORMALIZATION_PROMPT = """Você é especialista em projetos SAP.
Analise o nome de uma reunião de KT (Knowledge Transfer) e extraia:

1. Módulo(s) SAP principal(is) mencionado(s) (ex: MM, SD, FI, CO, EWM, WM)
2. Descrição resumida do tema principal (máximo 10 palavras)

Nome da reunião: {video_name}

Responda em formato JSON:
{{
  "modules": ["MM", "SD"],
  "description": "Descrição do tema principal"
}}

Responda APENAS com o JSON, sem explicações."""


class EnhancedVideoNormalizer:
    """Normaliza nomes de vídeos com suporte a LLM para extração inteligente.

    Funcionalidades:
    - Normalização de caracteres especiais e acentos
    - Remoção de timestamps e formatos de data
    - Extração de módulos SAP via regex e LLM
    - Geração de slug padronizado
    """

    def __init__(self, use_llm: bool = True):
        """Inicializa o normalizador.

        Args:
            use_llm: Se True, usa OpenAI para extração de módulos e descrição.
        """
        self.use_llm = use_llm
        self._openai_client: openai.OpenAI | None = None
        self._model = OPENAI_MODEL

        if use_llm and OPENAI_API_KEY:
            self._openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
            logger.info("EnhancedVideoNormalizer inicializado com suporte LLM")
        else:
            logger.info("EnhancedVideoNormalizer inicializado sem LLM (modo regex only)")

    def normalize(self, video_name: str, meeting_id: str = "") -> dict[str, Any]:
        """Normaliza nome de vídeo com extração de metadados.

        Args:
            video_name: Nome original do vídeo/reunião.
            meeting_id: ID único da reunião no TL:DV (garante unicidade do slug).

        Returns:
            Dict com:
                - normalized_name: Nome normalizado
                - slug: Slug para uso como ID e nome de pasta
                - modules: Módulos SAP detectados
                - description: Descrição resumida
                - original_name: Nome original
        """
        if not video_name:
            return {
                "normalized_name": "Reunião KT",
                "slug": "reuniao_kt",
                "modules": [],
                "description": "",
                "original_name": "",
            }

        # Aplicar substituições de caracteres
        cleaned = self._apply_char_replacements(video_name)

        # Remover timestamps no formato YYYYMMDD_HHMMSS
        cleaned = re.sub(r"\d{8}_\d{6}", "", cleaned)

        # Remover sufixo padrão TL:DV "Gravação de Reunião" (com variantes numéricas)
        cleaned = re.sub(r"-?\s*Grava[cç][aã]o de Reuni[aã]o\s*\d*", "", cleaned, flags=re.IGNORECASE)

        # Remover espaços extras e hífens soltos no final
        cleaned = re.sub(r"[-\s]+$", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # Normalizar unicode
        normalized_name = self._normalize_unicode(cleaned)

        # Extrair módulos SAP (retornados no resultado, não usados no slug)
        modules = self._extract_modules_regex(video_name)

        # Extração LLM se módulos não detectados via regex e LLM disponível
        description = ""
        if self.use_llm and self._openai_client and not modules:
            llm_result = self._extract_with_llm(video_name)
            if llm_result:
                modules = llm_result.get("modules", modules)
                description = llm_result.get("description", "")

        # Gerar slug a partir do nome completo + meeting_id como sufixo de unicidade
        slug = self._build_semantic_slug(video_name, meeting_id)

        return {
            "normalized_name": normalized_name,
            "slug": slug,
            "modules": modules,
            "description": description,
            "original_name": video_name,
        }

    def _apply_char_replacements(self, text: str) -> str:
        """Aplica substituições de caracteres especiais.

        Args:
            text: Texto original.

        Returns:
            Texto com caracteres substituídos.
        """
        for old_char, new_char in CHAR_REPLACEMENTS.items():
            text = text.replace(old_char, new_char)
        return text

    def _normalize_unicode(self, text: str) -> str:
        """Normaliza unicode mantendo acentos PT-BR.

        Args:
            text: Texto para normalizar.

        Returns:
            Texto normalizado.
        """
        # Normalizar forma composta (NFC) — mantém acentos corretamente
        return unicodedata.normalize("NFC", text)

    def _to_slug(self, text: str) -> str:
        """Converte texto para slug (lowercase, underscores).

        Args:
            text: Texto para converter.

        Returns:
            Slug normalizado.
        """
        # Remover acentos para slug
        no_accent = unicodedata.normalize("NFD", text)
        no_accent = "".join(c for c in no_accent if unicodedata.category(c) != "Mn")

        # Lowercase e substituir não-alfanuméricos por underscore
        slug = re.sub(r"[^\w\s]", "_", no_accent.lower())
        slug = re.sub(r"\s+", "_", slug)
        slug = re.sub(r"_+", "_", slug).strip("_")

        return slug[:50] if slug else "video_kt"

    def _build_semantic_slug(self, video_name: str, meeting_id: str = "") -> str:
        """Constrói slug único a partir do nome completo do vídeo + prefixo do meeting_id.

        O nome completo do vídeo (sem sufixo TL:DV, timestamp e colchetes) é usado
        como base legível. Os primeiros 8 chars do meeting_id garantem unicidade
        absoluta, inclusive entre dois vídeos com nomes praticamente idênticos.

        Formato: {video_name_sanitizado_40chars}_{meeting_id_8chars}

        Args:
            video_name: Nome original do vídeo/reunião.
            meeting_id: ID único da reunião no TL:DV (ex: "699f383b5027ff0012021c95").

        Returns:
            Slug no formato {nome_40chars}_{id8}, máx 49 chars.
        """
        if not meeting_id:
            logger.warning(f"meeting_id não fornecido para slug de '{video_name}' — unicidade do slug não garantida")

        # Remover sufixo TL:DV e timestamp para isolar o título da reunião
        base = re.sub(r"-?\s*Grava[cç][aã]o de Reuni[aã]o\s*\d*", "", video_name, flags=re.IGNORECASE)
        base = re.sub(r"-?\d{8}_\d{6}", "", base)
        # Remover colchetes e parênteses (delimitadores de cliente/contexto)
        base = re.sub(r"[\[\]\(\)]", " ", base)

        name_part = self._to_slug(base)[:40].strip("_")
        id_part = meeting_id[:8] if meeting_id else ""
        parts = [p for p in [name_part, id_part] if p]
        return "_".join(parts) if parts else "video_kt"

    def _extract_slug_client(self, video_name: str) -> str:
        """Extrai parte do cliente para o slug a partir de [BRACKET] ou fallback.

        Args:
            video_name: Nome original do vídeo.

        Returns:
            Nome do cliente em lowercase sem acentos (ex: "dexco", "vissimo").
        """
        bracket = re.search(r"\[([^\]]+)\]", video_name)
        if bracket:
            raw = bracket.group(1).strip()
            no_accent = unicodedata.normalize("NFD", raw)
            no_accent = "".join(c for c in no_accent if unicodedata.category(c) != "Mn")
            client = re.sub(r"[^a-z0-9]", "", no_accent.lower())
            return client if client else "dexco"
        return "dexco"

    def _extract_slug_keyword(self, video_name: str) -> str:
        """Extrai keyword do tema principal quando não há módulo SAP detectado.

        Args:
            video_name: Nome original do vídeo.

        Returns:
            Abreviação do tema (ex: "icms", "frete", "sus"), ou string vazia.
        """
        video_upper = video_name.upper()
        keywords = [
            ("ICMS", "icms"),
            ("FRETE", "frete"),
            ("ESTORNO", "estorno"),
            ("SUSTENTA", "sus"),
            ("ESTRATEG", "est"),
            ("CORREC", "cor"),
            ("SIMULADO", "sim"),
            ("INTEGRA", "int"),
            ("KICKOFF", "kickoff"),
            ("COMPLEMENTO", "comp"),
            ("REFORMA", "reform"),
            ("IFLOW", "iflow"),
            ("INVENTARIO", "inv"),
            ("WORKFLOW", "wf"),
            ("CUSTO", "custo"),
            ("FATURAMENTO", "fat"),
            ("RECEBIMENTO", "rec"),
            ("CONTABIL", "cont"),
        ]
        for key, abbrev in keywords:
            if key in video_upper:
                return abbrev
        return ""

    def _extract_modules_regex(self, video_name: str) -> list[str]:
        """Extrai módulos SAP do nome do vídeo via regex.

        Args:
            video_name: Nome do vídeo.

        Returns:
            Lista de módulos detectados.
        """
        known_modules = [
            "MM",
            "SD",
            "FI",
            "CO",
            "HR",
            "PP",
            "PM",
            "QM",
            "WM",
            "EWM",
            "TM",
            "GTS",
            "LE",
            "PS",
            "RE",
            "SRM",
            "CRM",
            "BW",
            "BI",
            "BTP",
            "ABAP",
            "FIORI",
            "CPI",
        ]
        video_upper = video_name.upper()
        found = []
        for module in known_modules:
            pattern = r"\b" + re.escape(module) + r"\b"
            if re.search(pattern, video_upper):
                found.append(module)
        return found

    def _extract_with_llm(self, video_name: str) -> dict[str, Any] | None:
        """Extrai módulos e descrição via LLM.

        Args:
            video_name: Nome do vídeo.

        Returns:
            Dict com modules e description, ou None se falhou.
        """
        if not self._openai_client:
            return None

        try:
            import json

            prompt = _NORMALIZATION_PROMPT.format(video_name=video_name)
            response = self._openai_client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
            )
            raw = (response.choices[0].message.content or "").strip()
            # Remover blocos de código markdown se presentes
            raw = re.sub(r"```json\s*|\s*```", "", raw).strip()
            return json.loads(raw)

        except Exception as e:
            logger.warning(f"Extração LLM falhou para '{video_name}': {e}")
            return None

    def get_migration_plan(self, video_names: list[str]) -> list[dict[str, Any]]:
        """Gera plano de migração para uma lista de nomes de vídeo.

        Args:
            video_names: Lista de nomes originais.

        Returns:
            Lista de dicts com mapeamento original → normalizado.
        """
        plan = []
        for name in video_names:
            result = self.normalize(name)
            plan.append(
                {
                    "original": name,
                    "normalized": result["normalized_name"],
                    "slug": result["slug"],
                    "modules": result["modules"],
                }
            )
        return plan


def normalize_video_name_enhanced(video_name: str, use_llm: bool = False) -> dict[str, Any]:
    """Função de conveniência para normalização de nome de vídeo.

    Args:
        video_name: Nome original do vídeo.
        use_llm: Se True, usa LLM para extração adicional.

    Returns:
        Dict com dados normalizados.
    """
    normalizer = EnhancedVideoNormalizer(use_llm=use_llm)
    return normalizer.normalize(video_name)


def get_migration_plan(video_names: list[str]) -> list[dict[str, Any]]:
    """Função de conveniência para gerar plano de migração.

    Args:
        video_names: Lista de nomes de vídeo.

    Returns:
        Plano de migração com mapeamentos.
    """
    normalizer = EnhancedVideoNormalizer(use_llm=False)
    return normalizer.get_migration_plan(video_names)
