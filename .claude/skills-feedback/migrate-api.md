## [2026-02-24] Projeto: KT-Transcriber

**Services criados:** 3 (kt_ingestion_service, kt_indexing_service, kt_search_service)
**Routers criados:** 3 (kt_search_router, kt_ingestion_router, kt_indexing_router)
**Tasks ARQ criadas:** 2 (kt_ingestion_task, kt_indexing_task)
**Scripts atualizados:** 1 (run_full_pipeline.py — removido FullPipelineRunner, agora usa services)
**Schemas criados:** 1 arquivo (kt_schemas.py com 5 modelos Pydantic)

**O que funcionou bem:**
- Padrão singleton thread-safe com `_instance` + `_lock` ficou uniforme nos 3 services
- Mover `FullPipelineRunner` de `scripts/` para os services eliminou duplicação real de lógica
- ARQ pool com try/except no lifespan — app sobe mesmo sem Redis disponível
- `arq.jobs.Job` (não `arq.Job`) — encontrado rapidamente verificando `dir(arq)`
- Ruff I001 auto-corrigido com `--fix`, E402 corrigido movendo imports para o topo

**O que foi difícil:**
- `src/tasks/__init__.py` gerado pelo auto-init referenciava `exemplo_task` — quebrou o import ao remover a task. Necessário atualizar manualmente o `__init__.py`
- Os 70 erros mypy de `kt_search/` "contaminam" a saída do mypy mesmo ao checar só os arquivos novos, pois a dependência transitiva (kt_search_service → search_engine) puxa o módulo

**Sugestão de melhoria para esta SKILL:**
- Adicionar instrução explícita: ao remover funções do `arq_worker.py`, verificar se o `__init__.py` auto-gerado referencia essas funções e atualizá-lo
- Mencionar que `arq.Job` não existe — o correto é `arq.jobs.Job`
