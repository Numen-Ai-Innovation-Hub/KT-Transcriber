# SKILL: /audit-pair

**Propósito:** Comparar dois projetos derivados do mesmo template FastAPI+ARQ+Redis e identificar
divergências de padronização — nomenclatura, estrutura, uso de utilitários, configuração e
conformidade com o template. Útil para manter consistência entre projetos da mesma área ou time.

**Argumento obrigatório:** `<pasta-projeto-1> <pasta-projeto-2>`

Exemplos:
```
/audit-pair ../Document_Query ../Learn_Assistant
/audit-pair C:/Numen/.../NPV_Assistant C:/Numen/.../Learn_Assistant
```

**Quando usar:**
- Antes de entregar dois projetos da mesma área (garantir consistência entre eles)
- Quando um projeto foi atualizado e o outro pode ter ficado desatualizado
- Para identificar boas práticas adotadas em um projeto que deveriam ser replicadas no outro

---

## Procedimento

### FASE 1 — Inventário dos Dois Projetos

Para cada projeto (P1 e P2), ler e registrar:

1. **Estrutura de pastas** — `src/`, `utils/`, `scripts/`, `tests/`
2. **Utilitários presentes** — quais `utils/*.py` cada projeto inclui
3. **Domínios** — pastas em `src/` além de `api/`, `config/`, `db/`, `helpers/`, `services/`, `tasks/`
4. **Services** — arquivos em `src/services/`
5. **Dependências** — `pyproject.toml` de cada projeto
6. **DIRECTORY_PATHS e FILE_PATHS** — entradas em `src/config/settings.py`
7. **Arquivos de domínio** — nomes dos `.py` em cada `src/<domínio>/`

---

### FASE 2 — Comparações

Executar cada comparação e registrar: ✅ (alinhados) / ⚠️ (divergência menor) / ❌ (divergência significativa).

---

#### 2.1 — Utilitários

```
[ ] Mesmos utils/*.py presentes nos dois projetos (para funcionalidades similares)
    → Se P1 tem utils/hash_manager.py e P2 não, mas P2 usa cache de conteúdo → ❌ inconsistência
    → Se P1 tem utils/dpt2_extractor.py e P2 não usa Landing.AI → ✅ esperado

[ ] Mesma versão lógica dos utilitários compartilhados
    → Comparar interface pública (funções exportadas) entre os utils/*.py de mesmo nome
    → Diferença de interface = um dos projetos está desatualizado
```

#### 2.2 — Nomenclatura de Arquivos em src/<domínio>/

```
[ ] Ambos seguem padrão <função>_<tipo>.py (2 palavras)
    → Listar todos os .py de src/<domínio>/ de cada projeto
    → Nomes de uma palavra (extractor.py, chunker.py) em qualquer um → ❌

[ ] Conceitos equivalentes têm nomes equivalentes
    → Exemplos de equivalência esperada:
      extraction_service.py (P1) vs extraction_service.py (P2) → ✅
      extraction_service.py (P1) vs extractor.py (P2)          → ❌ divergência de nomenclatura
      embedding_engine.py (P1) vs embedding_manager.py (P2)   → ❌ divergência de nomenclatura
    → Mapear pares de arquivos com função equivalente e comparar nomes
```

#### 2.3 — Estrutura de src/services/

```
[ ] Ambos têm llm_service.py se usam LLM
    → Verificar: se P1 tem active.py + providers.py em src/config/, DEVE ter src/services/llm_service.py
    → Ausência de llm_service.py mas presença de active.py/providers.py → ❌ wrapper padrão ausente
    → Services de domínio devem importar de src.services.llm_service, nunca de utils.llm_manager diretamente

[ ] Services equivalentes têm nomes equivalentes
    → Ex: document_service.py em P1 e P2 para o mesmo papel → ✅
    → Ex: document_service.py (P1) vs doc_processor_service.py (P2) → ⚠️ revisar
```

#### 2.4 — Configuração (settings.py)

```
[ ] DIRECTORY_PATHS com entradas equivalentes para o mesmo stack
    → Se ambos usam ChromaDB: ambos devem ter "vector_db" e "sqlite_db"
    → Se P1 tem "sqlite_db" e P2 tem "hashes" (legado JSON) → ❌ P2 desatualizado

[ ] FILE_PATHS com "hashes_db" se ambos usam hash_manager
    → Ambos devem apontar para data/sqlite_db/hashes.db

[ ] Variáveis de ambiente equivalentes no .env.example
    → Comparar chaves do .env.example de cada projeto
    → Chaves faltando em um dos projetos para funcionalidade equivalente → ⚠️
```

#### 2.5 — Dependências (pyproject.toml)

