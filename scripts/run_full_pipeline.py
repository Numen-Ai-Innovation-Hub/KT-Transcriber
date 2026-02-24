"""Pipeline completo de processamento KT — Ingestion + Indexação + Validação.

Orquestra as três fases do sistema KT Transcriber de forma incremental:

Fase 1 — Ingestion:  TL:DV API → JSONs estruturados em data/transcriptions/
Fase 2 — Indexação:  JSONs → ChromaDB em data/vector_db/ (chunks + embeddings + LLM metadata)
Fase 3 — Validação:  ChromaDB → estatísticas e confirmação

Por padrão, opera de forma INCREMENTAL:
    - Ingestion: pula reuniões já salvas em transcriptions/
    - Indexação: pula vídeos cujo meeting_id já está no ChromaDB

Uso:
    uv run python scripts/run_full_pipeline.py                    # Incremental (padrão)
    uv run python scripts/run_full_pipeline.py --force-clean      # Apaga tudo e reprocessa
    uv run python scripts/run_full_pipeline.py --skip-ingestion   # Apenas indexação + validação
    uv run python scripts/run_full_pipeline.py --skip-indexing    # Apenas ingestion

Exemplo:
    uv run python scripts/run_full_pipeline.py
    uv run python scripts/run_full_pipeline.py --force-clean
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Garantir que a raiz do projeto está no sys.path para imports de src/ e utils/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.config.settings import DIRECTORY_PATHS, TLDV_API_KEY
from src.config.startup import initialize_application
from src.kt_indexing.chromadb_store import ChromaDBStore
from src.kt_indexing.indexing_engine import IndexingEngine
from src.kt_indexing.kt_indexing_utils import extract_client_name_smart
from src.kt_ingestion.json_consolidator import JSONConsolidator
from src.kt_ingestion.smart_processor import SmartMeetingProcessor
from src.kt_ingestion.tldv_client import MeetingData, TLDVClient
from utils.exception_setup import ApplicationError
from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPAL
# ════════════════════════════════════════════════════════════════════════════


class FullPipelineRunner:
    """Orquestrador do pipeline completo de processamento KT.

    Gerencia as três fases de processamento de forma incremental,
    rastreando progresso e estatísticas por fase.
    """

    def __init__(self) -> None:
        """Inicializa o runner com diretórios e stats zerados."""
        self.transcriptions_dir: Path = DIRECTORY_PATHS["transcriptions"]
        self.vector_db_dir: Path = DIRECTORY_PATHS["vector_db"]

        self.stats: dict[str, Any] = {
            "start_time": None,
            "end_time": None,
            # Fase 1
            "meetings_found": 0,
            "meetings_already_downloaded": 0,
            "meetings_downloaded": 0,
            "meetings_skipped_incomplete": 0,
            "meetings_failed": 0,
            # Fase 2
            "videos_already_indexed": 0,
            "videos_indexed": 0,
            "chunks_indexed": 0,
            "videos_failed": 0,
            # Fase 3
            "total_documents": 0,
            "unique_clients": [],
            # Geral
            "errors": [],
        }

    # ────────────────────────────────────────────────────────────────────────
    # FORÇA LIMPEZA
    # ────────────────────────────────────────────────────────────────────────

    def force_clean(self) -> None:
        """Remove todos os dados processados — transcriptions + vector_db.

        ATENÇÃO: Operação irreversível. Todos os JSONs e índices serão apagados.
        O pipeline será executado do zero em seguida.
        """
        logger.warning("Iniciando limpeza forçada de todos os dados processados")

        if self.transcriptions_dir.exists():
            for json_file in self.transcriptions_dir.glob("*.json"):
                json_file.unlink()
            logger.info(f"JSONs de transcrição removidos de: {self.transcriptions_dir}")

        if self.vector_db_dir.exists():
            shutil.rmtree(self.vector_db_dir)
            self.vector_db_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Vector DB removido e recriado em: {self.vector_db_dir}")

        logger.warning("Limpeza concluída — pipeline será executado do zero")

    # ────────────────────────────────────────────────────────────────────────
    # FASE 1 — INGESTION
    # ────────────────────────────────────────────────────────────────────────

    def _get_existing_meeting_ids(self) -> set[str]:
        """Retorna IDs de reuniões já baixadas (JSONs em transcriptions/).

        Returns:
            Set com meeting_ids já presentes em disco.
        """
        existing_ids: set[str] = set()

        for json_file in self.transcriptions_dir.glob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                meeting_id = data.get("metadata", {}).get("meeting_id") or data.get("meeting_id", "")
                if meeting_id:
                    existing_ids.add(meeting_id)
            except Exception as e:
                logger.warning(f"Erro ao ler meeting_id de {json_file.name}: {e}")

        return existing_ids

    def _build_structured_json(self, meeting_data: dict[str, Any], client_name: str) -> dict[str, Any]:
        """Converte formato plano do SmartMeetingProcessor para estrutura esperada pelo IndexingEngine.

        O SmartMeetingProcessor retorna um dict plano com chaves no root level.
        O IndexingEngine espera {"metadata": {...}, "transcript": {"segments": [...]}}.
        Esta função faz a ponte entre os dois domínios.

        Args:
            meeting_data: Dict retornado por SmartMeetingProcessor.process_meeting_smart().
            client_name: Nome do cliente normalizado.

        Returns:
            Dict estruturado compatível com IndexingEngine.process_single_video().
        """
        transcript_segments = meeting_data.get("transcript", [])

        return {
            "metadata": {
                "video_name": meeting_data.get("video_name", ""),
                "client_name": client_name,
                "meeting_id": meeting_data.get("meeting_id", ""),
                "meeting_url": meeting_data.get("meeting_url", ""),
                "happened_at": meeting_data.get("happened_at", ""),
                "duration": meeting_data.get("duration", 0),
                "total_segments": meeting_data.get("total_segments", len(transcript_segments)),
                "total_highlights": meeting_data.get("total_highlights", 0),
                "consolidated_at": datetime.now().isoformat(),
            },
            "transcript": {
                "segments": transcript_segments,
            },
            "highlights": meeting_data.get("highlights", []),
        }

    def _process_single_meeting(
        self,
        meeting: MeetingData,
        processor: SmartMeetingProcessor,
        consolidator: JSONConsolidator,
    ) -> bool:
        """Baixa e salva uma reunião individual.

        Args:
            meeting: Dados da reunião obtidos da API TL:DV.
            processor: Processador smart já inicializado.
            consolidator: Consolidador JSON para persistência.

        Returns:
            True se processada com sucesso, False se falhou.
        """
        client_name = extract_client_name_smart(meeting.name)

        logger.info(f"Processando reunião: '{meeting.name}' | cliente: {client_name}")

        meeting_data = processor.process_meeting_smart(
            meeting_id=meeting.id,
            client_name=client_name,
            video_name=meeting.name,
            wait_for_complete=True,
        )

        if not meeting_data.get("is_complete"):
            logger.warning(
                f"Reunião '{meeting.name}' não está completa — "
                f"status: {meeting_data.get('status', 'unknown')}. Pulando."
            )
            self.stats["meetings_skipped_incomplete"] += 1
            return False

        # Converter formato plano para estrutura esperada pelo IndexingEngine
        structured_data = self._build_structured_json(meeting_data, client_name)

        video_name = meeting_data.get("video_name", meeting.name)
        safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in video_name)
        filename = f"{safe_name}.json"

        consolidator.save_consolidated_json(structured_data, filename=filename)

        segments_count = len(meeting_data.get("transcript", []))
        logger.info(f"Reunião salva: '{video_name}' — {segments_count} segmentos, arquivo: {filename}")

        self.stats["meetings_downloaded"] += 1
        return True

    def run_ingestion(self) -> bool:
        """Fase 1: Captura reuniões do TL:DV e salva JSONs estruturados.

        Opera de forma incremental: pula reuniões já presentes em transcriptions/.
        Apenas reuniões com status COMPLETED são processadas.

        Returns:
            True se ao menos uma reunião foi processada ou já existia, False se erro crítico.
        """
        logger.info("═" * 120)
        logger.info("FASE 1 — INGESTION: Capturando reuniões do TL:DV")
        logger.info("═" * 120)

        if not TLDV_API_KEY:
            raise ApplicationError(
                message="TLDV_API_KEY não configurada no .env",
                status_code=503,
                error_code="SERVICE_UNAVAILABLE",
            )

        client = TLDVClient(api_key=TLDV_API_KEY)
        consolidator = JSONConsolidator(output_dir=self.transcriptions_dir)
        processor = SmartMeetingProcessor(tldv_client=client, consolidator=consolidator)

        all_meetings = client.list_meetings()
        self.stats["meetings_found"] = len(all_meetings)
        logger.info(f"Reuniões encontradas na API: {len(all_meetings)}")

        existing_ids = self._get_existing_meeting_ids()
        logger.info(f"Reuniões já baixadas em disco: {len(existing_ids)}")

        new_meetings = [m for m in all_meetings if m.id not in existing_ids]
        self.stats["meetings_already_downloaded"] = len(existing_ids)

        if not new_meetings:
            logger.info("Nenhuma reunião nova para baixar — Fase 1 concluída (incremental)")
            return True

        logger.info(f"Reuniões novas para processar: {len(new_meetings)}")

        for i, meeting in enumerate(new_meetings):
            logger.info(f"Processando {i + 1}/{len(new_meetings)}: {meeting.name}")

            try:
                self._process_single_meeting(meeting, processor, consolidator)
            except ApplicationError as e:
                logger.error(f"Erro ao processar reunião '{meeting.name}': {e.message}")
                self.stats["meetings_failed"] += 1
                self.stats["errors"].append(f"Ingestion — {meeting.name}: {e.message}")
            except Exception as e:
                logger.error(f"Erro inesperado ao processar reunião '{meeting.name}': {e}")
                self.stats["meetings_failed"] += 1
                self.stats["errors"].append(f"Ingestion — {meeting.name}: {e!s}")

        logger.info(
            f"Fase 1 concluída — "
            f"baixadas: {self.stats['meetings_downloaded']}, "
            f"incompletas: {self.stats['meetings_skipped_incomplete']}, "
            f"falhas: {self.stats['meetings_failed']}"
        )

        processor.shutdown_background_threads()
        return True

    # ────────────────────────────────────────────────────────────────────────
    # FASE 2 — INDEXAÇÃO
    # ────────────────────────────────────────────────────────────────────────

    def _get_indexed_meeting_ids(self) -> set[str]:
        """Retorna IDs de reuniões já indexadas no ChromaDB.

        Returns:
            Set com meeting_ids já presentes no ChromaDB. Vazio se DB não existe.
        """
        if not self.vector_db_dir.exists():
            return set()

        try:
            store = ChromaDBStore()
            indexed_ids = store.get_distinct_values("meeting_id")
            return set(indexed_ids)
        except Exception as e:
            logger.warning(f"Erro ao consultar meeting_ids no ChromaDB: {e}")
            return set()

    def _get_new_json_files(self) -> list[Path]:
        """Retorna JSONs de transcrição que ainda não foram indexados.

        Compara meeting_ids dos JSONs em disco com os já presentes no ChromaDB.

        Returns:
            Lista de Paths de arquivos não indexados.
        """
        all_json_files = list(self.transcriptions_dir.glob("*.json"))

        if not all_json_files:
            return []

        indexed_ids = self._get_indexed_meeting_ids()

        if not indexed_ids:
            logger.info("Nenhum dado indexado ainda — processando todos os JSONs")
            return all_json_files

        new_files: list[Path] = []
        for json_file in all_json_files:
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                meeting_id = data.get("metadata", {}).get("meeting_id") or data.get("meeting_id", "")
                if meeting_id in indexed_ids:
                    logger.debug(f"Já indexado, pulando: {json_file.name}")
                    self.stats["videos_already_indexed"] += 1
                else:
                    new_files.append(json_file)
            except Exception as e:
                logger.warning(f"Erro ao verificar {json_file.name}, incluindo no processamento: {e}")
                new_files.append(json_file)

        return new_files

    def run_indexing(self) -> bool:
        """Fase 2: Indexa JSONs de transcrição no ChromaDB.

        Opera de forma incremental: pula vídeos cujo meeting_id já está no ChromaDB.
        Para cada JSON novo: faz chunking + extração LLM de metadados + geração de embeddings.

        Returns:
            True se ao menos um vídeo foi indexado ou já estava indexado, False se erro crítico.
        """
        logger.info("═" * 120)
        logger.info("FASE 2 — INDEXAÇÃO: Processando JSONs para ChromaDB")
        logger.info("═" * 120)

        new_files = self._get_new_json_files()
        total_existing = self.stats["videos_already_indexed"]

        if not new_files:
            logger.info(
                f"Nenhum JSON novo para indexar — "
                f"{total_existing} vídeo(s) já indexado(s). Fase 2 concluída (incremental)"
            )
            return True

        logger.info(f"JSONs para indexar: {len(new_files)} | já indexados: {total_existing}")

        engine = IndexingEngine(
            input_dir=self.transcriptions_dir,
            enable_chromadb=True,
            generate_txt_files=True,
        )

        for i, json_file in enumerate(new_files):
            logger.info(f"Indexando {i + 1}/{len(new_files)}: {json_file.name}")
            try:
                video_stats = engine.process_single_video(json_file)
                self.stats["videos_indexed"] += 1
                self.stats["chunks_indexed"] += video_stats.get("parts_created", 0)
                logger.info(
                    f"Vídeo indexado: {json_file.name} — "
                    f"{video_stats.get('parts_created', 0)} chunks, "
                    f"{video_stats.get('segments_processed', 0)} segmentos"
                )
            except ApplicationError as e:
                logger.error(f"Erro ao indexar '{json_file.name}': {e.message}")
                self.stats["videos_failed"] += 1
                self.stats["errors"].append(f"Indexação — {json_file.name}: {e.message}")
            except Exception as e:
                logger.error(f"Erro inesperado ao indexar '{json_file.name}': {e}")
                self.stats["videos_failed"] += 1
                self.stats["errors"].append(f"Indexação — {json_file.name}: {e!s}")

        logger.info(
            f"Fase 2 concluída — "
            f"indexados: {self.stats['videos_indexed']}, "
            f"chunks: {self.stats['chunks_indexed']}, "
            f"falhas: {self.stats['videos_failed']}"
        )
        return True

    # ────────────────────────────────────────────────────────────────────────
    # FASE 3 — VALIDAÇÃO
    # ────────────────────────────────────────────────────────────────────────

    def run_validation(self) -> bool:
        """Fase 3: Valida estado do ChromaDB e coleta estatísticas.

        Returns:
            True se ChromaDB contém documentos, False se vazio ou inacessível.
        """
        logger.info("═" * 120)
        logger.info("FASE 3 — VALIDAÇÃO: Verificando estado do ChromaDB")
        logger.info("═" * 120)

        if not self.vector_db_dir.exists():
            logger.error("Diretório vector_db não encontrado — indexação pode não ter sido executada")
            return False

        try:
            store = ChromaDBStore()
            info = store.get_collection_info()

            if "error" in info:
                logger.error(f"Erro ao obter informações da coleção: {info['error']}")
                return False

            total_docs = info.get("total_documents", 0)
            self.stats["total_documents"] = total_docs
            self.stats["unique_clients"] = info.get("unique_clients", [])

            if total_docs == 0:
                logger.warning("ChromaDB existe mas não contém documentos")
                return False

            logger.info(f"Total de documentos no ChromaDB: {total_docs}")
            logger.info(f"Clientes indexados: {info.get('unique_clients', [])}")
            logger.info(f"Coleção: {info.get('collection_name', '')}")
            logger.info(f"Dimensões de embedding: {info.get('embedding_dimensions', 1536)}")

            return True

        except Exception as e:
            logger.error(f"Erro ao validar ChromaDB: {e}")
            self.stats["errors"].append(f"Validação: {e!s}")
            return False

    # ────────────────────────────────────────────────────────────────────────
    # RELATÓRIO FINAL
    # ────────────────────────────────────────────────────────────────────────

    def _print_summary(self, success: bool) -> None:
        """Imprime resumo final do pipeline.

        Args:
            success: True se todas as fases concluíram com sucesso.
        """
        end_time = self.stats.get("end_time") or datetime.now()
        start_time = self.stats.get("start_time") or end_time
        duration = (end_time - start_time).total_seconds() if isinstance(start_time, datetime) else 0

        status_label = "CONCLUÍDO COM SUCESSO" if success else "CONCLUÍDO COM FALHAS"

        logger.info("═" * 120)
        logger.info(f"PIPELINE KT — {status_label}")
        logger.info("─" * 120)
        logger.info(f"Duração total:             {duration:.1f}s")
        logger.info("─" * 120)
        logger.info("FASE 1 — INGESTION:")
        logger.info(f"  Reuniões na API:          {self.stats['meetings_found']}")
        logger.info(f"  Já baixadas (skip):       {self.stats['meetings_already_downloaded']}")
        logger.info(f"  Baixadas nesta execução:  {self.stats['meetings_downloaded']}")
        logger.info(f"  Incompletas (skip):       {self.stats['meetings_skipped_incomplete']}")
        logger.info(f"  Falhas:                   {self.stats['meetings_failed']}")
        logger.info("─" * 120)
        logger.info("FASE 2 — INDEXAÇÃO:")
        logger.info(f"  Já indexados (skip):      {self.stats['videos_already_indexed']}")
        logger.info(f"  Indexados nesta execução: {self.stats['videos_indexed']}")
        logger.info(f"  Chunks gerados:           {self.stats['chunks_indexed']}")
        logger.info(f"  Falhas:                   {self.stats['videos_failed']}")
        logger.info("─" * 120)
        logger.info("FASE 3 — VALIDAÇÃO:")
        logger.info(f"  Total de documentos:      {self.stats['total_documents']}")
        logger.info(f"  Clientes indexados:       {self.stats['unique_clients']}")
        logger.info("─" * 120)

        if self.stats["errors"]:
            logger.warning(f"Erros encontrados ({len(self.stats['errors'])}):")
            for err in self.stats["errors"]:
                logger.warning(f"  • {err}")

        logger.info("═" * 120)

    # ────────────────────────────────────────────────────────────────────────
    # ORQUESTRADOR PRINCIPAL
    # ────────────────────────────────────────────────────────────────────────

    def run_full_pipeline(
        self,
        force_clean: bool = False,
        skip_ingestion: bool = False,
        skip_indexing: bool = False,
    ) -> bool:
        """Executa o pipeline completo de processamento KT.

        Args:
            force_clean: Se True, apaga todos os dados antes de processar.
            skip_ingestion: Se True, pula a Fase 1 (ingestion do TL:DV).
            skip_indexing: Se True, pula a Fase 2 (indexação no ChromaDB).

        Returns:
            True se todas as fases executadas concluíram com sucesso.
        """
        self.stats["start_time"] = datetime.now()
        success = True

        logger.info("═" * 120)
        logger.info("KT TRANSCRIBER — PIPELINE COMPLETO")
        logger.info(f"Início: {self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        if force_clean:
            logger.warning("Modo: FORCE CLEAN — todos os dados serão apagados e reprocessados")
        else:
            logger.info("Modo: INCREMENTAL — apenas dados novos serão processados")
        logger.info("═" * 120)

        if force_clean:
            self.force_clean()

        if not skip_ingestion:
            try:
                phase_ok = self.run_ingestion()
                if not phase_ok:
                    logger.error("Fase 1 (Ingestion) falhou")
                    success = False
            except ApplicationError as e:
                logger.error(f"Fase 1 abortada: {e.message}")
                success = False
                self.stats["errors"].append(f"Fase 1 abortada: {e.message}")
        else:
            logger.info("Fase 1 (Ingestion) pulada via --skip-ingestion")

        if not skip_indexing:
            try:
                phase_ok = self.run_indexing()
                if not phase_ok:
                    logger.error("Fase 2 (Indexação) falhou")
                    success = False
            except ApplicationError as e:
                logger.error(f"Fase 2 abortada: {e.message}")
                success = False
                self.stats["errors"].append(f"Fase 2 abortada: {e.message}")
        else:
            logger.info("Fase 2 (Indexação) pulada via --skip-indexing")

        try:
            phase_ok = self.run_validation()
            if not phase_ok:
                logger.warning("Fase 3 (Validação) reportou problemas")
                success = False
        except Exception as e:
            logger.error(f"Fase 3 abortada: {e}")
            success = False

        self.stats["end_time"] = datetime.now()
        self._print_summary(success)

        return success


# ════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA
# ════════════════════════════════════════════════════════════════════════════


def main() -> None:
    """Ponto de entrada do pipeline KT.

    Parseia argumentos de linha de comando e executa o pipeline completo.
    """
    parser = argparse.ArgumentParser(
        description="Pipeline completo de processamento KT Transcriber",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  uv run python scripts/run_full_pipeline.py\n"
            "  uv run python scripts/run_full_pipeline.py --force-clean\n"
            "  uv run python scripts/run_full_pipeline.py --skip-ingestion\n"
            "  uv run python scripts/run_full_pipeline.py --skip-indexing\n"
        ),
    )

    parser.add_argument(
        "--force-clean",
        action="store_true",
        help="ATENCAO: Apaga TODOS os dados (transcriptions/ + vector_db/) e reprocessa do zero",
    )
    parser.add_argument(
        "--skip-ingestion",
        action="store_true",
        help="Pula a Fase 1 (download do TL:DV) — usa JSONs já existentes em transcriptions/",
    )
    parser.add_argument(
        "--skip-indexing",
        action="store_true",
        help="Pula a Fase 2 (indexação no ChromaDB) — executa apenas ingestion + validação",
    )

    args = parser.parse_args()

    if args.skip_ingestion and args.skip_indexing:
        parser.error("Não é possível usar --skip-ingestion e --skip-indexing ao mesmo tempo")

    initialize_application()

    if args.force_clean:
        logger.warning("FORCE CLEAN ativado: todos os dados processados serão apagados")

    runner = FullPipelineRunner()

    try:
        success = runner.run_full_pipeline(
            force_clean=args.force_clean,
            skip_ingestion=args.skip_ingestion,
            skip_indexing=args.skip_indexing,
        )
    except KeyboardInterrupt:
        logger.warning("Pipeline interrompido pelo usuário (Ctrl+C)")
        raise SystemExit(1) from None
    except Exception as e:
        logger.error(f"Erro fatal no pipeline: {e}")
        raise SystemExit(1) from e

    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
