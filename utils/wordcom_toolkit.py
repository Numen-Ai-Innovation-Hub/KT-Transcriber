"""
Word COM Toolkit - Automação e Recovery do Microsoft Word via pywin32
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

100% STANDALONE - Reutilizável em qualquer projeto Python!
Zero dependências internas - usa apenas stdlib + pywin32 + psutil.

QUANDO USAR:
  ✅ Geração de documentos Word (.docx) a partir de templates
  ✅ Substituição de placeholders em documentos Word
  ✅ Recovery de cache COM corrompido (RPC_E_CALL_REJECTED, cache gen_py)
  ✅ Inicialização robusta do Word com fallback automático

RESPONSABILIDADES:
  - Recovery completo de cache COM (kill processes, clean caches, rebuild)
  - Substituição de texto em ranges, headers, footers, shapes, tabelas
  - Inicialização robusta do Word com retry automático
  - Cache global de constantes Word (evita lookups repetidos)

CARACTERÍSTICAS:
  - Suporte a textos longos (>255 caracteres) com substituição manual
  - Limpeza de cache pywin32 + caches de usuário (Office, Temp)
  - 3 métodos de fallback para rebuild: EnsureDispatch → TypeLib → MakePy
  - Fechamento de processos Word travados

NOTA: Este módulo é 100% standalone e pode ser copiado para outros projetos Python
que precisem de automação Word robusta.
"""

import glob
import logging
import os
import shutil
import subprocess
import sys
import time
from typing import Any

import psutil

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CACHE GLOBAL DE CONSTANTES WORD
# ─────────────────────────────────────────────────────────────────────────────

_CONSTANTES_WORD_CACHE: dict[str, int] | None = None


def get_word_constants() -> dict[str, int]:
    """
    Obtém as constantes do Word de forma robusta (com cache global).

    Returns:
        Dict com constantes Word mais comuns

    Nota:
        Usa cache para evitar imports repetidos. Se constantes não estiverem
        disponíveis (cache não otimizado), usa valores numéricos conhecidos.
    """
    global _CONSTANTES_WORD_CACHE

    if _CONSTANTES_WORD_CACHE is not None:
        return _CONSTANTES_WORD_CACHE

    try:
        from win32com.client import constants as wd

        _CONSTANTES_WORD_CACHE = {
            "wdFindContinue": wd.wdFindContinue,
            "wdReplaceAll": wd.wdReplaceAll,
            "wdHeaderFooterPrimary": wd.wdHeaderFooterPrimary,
            "wdAlignParagraphCenter": wd.wdAlignParagraphCenter,
            "wdCollapseEnd": 0,
        }
    except AttributeError:
        # Cache não otimizado - usar valores numéricos conhecidos
        logger.info("Constantes Word: Cache não otimizado, usando valores numéricos")
        _CONSTANTES_WORD_CACHE = {
            "wdFindContinue": 1,
            "wdReplaceAll": 2,
            "wdHeaderFooterPrimary": 1,
            "wdAlignParagraphCenter": 1,
            "wdCollapseEnd": 0,
        }

    return _CONSTANTES_WORD_CACHE


# ─────────────────────────────────────────────────────────────────────────────
# CLASSE: WordCOMRecovery
# ─────────────────────────────────────────────────────────────────────────────


