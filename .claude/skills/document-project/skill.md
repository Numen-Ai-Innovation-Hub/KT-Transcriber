# SKILL: /document-project

**Propósito:** Gerar e manter a documentação do projeto em `docs/`: estrutura de pastas e arquivos,
fluxos de processamento, referência de funções/classes e guia "where was I?" para retomada de
trabalho. Cria os arquivos se não existirem, verifica consistência com o código atual e atualiza
a documentação quando houver divergência.

**Argumento:** sem argumento — opera no projeto atual, analisa `src/`, `utils/`, `scripts/`, `data/`, `tests/` e raiz

**Quando usar:** Quando o utilizador pedir para documentar o projeto, atualizar a documentação
ou verificar se a documentação está correta/condizente com o código.

---

## Definições

| Item | Regra |
|------|--------|
| Local | Todos os arquivos de documentação em `docs/` |
| Obrigatório | `docs/WHERE_WAS_I.md` — sempre presente |
| Padrão de nomes | `STRUCTURE.md`, `FLOW.md`, `REFERENCE.md`, `WHERE_WAS_I.md` |
| Idioma | Português |
| Índice | Não criar `docs/README.md` — WHERE_WAS_I é o ponto de entrada |
| Detalhe | Textos sempre detalhados — sem resumos ou "N/A" |

---

## Procedimento

Sempre que esta skill for executada: (1) ler o que existe em `docs/`, (2) analisar o código no
escopo, (3) comparar com os critérios de consistência, (4) criar ou atualizar os arquivos necessários.

---

### FASE 1 — Ler estado atual da documentação

1. Listar todos os arquivos em `docs/` (se a pasta não existir, considerar "nenhum doc existente").
2. Para cada um de `STRUCTURE.md`, `FLOW.md`, `REFERENCE.md`, `WHERE_WAS_I.md`:
   - Se existir: ler o conteúdo e guardar mentalmente o que está documentado (pastas, fluxos, funções, entry points).
   - Se não existir: marcar para criação.
3. Garantir que `docs/` existe (criar se necessário ao escrever o primeiro arquivo).

---

### FASE 2 — Analisar o projeto (escopo)

Analisar as seguintes pastas e arquivos:

**Pastas principais (conteúdo detalhado):**
- `src/` — estrutura completa, módulos, responsabilidade de cada pasta/arquivo
- `utils/` — arquivos e propósito
- `scripts/` — scripts e propósito
- `data/` — apenas estrutura (subpastas e propósito; não conteúdo de ficheiros)

**Incluir em STRUCTURE com uma linha cada:**
- `tests/` — uma linha descrevendo a pasta
- Arquivos relevantes da raiz: `pyproject.toml`, `.env.example`, outros que afetem configuração ou entry points

**Para REFERENCE:** inspecionar funções e classes públicas em `src/` e `utils/`; ler docstrings e comentários existentes no código para refletir na documentação.

**Para FLOW:** identificar endpoints HTTP (síncronos e assíncronos), tasks ARQ registradas, e scripts de entrada; mapear fluxos request → router → service → domínio e enfileiramento → task ARQ.

**Para WHERE_WAS_I:** identificar entry points (uvicorn, arq worker, scripts), comandos de execução e testes, e "onde está cada tipo de lógica" (API, domínio, tasks, scripts).

---

### FASE 3 — Verificar consistência e decidir ações

Comparar o estado analisado (FASE 2) com o estado documentado (FASE 1). Atualizar quando:

| Documento | Atualizar quando |
|-----------|-------------------|
| **STRUCTURE** | Pasta ou arquivo novo, removido ou renomeado |
| **FLOW** | Novo ou removido endpoint, task ARQ ou script de entrada |
| **REFERENCE** | Função/classe nova, removida ou com assinatura/módulo alterado |
| **WHERE_WAS_I** | Mudança em entry points, comandos de run/test ou em "onde está a lógica X" |

Se não existir documento → criar. Se existir mas houver divergência → atualizar. Se existir e estiver conforme → não alterar (ou apenas confirmar ao utilizador).

---

### FASE 4 — Estrutura: `docs/STRUCTURE.md`

**Conteúdo:**
- Árvore completa de pastas e arquivos para `src/`, `utils/`, `scripts/`, `data/`.
- Incluir `tests/` e ficheiros da raiz com uma linha cada.
- Profundidade máxima: todos os níveis (não limitar).
- Para cada pasta: uma linha descrevendo a responsabilidade.
- Para cada arquivo: uma linha descrevendo o propósito (exceto `__init__.py` vazios — omitir ou citar apenas como "presente").
- `__init__.py` com conteúdo (exports, lógica): documentar como os demais arquivos.

**Formato:** listas em Markdown, indentação clara, texto em português, descrições detalhadas.

---

### FASE 5 — Fluxo: `docs/FLOW.md`

