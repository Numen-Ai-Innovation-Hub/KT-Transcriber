"""
Insights Prompts - Templates de prompt para o InsightsAgent.

Contém os 8 templates especializados de prompt como constantes de módulo,
separados da lógica do InsightsAgent para facilitar manutenção e testes.

Os templates usam placeholders {query} e {contexts} preenchidos em runtime
pelo método _build_specialized_prompt() do InsightsAgent.
"""

# ════════════════════════════════════════════════════════════════════════════
# Templates de prompt
# ════════════════════════════════════════════════════════════════════════════

BASE_PROMPT_TEMPLATE = """
PERGUNTA ESPECÍFICA: "{query}"
CONTEXTOS RELEVANTES: {contexts}

INSTRUÇÃO: Responda DIRETAMENTE à pergunta usando apenas os contextos fornecidos.
Seja específico, factual e foque na pergunta exata.

🚨 IMPORTANTE - DISTINÇÃO CLIENTE vs VÍDEO:
- CLIENTE = Empresa responsável (DEXCO, VÍSSIMO, ARCO, PC_FACTORY)
- VÍDEO = Título da reunião (ex: "KT Sustentação", "KT IMS")
- Sempre identifique o CLIENTE (empresa), não confunda com título do vídeo

FORMATO DE RESPOSTA:
1. **Resposta Direta:** [Resposta específica à pergunta]
2. **Contexto Adicional:** [Informações relevantes que complementam a resposta]
3. **Insights Estratégicos:** [Percepções acionáveis baseadas nos dados]

RESPOSTA:
"""

DECISION_PROMPT_TEMPLATE = """
PERGUNTA SOBRE DECISÕES: "{query}"

CONTEXTOS DAS REUNIÕES:
{contexts}

INSTRUÇÕES ESPECÍFICAS PARA INSIGHTS DE DECISÕES:
1. Identifique claramente QUAIS decisões foram tomadas e por quê
2. Extraia insights sobre QUEM tomou as decisões e seu contexto
3. Analise QUANDO foram tomadas (timestamps) e as circunstâncias
4. Se houver valores ou prazos, extraia insights sobre seu impacto
5. Se houver status de implementação, analise as implicações

FORMATO DA RESPOSTA (INSIGHTS):
**Insight sobre Decisão(ões):** [análise profunda das decisões identificadas]
**Insight sobre Responsáveis:** [percepções sobre quem decidiu e contexto]
**Insights sobre Impacto:** [valores, prazos, condições e suas implicações]
**Insight sobre Status:** [análise do andamento se mencionado]

RESPOSTA (INSIGHTS):
"""

PROBLEM_PROMPT_TEMPLATE = """
PERGUNTA SOBRE PROBLEMAS: "{query}"

CONTEXTOS DAS REUNIÕES:
{contexts}

INSTRUÇÕES ESPECÍFICAS PARA INSIGHTS DE PROBLEMAS:
1. Identifique claramente QUAL é o problema e sua natureza
2. Extraia insights sobre a CAUSA raiz se foi discutida
3. Analise QUEM relatou o problema e o contexto organizacional
4. Se houver solução proposta, extraia insights sobre sua viabilidade
5. Se houver status de resolução, analise as implicações

FORMATO DA RESPOSTA (INSIGHTS):
**Insight sobre o Problema:** [análise profunda da natureza do problema]
**Insight sobre Causas:** [percepções sobre causas raiz se identificadas]
**Insight sobre Contexto:** [análise de quem reportou e circunstâncias]
**Insight sobre Soluções:** [análise das propostas de solução se discutidas]
**Insight sobre Resolução:** [percepções sobre status e próximos passos]

RESPOSTA (INSIGHTS):
"""

GENERAL_PROMPT_TEMPLATE = """
PERGUNTA: "{query}"

INFORMAÇÕES ENCONTRADAS:
{contexts}

INSTRUÇÕES:
Responda DIRETAMENTE à pergunta fornecida usando as informações dos contextos.

🚨 P1-3 FIX: IMPORTANTE - DISTINÇÃO CLIENTE vs VÍDEO:
- CLIENTE = Empresa responsável (DEXCO, VÍSSIMO, ARCO, PC_FACTORY)
- VÍDEO = Título da reunião (ex: "KT Sustentação", "KT IMS", "KICKOFF AMS")
- Sempre identifique o CLIENTE (empresa), não confunda com título do vídeo
- Exemplo correto: "Cliente DEXCO, vídeo 'KT Sustentação'"
- Exemplo incorreto: "Cliente KT Sustentação"

DIRETRIZES:
1. Primeira prioridade: Responder especificamente o que foi perguntado
2. Se a pergunta for "sobre X", foque nas informações específicas sobre X
3. Se a pergunta for "qual/quem/quando", forneça a resposta precisa
4. Use os contextos para fundamentar sua resposta
5. Seja claro e direto, mas completo
6. Sempre distinguir entre empresa (cliente) e título do vídeo/reunião

FORMATO:
**Resposta à Pergunta:** [Resposta direta e específica baseada nos contextos]

**Detalhes Relevantes:** [Informações adicionais importantes que complementam a resposta]

RESPOSTA:
"""

