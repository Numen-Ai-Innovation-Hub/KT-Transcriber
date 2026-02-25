"""Testes unitários para kt_ingestion — TLDVClient, JSONConsolidator, SmartMeetingProcessor."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from utils.exception_setup import ApplicationError

# ════════════════════════════════════════════════════════════════════════════
# HELPERS INLINE
# ════════════════════════════════════════════════════════════════════════════


def make_meeting_data(
    meeting_id: str = "mtg-001",
    name: str = "KT Session",
    status: str = "completed",
) -> dict:
    """Retorna estrutura de meeting_data compatível com TLDVClient.get_complete_meeting_data."""
    return {
        "meeting": {
            "id": meeting_id,
            "name": name,
            "happened_at": "2024-01-15T10:00:00Z",
            "url": "https://tldv.io/meeting/001",
            "duration": 3600,
            "status": status,
            "organizer": {"name": "Ana"},
            "invitees": [{"name": "Carlos"}],
            "template": "meeting",
        },
        "transcript": [
            {"speaker": "Ana", "text": "Texto de exemplo.", "start_time": 0.0, "end_time": 5.0},
        ],
        "highlights": [
            {"text": "Ponto importante.", "start_time": 1.0, "source": "auto", "topic": None},
        ],
    }


def make_mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """Retorna mock de requests.Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status.return_value = None
    return mock_resp


# ════════════════════════════════════════════════════════════════════════════
# TLDVClient
# ════════════════════════════════════════════════════════════════════════════


class TestTLDVClientKeywordExtraction:
    """Testa extração de palavras-chave — método puro, sem I/O."""

    def test_extrai_palavras_relevantes(self) -> None:
        """Palavras longas são extraídas do nome."""
        from src.kt_ingestion.tldv_client import TLDVClient

        client = TLDVClient(api_key="fake-key")
        keywords = client._extract_keywords_from_name("KT Session SAP Finance")
        assert "session" in keywords
        assert "finance" in keywords

    def test_remove_stopwords_pt(self) -> None:
        """Stopwords em português são removidas."""
        from src.kt_ingestion.tldv_client import TLDVClient

        client = TLDVClient(api_key="fake-key")
        keywords = client._extract_keywords_from_name("Reunião de KT para cliente")
        assert "para" not in keywords
        assert "de" not in keywords

    def test_limita_5_palavras(self) -> None:
        """Retorna no máximo 5 palavras-chave."""
        from src.kt_ingestion.tldv_client import TLDVClient

        client = TLDVClient(api_key="fake-key")
        long_name = "Alpha Beta Gamma Delta Epsilon Zeta Eta"
        keywords = client._extract_keywords_from_name(long_name)
        assert len(keywords) <= 5

    def test_nome_vazio_retorna_lista_vazia(self) -> None:
        """Nome vazio retorna lista vazia."""
        from src.kt_ingestion.tldv_client import TLDVClient

        client = TLDVClient(api_key="fake-key")
        keywords = client._extract_keywords_from_name("")
        assert keywords == []


