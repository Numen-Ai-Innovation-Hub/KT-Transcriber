# Feedback: /migrate-infra

## [2026-02-24] Projeto: KT Transcriber

**Dependências adicionadas:** 8 (chromadb==1.5.1, openai==2.23.0, langchain-core==1.2.15, langchain-openai==1.1.10, streamlit==1.54.0, aiofiles==25.1.0, python-dateutil==2.9.0.post0, pytz==2025.2)
**providers.py criado:** não (projeto usa só OpenAI sem troca de provider em runtime)
**active.py criado:** não (mesmo motivo — removido do template)
**Subpastas data/ criadas:** sqlite_db, vector_db, transcriptions

**O que funcionou bem:**
- uv add resolveu chromadb sem pin de versão corretamente (1.5.1 + tokenizers=0.22.2 — sem conflito)
- Template já tinha pythonpath e markers smoke/e2e no pyproject.toml — nenhuma mudança necessária
- settings.py e startup.py do template já seguem o padrão exato — apenas adição de variáveis

**O que foi difícil:**
- src/config/__init__.py importava active.py e providers.py — gerou ModuleNotFoundError ao remover os arquivos antes de atualizar o __init__; resolver na ordem certa (primeiro remover arquivos, depois limpar __init__) é necessário
- uv add adiciona versões com `>=` em vez de `==` — exige edição manual para alinhar ao padrão do time de versões exatas

**Sugestão de melhoria para esta SKILL:**
- Adicionar passo explícito: "Se removendo providers.py/active.py, atualizar src/config/__init__.py antes de validar com python -c"
- Documentar que uv add usa >= por padrão — adicionar instrução para converter para == após a adição
