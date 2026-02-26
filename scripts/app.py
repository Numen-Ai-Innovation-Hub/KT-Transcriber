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
from typing import Any

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

PIPELINE_MEETINGS_ENDPOINT: str = f"{FASTAPI_URL}/v1/kt-pipeline/meetings"
PIPELINE_SELECTIVE_START_ENDPOINT: str = f"{FASTAPI_URL}/v1/kt-pipeline/start"
PIPELINE_SELECTIVE_STATUS_ENDPOINT: str = f"{FASTAPI_URL}/v1/kt-pipeline/status/{{job_id}}"

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

_POLL_INTERVAL_S = 0.5
_POLL_TIMEOUT_S = 120.0

_PAGE_CONSULTA = "🔍 Consulta"
_PAGE_PIPELINE = "📥 Pipeline Seletivo"


# ════════════════════════════════════════════════════════════════════════════
# PÁGINA
# ════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="KT Transcriber",
    page_icon="🔍",
    layout="wide",
)

# ────────────────────────────────────────────────────────────────────────────
# Sidebar — navegação
# ────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("KT Transcriber")
    st.caption("Busca semântica em transcrições de reuniões KT")
    st.divider()
    pagina: str = st.radio(
        "Navegação",
        [_PAGE_CONSULTA, _PAGE_PIPELINE],
        label_visibility="collapsed",
    )  # type: ignore[assignment]


# ════════════════════════════════════════════════════════════════════════════
# HELPERS — BUSCA RAG (pipeline de 6 estágios)
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


def _run_pipeline(query_text: str) -> dict[str, Any] | None:
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
# HELPER — PIPELINE SELETIVO (job único ARQ)
# ════════════════════════════════════════════════════════════════════════════