METADATA_LISTING_TEMPLATE = """
PERGUNTA: "{query}"
ENTIDADES ENCONTRADAS NA BASE DE CONHECIMENTO:
{contexts}

INSTRUÇÕES PARA LISTAGEM DE VÍDEOS:
1. Se a pergunta for sobre VÍDEOS, use o formato especial com links
2. Para VÍDEOS: Liste o nome do vídeo + link TL:DV se disponível
3. Para outras entidades: Use formato simples com bullets (•)
4. Extraia links TL:DV dos metadados se disponíveis
5. Seja DIRETO e OBJETIVO
6. Ordene por cliente primeiro, depois por tipo

FORMATO PARA VÍDEOS:
VÍDEOS DE KT REGISTRADOS NA BASE:
• **[CLIENTE] - [TIPO KT]**
  Link: [URL_TLDV se disponível]

FORMATO PARA OUTRAS ENTIDADES:
ENTIDADES REGISTRADAS:
• [NOME]: ([X] ocorrências)

RESPOSTA (LISTA FORMATADA):
"""

PARTICIPANTS_TEMPLATE = """
PERGUNTA: "{query}"
CONTEXTOS COM INFORMAÇÕES DE PARTICIPANTES:
{contexts}

INSTRUÇÕES PARA PARTICIPANTES:
1. Liste OBJETIVAMENTE os participantes encontrados nos contextos
2. Para cada participante, indique:
   - Nome (real se mencionado, ou identificador como "Participante X")
   - Papel/função se mencionado
   - Contexto onde foi identificado
3. Foque em NOMES e PAPÉIS, não em conteúdo técnico
4. Se houver menções a equipas, inclua também
5. Resposta máxima: 150 palavras, foco em IDENTIFICAR PESSOAS

FORMATO DE RESPOSTA:
PARTICIPANTES IDENTIFICADOS:
• [Nome/ID]: [Papel se conhecido]

PESSOAS MENCIONADAS:
• [Nome]: [Contexto onde foi mencionado]

RESPOSTA (PARTICIPANTES):
"""

PROJECT_LISTING_TEMPLATE = """
PERGUNTA: "{query}"
CONTEXTOS COM INFORMAÇÕES DE PROJETOS:
{contexts}

INSTRUÇÕES PARA LISTAGEM DE PROJETOS:
1. Identifique TODOS os projetos mencionados nos contextos
2. Para cada projeto encontrado:
   - Nome do projeto (exato como mencionado)
   - Cliente associado se identificado
   - Breve descrição baseada no contexto
   - Status/situação se mencionado
3. Foque em PROJETOS ESPECÍFICOS, não em conceitos gerais
4. Se mencionarem "projeto X", "implementação Y", etc., inclua
5. Ordene por relevância/frequência de menção
6. Resposta máxima: 200 palavras, seja OBJETIVO

FORMATO DE RESPOSTA:
PROJETOS IDENTIFICADOS NAS TRANSCRIÇÕES:
• **[Nome do Projeto]** ([Cliente]): [Breve descrição]
• **[Outro Projeto]**: [Descrição e status]

RESPOSTA (LISTA DE PROJETOS):
"""

HIGHLIGHTS_SUMMARY_TEMPLATE = """PERGUNTA: {query}

CONTEXTOS DAS REUNIÕES:
{contexts}

INSTRUÇÕES:
Extraia e organize os principais pontos da reunião de forma estruturada e objetiva.

ESTRATÉGIA:
1. Identifique decisões importantes tomadas
2. Liste ações definidas com responsáveis (se mencionado)
3. Destaque problemas identificados
4. Inclua informações técnicas relevantes
5. Organize por ordem de importância

FORMATO ESTRUTURADO:
**PRINCIPAIS PONTOS DA REUNIÃO:**

**🎯 DECISÕES TOMADAS:**
• [Decisão importante 1]
• [Decisão importante 2]

**📋 AÇÕES DEFINIDAS:**
• [Ação 1 - Responsável se mencionado]
• [Ação 2 - Responsável se mencionado]

**⚠️ PROBLEMAS IDENTIFICADOS:**
• [Problema 1 e contexto]
• [Problema 2 e contexto]

**🔧 ASPECTOS TÉCNICOS:**
• [Informação técnica relevante 1]
• [Informação técnica relevante 2]

DIRETRIZES:
- Se não houver informações para uma seção, omita-a
- Mantenha cada ponto claro e específico
- Priorize informações acionáveis

RESPOSTA:"""


# ════════════════════════════════════════════════════════════════════════════
# Dicionário unificado — consumido pelo InsightsAgent.__init__
# ════════════════════════════════════════════════════════════════════════════

PROMPT_TEMPLATES: dict[str, str] = {
    "base": BASE_PROMPT_TEMPLATE,
    "decision": DECISION_PROMPT_TEMPLATE,
    "problem": PROBLEM_PROMPT_TEMPLATE,
    "general": GENERAL_PROMPT_TEMPLATE,
    "metadata_listing": METADATA_LISTING_TEMPLATE,
    "participants": PARTICIPANTS_TEMPLATE,
    "project_listing": PROJECT_LISTING_TEMPLATE,
    "highlights_summary": HIGHLIGHTS_SUMMARY_TEMPLATE,
}
