# utils/ - Utilitários Portáveis

Módulos **sem nenhuma dependência do projeto**. Podem ser copiados para qualquer projeto Python sem modificação.
Estes utilitários são parte da **stack padrão do time** — futuramente serão distribuídos como pacote instalável via uv.

## Critério de Classificação como Utilitário

Um módulo é utilitário quando atende **todos** os critérios:

1. **Zero deps de projeto** — não importa nada de `src/`, não usa `.env` nem `settings.py`
2. **Propósito claro e genérico** — resolve um problema técnico recorrente (logging, exceções, hashes, I/O de documentos)
3. **Reuso comprovado** — a mesma lógica aparece (ou poderia aparecer) em 2+ projetos diferentes
4. **Copiável sem modificação** — funciona em qualquer projeto Python com as mesmas deps externas

Se violar qualquer critério → mover para `src/helpers/` (helper de projeto) ou `src/<domínio>/` (lógica de negócio).

## Utilitários do Time

Todos os projetos derivados do template devem usar estes utilitários para as funcionalidades que cobrem.
Não reinventar estas rodas — se o projeto precisa de logging, usa `logger_setup.py`; se precisa de hash, usa `hash_manager.py`.

### Infraestrutura (obrigatórios em todo projeto)

| Arquivo | Descrição | Deps Externas |
|---------|-----------|---------------|
| `exception_setup.py` | `ApplicationError` com `message`, `status_code`, `error_code`, `context` | Nenhuma |
| `logger_setup.py` | `LoggerManager` configurável (arquivo + console, rotação diária) | Nenhuma |

### Utilitários Especializados (incluir se o projeto usa a funcionalidade)

| Arquivo | Descrição | Deps Externas | Quando incluir |
|---------|-----------|---------------|----------------|
| `hash_manager.py` | Gestão de hashes MD5/SHA256, controle de cache por conteúdo | Nenhuma | Qualquer projeto com cache baseado em conteúdo |
| `pdfplumber_extractor.py` | Extração de texto e tabelas de PDFs | `pdfplumber` | Projetos que processam documentos PDF |
| `dpt2_extractor.py` | Extração de PDFs via API Landing.AI DPT-2 (OCR avançado) | `requests` | Projetos que precisam de extração OCR de alta qualidade |
| `wordcom_toolkit.py` | Manipulação de arquivos .docx via COM (Windows) | `pywin32` | Projetos que processam documentos Word |

### Utilitários de Integração (incluir apenas se o projeto usa LLMs)

| Arquivo | Descrição | Deps Externas |
|---------|-----------|---------------|
| `llm_manager.py` | Multi-provider LLM (OpenAI, Gemini, Anthropic, Ollama) | `langchain_core`, `langchain_openai`, `langchain_google_genai` |

**Padrão de uso do `llm_manager.py`:** é um utilitário standalone, mas nunca deve ser importado diretamente de `src/`. Todo projeto com LLM cria `src/services/llm_service.py` como re-export centralizado — e `src/` importa exclusivamente dali. Isso garante um único ponto de troca se o utilitário mudar.

## Error Codes Padrão (exception_setup.py)

`VALIDATION_ERROR` (422), `NOT_FOUND` (404), `SERVICE_UNAVAILABLE` (503), `QUOTA_EXCEEDED` (429), `INTERNAL_ERROR` (500)

## Regras de Standalone

Todos os utilitários são **100% standalone** — devem atender **todos** os critérios:

- **Zero imports de `src/`** ou dependências do projeto — copiável sem modificação
- **Parâmetros injetados via `__init__`** — nunca lê `.env` nem `settings.py` diretamente
- **Apenas exceções stdlib** — `ValueError`, `FileNotFoundError`, `ConnectionError`, `OSError`
  - NEVER `ApplicationError` nem qualquer exceção customizada de projeto
  - A camada de domínio (`src/<domínio>/`) faz o wrap e traduz para `ApplicationError`
- **HTTP retry com backoff** encapsulado dentro do utilitário que o usa (não criar `utils/http_client.py` genérico se o retry é específico de um provider)
- Funções puras quando possível
- Type hints completos, docstrings em português (Google-style)
- Testes em `tests/test_utils_*.py`
- NEVER adicionar lógica de domínio aqui
- NEVER duplicar lógica já coberta por um utilitário do time — usar o utilitário existente

## hash_manager.py — Padrão de Uso

- **Usar sempre `get_hash_manager()`** — NEVER implementar cache de hashes inline com `hashlib` + `sqlite3` diretamente nos services
- Storage: **SQLite em `data/sqlite_db/hashes.db`** — banco único, não um arquivo por documento
- Path configurado via `FILE_PATHS["hashes_db"]` em `settings.py`: `DATA_DIR / "sqlite_db" / "hashes.db"`
- A pasta `data/sqlite_db/` é criada pelo `startup.py` via `DIRECTORY_PATHS["sqlite_db"]`
- Interface pública: `generate_file_hash()`, `should_reprocess()`, `update_cache_hash()`, `load_hash_metadata()`
- NEVER usar `DIRECTORY_PATHS["hashes"]` (entrada JSON legada) — o padrão atual é `sqlite_db`