# tests/ - Testes Automatizados

Testes com pytest em três dimensões: unit (rápidos, isolados), smoke (stack sobe) e e2e (fluxo completo). Estrutura flat com `fixtures/` para dados de teste.

## Estrutura

- `tests/test_*.py` — Unit tests por módulo (sem marca — rápidos, zero I/O externo)
- `tests/test_smoke.py` — Smoke tests (`@pytest.mark.smoke`) — stack sobe e responde
- `tests/test_e2e.py` — E2E tests (`@pytest.mark.e2e`) — fluxo completo com stack real
- `tests/fixtures/` — Dados de teste (JSONs, arquivos de exemplo)
- `tests/conftest.py` — Fixtures compartilhadas

## Marcadores

- `@pytest.mark.smoke` — Stack sobe: FastAPI importa, Redis conecta, /health responde 200
- `@pytest.mark.e2e` — Fluxo completo com FastAPI + Redis + ARQ rodando
- `@pytest.mark.slow` — Testes que requerem I/O externo (Redis, banco, APIs) — para uso pontual em desenvolvimento
- Executar unit tests: `uv run python -m pytest tests/ -m "not smoke and not e2e"`
- Executar smoke: `uv run python -m pytest tests/ -m smoke`
- Executar e2e: `uv run python -m pytest tests/ -m e2e`
- Executar slow: `uv run python -m pytest tests/ -m slow`
- **NEVER** usar `--ignore` para excluir smoke/e2e — usar `-m "not smoke and not e2e"`

## Pré-requisitos para smoke/e2e

Para rodar testes `smoke` ou `e2e`, os serviços abaixo devem estar ativos:

| Serviço | Como iniciar | Obrigatório para |
|---------|-------------|-----------------|
| Redis Cloud | Configurar `.env` com `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` | smoke + e2e |
| ARQ Worker | `arq src.tasks.arq_worker.WorkerSettings` | e2e |
| FastAPI | `uvicorn src.api.main:app --reload` | e2e |

Se Redis não estiver acessível (credenciais ausentes ou serviço indisponível), os testes fazem `pytest.skip` automaticamente (via fixture `require_redis` em `conftest.py`). Não falham com erro de conexão.

Todo teste smoke ou e2e deve declarar `require_redis` como parâmetro de fixture. Nunca conectar ao Redis diretamente no corpo do teste sem esta fixture.

## Regras

- Ler a implementação ANTES de escrever asserts (idioma dos valores, defaults reais)
- Um arquivo de teste por módulo (`test_recurso_service.py` para `recurso_service.py`)
- Nomear testes descritivamente: `test_criar_recurso_nome_vazio` (não `test_1`)
- Helpers inline no arquivo de teste — NEVER importar de `conftest`
- Usar `pytest.raises(ApplicationError)` para testar exceções e validar `error_code`
- Usar `unittest.mock` para isolar dependências externas nos unit tests
- Isolamento obrigatório: testes NEVER dependem de estado global entre si
- NEVER hardcode credenciais ou URLs de produção em testes
- `isolated_test_dirs` em `conftest.py` DEVE espelhar EXATAMENTE as chaves de `DIRECTORY_PATHS` em `src/config/settings.py`. Ao adicionar ou renomear uma chave em `DIRECTORY_PATHS`, atualizar `conftest.py` imediatamente. Chaves inventadas fazem o monkeypatch sobrescrever com dict diferente, silenciando o erro e quebrando testes de integração.
- Se o projeto usa `utils/hash_manager.py`: `DIRECTORY_PATHS` deve ter chave `"sqlite_db"` (nunca `"hashes"` — padrão JSON legado) e `FILE_PATHS` deve ter `"hashes_db"` apontando para `data/sqlite_db/hashes.db`.