class TestTLDVClientImportMeeting:
    """Testa import_meeting com HTTP mockado."""

    def test_import_meeting_sucesso_retorna_job_id(self) -> None:
        """Import bem-sucedido retorna job_id."""
        from src.kt_ingestion.tldv_client import TLDVClient

        client = TLDVClient(api_key="fake-key")
        mock_resp = make_mock_response({"success": True, "jobId": "job-123", "message": "OK"})

        with patch.object(client.session, "post", return_value=mock_resp):
            job_id = client.import_meeting("https://example.com/video.mp4", "Reunião KT")

        assert job_id == "job-123"

    def test_import_meeting_sucesso_false_levanta_application_error(self) -> None:
        """Quando success=False, levanta ApplicationError SERVICE_UNAVAILABLE."""
        from src.kt_ingestion.tldv_client import TLDVClient

        client = TLDVClient(api_key="fake-key")
        mock_resp = make_mock_response({"success": False, "message": "Falha no import"})

        with patch.object(client.session, "post", return_value=mock_resp):
            with pytest.raises(ApplicationError) as exc_info:
                client.import_meeting("https://example.com/video.mp4", "Reunião")

        assert exc_info.value.error_code == "SERVICE_UNAVAILABLE"

    def test_import_meeting_401_levanta_service_unavailable(self) -> None:
        """HTTP 401 → ApplicationError SERVICE_UNAVAILABLE."""
        from src.kt_ingestion.tldv_client import TLDVClient

        client = TLDVClient(api_key="fake-key")
        http_error = requests.exceptions.HTTPError()
        mock_error_resp = MagicMock()
        mock_error_resp.status_code = 401
        http_error.response = mock_error_resp

        with patch.object(client.session, "post", side_effect=http_error):
            with pytest.raises(ApplicationError) as exc_info:
                client.import_meeting("https://example.com/v.mp4", "KT")

        assert exc_info.value.error_code == "SERVICE_UNAVAILABLE"
        assert exc_info.value.status_code == 503

    def test_import_meeting_400_levanta_validation_error(self) -> None:
        """HTTP 400 → ApplicationError VALIDATION_ERROR."""
        from src.kt_ingestion.tldv_client import TLDVClient

        client = TLDVClient(api_key="fake-key")
        http_error = requests.exceptions.HTTPError()
        mock_error_resp = MagicMock()
        mock_error_resp.status_code = 400
        mock_error_resp.text = "URL inválida"
        http_error.response = mock_error_resp

        with patch.object(client.session, "post", side_effect=http_error):
            with pytest.raises(ApplicationError) as exc_info:
                client.import_meeting("url-invalida", "KT")

        assert exc_info.value.error_code == "VALIDATION_ERROR"
        assert exc_info.value.status_code == 422

    def test_import_meeting_429_levanta_quota_exceeded(self) -> None:
        """HTTP 429 → ApplicationError QUOTA_EXCEEDED."""
        from src.kt_ingestion.tldv_client import TLDVClient

        client = TLDVClient(api_key="fake-key")
        http_error = requests.exceptions.HTTPError()
        mock_error_resp = MagicMock()
        mock_error_resp.status_code = 429
        http_error.response = mock_error_resp

        with patch.object(client.session, "post", side_effect=http_error):
            with pytest.raises(ApplicationError) as exc_info:
                client.import_meeting("https://example.com/v.mp4", "KT")

        assert exc_info.value.error_code == "QUOTA_EXCEEDED"

    def test_import_meeting_connection_error_levanta_service_unavailable(self) -> None:
        """Erro de conexão → ApplicationError SERVICE_UNAVAILABLE."""
        from src.kt_ingestion.tldv_client import TLDVClient

        client = TLDVClient(api_key="fake-key")
        with patch.object(client.session, "post", side_effect=requests.exceptions.ConnectionError("timeout")):
            with pytest.raises(ApplicationError) as exc_info:
                client.import_meeting("https://example.com/v.mp4", "KT")

        assert exc_info.value.error_code == "SERVICE_UNAVAILABLE"


class TestTLDVClientGetTranscript:
    """Testa get_transcript com HTTP mockado."""

    def test_get_transcript_retorna_segmentos_corretos(self) -> None:
        """Transcrição é parseada corretamente para lista de TranscriptSegment."""
        from src.kt_ingestion.tldv_client import TLDVClient

        client = TLDVClient(api_key="fake-key")
        payload = {
            "data": [
                {"speaker": "Ana", "text": "Olá pessoal.", "startTime": 0.0, "endTime": 3.0},
                {"speaker": "Carlos", "text": "Bom dia.", "startTime": 3.5, "endTime": 5.0},
            ]
        }
        mock_resp = make_mock_response(payload)

        with patch.object(client.session, "get", return_value=mock_resp):
            segments = client.get_transcript("mtg-001")

        assert len(segments) == 2
        assert segments[0].speaker == "Ana"
        assert segments[0].text == "Olá pessoal."
        assert segments[1].speaker == "Carlos"

    def test_get_transcript_404_levanta_not_found(self) -> None:
        """Transcrição não encontrada → ApplicationError NOT_FOUND."""
        from src.kt_ingestion.tldv_client import TLDVClient

        client = TLDVClient(api_key="fake-key")
        http_error = requests.exceptions.HTTPError()
        mock_error_resp = MagicMock()
        mock_error_resp.status_code = 404
        http_error.response = mock_error_resp

        with patch.object(client.session, "get", side_effect=http_error):
            with pytest.raises(ApplicationError) as exc_info:
                client.get_transcript("mtg-inexistente")

        assert exc_info.value.error_code == "NOT_FOUND"
        assert exc_info.value.status_code == 404

    def test_get_transcript_lista_vazia_retorna_lista_vazia(self) -> None:
        """Resposta sem segmentos retorna lista vazia."""
        from src.kt_ingestion.tldv_client import TLDVClient

        client = TLDVClient(api_key="fake-key")
        mock_resp = make_mock_response({"data": []})

        with patch.object(client.session, "get", return_value=mock_resp):
            segments = client.get_transcript("mtg-001")

        assert segments == []


