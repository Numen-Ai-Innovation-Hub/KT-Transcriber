# Feedback: /migrate-analyze

## [2026-02-24] Projeto: KT Transcriber

**Arquivos inventariados:** 43 arquivos .py

**O que funcionou bem:**
- Projeto já usa FastAPI + ARQ + Redis + ChromaDB — mesma stack do template, facilitou muito o inventário
- Domínios claramente separados no legado (`transcription/`, `processing/`, `indexing/`, `rag/`) — mapeamento para `kt_ingestion`, `kt_indexing`, `kt_search` foi direto
- Dashboard Streamlit já segue padrão correto (consome API via httpx, não mistura lógica de negócio)
- Schemas Pydantic v2 já em uso — sem conversão necessária

**O que foi difícil:**
- `search_engine.py` com mais de 25.000 tokens — arquivo muito grande, não foi possível ler completamente; conteúdo inferido pelo contexto (arq_worker.py + routers)
- 3 arquivos `config.py` espalhados por domínios + 1 na raiz — identificar o que vai para `settings.py` vs `_constants.py` exigiu leitura cuidadosa de cada um
- `rag/config.py` com path WSL absoluto hardcoded — detectado na leitura, seria um bug crítico silencioso se passasse

**Sugestão de melhoria para esta SKILL:**
- Adicionar alerta explícito: "arquivos com >800 linhas tendem a conter múltiplas responsabilidades — investigar se precisa ser dividido durante migrate-domain"
- Incluir checklist de "sinais de alerta": paths hardcoded, `load_dotenv()` fora de config, `if __name__ == "__main__"` em módulos de domínio