```
[ ] Mesmas dependências core para funcionalidades equivalentes
    → Se ambos processam PDFs: ambos devem ter pdfplumber (não PyPDF2/pypdf)
    → Se ambos usam ChromaDB: verificar se versões são IGUAIS entre si (breaking changes entre 0.5.x e 1.x)
      - ChromaDB 0.5.x usa IncludeEnum; ChromaDB 1.x usa strings — APIs incompatíveis
      - Projetos irmãos em versões diferentes de major → ❌ risco de comportamento inconsistente
      - Verificar uv.lock de ambos para a versão resolvida exata
    → Se ambos usam LangChain: mesma major version (ambos >=0.3 ou ambos 0.2 — nunca misturar)
    → Se ambos usam openai: mesma major version (1.x vs 2.x têm breaking changes de API)

[ ] Nenhum usa dependência que o outro substituiu por utilitário padrão
    → Ex: P1 usa openai.OpenAI() diretamente, P2 usa utils/llm_manager.py → ❌ P1 desatualizado
```

#### 2.6 — Padrões de Código

```
[ ] Mesmo mecanismo de cache de hashes
    → Ambos via get_hash_manager() + SQLite → ✅
    → P1 via get_hash_manager(), P2 via hashlib inline → ❌

[ ] Mesmo padrão de ChromaDB (se ambos usam)
    → Ambos usam chromadb.PersistentClient → ✅
    → Ambos usam include=["documents", ...] (API strings, não IncludeEnum) → ✅
    → P1 usa IncludeEnum, P2 usa strings → ❌ P1 em API legada

[ ] Mesmo padrão de singleton em services
    → Ambos com threading.Lock() + double-checked locking → ✅
    → Padrões diferentes de singleton → ⚠️ padronizar

[ ] Mesmo padrão de importação de llm_manager
    → Ambos via src.services.llm_service → ✅
    → Um importa diretamente de utils.llm_manager → ❌
```

#### 2.7 — Qualidade e Testes

```
[ ] Ambos têm tests/test_smoke.py e tests/test_e2e.py
[ ] Ambos têm markers smoke e e2e declarados em pyproject.toml
[ ] Cobertura de testes equivalente para módulos de domínio equivalentes
    → Diferença > 20% de cobertura em módulos com mesma função → ⚠️
```

---

### FASE 3 — Relatório Comparativo

Apresentar relatório estruturado com três colunas:

```
## Relatório Cross-Audit — <P1> vs <P2> — <data>

### Utilitários
| Dimensão | <P1> | <P2> | Status |
|----------|------|------|--------|
| hash_manager.py | ✅ presente | ✅ presente | ✅ |
| dpt2_extractor.py | ✅ presente | ❌ ausente | ⚠️ esperado se P2 não usa Landing.AI |
| Versão hash_manager | SQLite (atual) | JSON (legado) | ❌ P2 desatualizado |

### Nomenclatura de Domínio
| Conceito | <P1> | <P2> | Status |
|----------|------|------|--------|
| Extrator PDF | extraction_service.py | extractor.py | ❌ P2 fora do padrão |
| Embeddings | embedding_engine.py | embedding_engine.py | ✅ |

### Configuração
| Dimensão | <P1> | <P2> | Status |
|----------|------|------|--------|
| DIRECTORY_PATHS["sqlite_db"] | ✅ | ❌ ausente | ❌ P2 desatualizado |
| DIRECTORY_PATHS["vector_db"] | ✅ | ✅ | ✅ |

### Pendências por Projeto
| Projeto | Item | Ação recomendada | SKILL |
|---------|------|-----------------|-------|
| <P2> | hash_manager em JSON legado | Migrar para SQLite + sqlite_db | /migrate-infra + /migrate-domain |
| <P2> | extractor.py → extraction_service.py | Renomear arquivo e atualizar imports | manual |
| <P1> | IncludeEnum no ChromaDB | Atualizar para API de strings | manual |
```

**Output:** Tabela comparativa por dimensão + tabela de pendências por projeto com ação recomendada.
NÃO executa correções — aponta o que corrigir e em qual projeto.

---

## FASE FINAL — Registro de Feedback

Ao concluir, registrar entrada em `.claude/skills-feedback/audit-pair.md` **em ambos os projetos**:

```markdown
## [YYYY-MM-DD] Cross-audit: <P1> vs <P2>

**Divergências encontradas:** <N>
**Críticas (❌):** <N>
**Menores (⚠️):** <N>

**Divergências mais relevantes:**
- <item>: <P1 faz X, P2 faz Y>

**Sugestão de melhoria para esta SKILL:**
- <proposta>
```