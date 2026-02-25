# Feedback: /audit-project

## [2026-02-25] Projeto: KT Transcriber

**Itens auditados:** 50+
**Conformes:** 44 ✅
**Não conformes:** 2 ❌
**Pendentes (stack):** 2 ⏳ (smoke + e2e — stack não estava ativa)

**Resultados dos testes:**
- Unit:  61 passed, 0 failed
- Smoke: pendente (stack não rodando no momento da auditoria)
- E2E:   pendente (stack não rodando no momento da auditoria)

**Não conformidades encontradas:**
1. `hashlib.md5` usado diretamente em `src/kt_search/insights_agent.py:86` — duplica funcionalidade de `utils/hash_manager.py`
2. 9 arquivos com Stmts > 50 e cobertura < 20% (insights_agent, search_engine, chromadb_store, dynamic_client_manager, file_generator, indexing_engine, kt_indexing_utils, llm_metadata_extractor, kt_indexing_service)

**Avisos (⚠️ — não são ❌):**
- 2 `except Exception:` com fallback silencioso sem log: `kt_indexing_utils.py` (return "") e `chunk_selector.py` (return QueryType.SEMANTIC) — não é `pass` puro mas swallows exceptions sem evidência nos logs
- Utils do toolkit (dpt2_extractor, pdfplumber_extractor, wordcom_toolkit, string_helpers) não usados — **esperado** para projeto que processa APIs, não PDFs/Word

**Pontos fortes do projeto auditado:**
- ChromaDB 1.5.1 com API 1.x correta (strings, sem IncludeEnum) — migrado corretamente
- TYPE_CHECKING para InsightsAgent: padrão correto (lazy import em runtime)
- Singleton thread-safe com double-checked locking nos 3 services
- Zero print(), zero logging.basicConfig(), zero HTTPException fora de routers
- mypy 0 erros + ruff 0 erros — qualidade de código alta

**Sugestão de melhoria para esta SKILL:**
- Adicionar item explícito ao checklist: "hashlib direto em src/ — verificar se utils/hash_manager.py deveria ser usado"
- Distinguir no checklist de cobertura: arquivos com dependências externas reais (OpenAI, ChromaDB) vs arquivos que poderiam ter mocks — a baixa cobertura de chromadb_store/insights_agent é estrutural, não descuido
- Adicionar item: "except Exception: com fallback sem log — não é pass mas swallows sem evidência; adicionar logger.warning() antes do fallback"