class TestTLDVClientFindMeetingByName:
    """Testa find_meeting_by_name com HTTP mockado."""

    def test_encontra_por_nome_exato(self) -> None:
        """Retorna meeting_id quando nome é exato."""
        from src.kt_ingestion.tldv_client import TLDVClient

        client = TLDVClient(api_key="fake-key")
        meetings_payload = {
            "results": [
                {"id": "mtg-001", "name": "KT Finance Session"},
                {"id": "mtg-002", "name": "KT HR Session"},
            ]
        }
        mock_resp = make_mock_response(meetings_payload)

        with patch.object(client.session, "get", return_value=mock_resp):
            result = client.find_meeting_by_name("KT Finance Session")

        assert result == "mtg-001"

    def test_retorna_none_quando_nao_encontrado(self) -> None:
        """Retorna None quando reunião não está na lista."""
        from src.kt_ingestion.tldv_client import TLDVClient

        client = TLDVClient(api_key="fake-key")
        mock_resp = make_mock_response({"results": []})

        with patch.object(client.session, "get", return_value=mock_resp):
            result = client.find_meeting_by_name("Reunião Inexistente")

        assert result is None

    def test_busca_fuzzy_encontra_por_substring(self) -> None:
        """Busca fuzzy retorna resultado quando nome está contido."""
        from src.kt_ingestion.tldv_client import TLDVClient

        client = TLDVClient(api_key="fake-key")
        meetings_payload = {"results": [{"id": "mtg-003", "name": "KT Reunião Finance 2024"}]}
        mock_resp = make_mock_response(meetings_payload)

        with patch.object(client.session, "get", return_value=mock_resp):
            result = client.find_meeting_by_name("KT Finance")

        assert result == "mtg-003"


class TestTLDVClientValidateApiKey:
    """Testa validate_api_key."""

    def test_api_key_valida_retorna_true(self) -> None:
        """Resposta 200 → True."""
        from src.kt_ingestion.tldv_client import TLDVClient

        client = TLDVClient(api_key="valid-key")
        mock_resp = make_mock_response({"results": []})

        with patch.object(client.session, "get", return_value=mock_resp):
            assert client.validate_api_key() is True

    def test_api_key_invalida_retorna_false(self) -> None:
        """HTTP 401 → False (sem raise)."""
        from src.kt_ingestion.tldv_client import TLDVClient

        client = TLDVClient(api_key="bad-key")
        http_error = requests.exceptions.HTTPError()
        mock_error_resp = MagicMock()
        mock_error_resp.status_code = 401
        http_error.response = mock_error_resp
        mock_error_resp.raise_for_status.side_effect = http_error

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = http_error

        with patch.object(client.session, "get", return_value=mock_resp):
            assert client.validate_api_key() is False


# ════════════════════════════════════════════════════════════════════════════
# JSONConsolidator
# ════════════════════════════════════════════════════════════════════════════


