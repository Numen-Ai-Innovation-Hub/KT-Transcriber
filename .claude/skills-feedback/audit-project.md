# Feedback: /audit-project

## [2026-02-25] Projeto: KT Transcriber

**Itens auditados:** 50+
**Conformes:** 44 ✅
**Não conformes:** 2 ❌ → **resolvidas em 2026-02-25** ✅
**Pendentes (stack):** 2 ⏳ (smoke + e2e — stack não estava ativa)

**Resultados dos testes:**
- Unit:  115 passed, 0 failed (expandido de 61 → 115 após resolução das não-conformidades)
- Smoke: pendente (stack não rodando no momento da auditoria)
- E2E:   pendente (stack não rodando no momento da auditoria)

**Não conformidades — RESOLVIDAS:**
1. ✅ `hashlib.md5` usado diretamente em `src/kt_search/insights_agent.py:86` — corrigido em commit `2b8a4b2`: substituído por `utils/hash_manager.get_hash_manager().generate_content_hash()`
2. ✅ 9 arquivos com Stmts > 50 e cobertura < 20% — resolvidos com classes de mock dedicadas:
   - `kt_indexing_utils.py`: 56% | `file_generator.py`: 47% | `llm_metadata_extractor.py`: 48%
   - `kt_indexing_service.py`: 49% | `dynamic_client_manager.py`: 34%
   - `chromadb_store.py`: 24% | `indexing_engine.py`: 25%
   - `insights_agent.py`: 9% ⚠️ estrutural (depende OpenAI real)
   - `search_engine.py`: 13% ⚠️ estrutural (depende ChromaDB+OpenAI real)

**Avisos (⚠️) — RESOLVIDOS:**
- ✅ 2 `except Exception:` com fallback silencioso sem log: corrigidos em commit `2b8a4b2`
  (`kt_indexing_utils.py` e `chunk_selector.py` — agora com `logger.warning()` antes do fallback)
- Utils do toolkit (dpt2_extractor, pdfplumber_extractor, wordcom_toolkit, string_helpers) não usados — **esperado** para projeto que processa APIs, não PDFs/Word

**Pontos fortes do projeto auditado:**
- ChromaDB 1.5.1 com API 1.x correta (strings, sem IncludeEnum) — migrado corretamente
- TYPE_CHECKING para InsightsAgent: padrão correto (lazy import em runtime)
- Singleton thread-safe com double-checked locking nos 3 services
- Zero print(), zero logging.basicConfig(), zero HTTPException fora de routers
- mypy 0 erros + ruff 0 erros — qualidade de código alta

**Ponto de atenção residual:**
- `insights_agent.py` (1855 linhas) e `search_engine.py` (2502 linhas) são arquivos muito grandes
  O `/migrate-domain` sinalizou: "investigar se precisa ser dividido ANTES de corrigir mypy"
  Cobertura estruturalmente limitada enquanto não forem divididos em submódulos menores

**Sugestão de melhoria para esta SKILL:**
- Adicionar item explícito ao checklist: "hashlib direto em src/ — verificar se utils/hash_manager.py deveria ser usado"
- Distinguir no checklist de cobertura: arquivos com dependências externas reais (OpenAI, ChromaDB) vs arquivos que poderiam ter mocks — a baixa cobertura de chromadb_store/insights_agent é estrutural, não descuido
- Adicionar item: "except Exception: com fallback sem log — não é pass mas swallows sem evidência; adicionar logger.warning() antes do fallback"
