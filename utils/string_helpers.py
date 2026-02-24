"""
Utilitários de string portáveis.

Funções puras para normalização, sanitização e transformação de texto.
Sem dependências de src/ ou config/.
"""

import re
import unicodedata
from pathlib import Path


def normalize_unicode(text: str) -> str:
    """Normaliza caracteres Unicode para NFC e remove caracteres de controle.

    Args:
        text: Texto a normalizar.

    Returns:
        Texto com Unicode normalizado e caracteres de controle removidos.
    """
    normalized = unicodedata.normalize("NFC", text)
    # Remove caracteres de controle exceto tab, newline e carriage return
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Cc" or ch in "\t\n\r")


def slugify(text: str, separator: str = "_") -> str:
    """Converte texto em slug seguro para uso em nomes de arquivo ou chaves.

    Args:
        text: Texto a converter.
        separator: Separador entre palavras (default: underscore).

    Returns:
        Slug em minúsculas sem caracteres especiais.

    Examples:
        >>> slugify("Reunião KT — SAP S/4HANA")
        'reuniao_kt_sap_s_4hana'
    """
    # Normaliza acentos (NFD separa base + diacrítico)
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")

    text = text.lower()
    # Substitui caracteres não alfanuméricos por separador
    text = re.sub(r"[^\w\s]", separator, text)
    # Substitui espaços e underscores múltiplos por separador único
    text = re.sub(r"[\s_]+", separator, text)
    return text.strip(separator)


def clean_filename(name: str, max_length: int = 100) -> str:
    """Sanitiza string para uso seguro como nome de arquivo.

    Args:
        name: Nome a sanitizar.
        max_length: Comprimento máximo do resultado.

    Returns:
        Nome de arquivo válido e seguro.
    """
    slug = slugify(name)
    return slug[:max_length].rstrip("_")


def truncate(text: str, max_chars: int, suffix: str = "...") -> str:
    """Trunca texto preservando palavras inteiras.

    Args:
        text: Texto a truncar.
        max_chars: Número máximo de caracteres (incluindo suffix).
        suffix: Sufixo adicionado quando truncado.

    Returns:
        Texto truncado ou original se dentro do limite.
    """
    if len(text) <= max_chars:
        return text
    limit = max_chars - len(suffix)
    truncated = text[:limit].rsplit(" ", 1)[0]
    return f"{truncated}{suffix}"


def extract_first_words(text: str, n: int) -> str:
    """Extrai as primeiras N palavras do texto.

    Args:
        text: Texto de origem.
        n: Número de palavras a extrair.

    Returns:
        String com as primeiras N palavras.
    """
    words = text.split()
    return " ".join(words[:n])


def count_words(text: str) -> int:
    """Conta palavras no texto.

    Args:
        text: Texto a contar.

    Returns:
        Número de palavras.
    """
    return len(text.split())


def normalize_whitespace(text: str) -> str:
    """Normaliza espaços em branco excessivos e quebras de linha.

    Args:
        text: Texto com espaçamento irregular.

    Returns:
        Texto com espaçamento normalizado.
    """
    # Colapsa múltiplos espaços/tabs em um único espaço
    text = re.sub(r"[ \t]+", " ", text)
    # Colapsa múltiplas quebras de linha em no máximo duas
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sanitize_metadata_value(value: object) -> str:
    """Sanitiza valor para uso como metadado no ChromaDB.

    ChromaDB aceita apenas strings, inteiros e floats como metadados.
    Esta função converte qualquer valor para string segura.

    Args:
        value: Valor a sanitizar.

    Returns:
        String segura para armazenar como metadado.
    """
    if value is None:
        return ""
    text = str(value)
    # Remove caracteres nulos que podem causar problemas em SQL/indexes
    return text.replace("\x00", "").strip()


def mask_api_key(key: str, visible_chars: int = 4) -> str:
    """Mascara chave de API para logging seguro.

    Args:
        key: Chave a mascarar.
        visible_chars: Número de caracteres visíveis no final.

    Returns:
        Chave com a maior parte substituída por asteriscos.
    """
    if not key or len(key) <= visible_chars:
        return "***"
    return f"{'*' * (len(key) - visible_chars)}{key[-visible_chars:]}"
