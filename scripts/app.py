"""Interface Streamlit para busca semântica KT Transcriber.

Conecta ao FastAPI local via HTTP para executar o pipeline RAG de busca
sobre transcrições de reuniões KT. Não importa de src/ — consome apenas
endpoints HTTP.

O pipeline RAG é executado de forma transparente em 6 estágios via ARQ,
exibindo o progresso em tempo real via st.progress().

Uso:
    streamlit run scripts/app.py

Exemplo:
    .venv\\Scripts\\streamlit.exe run scripts/app.py --server.port 8501
"""

import os
import time

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ════════════════════════════════════════════════════════════════════════════

FASTAPI_URL: str = os.getenv("FASTAPI_URL", "http://localhost:8000")
SEARCH_ENDPOINT: str = f"{FASTAPI_URL}/v1/kt-search/"
INDEXING_STATUS_ENDPOINT: str = f"{FASTAPI_URL}/v1/kt-indexing/status"
HEALTH_ENDPOINT: str = f"{FASTAPI_URL}/v1/health"

PIPELINE_START_ENDPOINT: str = f"{FASTAPI_URL}/v1/kt-search/pipeline/start"
PIPELINE_STAGE_ENDPOINT: str = f"{FASTAPI_URL}/v1/kt-search/pipeline/{{session_id}}/{{stage}}"
PIPELINE_STATUS_ENDPOINT: str = f"{FASTAPI_URL}/v1/kt-search/pipeline/status/{{job_id}}"
PIPELINE_RESULT_ENDPOINT: str = f"{FASTAPI_URL}/v1/kt-search/pipeline/{{session_id}}/result"

QUERY_TYPE_LABELS: dict[str, str] = {
    "SEMANTIC": "Semântica",
    "METADATA": "Metadados",
    "ENTITY": "Entidade",
    "TEMPORAL": "Temporal",
    "CONTENT": "Conteúdo",
    "EARLY_EXIT": "Cliente não encontrado",
}

# Estágios do pipeline: (nome_endpoint, nome_task_display)
# O primeiro estágio (enrich) é enfileirado pelo /start — não tem endpoint próprio
PIPELINE_STAGES: list[tuple[str | None, str]] = [
    (None, "Enriquecimento da query"),
    ("classify", "Classificação do tipo RAG"),
    ("chromadb", "Busca ChromaDB"),
    ("discover", "Descoberta de clientes"),
    ("select", "Seleção de chunks"),
    ("insights", "Geração de insights (GPT)"),
]

_POLL_INTERVAL_S = 1.0
_POLL_TIMEOUT_S = 120.0


# ════════════════════════════════════════════════════════════════════════════
# PÁGINA
# ════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="KT Transcriber — Busca",
    page_icon="🔍",
    layout="wide",
)

# ────────────────────────────────────────────────────────────────────────────
# Sidebar
# ────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("KT Transcriber")
    st.caption("Busca semântica em transcrições de reuniões KT")

    st.divider()

    # Status da API
    st.subheader("Status da API")
    try:
        health = requests.get(HEALTH_ENDPOINT, timeout=2)
        if health.status_code == 200:
            st.success("FastAPI: online")
        else:
            st.error(f"FastAPI: erro {health.status_code}")
    except requests.exceptions.ConnectionError:
        st.error("FastAPI: offline")
        st.info("Inicie a stack com start-services.bat")

    st.divider()

    # Status do índice
    st.subheader("Índice ChromaDB")
    try:
        idx = requests.get(INDEXING_STATUS_ENDPOINT, timeout=3)
        if idx.status_code == 200:
            data = idx.json()
            st.metric("Documentos indexados", data.get("total_documents", 0))
            st.metric("Coleção", data.get("collection_name", "—"))
            clientes = data.get("unique_clients", [])
            if clientes:
                st.caption("Clientes:")
                for c in clientes:
                    st.caption(f"• {c}")
        else:
            st.warning("Índice indisponível")
    except requests.exceptions.ConnectionError:
        st.warning("FastAPI offline — status do índice indisponível")
    except Exception as exc:
        st.warning(f"Não foi possível obter status do índice: {exc}")

    st.divider()
    st.caption("[Swagger UI](http://localhost:8000/docs)")