class TestJSONConsolidator:
    """Testa JSONConsolidator — criação e persistência de JSON consolidado."""

    def test_create_consolidated_json_campos_obrigatorios(self) -> None:
        """JSON consolidado contém todos os campos esperados."""
        from src.kt_ingestion.json_consolidator import JSONConsolidator

        consolidator = JSONConsolidator()
        data = make_meeting_data()
        result = consolidator.create_consolidated_json(data, client_name="ClienteX")

        assert result["client_name"] == "ClienteX"
        assert result["video_name"] == "KT Session"
        assert result["meeting_id"] == "mtg-001"
        assert result["total_segments"] == 1
        assert result["total_highlights"] == 1
        assert "consolidated_at" in result

    def test_create_consolidated_json_video_name_override(self) -> None:
        """video_name passado explicitamente sobrescreve o nome da reunião."""
        from src.kt_ingestion.json_consolidator import JSONConsolidator

        consolidator = JSONConsolidator()
        data = make_meeting_data(name="Nome Original")
        result = consolidator.create_consolidated_json(data, client_name="X", video_name="Nome Customizado")

        assert result["video_name"] == "Nome Customizado"

    def test_create_consolidated_json_sem_highlights(self) -> None:
        """JSON com highlights vazios é criado corretamente."""
        from src.kt_ingestion.json_consolidator import JSONConsolidator

        consolidator = JSONConsolidator()
        data = make_meeting_data()
        data["highlights"] = []
        result = consolidator.create_consolidated_json(data, client_name="X")

        assert result["total_highlights"] == 0
        assert result["highlights"] == []

    def test_save_consolidated_json_cria_arquivo(self, tmp_path: Path) -> None:
        """save_consolidated_json cria arquivo JSON em disco."""
        from src.kt_ingestion.json_consolidator import JSONConsolidator

        consolidator = JSONConsolidator(output_dir=tmp_path)
        data = make_meeting_data()
        consolidated = consolidator.create_consolidated_json(data, client_name="ClienteX")

        output_path = consolidator.save_consolidated_json(consolidated, filename="test_output.json")

        assert output_path.exists()
        with open(output_path, encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["client_name"] == "ClienteX"

    def test_save_consolidated_json_gera_nome_automatico(self, tmp_path: Path) -> None:
        """Sem filename explícito, nome é gerado a partir do video_name."""
        from src.kt_ingestion.json_consolidator import JSONConsolidator

        consolidator = JSONConsolidator(output_dir=tmp_path)
        data = make_meeting_data(name="KT Finance")
        consolidated = consolidator.create_consolidated_json(data, client_name="X")

        output_path = consolidator.save_consolidated_json(consolidated)

        assert output_path.exists()
        assert output_path.suffix == ".json"

    def test_process_from_tldv_data_sem_salvar(self, tmp_path: Path) -> None:
        """process_from_tldv_data com save=False não cria arquivo JSON."""
        from src.kt_ingestion.json_consolidator import JSONConsolidator

        output_dir = tmp_path / "consolidation_only"
        output_dir.mkdir()
        consolidator = JSONConsolidator(output_dir=output_dir)
        data = make_meeting_data()

        result = consolidator.process_from_tldv_data(data, client_name="X", save=False)

        assert result["client_name"] == "X"
        assert list(output_dir.iterdir()) == []  # nenhum JSON criado no diretório de saída


# ════════════════════════════════════════════════════════════════════════════
# SmartMeetingProcessor
# ════════════════════════════════════════════════════════════════════════════


class TestSmartMeetingProcessorNormalization:
    """Testa _normalize_video_name — método puro."""

    def test_normaliza_espacos_para_underscore(self) -> None:
        """Espaços são convertidos para underscore e lowercase."""
        from src.kt_ingestion.smart_processor import SmartMeetingProcessor
        from src.kt_ingestion.tldv_client import TLDVClient

        processor = SmartMeetingProcessor(tldv_client=TLDVClient(api_key="fake"))
        result = processor._normalize_video_name("KT Finance Session")
        assert " " not in result
        assert result == result.lower()

    def test_nome_vazio_retorna_default(self) -> None:
        """Nome vazio retorna 'reuniao_kt'."""
        from src.kt_ingestion.smart_processor import SmartMeetingProcessor
        from src.kt_ingestion.tldv_client import TLDVClient

        processor = SmartMeetingProcessor(tldv_client=TLDVClient(api_key="fake"))
        result = processor._normalize_video_name("")
        assert result == "reuniao_kt"


class TestSmartMeetingProcessorMain:
    """Testa process_meeting_smart com TLDVClient mockado."""

    def _make_processor(self, meeting_status: str = "completed") -> tuple:
        """Cria processor com TLDVClient mockado."""
        from src.kt_ingestion.smart_processor import SmartMeetingProcessor
        from src.kt_ingestion.tldv_client import MeetingData, MeetingStatus, TLDVClient

        mock_client = MagicMock(spec=TLDVClient)

        status_enum = MeetingStatus(meeting_status)
        mock_meeting = MagicMock(spec=MeetingData)
        mock_meeting.status = status_enum
        mock_meeting.name = "KT Session"
        mock_meeting.url = "https://tldv.io/001"
        mock_meeting.happened_at = "2024-01-15T10:00:00Z"
        mock_meeting.duration = 3600

        mock_client.get_meeting_status.return_value = mock_meeting
        mock_client.get_meeting_transcript.return_value = [
            {"speaker": "Ana", "text": "Texto", "start_time": 0.0, "end_time": 5.0}
        ]
        mock_client.get_meeting_highlights.return_value = []

        processor = SmartMeetingProcessor(tldv_client=mock_client)
        return processor, mock_client

    def test_process_meeting_completed_retorna_dados_completos(self) -> None:
        """Reunião completed retorna is_complete=True com transcript."""
        processor, _ = self._make_processor(meeting_status="completed")
        result = processor.process_meeting_smart("mtg-001", client_name="ClienteX")

        assert result["meeting_id"] == "mtg-001"
        assert result["client_name"] == "ClienteX"
        assert result["is_complete"] is True
        assert len(result["transcript"]) == 1

    def test_process_meeting_processing_retorna_incompleto(self) -> None:
        """Reunião processing retorna is_complete=False sem transcript."""
        processor, _ = self._make_processor(meeting_status="processing")
        result = processor.process_meeting_smart("mtg-002", client_name="ClienteY")

        assert result["is_complete"] is False
        assert result["transcript"] == []

    def test_process_meeting_com_video_name_explicito(self) -> None:
        """video_name passado sobrescreve nome da reunião."""
        processor, _ = self._make_processor(meeting_status="completed")
        result = processor.process_meeting_smart("mtg-001", client_name="X", video_name="Meu KT")

        assert result["video_name"] == "Meu KT"
