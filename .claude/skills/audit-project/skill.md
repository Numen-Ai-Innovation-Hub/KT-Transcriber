# SKILL: /audit-project

**Propósito:** Checklist declarativo — verificar se o projeto migrado atende ao padrão
FastAPI+ARQ+Redis para produção. NÃO executa correções — apenas reporta o que está
conforme e o que precisa ser corrigido.

**Argumento:** sem argumento — audita o projeto atual

**Pré-requisito:** `/migrate-tests` concluído. Se `tests/test_smoke.py` ou `tests/test_e2e.py`
estiverem ausentes, reportar como ❌ e recomendar executar `/migrate-tests` antes de prosseguir.

---

## Definições de Plataforma (referência para checklist)

| Categoria | Padrão obrigatório |
|-----------|-------------------|
| Banco vetorial | ChromaDB persistent (nunca http mode) |
| Filas/workers | ARQ + Redis Cloud (nunca Celery, nunca Docker Redis) |
| Redis | Redis Cloud via .env (nunca Docker, nunca local/WSL2) |
| Containerização | Nenhuma (zero Docker em qualquer camada) |
| Framework HTTP | FastAPI com lifespan |
| Gestão de deps | uv (nunca pip diretamente) |

---

## Procedimento

### FASE 0 — Preparar Stack para Testes

Esta fase é obrigatória e deve ser executada ANTES do checklist.
Os testes smoke e e2e requerem Redis + FastAPI + ARQ Worker rodando.

**Passo 1 — Verificar estado atual da stack:**

Executar `check-services.ps1` (não-interativo, invocável pelo Claude Code):

```bash
powershell -ExecutionPolicy Bypass -File ".vscode/scripts/check-services.ps1" 2>/dev/null
```

Interpretar o output:
- `REDIS: OK` / `FASTAPI: OK` → stack já está ativa, avançar para Passo 3
- Qualquer `ERRO` → stack não está disponível, executar Passo 2

**Se `check-services.ps1` não existir:** o projeto não tem a versão atualizada do template.
Verificar FastAPI via curl como fallback:
```bash
curl -s -o /dev/null -w "FASTAPI: %{http_code}" http://localhost:8000/v1/health 2>/dev/null
```
Redis Cloud é verificado indiretamente — se o ARQ Worker subiu sem erro, a conexão está ok.

**Passo 2 — Instruir o utilizador a iniciar a stack (se necessário):**

> **IMPORTANTE:** `start-services.ps1` é interativo (abre Windows Terminal)
> e **não pode ser executado pelo Claude Code via Bash**. O utilizador deve executá-lo manualmente.

Apresentar ao utilizador e aguardar confirmação antes de prosseguir:

```
Por favor, no terminal do VSCode (Ctrl+`):
  1. Executar: .\.vscode\scripts\start-services.ps1
  2. Aguardar a mensagem "Servicos prontos!"
  3. Confirmar aqui quando a stack estiver disponível
```

Após confirmação, re-executar `check-services.ps1` para validar:

```bash
powershell -ExecutionPolicy Bypass -File ".vscode/scripts/check-services.ps1" 2>/dev/null
```

**Passo 3 — Executar os 3 tipos de teste:**

Apenas com `RESULTADO: OK` confirmado pelo `check-services.ps1`, executar em sequência:

```bash
uv run python -m pytest tests/ -m "not smoke and not e2e" --tb=short   # unit
uv run python -m pytest tests/ -m smoke --tb=short                     # smoke
uv run python -m pytest tests/ -m e2e --tb=short                       # e2e
```

> **AVISO — Falso positivo:** Se smoke/e2e reportarem "passed" sem `RESULTADO: OK` confirmado,
> é `pytest.skip` por Redis indisponível — **não é aprovação**. Só interpretar resultados
> após `check-services.ps1` confirmar stack ativa.

**Passo 4 — Ler logs de serviço após os testes:**

Após executar os testes, ler os logs para identificar erros de runtime:

```bash
tail -100 logs/fastapi.log   # erros do uvicorn / exceptions de endpoint
tail -100 logs/arq.log       # erros do ARQ Worker / falhas de task
```

Reportar qualquer `ERROR`, `Exception` ou `Traceback` encontrado nos logs.

**Se `start-services.ps1` não existir:**
Reportar como ❌ na seção Executabilidade. Executar unit tests apenas.
Marcar smoke e e2e como ❌ (stack não disponível) e indicar que o script deve ser criado.

---

### FASE 1 — Executar Checklist

Verificar cada item abaixo. Para cada um: ✅ (conforme) ou ❌ (não conforme + descrição do problema).

---

### Checklist de Infraestrutura

```
[ ] src/config/ tem settings.py e startup.py (obrigatórios)
[ ] providers.py + active.py presentes SE o projeto tem seleção de provider em runtime via UI
    (ausência é correta se não há UI de troca de provider)