# ────────────────────────────────────────────────────────────────────────────
# Área principal
# ────────────────────────────────────────────────────────────────────────────

st.title("🔍 Busca em Reuniões KT")
st.caption("Faça perguntas em linguagem natural sobre as transcrições indexadas.")

query = st.text_input(
    label="Sua pergunta",
    placeholder="Ex: Quais módulos SAP foram discutidos? Quais decisões foram tomadas sobre integração?",
    help="Mínimo 3 caracteres. A busca usa pipeline RAG com ChromaDB + GPT.",
)

buscar = st.button("Buscar", type="primary", use_container_width=False)


# ════════════════════════════════════════════════════════════════════════════
# HELPERS DE EXECUÇÃO DO PIPELINE
# ════════════════════════════════════════════════════════════════════════════


def _poll_until_ready(job_id: str, stage_label: str) -> bool:
    """Faz polling do status de um job ARQ até completar ou timeout.

    Args:
        job_id: ID do job ARQ a aguardar.
        stage_label: Nome do estágio para mensagens de erro.

    Returns:
        True se o job completou com stage_ready=True. False em caso de falha ou timeout.
    """
    deadline = time.time() + _POLL_TIMEOUT_S
    while time.time() < deadline:
        try:
            resp = requests.get(
                PIPELINE_STATUS_ENDPOINT.format(job_id=job_id),
                timeout=5,
            )
            if resp.status_code != 200:
                st.error(f"Erro ao consultar status do estágio '{stage_label}': HTTP {resp.status_code}")
                return False

            data = resp.json()
            arq_status: str = data.get("arq_status", "")

            if arq_status == "failed":
                st.error(f"Falha no estágio '{stage_label}': {data.get('error', 'sem detalhes')}")
                return False

            if arq_status == "complete" and data.get("stage_ready"):
                return True

        except requests.exceptions.ConnectionError:
            st.error("Conexão com FastAPI perdida durante execução do pipeline.")
            return False
        except requests.exceptions.Timeout:
            pass  # Continua tentando

        time.sleep(_POLL_INTERVAL_S)

    st.error(f"Timeout: o estágio '{stage_label}' demorou mais de {_POLL_TIMEOUT_S:.0f}s.")
    return False


