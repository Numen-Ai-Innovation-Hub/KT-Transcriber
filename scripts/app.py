"""Interface Streamlit para busca semântica KT Transcriber.

Conecta ao FastAPI local via HTTP para executar o pipeline RAG de busca
sobre transcrições de reuniões KT. Não importa de src/ — consome apenas
endpoints HTTP.

Uso:
    streamlit run scripts/app.py

Exemplo:
    .venv\\Scripts\\streamlit.exe run scripts/app.py --server.port 8501
"""

import os

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

QUERY_TYPE_LABELS: dict[str, str] = {
    "SEMANTIC": "Semântica",
    "METADATA": "Metadados",
    "ENTITY": "Entidade",
    "TEMPORAL": "Temporal",
    "CONTENT": "Conteúdo",
}

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

# ────────────────────────────────────────────────────────────────────────────
# Execução da busca
# ────────────────────────────────────────────────────────────────────────────

if buscar:
    if not query or len(query.strip()) < 3:
        st.warning("Digite pelo menos 3 caracteres para buscar.")
    else:
        with st.spinner("Processando busca RAG..."):
            try:
                response = requests.post(
                    SEARCH_ENDPOINT,
                    json={"query": query.strip()},
                    timeout=60,
                )

                if response.status_code == 200:
                    result = response.json()

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
                        st.subheader(f"Contextos relevantes ({len(contexts)})")
                        for i, ctx in enumerate(contexts):
                            doc = ctx.get("document", ctx.get("content", ctx.get("text", "")))
                            meta = ctx.get("metadata", {})
                            video = meta.get("video_name", meta.get("video_folder", f"Contexto {i + 1}"))
                            speaker = meta.get("speaker", "")
                            label = f"📄 {video}" + (f" — {speaker}" if speaker else "")
                            with st.expander(label, expanded=(i == 0)):
                                st.markdown(doc)
                                if meta:
                                    with st.expander("Metadados", expanded=False):
                                        st.json(meta)

                elif response.status_code == 422:
                    st.error("Erro de validação: a query é muito curta ou inválida.")
                else:
                    st.error(f"Erro da API: {response.status_code}")
                    try:
                        st.json(response.json())
                    except Exception:
                        st.text(response.text)

            except requests.exceptions.ConnectionError:
                st.error("Não foi possível conectar ao FastAPI em http://localhost:8000")
                st.info("Verifique se a stack está rodando com start-services.bat")
            except requests.exceptions.Timeout:
                st.error("Timeout: a busca demorou mais de 60 segundos.")
            except Exception as exc:
                st.error(f"Erro inesperado: {exc}")