[ ] REDIS_HOST, REDIS_PORT configurados em settings.py e no .env
[ ] Redis configurado via Redis Cloud no .env (REDIS_HOST, REDIS_PORT, REDIS_PASSWORD)
    → Verificar: zero referências a Docker Redis, redis local/WSL2
[ ] data/**/* no .gitignore (padrão global)
    → Verificar: NÃO deve ter entradas por subpasta (data/cache/, data/databases/)
[ ] Zero referências a Docker em qualquer arquivo do projeto
    → Verificar: Dockerfile, docker-compose.yml, requirements no formato Docker
[ ] Se o projeto gera ou persiste embeddings: usa ChromaDB.PersistentClient
    → Verificar: chromadb presente em pyproject.toml como dependência
    → Verificar: chromadb.PersistentClient no código (nunca chromadb.HttpClient)
    → Verificar: zero EmbeddingManager standalone em src/ (embeddings geridos pelo ChromaDB)
    → Verificar: zero PKL/pickle para persistência de embeddings
    → Verificar: zero busca coseno manual em memória (numpy) — usar collection.query()
    → NOTA: Se o projeto ainda não passou por /migrate-domain, PKL é esperado.
      Reportar como ❌ mas indicar pré-requisito (/migrate-domain), não blocker para deploy.
[ ] Se chromadb presente: versão instalada é 1.x E API usada é coerente com a versão
    → Verificar versão em pyproject.toml (deve ser chromadb==1.x.y — nunca 0.5.x)
    → Verificar: grep "IncludeEnum" src/ — deve estar vazio (IncludeEnum é API 0.5.x, removida na 1.x)
    → Verificar: grep 'include=\["' src/ — deve aparecer nos métodos query/get (padrão correto para 1.x)
    → Se IncludeEnum presente com chromadb==0.5.x: API consistente mas versão desatualizada — atualizar ambos
    → Se IncludeEnum presente com chromadb==1.x: quebra em runtime — corrigir para strings imediatamente
    → Após upgrade de versão: apagar data/vector_db/ (schema ChromaDB não é compatível entre 0.5.x e 1.x)
      — dados precisam ser re-ingeridos; schema corrompido causa erros silenciosos difíceis de diagnosticar
[ ] pyproject.toml tem pythonpath = ["."] em [tool.pytest.ini_options]
    → Verificar: ausência quebra pytest tests/ no Windows com ModuleNotFoundError: No module named 'src'
[ ] uv usado para gestão de deps (pyproject.toml como fonte de verdade)
    → Verificar: zero requirements.txt standalone, zero pip install em scripts
```

### Checklist de Domínio

```
[ ] Pelo menos uma pasta de domínio em src/ (além de api/, config/, db/, helpers/, services/, tasks/)
[ ] Nenhum arquivo de domínio importa de src/api/ ou src/services/
    → Verificar: grep "from src.api" src/<domínio>/ e grep "from src.services" src/<domínio>/
[ ] Zero Path("data/...") hardcoded — apenas DIRECTORY_PATHS
    → Verificar: grep 'Path("data' src/
[ ] Zero logging.basicConfig() — apenas get_logger(__name__) de utils/logger_setup.py
    → Verificar: grep "logging.basicConfig" src/
[ ] Zero print() fora de scripts/
    → Verificar: grep "print(" src/