class WordCOMRecovery:
    """
    Recovery completo de cache COM corrompido para Microsoft Word.

    Funcionalidades:
    - Fechamento de processos Word travados
    - Limpeza de cache pywin32 (gen_py)
    - Limpeza de caches de usuário (Office, Temp)
    - Reconstrução de cache COM com 3 métodos de fallback

    Uso:
        WordCOMRecovery.full_recovery()  # Recovery completo

        # Ou métodos individuais
        WordCOMRecovery.kill_word_processes()
        WordCOMRecovery.clean_pywin32_cache()
        WordCOMRecovery.rebuild_cache()
    """

    @staticmethod
    def kill_word_processes() -> int:
        """
        Fecha todos os processos do Microsoft Word em execução.

        Returns:
            Número de processos fechados
        """
        processos_word = ["WINWORD.EXE", "Word.exe", "Microsoft Word", "winword.exe"]
        processos_fechados = 0

        logger.info("Verificando processos do Microsoft Word em execução")

        for processo in psutil.process_iter(["name", "pid"]):
            try:
                nome = processo.info["name"]
                if nome and any(p.lower() in nome.lower() for p in processos_word):
                    logger.info(f"Fechando processo Word: {nome} (PID {processo.info['pid']})")
                    processo.kill()
                    processos_fechados += 1
                    time.sleep(0.5)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        if processos_fechados > 0:
            logger.info(f"Processos Word fechados: {processos_fechados}")
        else:
            logger.info("Nenhum processo Word estava em execução")

        return processos_fechados

    @staticmethod
    def clean_pywin32_cache() -> bool:
        """
        Remove completamente o cache do pywin32 (gen_py).

        Returns:
            True se limpeza foi bem-sucedida
        """
        try:
            import win32com

            win32com_path = os.path.dirname(win32com.__file__)
            gen_py_path = os.path.join(win32com_path, "gen_py")

            logger.info(f"Limpando cache pywin32: {gen_py_path}")

            if os.path.exists(gen_py_path):
                shutil.rmtree(gen_py_path, ignore_errors=True)
                time.sleep(1)
                logger.info("Cache pywin32 removido com sucesso")
            else:
                logger.info("Cache pywin32 não existia")

            # Recriar diretório vazio
            os.makedirs(gen_py_path, exist_ok=True)
            logger.info("Diretório gen_py recriado")
            return True

        except Exception as e:
            logger.error(f"Erro ao limpar cache pywin32: {e}")
            return False

    @staticmethod
    def clean_user_caches() -> int:
        """
        Limpa caches do usuário relacionados ao COM/Office.

        Returns:
            Número de itens removidos
        """
        logger.info("Limpando caches temporários do Microsoft Office")

        caminhos_cache = [
            os.path.expanduser("~\\AppData\\Local\\Microsoft\\Office\\16.0\\OfficeFileCache"),
            os.path.expanduser("~\\AppData\\Local\\Microsoft\\Office\\15.0\\OfficeFileCache"),
            os.path.expanduser("~\\AppData\\Local\\Temp\\Word*"),
            os.path.expanduser("~\\AppData\\Roaming\\Microsoft\\Word\\STARTUP"),
        ]

        removidos = 0
        for caminho in caminhos_cache:
            try:
                if "*" in caminho:
                    for path in glob.glob(caminho):
                        if os.path.isdir(path):
                            shutil.rmtree(path, ignore_errors=True)
                        elif os.path.isfile(path):
                            os.remove(path)
                        logger.info(f"Removido cache: {path}")
                        removidos += 1
                else:
                    if os.path.exists(caminho):
                        if os.path.isdir(caminho):
                            shutil.rmtree(caminho, ignore_errors=True)
                        else:
                            os.remove(caminho)
                        logger.info(f"Removido cache: {caminho}")
                        removidos += 1
            except Exception as e:
                logger.warning(f"Não foi possível remover {caminho}: {e}")

        if removidos > 0:
            logger.info(f"Limpeza de caches concluída: {removidos} itens removidos")
        else:
            logger.info("Nenhum cache temporário encontrado")

        return removidos

    @staticmethod
    def rebuild_cache() -> bool:
        """
        Reconstrói o cache do pywin32 com 3 métodos de fallback.

        Métodos tentados (ordem):
        1. EnsureDispatch direto (cria cache automaticamente)
        2. Detecção automática de TypeLib + EnsureModule
        3. MakePy via subprocess

        Returns:
            True se cache foi reconstruído com sucesso
        """
        try:
            import win32com.client

            logger.info("Iniciando rebuild do cache COM")
            win32com.client.gencache.Rebuild()
            logger.info("Rebuild base concluído")

            # Método 1: EnsureDispatch direto
            logger.info("Tentativa 1/3: EnsureDispatch direto")
            try:
                word = win32com.client.gencache.EnsureDispatch("Word.Application")
                word.Visible = False
                version = word.Version
                logger.info(f"Cache gerado via EnsureDispatch (Word {version})")
                word.Quit()
                time.sleep(1)
                return True

            except Exception as e1:
                logger.warning(f"EnsureDispatch direto falhou: {e1}")

                # Método 2: Detecção automática de TypeLib
                logger.info("Tentativa 2/3: Detecção automática de TypeLib")
                try:
                    word_dynamic = win32com.client.dynamic.Dispatch("Word.Application")
                    word_dynamic.Visible = False

                    typeinfo = word_dynamic._oleobj_.GetTypeInfo()
                    typelib, index = typeinfo.GetContainingTypeLib()
                    tlb_attr = typelib.GetLibAttr()

                    guid = str(tlb_attr[0])
                    major = tlb_attr[1]
                    minor = tlb_attr[2]

                    logger.info(f"TypeLib detectada: {guid} v{major}.{minor}")

                    version = word_dynamic.Version
                    word_dynamic.Quit()
                    time.sleep(1)

                    logger.info(f"Gerando cache para Word {version}")
                    win32com.client.gencache.EnsureModule(guid, 0, major, minor)

                    # Validar cache gerado
                    logger.info("Validando cache gerado")
                    word_test = win32com.client.gencache.EnsureDispatch("Word.Application")
                    word_test.Visible = False
                    word_test.Quit()
                    time.sleep(1)

                    logger.info("Cache gerado via detecção automática")
                    return True

                except Exception as e2:
                    logger.warning(f"Detecção automática falhou: {e2}")

                    # Método 3: MakePy via subprocess
                    logger.info("Tentativa 3/3: MakePy via subprocess")
                    try:
                        result = subprocess.run(
                            [sys.executable, "-m", "win32com.client.makepy", "Word.Application"],
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )

                        if result.returncode == 0:
                            logger.info("MakePy executado com sucesso")

                            word_test = win32com.client.gencache.EnsureDispatch("Word.Application")
                            word_test.Visible = False
                            word_test.Quit()
                            time.sleep(1)

                            logger.info("Cache gerado via MakePy")
                            return True
                        else:
                            raise Exception(f"MakePy retornou código {result.returncode}")

                    except Exception as e3:
                        logger.warning(f"MakePy falhou: {e3}")
                        logger.warning("Cache otimizado não pôde ser criado")
                        logger.info("Sistema funcionará com Dispatch básico (performance reduzida)")
                        return False

        except Exception as e:
            logger.error(f"Erro crítico na reconstrução do cache COM: {e}")
            return False

    @staticmethod
    def full_recovery() -> bool:
        """
        Executa recovery completo do ambiente COM Word.

        Pipeline:
        1. Fechar processos Word travados
        2. Limpar cache pywin32
        3. Limpar caches de usuário
        4. Reconstruir cache com retry (3 métodos)

        Returns:
            True se recovery foi bem-sucedido
        """
        logger.info("Iniciando recovery completo do ambiente COM Word")

        WordCOMRecovery.kill_word_processes()
        WordCOMRecovery.clean_pywin32_cache()
        WordCOMRecovery.clean_user_caches()
        success = WordCOMRecovery.rebuild_cache()

        if success:
            logger.info("Recovery COM concluído com sucesso")
        else:
            logger.warning("Recovery COM parcial - funcionará com performance reduzida")

        return success