**Conteúdo:**
- Diagrama em **Mermaid** obrigatório (fluxo HTTP síncrono, fluxo HTTP assíncrono, fluxo de task ARQ).
- Texto explicativo em português para cada fluxo: passos, componentes envolvidos, ordem de chamadas.
- Documentar: endpoints HTTP (síncrono e assíncrono), tasks ARQ (nome, onde são registradas, o que fazem).
- Sempre criar/conteúdo detalhado — não usar "N/A" ou resumo mínimo.

**Exemplo de secção (adaptar ao projeto):**
```markdown
## Fluxo HTTP síncrono
[Diagrama Mermaid]
[Texto explicativo]

## Fluxo HTTP assíncrono (job)
[Diagrama Mermaid]
[Texto explicativo]

## Fluxo das tasks ARQ
[Diagrama Mermaid]
[Texto explicativo]
```

---

### FASE 6 — Referência: `docs/REFERENCE.md`

**Conteúdo:**
- Funções e classes **públicas** de módulos em `src/` e `utils/`.
- Refletir as **docstrings e comentários já existentes no código** — não inventar descrições; usar o que está nos arquivos.
- Por módulo: listar funções/classes com nome, assinatura (parâmetros e retorno quando relevante) e descrição breve baseada no código.
- Texto em português; descrições detalhadas quando o código já as tiver.

**Formato:** cabeçalhos por módulo ou pasta, lista de funções/classes com assinatura e descrição.

---

### FASE 7 — Where was I: `docs/WHERE_WAS_I.md`

**Propósito deste documento:** Guiar qualquer pessoa ou IA a retomar o trabalho no projeto após uma pausa (melhorias, ajustes, implementação interrompida). Cenários: desenvolvedor que parou e volta; IA que perde contexto; troca de IA. O utilizador deve poder consultar este documento (com ou sem IA) para continuar a implementação com clareza do estado atual do sistema.

**Conteúdo obrigatório (em português, detalhado):**
- **Estado atual do projeto:** o que já está implementado e estável; o que está em progresso ou pendente.
- **Entry points:** como iniciar a aplicação (ex.: `uvicorn src.api.main:app`, `arq src.tasks.arq_worker.WorkerSettings`), scripts em `scripts/` que são pontos de entrada.
- **Como rodar e testar:** comandos para executar a aplicação e os testes (ex.: `pytest tests/`, `pytest tests/ -m smoke`, `pytest tests/ -m e2e`).
- **Onde está cada tipo de lógica:** onde fica a API (routers, main), domínio (pastas em `src/`), tasks ARQ, scripts, configuração; referências concretas (pastas/arquivos).
- **Links para os outros documentos:** referência a [STRUCTURE.md](STRUCTURE.md), [FLOW.md](FLOW.md), [REFERENCE.md](REFERENCE.md) para quem quiser aprofundar.

Atualizar sempre que houver mudança em entry points, comandos de run/test ou na organização da lógica do projeto.

---

### FASE 8 — Escrever ou atualizar os arquivos

1. Para cada arquivo em `docs/` que deve ser criado ou atualizado (resultado da FASE 3):
   - Gerar o conteúdo conforme as FASEs 4 a 7.
   - Escrever em `docs/` com o nome correto (`STRUCTURE.md`, `FLOW.md`, `REFERENCE.md`, `WHERE_WAS_I.md`).
2. Garantir que `docs/WHERE_WAS_I.md` existe sempre — se não existir, criar; se existir e estiver desatualizado, atualizar.
3. Revisar: tudo em português, sem resumos vagos, com o nível de detalhe definido.

---

## Critérios de conclusão

- `docs/` existe e contém pelo menos `WHERE_WAS_I.md`.
- `STRUCTURE.md`, `FLOW.md`, `REFERENCE.md` existem e estão alinhados com o projeto (criados ou atualizados conforme análise).
- STRUCTURE: árvore completa (src, utils, scripts, data, tests, raiz); uma linha por item; __init__.py vazios omitidos ou só citados.
- FLOW: diagrama Mermaid presente; HTTP síncrono/assíncrono e tasks ARQ documentados; texto detalhado.
- REFERENCE: funções/classes públicas; descrições refletem docstrings/comentários do código.
- WHERE_WAS_I: estado atual, entry points, como rodar/testar, onde está cada lógica, links para os outros docs; conteúdo detalhado em português.

---

## FASE FINAL — Registro de feedback (opcional)

Ao concluir, pode registrar entrada em `.claude/skills-feedback/document-project.md`:

```markdown
## [YYYY-MM-DD] Projeto: <nome>

**Documentos criados:** <lista>
**Documentos atualizados:** <lista>

**O que funcionou bem:**
- <ponto positivo>

**O que foi difícil:**
- <ponto de atrito>

**Sugestão de melhoria para esta SKILL:**
- <proposta>
```
