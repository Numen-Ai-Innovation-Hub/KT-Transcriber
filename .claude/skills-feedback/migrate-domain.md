# Feedback: /migrate-domain

## [2026-02-25] Projeto: KT Transcriber — Domínio kt_search/

**Domínios migrados:** kt_indexing/, kt_ingestion/, kt_search/
**Resultado final:** mypy 0 erros em todos os domínios + ruff 0 erros

**O que funcionou bem:**
- Separação clara de responsabilidades por domínio facilitou migração faseada
- Padrão ChromaDB guard (verificar tipo de metadatas antes de usar) encapsulado e reutilizável
- `_constants.py` por domínio para constantes — evitou config dicts sem tipo explícito

**O que foi difícil:**
- `search_engine.py` era arquivo muito grande (~25k tokens) — continha múltiplas responsabilidades (CLI, Teams integration, 5-stage pipeline), precisou de refatoração estrutural além da migração pura
- 70 erros mypy em kt_search/ — maioria: `str | None` implícito, metadatas ChromaDB sem type guard, config dicts sem anotação de tipo
- Import legados apontando para módulos do projeto antigo (`from ..indexing.chromadb_manager import ChromaDBManager`) — necessário mapear para novos paths

**Padrões de correção mais usados:**
1. `def func(arg: str = None)` → `def func(arg: str | None = None)`
2. `CONFIG = {...}` → `CONFIG: dict[str, Any] = {...}`
3. ChromaDB metadatas: sempre verificar `if raw_metas` antes de iterar `raw_metas[0]`
4. `isinstance(val, str)` guard antes de usar valores de metadatas como `str`

**Sugestão de melhoria para esta SKILL:**
- Adicionar checklist explícito de "padrões mypy comuns em ChromaDB": metadatas são `list[list[Mapping[str, str | int | float | bool]]] | None` — documentar o guard pattern
- Alertar sobre arquivos >500 linhas: investigar se precisa ser dividido ANTES de corrigir mypy (evita corrigir código que vai ser refatorado)
- Incluir verificação de imports legados como passo explícito no checklist da skill