# ─────────────────────────────────────────────────────────────────────────────
# INICIALIZAÇÃO DO WORD COM RETRY
# ─────────────────────────────────────────────────────────────────────────────


def initialize_word_with_retry(visible: bool = False, display_alerts: bool = False, max_retries: int = 1) -> Any:
    """
    Inicializa o Word de forma robusta com retry automático.

    Args:
        visible: Se True, torna Word visível
        display_alerts: Se True, exibe alertas do Word
        max_retries: Número máximo de tentativas com recovery (default: 1)

    Returns:
        Instância do Word Application

    Raises:
        RuntimeError: Se falhar todas as tentativas

    Nota:
        Em caso de falha, executa WordCOMRecovery.full_recovery() automaticamente
        e tenta novamente até max_retries.
    """
    import win32com.client as win32

    for tentativa in range(max_retries + 1):
        try:
            # Método 1: EnsureDispatch (preferido - usa cache otimizado)
            logger.info(f"Inicializando Word (tentativa {tentativa + 1}/{max_retries + 1}): EnsureDispatch")
            word = win32.gencache.EnsureDispatch("Word.Application")
            word.Visible = visible
            word.DisplayAlerts = display_alerts
            logger.info("Word inicializado com sucesso via EnsureDispatch")
            return word

        except Exception as e1:
            logger.warning(f"EnsureDispatch falhou: {e1}")

            # Método 2: Rebuild + Dispatch normal
            try:
                logger.info("Tentando Rebuild + Dispatch normal")
                win32.gencache.Rebuild()
                word = win32.Dispatch("Word.Application")
                word.Visible = visible
                word.DisplayAlerts = display_alerts
                logger.info("Word inicializado após rebuild")
                return word

            except Exception as e2:
                logger.warning(f"Rebuild + Dispatch falhou: {e2}")

                # Se ainda temos tentativas, executar recovery completo
                if tentativa < max_retries:
                    logger.warning(f"Executando recovery completo (tentativa {tentativa + 1}/{max_retries})")
                    WordCOMRecovery.full_recovery()
                    time.sleep(2)  # Aguarda estabilização
                else:
                    # Última tentativa: Dispatch básico sem recovery
                    try:
                        logger.info("Última tentativa: Dispatch básico")
                        word = win32.Dispatch("Word.Application")
                        word.Visible = visible
                        word.DisplayAlerts = display_alerts
                        logger.info("Word inicializado com Dispatch básico")
                        return word
                    except Exception as e3:
                        logger.error(f"Falha crítica ao inicializar Word: {e3}")
                        raise RuntimeError("Falha crítica ao inicializar Word após todos os retries") from e3

    raise RuntimeError("Falha ao inicializar Word após recovery")