[ ] Constantes de domínio em src/<domínio>/<domínio>_constants.py (nunca em settings.py, nunca constants.py sem prefixo de domínio)
[ ] Funções com type hints Python 3.10+ (sem Optional, sem List, sem Dict de typing)
[ ] Docstrings Google-style em português nas funções públicas
[ ] Zero arquivos de domínio com cobertura de testes < 20%
    → Usar output do pytest --cov obtido na FASE 0
    → Arquivos com Stmts > 50 e Cover < 20% sem testes dedicados são código morto — remover
[ ] Zero except Exception: pass silencioso no domínio
    → Verificar: grep -rn "except Exception:\s*$" src/<domínio>/
    → except Exception sem corpo (só pass) é supressão silenciosa — proibido
```

### Checklist de Utilitários Padrão do Time

Verificar se os utilitários padrão estão sendo usados onde deveriam.
Lógica duplicada é sinal de migração incompleta.

```
[ ] utils/exception_setup.py e utils/logger_setup.py presentes (obrigatórios em todo projeto)
[ ] Zero exception customizada PARALELA (não subclasse) ao ApplicationError
    → Verificar: grep "class.*Error.*Exception" src/ utils/
    → Correto:   class FooError(ApplicationError): ...   ← subclasse legítima
    → Incorreto: class FooError(Exception): ...          ← paralela, viola padrão
[ ] Zero logger de módulo fora de utils/logger_setup.py
    → Verificar: grep "logging.getLogger" src/ — deve aparecer apenas em logger_setup.py
    → EXCEÇÃO LEGÍTIMA: logging.getLogger("lib_externa").setLevel(...) em startup.py
      para suprimir telemetria de libs (chromadb, httpx, etc.) — não é violação
[ ] Zero import direto de pdfplumber em src/
    → Verificar: grep "import pdfplumber\|from pdfplumber" src/
    → Extração bruta de texto/tabelas delegada a utils/pdfplumber_extractor.py
    → Lógica de domínio sobre o conteúdo extraído (chunking, indexação) fica em src/ — correto
[ ] Se projeto processa .docx: usa utils/wordcom_toolkit.py
    → Verificar: grep "win32com\|python-docx\|docx" src/ (não deve aparecer fora de utils/)
[ ] Se projeto usa cache por conteúdo ou hashes: usa utils/hash_manager.py
    → Verificar: grep "hashlib" src/ (não deve aparecer fora de utils/)
    → Verificar: DIRECTORY_PATHS tem entrada "sqlite_db" (data/sqlite_db/)
    → Verificar: FILE_PATHS tem "hashes_db" apontando para data/sqlite_db/hashes.db
    → Verificar: zero entrada "hashes" em DIRECTORY_PATHS (padrão JSON legado — substituído por sqlite_db)
[ ] Nenhum utilitário padrão foi reimplementado em src/helpers/ ou src/<domínio>/
    → Em especial: zero wrapper LLM próprio (utils/llm_manager.py cobre todos os providers)
[ ] Zero arquivos de template não removidos (example_service.py, example_router.py, etc.)
    → Verificar: grep -r "example" src/services/ src/api/routers/ (nomes de placeholder do template)
    → Arquivos do template não referenciados por nenhum router/service devem ser removidos
```

### Checklist de Coerência Interna

Verificar se as peças do projeto se encaixam de forma consistente entre si.
Estes itens não são violações de padrão do template, mas sinais de migração incompleta ou dead code.

```
[ ] Zero utils importados apenas em TYPE_CHECKING mas nunca usados em runtime
    → Verificar: grep -rn "TYPE_CHECKING" src/
    → Para cada ocorrência: confirmar se o tipo importado é passado como argumento em __init__ em runtime
    → Sinal de problema: tipo importado em TYPE_CHECKING mas instância nunca recebida via parâmetro

