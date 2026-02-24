# SKILL: /migrate-analyze

**Propósito:** Ponto de entrada obrigatório de qualquer migração. Inventaria o projeto
legado, classifica cada arquivo no destino correto do template FastAPI+ARQ+Redis e produz
dois artefatos que as demais SKILLs irão consumir.

**Argumento obrigatório:** `<pasta-legado>` — path absoluto ou relativo ao projeto original

---

## Definições de Plataforma

Decisões arquiteturais fixas do template — não são preferências, são padrões do time.
Identificar e documentar no plano se o legado usa alternativas.

| Categoria | Definição do template | Alternativas comuns (migrar de) |
|-----------|----------------------|----------------------------------|
| Banco vetorial | ChromaDB persistent (nunca http mode) | Pinecone, Weaviate, Qdrant |
| Filas/workers | ARQ + Redis Cloud | Celery + RabbitMQ, Celery + Redis |
| Redis | Redis Cloud via .env (nunca Docker, nunca local) | Docker Redis, Redis local/WSL2 |
| Containerização | Nenhuma (zero Docker em qualquer camada) | Docker, docker-compose |
| Framework HTTP | FastAPI com lifespan | Flask, Django, aiohttp |
| Gestão de deps | uv (nunca pip diretamente) | pip, poetry, conda |

---

## Procedimento

### FASE 1 — Inventário do Legado

1. Ler estrutura completa do projeto legado em `<pasta-legado>`
2. Listar todos os `.py` (excluindo `.venv`, `__pycache__`, `tests/`, `*.pyc`)
3. Para cada arquivo, ler o conteúdo e identificar:
   - Propósito principal
   - Dependências externas (libs usadas)
   - Dependências internas (imports de outros módulos do projeto)
   - Se tem `if __name__ == "__main__":`
   - Se é portável (zero deps de projeto) ou acoplado ao projeto

### FASE 2 — Classificação de Arquivos

Classificar cada arquivo segundo a tabela de destinos:

| Classificação | Critério | Destino no template |
|--------------|----------|---------------------|
| **Domínio** | Lógica core de negócio específica do produto | `src/<domínio>/` |
| **Helper transversal** | Usado por 2+ domínios, depende de config do projeto | `src/helpers/` |
| **Util padrão do time** | Lógica já coberta por utilitário existente em `utils/` | substituir pelo utilitário (não copiar) |
| **Util portável** | Zero imports de `src/`, copiável para qualquer projeto, lógica nova | `utils/` |
| **Config** | Constantes, paths, variáveis de ambiente | `src/config/settings.py` |
| **Service** | Orquestra múltiplos componentes de domínio | `src/services/` |
| **Task ARQ** | Operação em que o utilizador não pode/deve esperar a resposta HTTP | `src/tasks/` |
| **Script** | Execução pontual/administrativa, fora do workflow HTTP | `scripts/` |
| **Deps** | Declaração de dependências | `pyproject.toml` |
| **Data** | Arquivos de dados, bases, índices | `data/` |
| **Embeddings/busca semântica** | EmbeddingManager standalone, ChunkingService standalone, busca coseno em memória, PKL de embeddings | `src/<domínio>/store.py` (ChromaDB — ver seção Decisões Arquiteturais) |

**Utilitários padrão do time — verificar antes de classificar como "Util portável":**

| Utilitário | Cobre | Quando substituir o código legado |
|-----------|-------|-----------------------------------|
| `utils/logger_setup.py` | Logging com arquivo + console, rotação diária | Qualquer `logging.basicConfig()`, `print()` para debug, logger customizado |
| `utils/exception_setup.py` | `ApplicationError` com status_code, error_code, context | Qualquer exception customizada, retorno de dict com erro |
| `utils/hash_manager.py` | Hashes MD5/SHA256, cache por conteúdo | Qualquer `hashlib.md5()`, `hashlib.sha256()` solto, lógica de cache por conteúdo |
| `utils/pdfplumber_extractor.py` | Extração texto/tabelas de PDFs (OCR simples) | Qualquer uso de `pdfplumber`, `PyPDF2`, `pypdf` direto no legado |
| `utils/dpt2_extractor.py` | Extração OCR avançada via Landing.AI DPT-2 | Legado com chamadas diretas à API Landing.AI ou OCR de alta qualidade |
| `utils/wordcom_toolkit.py` | Manipulação .docx via COM (Windows) | Qualquer uso de `win32com.client` para Word, `python-docx` para geração |
| `utils/llm_manager.py` | Cliente LLM multi-provider (OpenAI, Gemini, Anthropic, Ollama), completion com timeout e retries | Qualquer wrapper LLM próprio, `openai.OpenAI()` direto, cliente Anthropic/Gemini customizado |

Se o legado tem lógica **similar mas diferente** de um utilitário padrão:
1. **Usar o utilitário oficial agora** — classificar como "Util padrão do time" na tabela de destinos
2. **Adaptar os callers** para usar o utilitário oficial (ajustar assinaturas, adicionar parâmetros)
3. **Registrar no feedback** desta SKILL com sugestão de expandir o utilitário oficial para cobrir o caso
4. **Remover** a versão do projeto — nunca manter implementação paralela ao utilitário oficial

**Nunca** manter uma variante paralela ao utilitário oficial enquanto aguarda a expansão do utilitário.