# ─────────────────────────────────────────────────────────────────────────────
# SUBSTITUIÇÃO DE TEXTO EM DOCUMENTOS
# ─────────────────────────────────────────────────────────────────────────────


def replace_text_in_range(text_range: Any, marker: str, replacement: Any) -> bool:
    """
    Substitui texto em um range específico do Word.

    Args:
        text_range: Range do Word onde fazer substituição
        marker: Marcador a ser substituído (ex: "<<<NOME>>>")
        replacement: Texto de substituição (pode ser str, list, ou Any com __str__)

    Returns:
        True se substituição foi bem-sucedida, False caso contrário

    Nota:
        - Suporta textos longos (>255 caracteres) com substituição manual
        - Converte listas em texto com quebras de linha
        - Fallback automático para substituição manual em caso de falha
    """
    if isinstance(replacement, list):
        replacement = "\n".join(replacement)
    replacement = str(replacement)

    MAX_WORD_REPLACE_LENGTH = 255

    try:
        constants = get_word_constants()

        # Textos longos (>255 chars): substituição manual
        if len(replacement) > MAX_WORD_REPLACE_LENGTH:
            find = text_range.Find
            find.ClearFormatting()
            find.Text = marker
            find.Forward = True
            find.Wrap = constants["wdFindContinue"]

            if find.Execute():
                found_range = text_range.Duplicate
                found_range.Start = find.Parent.Start
                found_range.End = find.Parent.End
                found_range.Text = replacement
                return True
            else:
                return False

        # Textos normais: Find/Replace padrão do Word
        find = text_range.Find
        find.ClearFormatting()
        find.Replacement.ClearFormatting()
        find.Text = marker
        find.Replacement.Text = replacement
        find.Forward = True
        find.Wrap = constants["wdFindContinue"]
        find.Format = False
        find.MatchCase = False
        find.MatchWholeWord = False
        find.MatchWildcards = False
        find.MatchSoundsLike = False
        find.MatchAllWordForms = False

        found = find.Execute(Replace=constants["wdReplaceAll"])

        # Verificação pós-substituição (fallback manual se Find/Replace falhou)
        if not found and marker in text_range.Text:
            logger.info(f"Find/Replace para '{marker}' falhou - Tentando substituição manual")
            find_manual = text_range.Find
            find_manual.ClearFormatting()
            find_manual.Text = marker
            if find_manual.Execute():
                found_range = text_range.Duplicate
                found_range.Start = find_manual.Parent.Start
                found_range.End = find_manual.Parent.End
                found_range.Text = replacement
                found = True

        return found

    except Exception as e:
        logger.warning(f"Erro na substituição de texto para '{marker}': {e}")

        # Fallback final: substituição de string pura
        try:
            if marker in text_range.Text:
                text_range.Text = text_range.Text.replace(marker, replacement)
                return True
        except Exception as e2:
            logger.warning(f"Fallback manual para '{marker}' falhou: {e2}")

        return False


