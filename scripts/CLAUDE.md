# scripts/ - Scripts Utilitários do Projeto

Scripts Python de demanda pontual que **dependem do projeto** (importam de `src/`, usam `.env`). Diferente de `utils/` que é portável.

## Quando Criar Aqui

- Tarefas de manutenção (migração de dados, reindexação, limpeza de cache)
- Processamento batch que não precisa ser endpoint REST
- Scripts de inicialização ou seed de dados

## Quando NÃO Criar Aqui

- Código reutilizável sem dependência do projeto → `utils/`
- Lógica de negócio recorrente → endpoint em `src/api/` + service em `src/services/`
- Automação de setup/ambiente → `.vscode/scripts/` (PowerShell)
- Smoke tests e testes E2E → `tests/test_smoke.py` e `tests/test_e2e.py`

## Padrão de Script

Todo script MUST ter: docstring com `Uso:` e `Exemplo:`, `sys.path.insert(0, ...)`, `initialize_application()`, proteção `if __name__ == "__main__":`, log de início e conclusão.

## Regras

- ALWAYS adicione docstring com `Uso:` e `Exemplo:` no topo
- ALWAYS use `initialize_application()` para garantir logging e diretórios
- ALWAYS proteja execução com `if __name__ == "__main__":`
- NEVER coloque lógica de negócio recorrente aqui — criar service
- NEVER commite scripts com credenciais hardcoded