**Critério síncrono vs. assíncrono:**
- Utilizador pode esperar a resposta HTTP → endpoint síncrono (router chama service diretamente)
- Utilizador não pode/deve esperar → endpoint assíncrono (router enfileira ARQ task, retorna `job_id`)
- O critério é experiência do utilizador e confiabilidade, não tempo absoluto

**Regras de classificação:**
- Na dúvida entre domínio e helper → **domínio** (`helpers/` frequentemente fica vazio)
- Na dúvida entre helper e utils → **utils/** (mais restritivo: zero deps de projeto)
- Lógica já coberta por util padrão → **substituir** (não copiar código legado)
- Constantes de domínio específico → `src/<domínio>/constants.py` (NUNCA `settings.py`)
- Constantes globais/infra → `src/config/settings.py`

### FASE 3 — Agrupamento de Domínios

Agrupar arquivos de domínio em pastas lógicas por **funcionalidade de negócio** (nunca por tipo técnico).

Exemplos de nomes ruins: `models/`, `utils/` dentro de src, `processors/`
Exemplos de nomes bons: `document_query/`, `npv_analysis/`, `sap_integration/`

### FASE 4 — Análise do Projeto Destino

Verificar o que já existe no projeto destino (template ou projeto já iniciado):
- Quais arquivos já existem e estão corretos → **ignorar**
- Quais existem mas precisam de atualização → **atualizar**
- Quais precisam ser criados do zero → **criar**

Identificar também se o projeto precisará de:
- `providers.py` + `active.py` → apenas se tiver seleção de provider LLM em runtime via UI
- Subpastas específicas em `data/` → baseado nos dados que o legado manipula

### FASE 5 — Apresentação e Aprovação

Apresentar ao utilizador:

**Tabela de classificação:**
```
| Arquivo original | Classificação | Destino | Ação |
|-----------------|---------------|---------|------|
| legado/main.py  | entry point   | main.py | criar/atualizar |
| legado/rag.py   | domínio       | src/document_query/engine.py | criar |
...
```

**Decisões arquiteturais obrigatórias:**

Para cada desvio de plataforma identificado, indicar qual SKILL resolve e como:

| Desvio identificado no legado | SKILL responsável | Como resolver |
|-------------------------------|-------------------|---------------|
| Embeddings em PKL/numpy, EmbeddingManager standalone, busca coseno | `/migrate-domain` | Criar `src/<domínio>/store.py` com `chromadb.PersistentClient`; `/migrate-infra` adiciona `chromadb` como dep |
| Celery + RabbitMQ / Celery + Redis | `/migrate-api` | Substituir tasks Celery por ARQ tasks em `src/tasks/`; WorkerSettings em `arq_worker.py` |
| Flask / Django / aiohttp | `/migrate-api` | Reescrever routers como FastAPI com lifespan; mover lógica para services |
| Docker / docker-compose | `/migrate-infra` | Remover todos os arquivos Docker; Redis via Cloud (configurar .env) |
| pip / poetry / conda | `/migrate-infra` | Migrar deps para `pyproject.toml`; usar `uv add` |
| `main.py` na raiz como entry point | `/migrate-infra` | Remover `main.py` da raiz; entry point é `uvicorn src.api.main:app` |
| Streamlit / Tkinter como frontend | `/migrate-api` | Manter frontend separado; expor API FastAPI que o frontend consome — nunca misturar lógica de negócio no frontend |

**Aguardar aprovação explícita do utilizador antes de salvar artefatos.**

### FASE 6 — Salvar Artefatos

Após aprovação, salvar em `.claude/skills-feedback/`:

**`migration-plan-<projeto>.md`** — Plano de execução consumido pelas SKILLs do Cluster 2:
```markdown
# Migration Plan: <projeto>

## Domínios identificados
- <domínio-1>: <arquivos>
- <domínio-2>: <arquivos>

## Config necessária
- settings.py: <variáveis a adicionar>
- providers.py + active.py: sim/não (motivo)
- data/: <subpastas a criar>

## Dependências a adicionar
- <lib>==<versão>

## Decisões arquiteturais obrigatórias
<!-- Para cada desvio: indicar SKILL responsável e ação concreta -->
- <ex: embeddings em PKL → /migrate-infra adiciona chromadb; /migrate-domain cria store.py com PersistentClient>
- <ex: main.py na raiz → /migrate-infra remove o arquivo>

## Checklist de execução
- [ ] /migrate-infra
- [ ] /migrate-domain
- [ ] /migrate-api
- [ ] /migrate-tests
- [ ] /audit-project
```

**`migration-map-<projeto>.md`** — Mapa de rastreabilidade completo:
```markdown
# Migration Map: <projeto>

| Arquivo original | Função/Classe | Destino no template | Status |
|-----------------|---------------|---------------------|--------|
| rag.py | RAGEngine | src/document_query/engine.py | ✅ |
| helpers.py | format_text() | src/helpers/text_helper.py | ✅ |
| config.py | DB_PATH | src/config/settings.py | ✅ |
```

Status: `✅` correto | `⚠️` local não-padrão | `❌` não encontrado/pendente

---

## FASE FINAL — Registro de Feedback

Ao concluir a execução desta SKILL, registrar entrada em `.claude/skills-feedback/migrate-analyze.md`:

```markdown
## [YYYY-MM-DD] Projeto: <nome>

**Duração:** <estimativa>
**Arquivos inventariados:** <N>

**O que funcionou bem:**
- <ponto positivo>

**O que foi difícil:**
- <ponto de atrito>

**Sugestão de melhoria para esta SKILL:**
- <proposta>
```