def replace_in_document(doc: Any, marker: str, replacement: Any) -> bool:
    """
    Substitui texto em TODO o documento Word (corpo, headers, footers, shapes, tabelas).

    Args:
        doc: Documento Word (win32com Document object)
        marker: Marcador a ser substituído (ex: "<<<TITULO>>>")
        replacement: Texto de substituição

    Returns:
        True se marcador foi encontrado em pelo menos um lugar

    Nota:
        Procura o marcador em:
        1. Corpo principal do documento
        2. Headers (cabeçalhos) de todas as seções
        3. Footers (rodapés) de todas as seções
        4. Shapes (caixas de texto) em headers/footers/corpo
        5. StoryRanges (áreas especiais do Word)
        6. Tabelas (todas as células)
    """
    found = False

    # 1. Corpo principal
    if replace_text_in_range(doc.Content, marker, replacement):
        found = True

    # 2. Headers e Footers
    for section in doc.Sections:
        # Headers
        for header in section.Headers:
            if replace_text_in_range(header.Range, marker, replacement):
                found = True

            # Shapes em Headers (caixas de texto)
            for shape in header.Shapes:
                if shape.TextFrame.HasText:
                    text_shape = shape.TextFrame.TextRange.Text
                    if marker in text_shape:
                        shape.TextFrame.TextRange.Text = text_shape.replace(marker, replacement)
                        found = True

        # Footers
        for footer in section.Footers:
            if replace_text_in_range(footer.Range, marker, replacement):
                found = True

            # Shapes em Footers
            for shape in footer.Shapes:
                if shape.TextFrame.HasText:
                    text_shape = shape.TextFrame.TextRange.Text
                    if marker in text_shape:
                        shape.TextFrame.TextRange.Text = text_shape.replace(marker, replacement)
                        found = True

    # 3. StoryRanges (áreas especiais do documento)
    story = doc.StoryRanges.Item(1)
    while story is not None:
        if replace_text_in_range(story, marker, replacement):
            found = True
        story = story.NextStoryRange

    # 4. Shapes no corpo principal
    for shape in doc.Shapes:
        if shape.TextFrame.HasText:
            text_shape = shape.TextFrame.TextRange.Text
            if marker in text_shape:
                shape.TextFrame.TextRange.Text = text_shape.replace(marker, replacement)
                found = True

    # 5. Tabelas (todas as células)
    for table in doc.Tables:
        for row in table.Rows:
            for cell in row.Cells:
                text_cell = cell.Range.Text.replace("\r", "").replace("\a", "")
                if marker in text_cell:
                    cell.Range.Text = text_cell.replace(marker, replacement)
                    found = True

    return found
