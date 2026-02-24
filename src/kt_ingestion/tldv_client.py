"""Cliente TL:DV — Transcrição de KT.

Gerencia integração com TL:DV para importação e obtenção de transcrições de vídeos.
"""

import time
from dataclasses import dataclass
from enum import Enum

import requests

from src.config.settings import TLDV_BASE_URL, TLDV_TIMEOUT
from utils.exception_setup import ApplicationError
from utils.logger_setup import LoggerManager

logger = LoggerManager.get_logger(__name__)


class MeetingStatus(Enum):
    """Status possíveis de uma reunião no TL:DV."""

    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PENDING = "pending"


@dataclass
class TranscriptSegment:
    """Segmento individual de transcrição."""

    speaker: str
    text: str
    start_time: float
    end_time: float


@dataclass
class Highlight:
    """Ponto importante destacado da reunião."""

    text: str
    start_time: float
    source: str
    topic: dict | None = None


@dataclass
class MeetingData:
    """Dados completos de uma reunião processada."""

    id: str
    name: str
    happened_at: str
    url: str
    duration: int
    status: MeetingStatus
    organizer: dict | None = None
    invitees: list[dict] | None = None
    template: str = "meeting"


class TLDVClient:
    """Cliente para integração com TL:DV API."""

    def __init__(self, api_key: str):
        """Inicializa cliente TL:DV.

        Args:
            api_key: Chave da API TL:DV.
        """
        self.api_key = api_key
        self.base_url = TLDV_BASE_URL
        self.timeout = TLDV_TIMEOUT
        self.session = requests.Session()
        self.session.headers.update({"x-api-key": api_key, "Content-Type": "application/json"})
        logger.info("Cliente TL:DV inicializado")

    def import_meeting(self, video_url: str, meeting_name: str, happened_at: str | None = None) -> str:
        """Importa vídeo para processamento no TL:DV.

        IMPORTANTE: Import é assíncrono e retorna apenas jobId (referência de log).
        Para obter o meeting_id, deve-se buscar na lista de meetings por nome.

        Args:
            video_url: URL pública do vídeo.
            meeting_name: Nome da reunião.
            happened_at: Data/hora da reunião (ISO format, opcional).

        Returns:
            Job ID para referência de log (NÃO é o meeting_id).
        """
        try:
            from datetime import datetime

            payload: dict = {"url": video_url, "name": meeting_name}
            if happened_at:
                payload["happenedAt"] = happened_at
            else:
                payload["happenedAt"] = datetime.now().isoformat() + "Z"

            response = self.session.post(f"{self.base_url}/meetings/import", json=payload, timeout=self.timeout)
            response.raise_for_status()
            import_response = response.json()

            logger.info(f"Response do import: {import_response}")
            success = import_response.get("success", False)
            job_id = import_response.get("jobId")
            message = import_response.get("message", "")

            if not success:
                error_msg = f"Import falhou: {message or 'Erro desconhecido'}"
                logger.error(error_msg)
                raise ApplicationError(
                    message=error_msg,
                    status_code=503,
                    error_code="SERVICE_UNAVAILABLE",
                    context={"meeting_name": meeting_name, "video_url": video_url},
                )

            if not job_id:
                logger.warning("jobId não retornado, mas success=true")

            logger.info(f"Import bem-sucedido — JobID: {job_id} — Mensagem: {message}")
            return job_id

        except requests.exceptions.HTTPError as e:
            resp = e.response
            if resp is not None and resp.status_code == 401:
                raise ApplicationError(
                    message="API key TL:DV inválida ou expirada",
                    status_code=503,
                    error_code="SERVICE_UNAVAILABLE",
                    context={"meeting_name": meeting_name},
                ) from e
            elif resp is not None and resp.status_code == 400:
                raise ApplicationError(
                    message=f"URL ou dados do vídeo inválidos: {resp.text}",
                    status_code=422,
                    error_code="VALIDATION_ERROR",
                    context={"meeting_name": meeting_name, "video_url": video_url},
                ) from e
            elif resp is not None and resp.status_code == 429:
                raise ApplicationError(
                    message="Muitas requisições à API TL:DV. Aguarde antes de tentar novamente.",
                    status_code=429,
                    error_code="QUOTA_EXCEEDED",
                    context={"meeting_name": meeting_name},
                ) from e
            else:
                raise ApplicationError(
                    message=f"Erro HTTP ao importar reunião: {e}",
                    status_code=503,
                    error_code="SERVICE_UNAVAILABLE",
                    context={"meeting_name": meeting_name},
                ) from e
        except requests.exceptions.RequestException as e:
            raise ApplicationError(
                message=f"Erro de conexão com TL:DV: {e}",
                status_code=503,
                error_code="SERVICE_UNAVAILABLE",
                context={"meeting_name": meeting_name},
            ) from e

    def find_meeting_by_name(self, meeting_name: str, debug_list: bool = False) -> str | None:
        """Busca reunião recém-criada pelo nome com busca fuzzy.

        Args:
            meeting_name: Nome da reunião para buscar.
            debug_list: Se True, lista todas as reuniões encontradas para debug.

        Returns:
            Meeting ID se encontrado, None caso contrário.
        """
        try:
            response = self.session.get(
                f"{self.base_url}/meetings",
                params={"limit": 100},
                timeout=self.timeout // 2,
            )
            response.raise_for_status()
            meetings_data = response.json()
            meetings_list = meetings_data.get("results", [])

            if debug_list:
                logger.info(f"=== DEBUG: Listando {len(meetings_list)} reuniões encontradas ===")
                for i, meeting in enumerate(meetings_list[:10]):
                    logger.info(f"  {i+1}: ID={meeting.get('id')} | Nome='{meeting.get('name')}'")
                logger.info("=== FIM DEBUG ===")

            # Estratégia 1: Busca por nome exato
            for meeting in meetings_list:
                if meeting.get("name") == meeting_name:
                    logger.info(f"Reunião encontrada (nome exato): {meeting.get('id')} — {meeting_name}")
                    return meeting.get("id")

            # Estratégia 2: Busca fuzzy
            original_name_clean = meeting_name.replace(" ", "").lower()
            for meeting in meetings_list:
                meeting_name_clean = meeting.get("name", "").replace(" ", "").lower()
                if original_name_clean in meeting_name_clean or meeting_name_clean in original_name_clean:
                    logger.info(
                        f"Reunião encontrada (busca fuzzy): {meeting.get('id')} — '{meeting.get('name')}'"
                    )
                    return meeting.get("id")

            # Estratégia 3: Busca por palavras-chave
            keywords = self._extract_keywords_from_name(meeting_name)
            if keywords:
                for meeting in meetings_list:
                    meeting_name_lower = meeting.get("name", "").lower()
                    matches = sum(1 for keyword in keywords if keyword in meeting_name_lower)
                    if matches / len(keywords) >= 0.6:
                        logger.info(
                            f"Reunião encontrada (palavras-chave): {meeting.get('id')} — '{meeting.get('name')}'"
                        )
                        return meeting.get("id")

            logger.warning(f"Reunião não encontrada com nenhuma estratégia: {meeting_name}")
            return None

        except requests.exceptions.HTTPError as e:
            resp = e.response
            if resp is not None and resp.status_code == 401:
                logger.error("API key inválida ao buscar reuniões")
            else:
                logger.error(f"Erro HTTP ao buscar reunião {meeting_name}: {e}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao buscar reunião {meeting_name}: {e}")
            return None

    def _extract_keywords_from_name(self, meeting_name: str) -> list[str]:
        """Extrai palavras-chave significativas do nome da reunião.

        Args:
            meeting_name: Nome original da reunião.

        Returns:
            Lista de palavras-chave em lowercase.
        """
        import re

        clean_name = re.sub(r"[-()\[\]_]+", " ", meeting_name)
        words = [word.strip().lower() for word in clean_name.split() if len(word.strip()) > 2]

        stopwords = {"para", "de", "da", "do", "em", "com", "por", "uma", "um", "na", "no", "que", "the", "and"}
        keywords = [word for word in words if word not in stopwords and len(word) > 2]

        logger.info(f"Palavras-chave extraídas de '{meeting_name}': {keywords}")
        return keywords[:5]

    def get_meeting_status(self, meeting_id: str) -> MeetingData:
        """Obtém status e dados de uma reunião.

        Args:
            meeting_id: ID da reunião.

        Returns:
            Dados da reunião.
        """
        try:
            response = self.session.get(f"{self.base_url}/meetings/{meeting_id}", timeout=self.timeout // 2)
            response.raise_for_status()
            data = response.json()

            return MeetingData(
                id=data.get("id"),
                name=data.get("name"),
                happened_at=data.get("happenedAt"),
                url=data.get("url"),
                duration=data.get("duration", 0),
                status=MeetingStatus(data.get("status", "pending")),
                organizer=data.get("organizer"),
                invitees=data.get("invitees", []),
                template=data.get("template", "meeting"),
            )

        except requests.exceptions.HTTPError as e:
            resp = e.response
            if resp is not None and resp.status_code == 404:
                raise ApplicationError(
                    message=f"Reunião {meeting_id} não encontrada",
                    status_code=404,
                    error_code="NOT_FOUND",
                    context={"meeting_id": meeting_id},
                ) from e
            elif resp is not None and resp.status_code == 401:
                raise ApplicationError(
                    message="API key TL:DV inválida",
                    status_code=503,
                    error_code="SERVICE_UNAVAILABLE",
                    context={"meeting_id": meeting_id},
                ) from e
            else:
                raise ApplicationError(
                    message=f"Erro HTTP ao obter status da reunião: {e}",
                    status_code=503,
                    error_code="SERVICE_UNAVAILABLE",
                    context={"meeting_id": meeting_id},
                ) from e
        except requests.exceptions.RequestException as e:
            raise ApplicationError(
                message=f"Erro de conexão ao obter status da reunião: {e}",
                status_code=503,
                error_code="SERVICE_UNAVAILABLE",
                context={"meeting_id": meeting_id},
            ) from e

    def get_transcript(self, meeting_id: str) -> list[TranscriptSegment]:
        """Obtém transcrição completa de uma reunião.

        Args:
            meeting_id: ID da reunião.

        Returns:
            Lista de segmentos de transcrição.
        """
        try:
            response = self.session.get(
                f"{self.base_url}/meetings/{meeting_id}/transcript", timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            segments = []
            for item in data.get("data", []):
                segments.append(
                    TranscriptSegment(
                        speaker=item.get("speaker", "Unknown"),
                        text=item.get("text", ""),
                        start_time=item.get("startTime", 0.0),
                        end_time=item.get("endTime", 0.0),
                    )
                )

            logger.info(f"Transcrição obtida: {len(segments)} segmentos para reunião {meeting_id}")
            return segments

        except requests.exceptions.HTTPError as e:
            resp = e.response
            if resp is not None and resp.status_code == 404:
                raise ApplicationError(
                    message=f"Transcrição não disponível para reunião {meeting_id}",
                    status_code=404,
                    error_code="NOT_FOUND",
                    context={"meeting_id": meeting_id},
                ) from e
            elif resp is not None and resp.status_code == 402:
                raise ApplicationError(
                    message="Limite de créditos TL:DV excedido. Verifique sua conta.",
                    status_code=429,
                    error_code="QUOTA_EXCEEDED",
                    context={"meeting_id": meeting_id},
                ) from e
            else:
                raise ApplicationError(
                    message=f"Erro HTTP ao obter transcrição: {e}",
                    status_code=503,
                    error_code="SERVICE_UNAVAILABLE",
                    context={"meeting_id": meeting_id},
                ) from e
        except requests.exceptions.RequestException as e:
            raise ApplicationError(
                message=f"Erro de conexão ao obter transcrição: {e}",
                status_code=503,
                error_code="SERVICE_UNAVAILABLE",
                context={"meeting_id": meeting_id},
            ) from e

    def get_highlights(self, meeting_id: str) -> list[Highlight]:
        """Obtém pontos importantes destacados de uma reunião.

        Args:
            meeting_id: ID da reunião.

        Returns:
            Lista de highlights.
        """
        try:
            response = self.session.get(
                f"{self.base_url}/meetings/{meeting_id}/highlights", timeout=self.timeout // 2
            )
            response.raise_for_status()
            data = response.json()

            highlights = []
            for item in data.get("data", []):
                highlights.append(
                    Highlight(
                        text=item.get("text", ""),
                        start_time=item.get("startTime", 0.0),
                        source=item.get("source", "auto"),
                        topic=item.get("topic"),
                    )
                )

            logger.info(f"Highlights obtidos: {len(highlights)} itens para reunião {meeting_id}")
            return highlights

        except requests.exceptions.HTTPError as e:
            resp = e.response
            if resp is not None and resp.status_code == 404:
                raise ApplicationError(
                    message=f"Highlights não disponíveis para reunião {meeting_id}",
                    status_code=404,
                    error_code="NOT_FOUND",
                    context={"meeting_id": meeting_id},
                ) from e
            else:
                raise ApplicationError(
                    message=f"Erro HTTP ao obter highlights: {e}",
                    status_code=503,
                    error_code="SERVICE_UNAVAILABLE",
                    context={"meeting_id": meeting_id},
                ) from e
        except requests.exceptions.RequestException as e:
            raise ApplicationError(
                message=f"Erro de conexão ao obter highlights: {e}",
                status_code=503,
                error_code="SERVICE_UNAVAILABLE",
                context={"meeting_id": meeting_id},
            ) from e

    def wait_for_meeting_by_name(
        self,
        meeting_name: str,
        max_wait_time: int = 3600,
        polling_interval: int = 30,
        debug_first_attempt: bool = True,
    ) -> str:
        """Aguarda criação da reunião pelo nome após import.

        Args:
            meeting_name: Nome da reunião importada.
            max_wait_time: Tempo máximo de espera em segundos.
            polling_interval: Intervalo entre verificações em segundos.
            debug_first_attempt: Se True, ativa debug na primeira tentativa.

        Returns:
            Meeting ID quando reunião for encontrada.
        """
        start_time = time.time()
        logger.info(f"Aguardando criação da reunião: {meeting_name}")
        attempt_count = 0

        while time.time() - start_time < max_wait_time:
            try:
                attempt_count += 1
                debug_mode = debug_first_attempt and attempt_count == 1
                meeting_id = self.find_meeting_by_name(meeting_name, debug_list=debug_mode)

                if meeting_id:
                    logger.info(f"Reunião criada com sucesso: {meeting_id} (tentativa {attempt_count})")
                    return meeting_id

                elapsed = time.time() - start_time
                logger.info(
                    f"Reunião ainda não disponível — tentativa {attempt_count}, {elapsed:.0f}s decorridos"
                )
                time.sleep(polling_interval)

            except Exception as e:
                logger.error(f"Erro durante busca da reunião {meeting_name} (tentativa {attempt_count}): {e}")
                time.sleep(polling_interval)

        raise ApplicationError(
            message=f"Timeout aguardando criação da reunião '{meeting_name}' após {max_wait_time}s",
            status_code=503,
            error_code="SERVICE_UNAVAILABLE",
            context={"meeting_name": meeting_name, "attempts": attempt_count},
        )

    def wait_for_completion(
        self, meeting_id: str, max_wait_time: int = 3600, polling_interval: int = 30
    ) -> MeetingData:
        """Aguarda conclusão do processamento de uma reunião.

        Args:
            meeting_id: ID da reunião.
            max_wait_time: Tempo máximo de espera em segundos.
            polling_interval: Intervalo entre verificações em segundos.

        Returns:
            Dados da reunião quando processamento concluído.
        """
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            try:
                meeting = self.get_meeting_status(meeting_id)

                if meeting.status == MeetingStatus.COMPLETED:
                    logger.info(f"Processamento concluído para reunião {meeting_id}")
                    return meeting

                if meeting.status == MeetingStatus.FAILED:
                    raise ApplicationError(
                        message=f"Processamento falhou para reunião {meeting_id}",
                        status_code=503,
                        error_code="SERVICE_UNAVAILABLE",
                        context={"meeting_id": meeting_id},
                    )

                logger.info(f"Reunião {meeting_id} em processamento. Status: {meeting.status.value}")
                time.sleep(polling_interval)

            except ApplicationError:
                raise
            except Exception as e:
                logger.error(f"Erro durante polling da reunião {meeting_id}: {e}")
                time.sleep(polling_interval)

        raise ApplicationError(
            message=f"Timeout aguardando processamento da reunião {meeting_id}",
            status_code=503,
            error_code="SERVICE_UNAVAILABLE",
            context={"meeting_id": meeting_id},
        )

    def get_complete_meeting_data(self, meeting_id: str) -> dict:
        """Obtém todos os dados de uma reunião (metadata, transcrição e highlights).

        Args:
            meeting_id: ID da reunião.

        Returns:
            Dicionário com todos os dados da reunião.
        """
        meeting = self.get_meeting_status(meeting_id)

        if meeting.status != MeetingStatus.COMPLETED:
            raise ApplicationError(
                message=f"Reunião {meeting_id} ainda não foi processada completamente",
                status_code=503,
                error_code="SERVICE_UNAVAILABLE",
                context={"meeting_id": meeting_id, "status": meeting.status.value},
            )

        transcript = self.get_transcript(meeting_id)
        highlights = self.get_highlights(meeting_id)

        complete_data = {
            "meeting": {
                "id": meeting.id,
                "name": meeting.name,
                "happened_at": meeting.happened_at,
                "url": meeting.url,
                "duration": meeting.duration,
                "status": meeting.status.value,
                "organizer": meeting.organizer,
                "invitees": meeting.invitees,
                "template": meeting.template,
            },
            "transcript": [
                {"speaker": seg.speaker, "text": seg.text, "start_time": seg.start_time, "end_time": seg.end_time}
                for seg in transcript
            ],
            "highlights": [
                {"text": hl.text, "start_time": hl.start_time, "source": hl.source, "topic": hl.topic}
                for hl in highlights
            ],
        }

        logger.info(f"Dados completos obtidos para reunião {meeting_id}")
        return complete_data

    def validate_api_key(self) -> bool:
        """Valida se a API key está funcionando.

        Returns:
            True se API key é válida, False caso contrário.
        """
        try:
            response = self.session.get(f"{self.base_url}/meetings", params={"limit": 1}, timeout=10)
            response.raise_for_status()
            logger.info("API key TL:DV validada com sucesso")
            return True

        except requests.exceptions.HTTPError as e:
            resp = e.response
            if resp is not None and resp.status_code == 401:
                logger.error("API key TL:DV inválida")
            elif resp is not None and resp.status_code == 429:
                logger.error("Rate limit excedido ao validar API key")
            else:
                logger.error(f"Erro HTTP ao validar API key: {e}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao validar API key: {e}")
            return False

    def import_and_wait_meeting(
        self, video_url: str, meeting_name: str, happened_at: str | None = None, max_wait_time: int = 3600
    ) -> str:
        """Método integrado: importa vídeo e aguarda até reunião estar disponível.

        Args:
            video_url: URL pública do vídeo.
            meeting_name: Nome da reunião (deve ser único para identificação).
            happened_at: Data/hora da reunião (opcional).
            max_wait_time: Tempo máximo de espera em segundos.

        Returns:
            Meeting ID final após processamento completo.
        """
        job_id = self.import_meeting(video_url, meeting_name, happened_at)
        logger.info(f"Import iniciado com JobID: {job_id}")

        meeting_id = self.wait_for_meeting_by_name(meeting_name, max_wait_time // 2)
        self.wait_for_completion(meeting_id, max_wait_time // 2)

        logger.info(f"Processamento completo finalizado para: {meeting_name}")
        return meeting_id

    def get_meeting_transcript(self, meeting_id: str) -> list[dict]:
        """Alias para get_transcript() — compatibilidade com SmartMeetingProcessor.

        Returns:
            Lista de dicionários com segmentos de transcrição.
        """
        segments = self.get_transcript(meeting_id)
        return [
            {"speaker": seg.speaker, "text": seg.text, "start_time": seg.start_time, "end_time": seg.end_time}
            for seg in segments
        ]

    def get_meeting_highlights(self, meeting_id: str) -> list[dict]:
        """Alias para get_highlights() — compatibilidade com SmartMeetingProcessor.

        Returns:
            Lista de dicionários com highlights.
        """
        highlights = self.get_highlights(meeting_id)
        return [
            {"text": h.text, "start_time": h.start_time, "source": h.source, "topic": h.topic}
            for h in highlights
        ]

    def list_meetings(self, limit: int = 100) -> list[MeetingData]:
        """Lista todas as reuniões disponíveis na conta.

        Args:
            limit: Número máximo de reuniões para retornar.

        Returns:
            Lista de objetos MeetingData.
        """
        try:
            response = self.session.get(
                f"{self.base_url}/meetings", params={"limit": limit}, timeout=self.timeout // 2
            )
            response.raise_for_status()
            meetings_data = response.json()
            meetings_list = meetings_data.get("results", [])

            meetings = []
            for meeting_dict in meetings_list:
                try:
                    status_str = meeting_dict.get("status", "unknown").lower()
                    status_map = {
                        "completed": MeetingStatus.COMPLETED,
                        "processing": MeetingStatus.PROCESSING,
                        "failed": MeetingStatus.FAILED,
                        "pending": MeetingStatus.PENDING,
                    }
                    status = status_map.get(status_str, MeetingStatus.PENDING)

                    meetings.append(
                        MeetingData(
                            id=meeting_dict.get("id", ""),
                            name=meeting_dict.get("name", ""),
                            happened_at=meeting_dict.get("happened_at", ""),
                            url=meeting_dict.get("url", ""),
                            duration=meeting_dict.get("duration", 0),
                            status=status,
                            organizer=meeting_dict.get("organizer"),
                        )
                    )
                except Exception as e:
                    logger.warning(f"Erro ao processar reunião {meeting_dict.get('id')}: {e}")

            logger.info(f"Listadas {len(meetings)} reuniões")
            return meetings

        except requests.exceptions.HTTPError as e:
            raise ApplicationError(
                message=f"Erro HTTP ao listar reuniões: {e}",
                status_code=503,
                error_code="SERVICE_UNAVAILABLE",
            ) from e
        except requests.exceptions.RequestException as e:
            raise ApplicationError(
                message=f"Erro de conexão ao listar reuniões: {e}",
                status_code=503,
                error_code="SERVICE_UNAVAILABLE",
            ) from e