def _poll_job_until_complete(
    job_id: str,
    status_placeholder: Any,
    timeout_s: float = 900.0,
) -> dict[str, Any] | None:
    """Faz polling de um job ARQ simples até completar ou timeout.

    Args:
        job_id: ID do job ARQ a aguardar.
        status_placeholder: Placeholder Streamlit para atualizar mensagem de status.
        timeout_s: Timeout total em segundos (padrão: 15 min para indexação longa).

    Returns:
        Dict com resultado do job ou None em caso de falha ou timeout.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            resp = requests.get(
                PIPELINE_SELECTIVE_STATUS_ENDPOINT.format(job_id=job_id),
                timeout=5,
            )
            if resp.status_code != 200:
                st.error(f"Erro ao consultar status do job: HTTP {resp.status_code}")
                return None

            data = resp.json()
            status_str: str = data.get("status", "")

            if status_str == "failed":
                st.error(f"Falha no pipeline: {data.get('error', 'sem detalhes')}")
                return None

            if status_str == "complete":
                return data.get("result")

            status_placeholder.caption(f"⏳ Status: {status_str}...")

        except requests.exceptions.ConnectionError:
            st.error("Conexão com FastAPI perdida.")
            return None
        except requests.exceptions.Timeout:
            pass  # Continua tentando

        time.sleep(_POLL_INTERVAL_S)

    st.error(f"Timeout: o pipeline demorou mais de {timeout_s:.0f}s.")
    return None


# ════════════════════════════════════════════════════════════════════════════
# PÁGINA: CONSULTA RAG
# ════════════════════════════════════════════════════════════════════════════

if pagina == _PAGE_CONSULTA:
    st.header("🔍 Consulta em Reuniões KT")
    st.caption("Faça perguntas em linguagem natural sobre as transcrições indexadas.")

    query = st.text_input(
        label="Sua pergunta",
        placeholder="Ex: Quais módulos SAP foram discutidos? Quais decisões foram tomadas sobre integração?",
        help="Mínimo 3 caracteres. A busca usa pipeline RAG com ChromaDB + GPT.",
    )

    buscar = st.button("Buscar", type="primary", use_container_width=False)

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
                            if timestamp and timestamp not in ("Unknown", "", "00:00-00:00", "-"):
                                st.caption(f"Tempo: {timestamp}")
                            if url:
                                st.markdown(f"[Assistir no TL:DV]({url})")

# ════════════════════════════════════════════════════════════════════════════
# PÁGINA: PIPELINE SELETIVO
# ════════════════════════════════════════════════════════════════════════════

elif pagina == _PAGE_PIPELINE:
    st.header("📥 Pipeline Seletivo")
    st.caption("Selecione reuniões do TL:DV para baixar e indexar no ChromaDB.")

    col_btn, _ = st.columns([1, 4])
    with col_btn:
        buscar_reunioes = st.button("🔄 Buscar reuniões", use_container_width=True)

    if buscar_reunioes:
        with st.spinner("Consultando TL:DV..."):
            try:
                resp_meetings = requests.get(PIPELINE_MEETINGS_ENDPOINT, timeout=15)
                if resp_meetings.status_code == 200:
                    st.session_state["meetings"] = resp_meetings.json().get("meetings", [])
                else:
                    st.error(f"Erro ao listar reuniões: HTTP {resp_meetings.status_code}")
            except requests.exceptions.ConnectionError:
                st.error("Não foi possível conectar ao FastAPI.")

    meetings: list[dict[str, Any]] = st.session_state.get("meetings", [])

    if meetings:
        options: dict[str, str] = {
            f"{'✅ ' if m['already_indexed'] else ''}{m['name']}": m["id"]
            for m in meetings
        }
        selected_labels: list[str] = st.multiselect(
            "Selecione as reuniões a indexar:",
            options=list(options.keys()),
            help="✅ = já baixada anteriormente. Você pode resselecionar para re-indexar.",
        )
        selected_ids: list[str] = [options[label] for label in selected_labels]

        force_clean = st.checkbox(
            "⚠️ Force clean (apaga todos os dados antes de iniciar)",
            value=False,
            help="Remove transcriptions/, vector_db/ e chunks/ antes de baixar. Use com cuidado.",
        )
        if force_clean:
            st.warning("⚠️ Force clean ativado: todos os dados existentes serão apagados antes do download.")

        iniciar = st.button(
            "▶️ Iniciar download e indexação",
            type="primary",
            disabled=not selected_ids,
        )

        if iniciar and selected_ids:
            status_ph = st.empty()
            status_ph.info(f"Enfileirando pipeline para {len(selected_ids)} reunião(ões)...")

            try:
                resp_start = requests.post(
                    PIPELINE_SELECTIVE_START_ENDPOINT,
                    json={"meeting_ids": selected_ids, "force_clean": force_clean},
                    timeout=10,
                )
                if resp_start.status_code != 200:
                    st.error(f"Falha ao iniciar pipeline: HTTP {resp_start.status_code}")
                    status_ph.empty()
                else:
                    start_data = resp_start.json()
                    job_id_pipeline: str = start_data["job_id"]
                    status_ph.info(f"Pipeline enfileirado (job={job_id_pipeline[:8]}...). Aguardando conclusão...")

                    with st.spinner("Processando... Isso pode levar alguns minutos."):
                        pipeline_result = _poll_job_until_complete(job_id_pipeline, status_ph)

                    status_ph.empty()

                    if pipeline_result is not None:
                        ingestion: dict[str, Any] = pipeline_result.get("ingestion", {})
                        indexing: dict[str, Any] = pipeline_result.get("indexing", {})

                        st.success("✅ Pipeline concluído!")
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Reuniões baixadas", ingestion.get("meetings_downloaded", 0))
                        col2.metric("Chunks indexados", indexing.get("chunks_indexed", 0))
                        col3.metric("Erros", ingestion.get("meetings_failed", 0))

            except requests.exceptions.ConnectionError:
                st.error("Não foi possível conectar ao FastAPI.")
    else:
        st.info("Clique em '🔄 Buscar reuniões' para listar as reuniões disponíveis no TL:DV.")
