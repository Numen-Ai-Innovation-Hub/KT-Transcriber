"""Testes unitários para insights_prompts — templates de prompt do InsightsAgent."""


# ════════════════════════════════════════════════════════════════════════════
# PROMPT_TEMPLATES — integridade do dicionário
# ════════════════════════════════════════════════════════════════════════════


class TestPromptTemplates:
    """Testa a integridade do dicionário PROMPT_TEMPLATES."""

    _CHAVES_ESPERADAS = {
        "base",
        "decision",
        "problem",
        "general",
        "metadata_listing",
        "participants",
        "project_listing",
        "highlights_summary",
    }

    def test_prompt_templates_tem_exatamente_oito_chaves(self) -> None:
        """PROMPT_TEMPLATES deve ter exatamente 8 entradas."""
        from src.kt_search.insights_prompts import PROMPT_TEMPLATES

        assert len(PROMPT_TEMPLATES) == 8

    def test_prompt_templates_contem_chaves_esperadas(self) -> None:
        """Chaves do dicionário são exatamente as 8 esperadas."""
        from src.kt_search.insights_prompts import PROMPT_TEMPLATES

        assert set(PROMPT_TEMPLATES.keys()) == self._CHAVES_ESPERADAS

    def test_todos_os_templates_sao_strings(self) -> None:
        """Todos os valores são strings (não None, int, etc.)."""
        from src.kt_search.insights_prompts import PROMPT_TEMPLATES

        for chave, template in PROMPT_TEMPLATES.items():
            assert isinstance(template, str), f"Template '{chave}' não é str"

    def test_todos_os_templates_nao_sao_vazios(self) -> None:
        """Nenhum template é string vazia ou só espaços em branco."""
        from src.kt_search.insights_prompts import PROMPT_TEMPLATES

        for chave, template in PROMPT_TEMPLATES.items():
            assert template.strip(), f"Template '{chave}' está vazio"

    def test_todos_os_templates_contem_placeholder_query(self) -> None:
        """Todos os templates contêm o placeholder {query}."""
        from src.kt_search.insights_prompts import PROMPT_TEMPLATES

        for chave, template in PROMPT_TEMPLATES.items():
            assert "{query}" in template, f"Template '{chave}' não contém {{query}}"

    def test_todos_os_templates_contem_placeholder_contexts(self) -> None:
        """Todos os templates contêm o placeholder {contexts}."""
        from src.kt_search.insights_prompts import PROMPT_TEMPLATES

        for chave, template in PROMPT_TEMPLATES.items():
            assert "{contexts}" in template, f"Template '{chave}' não contém {{contexts}}"


# ════════════════════════════════════════════════════════════════════════════
# Constantes individuais — aliases do dicionário
# ════════════════════════════════════════════════════════════════════════════