[ ] Zero utils presentes no projeto mas sem nenhum import real em src/
    → Para cada arquivo em utils/*.py: grep -r "from utils.<nome>" src/ scripts/ tests/
    → Distinguir dois casos antes de reportar:
      - utils nunca importados E sem relação com o domínio → remover (❌)
      - utils do toolkit do time (ex: dpt2_extractor.py, wordcom_toolkit.py) presentes mas não integrados
        porque a funcionalidade ainda não foi implementada → ⚠️ (não ❌), anotar como "futuro"
    → Regra: copresença de utils no projeto é intencional quando o sync-to-project os inclui;
      não reportar como não-conformidade apenas porque ainda não são usados

[ ] Zero cache duplicado em camadas diferentes para o mesmo recurso
    → Verificar: hash_manager chamado tanto em src/<domínio>/ quanto em src/services/ para o mesmo arquivo
    → Deve haver um único ponto de cache — preferencialmente no service

[ ] Services de domínio não importam utils.llm_manager diretamente
    → Verificar: grep -rn "from utils.llm_manager" src/
    → Correto: importar de src.services.llm_service (re-export centralizado)

[ ] Zero sqlite3 inline em src/ fora do hash_manager
    → Verificar: grep -rn "import sqlite3" src/
    → Qualquer sqlite3 direto em src/ deve ser substituído por get_hash_manager()
    → Exceção: src/db/repositories.py com SQLAlchemy (ORM) é aceitável
```

### Checklist de API

```
[ ] Pelo menos um service com singleton thread-safe (threading.Lock() + double-checked locking)
[ ] Pelo menos um router registrado em src/api/main.py
[ ] Todos os routers com prefix /v1/<recurso>
[ ] Zero HTTPException fora de routers
    → Verificar: grep "HTTPException" src/services/ src/<domínio>/
[ ] Zero logger.exception() fora do global handler em src/api/main.py
    → Verificar: grep "logger.exception" src/ (deve aparecer apenas em main.py)
[ ] Zero lógica de negócio nos routers (apenas delegação ao service)
[ ] Services não importam de src/api/
    → Verificar: grep "from src.api" src/services/
[ ] Tasks ARQ com primeiro parâmetro ctx: dict[str, Any]
[ ] Tasks registradas em WorkerSettings.functions contêm implementações reais (não placeholders)
    → Verificar: WorkerSettings.functions lista apenas tasks que existem em tasks/*.py
    → Verificar: tasks listadas NÃO são exemplo_task ou placeholders do template
    → Verificar: toda task implementada em tasks/*.py está referenciada em WorkerSettings.functions
      — task implementada mas não registrada nunca será executada pelo worker
    → Sinal de problema: task com nome genérico (exemplo_task, process_item) sem lógica real
[ ] Docstrings de tasks não mencionam tecnologias substituídas
    → Verificar: grep -rn "pkl\|pickle\|PKL\|celery\|Celery\|rabbitmq" src/tasks/
    → Docstrings que mencionam PKL, pickle ou Celery são artefatos de migração incompleta
    → Atualizar docstrings para refletir o stack atual (ARQ + Redis)
[ ] arq_worker.py não tem bloco if __name__ == "__main__":
    → Entry point exclusivo é: arq src.tasks.arq_worker.WorkerSettings
    → Bloco __main__ em arq_worker.py é redundante e cria ambiguidade sobre o entry point
```

### Checklist de Testes

Os resultados deste checklist vêm do output real obtido na FASE 0.
Não inferir — usar o output do pytest para preencher cada item.

```
[ ] tests/test_*.py existe para cada módulo de domínio principal
[ ] tests/test_smoke.py existe com @pytest.mark.smoke
[ ] tests/test_e2e.py existe com @pytest.mark.e2e e pelo menos um fluxo completo
[ ] Markers smoke e e2e declarados em [tool.pytest.ini_options] do pyproject.toml
    → Sem declaração: pytest -m smoke não filtra corretamente
[ ] pytest tests/ -m "not smoke and not e2e" — todos passam (0 falhas, 0 erros)
    → Reportar número exato: X passed, Y failed, Z errors
[ ] pytest tests/ -m smoke — todos passam (0 falhas, 0 erros)
    → Reportar número exato: X passed, Y failed, Z errors
[ ] pytest tests/ -m e2e — todos passam (0 falhas, 0 erros)
    → Reportar número exato: X passed, Y failed, Z errors
[ ] Cobertura de testes: nenhum arquivo com Stmts > 50 e Cover < 20%
    → Usar output --cov-report=term-missing da FASE 0
```

### Checklist de Qualidade

```
[ ] ruff check src utils scripts tests — zero erros
    → ruff cobre src/, utils/, scripts/ E tests/ (linting em todos)
[ ] mypy --config-file=pyproject.toml src utils scripts — zero erros
    → mypy cobre src/, utils/, scripts/ — NÃO cobre tests/ (type checking não se aplica a fixtures)
[ ] Zero # type: ignore no código — exceto # type: ignore[import-untyped]
    → Exceção documentada: bibliotecas sem stubs (ex: pandas, win32com, langchain_*)
    → Solução preferida: uv add --dev <lib>-stubs (ex: pandas-stubs)
    → Se stubs não existem: # type: ignore[import-untyped] é aceitável
    → Qualquer outro uso de # type: ignore é proibido
[ ] Zero "..." (ellipsis) como valor de string
```

### Checklist de Executabilidade (Claude Code)

```
[ ] .vscode\scripts\start-services.ps1 existe
    → Script unificado que verifica Redis, valida .env, e sobe FastAPI + ARQ Worker
[ ] CLAUDE.md tem seção "Commands" com entry points documentados:
    - uvicorn src.api.main:app --reload
    - arq src.tasks.arq_worker.WorkerSettings
    - pytest tests/
    - pytest tests/ -m smoke
    - pytest tests/ -m e2e
[ ] .env.example tem todas as variáveis com instrução clara para cada uma
[ ] .env existe com valores funcionais para desenvolvimento
[ ] Todos os commands do CLAUDE.md executam sem configuração manual adicional
[ ] Ausência de main.py na raiz do projeto
    → Entry point da aplicação é exclusivamente uvicorn src.api.main:app
    → main.py na raiz é artefato de migração incompleta do legado
    → Exceção: projetos CLI puro (Typer sem FastAPI) podem ter main.py na raiz
```

---

### FASE 2 — Relatório

Apresentar relatório estruturado:

```
## Relatório de Auditoria — <projeto> — <data>

### Resultados dos Testes
| Suite | Resultado | Detalhe |
|-------|-----------|---------|
| Unit  | ✅ 42 passed | 0 failed, 0 errors |
| Smoke | ✅ 3 passed  | 0 failed, 0 errors |
| E2E   | ❌ 1 failed  | test_fluxo_completo — KeyError: 'metadata' |

### Cobertura
| Arquivo | Stmts | Cover |
|---------|-------|-------|
| src/rag/embedding_engine.py | 80 | 45% |

### Infraestrutura
✅ settings.py e startup.py presentes
❌ providers.py ausente mas projeto tem UI de troca de provider → /migrate-infra

### Domínio
✅ 2 domínios identificados: document_query, analytics
❌ Path hardcoded encontrado em src/document_query/store.py:45 → /migrate-domain

...

### Pendências
| Item | SKILL para corrigir |
|------|---------------------|
| providers.py ausente | /migrate-infra |
| Path hardcoded em store.py | /migrate-domain |
| logger.exception em service | /migrate-api |
```

**Output:** Relatório com ✅/❌ por item + resultados reais dos testes + tabela de pendências.
NÃO executa correções — indica o caminho para resolver.

---

## FASE FINAL — Registro de Feedback

Ao concluir, registrar entrada em `.claude/skills-feedback/audit-project.md`:

```markdown
## [YYYY-MM-DD] Projeto: <nome>

**Itens auditados:** <N>
**Conformes:** <N> ✅
**Não conformes:** <N> ❌

**Resultados dos testes:**
- Unit:  X passed, Y failed
- Smoke: X passed, Y failed
- E2E:   X passed, Y failed

**Não conformidades mais comuns:**
- <item>: <frequência>

**Sugestão de melhoria para esta SKILL:**
- <proposta (novo item de checklist, item desnecessário, etc.)>
```