def _run_pipeline(query_text: str) -> dict | None:
    """Executa o pipeline RAG de 6 estágios com barra de progresso em tempo real.

    Args:
        query_text: Query do usuário.

    Returns:
        Dict com o resultado final (compatível com KTSearchResponse) ou None em caso de falha.
    """
    total = len(PIPELINE_STAGES)
    progress = st.progress(0.0, text="Iniciando pipeline...")

    # ── Fase 1: start + enrich (enfileirado automaticamente pelo /start)
    _, stage_label = PIPELINE_STAGES[0]
    progress.progress(0.0, text=f"⏳ {stage_label}...")

    try:
        resp = requests.post(PIPELINE_START_ENDPOINT, json={"query": query_text}, timeout=10)
        if resp.status_code != 200:
            progress.progress(0.0, text="❌ Falha ao iniciar pipeline")
            st.error(f"Falha ao iniciar pipeline: HTTP {resp.status_code}")
            return None
        start_data = resp.json()
    except requests.exceptions.ConnectionError:
        progress.progress(0.0, text="❌ Sem conexão com FastAPI")
        st.error("Não foi possível conectar ao FastAPI.")
        return None

    session_id: str = start_data["session_id"]
    job_id: str = start_data["job_id"]

    if not _poll_until_ready(job_id, stage_label):
        progress.progress(0.0, text=f"❌ Falha: {stage_label}")
        return None

    progress.progress(1 / total, text=f"✅ {stage_label}")

    # ── Fases 2–6: cada uma enfileirada após a anterior completar
    for i, (stage_endpoint, stage_label) in enumerate(PIPELINE_STAGES[1:], start=1):
        progress.progress(i / total, text=f"⏳ {stage_label}...")

        try:
            resp = requests.post(
                PIPELINE_STAGE_ENDPOINT.format(session_id=session_id, stage=stage_endpoint),
                timeout=10,
            )
            if resp.status_code != 200:
                progress.progress(i / total, text=f"❌ Falha: {stage_label}")
                st.error(f"Falha ao enfileirar '{stage_label}': HTTP {resp.status_code}")
                return None
            stage_data = resp.json()
        except requests.exceptions.ConnectionError:
            progress.progress(i / total, text="❌ Sem conexão com FastAPI")
            st.error("Não foi possível conectar ao FastAPI.")
            return None

        job_id = stage_data["job_id"]
        if not _poll_until_ready(job_id, stage_label):
            # Verifica se houve early-exit (resultado final já disponível)
            result_resp = requests.get(PIPELINE_RESULT_ENDPOINT.format(session_id=session_id), timeout=5)
            if result_resp.status_code == 200:
                progress.progress(1.0, text="✅ Pipeline concluído")
                return result_resp.json()
            progress.progress(i / total, text=f"❌ Falha: {stage_label}")
            return None

        progress.progress((i + 1) / total, text=f"✅ {stage_label}")

    progress.progress(1.0, text="✅ Pipeline concluído")

    # ── Lê resultado final
    result_resp = requests.get(PIPELINE_RESULT_ENDPOINT.format(session_id=session_id), timeout=10)
    if result_resp.status_code == 200:
        return result_resp.json()

    st.error("Resultado final indisponível após conclusão do pipeline.")
    return None


# ════════════════════════════════════════════════════════════════════════════
# EXECUÇÃO DA BUSCA
# ════════════════════════════════════════════════════════════════════════════

if buscar:
    if not query or len(query.strip()) < 3:
        st.warning("Digite pelo menos 3 caracteres para buscar.")
    else:
        result = _run_pipeline(query.strip())

        if result is not None:
            # Métricas
            col1, col2, col3 = st.columns(3)
            query_type_raw = result.get("query_type", "")
            query_type_label = QUERY_TYPE_LABELS.get(query_type_raw, query_type_raw)
            col1.metric("Tipo de consulta", query_type_label)
            col2.metric("Contextos encontrados", len(result.get("contexts", [])))
            col3.metric("Tempo de processamento", f"{result.get('processing_time', 0):.2f}s")

            st.divider()

            # Resposta principal
            st.subheader("Resposta")
            answer = result.get("answer", "")
            if answer:
                st.markdown(answer)
            else:
                st.info("Nenhuma resposta gerada. Verifique se há documentos indexados.")

            # Contextos
            contexts = result.get("contexts", [])
            if contexts:
                st.divider()
                section_title = "Vídeos disponíveis" if query_type_raw == "METADATA" else "Contextos relevantes"
                st.subheader(f"{section_title} ({len(contexts)})")
                for i, ctx in enumerate(contexts):
                    video = ctx.get("video_name", f"Contexto {i + 1}")
                    speaker = ctx.get("speaker", "")
                    label = f"📄 {video}" + (f" — {speaker}" if speaker else "")
                    with st.expander(label, expanded=(i == 0)):
                        doc = ctx.get("content", "")
                        if doc:
                            st.markdown(doc)
                        client = ctx.get("client", "")
                        timestamp = ctx.get("timestamp", "")
                        url = ctx.get("original_url", "")
                        if client:
                            st.caption(f"Cliente: {client}")
                        if timestamp and timestamp not in ("Unknown", "", "00:00-00:00"):
                            st.caption(f"Tempo: {timestamp}")
                        if url:
                            st.markdown(f"[Assistir no TL:DV]({url})")
