# Sistema de Feedback das SKILLs

Este diretório acumula feedbacks automáticos gerados pelo Claude ao final de cada execução de SKILL.
O objetivo é alimentar melhorias contínuas nos procedimentos das SKILLs com base em situações reais.

---

## O Que É Este Sistema

Cada vez que uma SKILL é executada, o Claude registra o que aconteceu de inesperado:
desvios do procedimento, erros encontrados, decisões que o procedimento não cobria,
fixes manuais aplicados. Esse histórico acumula aqui e serve de insumo para evoluir as SKILLs.

---

## Estrutura de Arquivos

Um arquivo por SKILL + artefatos de migração:

```
.claude/skills-feedback/
├── README.md                          ← Este arquivo
├── migrate-analyze.md                 ← Feedback de /migrate-analyze
├── migrate-infra.md                   ← Feedback de /migrate-infra
├── migrate-domain.md                  ← Feedback de /migrate-domain
├── migrate-api.md                     ← Feedback de /migrate-api
├── migrate-tests.md                   ← Feedback de /migrate-tests
├── audit-project.md                   ← Feedback de /audit-project
├── audit-pair.md                     ← Feedback de /audit-pair (comparação entre projetos)
├── migration-plan-<projeto>.md        ← Plano gerado por /migrate-analyze (consumido pelo Cluster 2)
└── migration-map-<projeto>.md         ← Mapa de rastreabilidade gerado por /migrate-analyze
```

Os arquivos individuais de feedback são criados automaticamente pelo Claude na primeira
execução de cada SKILL. O diretório começa vazio (exceto este README).

---

## Formato de uma Entrada de Feedback

### Execução sem desvios (linha única):

```
[YYYY-MM-DD] <projeto> — [OK] Sem desvios
```

### Execução com desvio (entrada completa):

```markdown
## [YYYY-MM-DD] <projeto> — <resumo em 1 linha>

**SKILL:** <nome-da-skill>
**Fase onde ocorreu:** <ex: FASE 2, FASE 3>
**Tipo:** problema | decisão | desvio | melhoria-sugerida

**O que aconteceu:**
<descrição objetiva — o que o procedimento da SKILL não cobria ou cobria errado>

**Fix aplicado:**
<o que foi feito para resolver no momento>

**Sugestão para a SKILL:**
<onde exatamente na SKILL adicionar/alterar para prevenir isso>
```

---

## Regras de Preenchimento

- **Só registrar se houve algo que a SKILL não cobria ou cobria de forma insuficiente**
- **Execução perfeita** → linha única: `[YYYY-MM-DD] <projeto> — [OK] Sem desvios`
- **Máximo 10 linhas por entrada** — objetivo e direto
- **Nunca registrar detalhes do projeto** (paths específicos, nomes de variáveis do cliente)
  — o feedback deve ser generalizável para outros projetos
- **O feedback é escrito pelo Claude** durante/após a execução — não é formulário manual
- O arquivo usa **append** (nunca sobrescreve) — cada execução adiciona uma entrada

---

## Como Interpretar as Entradas

| Tipo | Significado |
|------|-------------|
| `problema` | A SKILL falhou em cobrir uma situação que deveria cobrir |
| `decisão` | O procedimento não guiava a decisão tomada — foi feito por julgamento |
| `desvio` | O procedimento foi seguido mas com adaptação necessária |
| `melhoria-sugerida` | O procedimento funciona mas poderia ser mais claro/robusto |

---

## Ciclo de Melhoria

```
Execução da SKILL
      ↓
Registro de feedback
      ↓
Acúmulo de padrões (2-3 execuções com o mesmo problema)
      ↓
Revisão do procedimento da SKILL (adicionar/alterar passo)
      ↓
Nova execução com procedimento melhorado
      ↓
Novo feedback (confirma melhoria ou revela novo desvio)
```

Quando um mesmo problema aparece em 2+ projetos diferentes, é sinal de que o procedimento
da SKILL precisa ser atualizado. Use o histórico aqui para identificar esses padrões.

---

## Artefatos de Migração

### migration-plan-\<projeto\>.md

Gerado pelo `/migrate-analyze` após aprovação do utilizador. Contém:

- Domínios identificados e seus arquivos
- Config necessária (providers.py opcional, subpastas data/, variáveis .env)
- Dependências a adicionar
- Desvios de plataforma identificados no legado
- Checklist de execução das SKILLs do Cluster 2

Consumido pelas SKILLs `/migrate-infra`, `/migrate-domain`, `/migrate-api`.

### migration-map-\<projeto\>.md

Gerado pelo `/migrate-analyze` junto com o plano. Contém:

- Tabela de rastreabilidade: arquivo original → destino no template
- Status por item: ✅ migrado / ⚠️ local não-padrão / ❌ não migrado
- Base para o `/audit-project` criticar o resultado da migração

Ao contrário dos arquivos de feedback (append), `migration-map-<projeto>.md` pode ser
atualizado a cada ciclo de migração — representa o estado atual do mapeamento.

---

## Fluxo das SKILLs

```
CLUSTER 1 — ENTENDER
  /migrate-analyze <pasta-legado>   → plano + mapa salvos aqui

CLUSTER 2 — CONSTRUIR (sem argumento, consomem migration-plan-<projeto>.md)
  /migrate-infra                    → fundação pronta
  /migrate-domain                   → domínios criados
  /migrate-api                      → services + routers + tasks

CLUSTER 3 — VALIDAR
  /migrate-tests                    → unit + smoke + e2e
  /audit-project                    → checklist verde (audita contra padrão ideal)

CLUSTER 4 — ALINHAR (inter-projetos)
  /audit-pair <pasta-p1> <pasta-p2>  → divergências entre dois projetos do mesmo template
```