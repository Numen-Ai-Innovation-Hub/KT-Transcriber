# Feedback: /migrate-tests

## [2026-02-25] Projeto: KT Transcriber

**Unit tests criados:** 61 testes em 4 arquivos (test_kt_ingestion.py, test_kt_indexing.py, test_kt_search.py + conftest.py)
**Smoke tests criados:** 8 verificações (test_smoke.py)
**E2E tests criados:** 5 fluxos (test_e2e.py)

**O que funcionou bem:**
- Padrão de imports lazy dentro de cada método de teste (`from src.xxx import Yyy`) eliminou conflitos de escopo de fixture com módulos pesados
- `MagicMock(spec=TLDVClient)` com atributos `.status`, `.name`, etc. configurados manualmente foi mais estável que mocks auto-especificados
- `IndexingEngine(enable_chromadb=False)` permite testar lógica de pipeline sem inicializar ChromaDB ou OpenAI
- `EmbeddingGenerator._build_hybrid_input()` é método puro — testável sem mock, apenas patchando `openai.OpenAI` no __init__

**O que foi difícil:**
- SearchEngine.__init__ inicializa ChromaDB + OpenAI + InsightsAgent em `_initialize_integrations()` — impossível testar sem contornar __init__ via `__new__` e configuração manual dos atributos
- QueryEnricher captura ValueError para query=None internamente e retorna EnrichmentResult padrão — comportamento defensivo não óbvio na leitura superficial, descoberto só rodando o teste
- conftest.py `isolated_test_dirs` precisa de chaves exatas de DIRECTORY_PATHS (`sqlite_db`, `vector_db`, `transcriptions`) — dirs criados pelo autouse fixture aparecem em `tmp_path.iterdir()`, quebrando asserts que esperavam diretório vazio

**2 falhas iniciais corrigidas:**
1. `test_process_from_tldv_data_sem_salvar` — usava `list(tmp_path.iterdir()) == []` mas tmp_path já tinha dirs do autouse fixture; solução: usar subdir exclusivo `tmp_path / "consolidation_only"`
2. `test_enrich_query_none_levanta_erro` — QueryEnricher não levanta para None, apenas loga e retorna; solução: testar que não crasha e retorna EnrichmentResult

**Sugestão de melhoria para esta SKILL:**
- Adicionar seção explícita: "Para classes com __init__ que inicializa infra pesada (DB, APIs), usar `Class.__new__(Class)` + configuração manual de atributos — evita patches complexos de construtor"
- Alertar sobre autouse fixtures em conftest: "tmp_path em testes com isolated_test_dirs já contém subdiretórios — nunca assertar `list(tmp_path.iterdir()) == []`; usar um subdir exclusivo"
- Documentar padrão para comportamento defensivo vs fail-fast: "Antes de testar raises, verificar se o método realmente levanta — alguns módulos logam e retornam ao invés de levantar"