class TestConstantesIndividuais:
    """Verifica que cada constante individual é o mesmo objeto referenciado no dict."""

    def test_base_prompt_template_e_alias_correto(self) -> None:
        from src.kt_search.insights_prompts import BASE_PROMPT_TEMPLATE, PROMPT_TEMPLATES

        assert PROMPT_TEMPLATES["base"] is BASE_PROMPT_TEMPLATE

    def test_decision_prompt_template_e_alias_correto(self) -> None:
        from src.kt_search.insights_prompts import DECISION_PROMPT_TEMPLATE, PROMPT_TEMPLATES

        assert PROMPT_TEMPLATES["decision"] is DECISION_PROMPT_TEMPLATE

    def test_problem_prompt_template_e_alias_correto(self) -> None:
        from src.kt_search.insights_prompts import PROBLEM_PROMPT_TEMPLATE, PROMPT_TEMPLATES

        assert PROMPT_TEMPLATES["problem"] is PROBLEM_PROMPT_TEMPLATE

    def test_general_prompt_template_e_alias_correto(self) -> None:
        from src.kt_search.insights_prompts import GENERAL_PROMPT_TEMPLATE, PROMPT_TEMPLATES

        assert PROMPT_TEMPLATES["general"] is GENERAL_PROMPT_TEMPLATE

    def test_metadata_listing_template_e_alias_correto(self) -> None:
        from src.kt_search.insights_prompts import METADATA_LISTING_TEMPLATE, PROMPT_TEMPLATES

        assert PROMPT_TEMPLATES["metadata_listing"] is METADATA_LISTING_TEMPLATE

    def test_participants_template_e_alias_correto(self) -> None:
        from src.kt_search.insights_prompts import PARTICIPANTS_TEMPLATE, PROMPT_TEMPLATES

        assert PROMPT_TEMPLATES["participants"] is PARTICIPANTS_TEMPLATE

    def test_project_listing_template_e_alias_correto(self) -> None:
        from src.kt_search.insights_prompts import PROJECT_LISTING_TEMPLATE, PROMPT_TEMPLATES

        assert PROMPT_TEMPLATES["project_listing"] is PROJECT_LISTING_TEMPLATE

    def test_highlights_summary_template_e_alias_correto(self) -> None:
        from src.kt_search.insights_prompts import HIGHLIGHTS_SUMMARY_TEMPLATE, PROMPT_TEMPLATES

        assert PROMPT_TEMPLATES["highlights_summary"] is HIGHLIGHTS_SUMMARY_TEMPLATE


# ════════════════════════════════════════════════════════════════════════════
# Conteúdo específico por template
# ════════════════════════════════════════════════════════════════════════════


class TestConteudoTemplates:
    """Verifica que cada template contém termos específicos ao seu domínio."""

    def test_base_prompt_contem_instrucao_de_resposta(self) -> None:
        """BASE_PROMPT_TEMPLATE instrui o modelo a responder diretamente."""
        from src.kt_search.insights_prompts import BASE_PROMPT_TEMPLATE

        texto = BASE_PROMPT_TEMPLATE.lower()
        assert "instrução" in texto or "responda" in texto

    def test_decision_prompt_contem_palavra_decisao(self) -> None:
        """DECISION_PROMPT_TEMPLATE foca em decisões."""
        from src.kt_search.insights_prompts import DECISION_PROMPT_TEMPLATE

        assert "decis" in DECISION_PROMPT_TEMPLATE.lower()

    def test_problem_prompt_contem_palavra_problema(self) -> None:
        """PROBLEM_PROMPT_TEMPLATE foca em problemas."""
        from src.kt_search.insights_prompts import PROBLEM_PROMPT_TEMPLATE

        assert "problema" in PROBLEM_PROMPT_TEMPLATE.lower()

    def test_participants_template_contem_participante(self) -> None:
        """PARTICIPANTS_TEMPLATE foca em participantes."""
        from src.kt_search.insights_prompts import PARTICIPANTS_TEMPLATE

        assert "participante" in PARTICIPANTS_TEMPLATE.lower()

    def test_project_listing_template_contem_projeto(self) -> None:
        """PROJECT_LISTING_TEMPLATE foca em projetos."""
        from src.kt_search.insights_prompts import PROJECT_LISTING_TEMPLATE

        assert "projeto" in PROJECT_LISTING_TEMPLATE.lower()

    def test_highlights_summary_template_contem_reuniao(self) -> None:
        """HIGHLIGHTS_SUMMARY_TEMPLATE resume pontos de reunião."""
        from src.kt_search.insights_prompts import HIGHLIGHTS_SUMMARY_TEMPLATE

        assert "reunião" in HIGHLIGHTS_SUMMARY_TEMPLATE.lower() or "meeting" in HIGHLIGHTS_SUMMARY_TEMPLATE.lower()

    def test_metadata_listing_template_contem_listagem(self) -> None:
        """METADATA_LISTING_TEMPLATE trata de listagens."""
        from src.kt_search.insights_prompts import METADATA_LISTING_TEMPLATE

        texto = METADATA_LISTING_TEMPLATE.lower()
        assert "lista" in texto or "vídeo" in texto or "entidade" in texto
