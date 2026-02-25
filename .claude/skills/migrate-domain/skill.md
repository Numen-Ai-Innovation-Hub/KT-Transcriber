# SKILL: /migrate-domain

**Propósito:** Extrair lógica de negócio do legado para as pastas de domínio em `src/`.
É a fase mais longa e mais importante — aqui fica o core do produto.

**Argumento:** sem argumento — opera no projeto atual, executa todos os domínios do plano

**Pré-requisito:** `/migrate-infra` concluído.

---

## Procedimento (por domínio, sequencialmente)

Para cada domínio identificado no `migration-plan-<projeto>.md`:

### FASE 1 — Ler Implementação Original

Ler o(s) arquivo(s) do legado correspondentes ao domínio.

**Registrar antes de qualquer modificação:**
- Idioma dos valores de retorno (português ou inglês? ex: `"tabela"` ou `"table"`)
- Defaults de parâmetros
- Comportamento em edge cases (None, lista vazia, etc.)
- Contratos das funções públicas

**Atenção:** Ler ANTES de escrever. Asserts incorretos vêm de não ler a implementação real.

**Identificar código morto antes de migrar:**

Para cada arquivo do domínio, verificar se é feature ativa, incompleta ou abandonada:
- Arquivo sem nenhum import em outros módulos do projeto → candidato a código morto
- Arquivo com cobertura de testes < 20% sem testes dedicados → candidato a feature não terminada
- Arquivo referenciado apenas por variável de ambiente com valor placeholder → candidato a feature inativa

**Para cada candidato, confirmar com o utilizador:**
- Feature ativa sem testes → criar testes antes de migrar
- Feature incompleta → documentar com comentário `# TODO: feature incompleta — <descrição>` e migrar
- Feature abandonada → **não migrar** — remover do legado sem criar equivalente no projeto

Nunca migrar código morto — herdar código abandonado polui o projeto e gera falsos negativos na cobertura.

### FASE 2 — Criar Estrutura do Domínio

```
src/<domínio>/
├── __init__.py               # Exporta interface pública do domínio
├── <domínio>_constants.py    # Constantes específicas deste domínio
├── engine.py                 # Lógica principal (nome varia: processor, client, store, parser)
└── schemas.py                # Schemas Pydantic (apenas se domínio tiver estruturas próprias)
```

Nomes de módulos por papel (padrão `<função>_<tipo>.py`, 2 palavras):
- `extraction_service.py` — extração de dados de fontes externas (PDF, API)
- `chunking_engine.py` — divisão/transformação de conteúdo
- `embedding_engine.py` — geração e gestão de embeddings
- `<domínio>_constants.py` — constantes específicas do domínio (NUNCA `constants.py` sem prefixo, NUNCA em `settings.py`)
- `store.py` / `<domínio>_store.py` — persistência (ChromaDB, SQLite, arquivo)
- `client.py` / `<domínio>_client.py` — integração com serviço externo (API, SDK)

### FASE 3 — Extrair e Refatorar

Mover a lógica do legado para os módulos do domínio aplicando as regras:

**Type hints (Python 3.10+):**
```python
# ✅ correto
def process(data: str | None, items: list[str]) -> dict[str, Any]: ...

# ❌ evitar
def process(data: Optional[str], items: List[str]) -> Dict[str, Any]: ...
```

**Docstrings (Google-style em português):**
```python
def processar_documento(caminho: str) -> dict[str, Any]:
    """Processa documento e retorna metadados extraídos.

    Args:
        caminho: Caminho absoluto para o arquivo a processar.

    Returns:
        Dicionário com metadados: título, autor, data, conteúdo.

    Raises:
        ApplicationError: Se arquivo não encontrado ou formato inválido.
    """
```

**Erros (ApplicationError, nunca return de erro):**
```python
# ✅ correto
from utils.exception_setup import ApplicationError

raise ApplicationError(
    message="Arquivo não encontrado",
    status_code=404,
    error_code="NOT_FOUND",
    context={"caminho": caminho},
)

# ❌ proibido
return {"error": "Arquivo não encontrado"}
return None  # para indicar erro
```

**Exceção ao Fail-Fast — `return None` como sentinel em iteração:**

`return None` é aceitável SOMENTE quando o chamador itera sobre uma coleção e o comportamento
correto é pular o item com falha (não interromper toda a iteração). Três condições obrigatórias:
1. O docstring documenta explicitamente: `Returns: ... ou None se <condição> falhar`
2. O chamador trata `None` e continua — nunca silencia
3. A exceção é logada antes do `return None` — nunca silenciada

```python
# ✅ aceitável — sentinel documentado, log presente, chamador trata
def gerar_pergunta(chunk: str) -> str | None:
    """Gera pergunta para o chunk.

    Returns:
        Pergunta gerada, ou None se a geração falhar (chunk inválido ou erro LLM).
        O chamador deve filtrar None e continuar para o próximo chunk.
    """
    try:
        return llm.generate(chunk)
    except Exception as e:
        logger.warning(f"Falha ao gerar pergunta: {e}")
        return None  # sentinel — chamador filtra e continua

# ❌ proibido — return None para indicar falha de operação principal
def processar_documento(caminho: str) -> dict[str, Any] | None:
    if not Path(caminho).exists():
        return None  # ERRADO — deve ser ApplicationError
```

**Paths (DIRECTORY_PATHS / FILE_PATHS, nunca hardcoded):**
```python
# ✅ correto — banco SQLite de domínio
from src.config.settings import DIRECTORY_PATHS
caminho = DIRECTORY_PATHS["sqlite_db"] / "meu_banco.db"

# ✅ correto — hashes (via FILE_PATHS)
from src.config.settings import FILE_PATHS
caminho = FILE_PATHS["hashes_db"]

# ❌ proibido
caminho = Path("data/sqlite_db/meu_banco.db")
```

**Logging:**
```python
# ✅ correto
from utils.logger_setup import LoggerManager
logger = LoggerManager.get_logger(__name__)
logger.info("Processamento iniciado")

# ❌ proibido
import logging
logging.basicConfig(...)
print("Processamento iniciado")
```

**Imports:**
```python
# ✅ correto — imports dentro do domínio são relativos
from .processor import ExampleProcessor
from .constants import MAX_ITEMS

# ❌ proibido — domínio NUNCA importa de api/ ou services/
from src.api.routers import example_router
from src.services.example_service import ExampleService
```

**Remover:**
- `if __name__ == "__main__":` — módulos de domínio não são executáveis diretamente
- `logging.basicConfig()` — substituir por `get_logger(__name__)`
- `print()` — substituir por `logger.info/debug/warning`

### FASE 4 — Identificar Helpers, Utils e Utilitários Padrão

Após extrair todos os domínios, revisar funções auxiliares em três etapas:

**Etapa 4a — Verificar utilitários padrão do time primeiro:**

Antes de criar qualquer helper ou util novo, verificar se a lógica já está coberta:

| Se o código legado faz... | Usar o utilitário padrão |
|--------------------------|--------------------------|
| Logging, `logging.basicConfig()`, `print()` para debug | `utils/logger_setup.py` — `LoggerManager.get_logger(__name__)` |
| Exception customizada, `return {"error": ...}` | `utils/exception_setup.py` — `ApplicationError` |
| `hashlib.md5()`, `hashlib.sha256()`, `sqlite3` inline para cache de conteúdo | `utils/hash_manager.py` — persiste em `data/sqlite_db/hashes.db` |
| `pdfplumber` direto, `PyPDF2`, `pypdf` no legado para extração de PDF | `utils/pdfplumber_extractor.py` (OCR simples) ou `utils/dpt2_extractor.py` (OCR avançado via Landing.AI) |
| `win32com.client` para Word, geração de `.docx` | `utils/wordcom_toolkit.py` |
| Cliente LLM próprio (`openai.OpenAI()`, wrapper Gemini/Anthropic), wrappers de completion | `utils/llm_manager.py` |

Se o legado tem lógica **similar mas diferente** (ex: hashing com algoritmo diferente, extração PDF
com lógica adicional):
1. **Usar o utilitário oficial agora** — adaptar os callers para usar o utilitário com os parâmetros disponíveis
2. **Remover** a versão do projeto — nunca manter implementação paralela ao utilitário oficial
3. **Registrar no feedback** desta SKILL com sugestão de expandir o utilitário oficial para cobrir o caso adicional

**Nunca** manter uma variante paralela enquanto aguarda a expansão do utilitário.
A funcionalidade temporariamente não coberta é preferível a ter duas implementações do mesmo problema.

**Etapa 4a.1 — Caso especial: embeddings e busca semântica**

Se o legado tem qualquer um destes padrões → **NÃO mover para `src/`** — substituir por ChromaDB:

| Padrão no legado | Problema | Solução obrigatória |
|-----------------|----------|---------------------|
| `EmbeddingManager` standalone, `SentenceTransformer` direto | Busca O(n), sem índice, sem filtros | ChromaDB gerencia embeddings internamente |
| `ChunkingService` standalone, chunks salvos em arquivos | Acoplamento entre chunking e storage | Chunking é pré-processamento feito antes de `collection.add()` |
| Embeddings salvos em PKL/pickle | Não transacional, corrupção perde tudo | `chromadb.PersistentClient` persiste em SQLite |
| Busca coseno em memória (`numpy`) | Carrega tudo em RAM a cada query | `collection.query()` do ChromaDB é eficiente |

**Como implementar:**

> **Atenção ChromaDB:** Use sempre `include=["documents", "metadatas", "distances"]` (strings).
> `IncludeEnum` foi removido na versão 1.x — código com `IncludeEnum` só funciona em 0.5.x.

```python
# src/<domínio>/store.py
import chromadb
from chromadb.utils import embedding_functions
from src.config.settings import DIRECTORY_PATHS

class DocumentStore:
    """Persistência e busca semântica via ChromaDB.

    Ponto único de interação com o banco vetorial do domínio.
    """

    def __init__(self) -> None:
        client = chromadb.PersistentClient(
            path=str(DIRECTORY_PATHS["vector_db"])
        )
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self._collection = client.get_or_create_collection(
            name="<domínio>_documents",
            embedding_function=ef,
        )

    def add(self, chunks: list[str], metadatas: list[dict], ids: list[str]) -> None:
        """Ingere chunks com metadados na coleção."""
        self._collection.add(documents=chunks, metadatas=metadatas, ids=ids)

    def query(self, text: str, n_results: int = 5) -> list[dict]:
        """Busca semântica — retorna n_results chunks mais relevantes."""
        results = self._collection.query(query_texts=[text], n_results=n_results)
        return results["documents"][0]
```

**Regras:**
- `chromadb.PersistentClient` — nunca `chromadb.HttpClient`
- Path sempre via `DIRECTORY_PATHS["vector_db"]` — nunca hardcoded
- `EmbeddingManager`, `ChunkingService` standalone → remover completamente após criar `store.py`
- Chunking (divisão de texto em chunks) vai dentro do método de ingestão do `store.py`, não como classe separada

**Etapa 4b — Classificar o que sobrar:**

**→ `src/helpers/`** se:
- Usada por 2 ou mais domínios diferentes
- Depende de configuração do projeto (`settings.py`, `DIRECTORY_PATHS`)
- Ex: formatação de output específica do projeto, validações de negócio transversais

**→ `utils/`** (novo utilitário) se:
- Zero imports de `src/` — copiável para qualquer projeto
- Apenas stdlib + libs genéricas
- Resolve problema genérico não coberto pelos utilitários padrão
- Ex: formatação de strings genérica, parse de datas, manipulação de arquivos

**Dúvida entre domínio e helper:** Manter no domínio. `helpers/` frequentemente fica vazio.
**Dúvida entre helper e utils:** Preferir `utils/` (mais restritivo garante portabilidade).
**Lógica já coberta por util padrão:** Substituir — não criar helper nem util paralelo.

### FASE 5 — Limpeza e Validação

Por domínio, após extração completa:

1. **Avaliar e deletar** arquivos do legado — regras por caso:
   - Arquivo original do legado já migrado → deletar
   - Arquivo de domínio que foi **totalmente** delegado a utils (só faz pass-through) → deletar
   - Arquivo de domínio que foi **parcialmente** delegado a utils mas adiciona lógica legítima
     (cache via `hash_manager`, validação específica do projeto, enriquecimento de metadados)
     → manter, mas remover os métodos que são duplicação direta do utilitário
   - `EmbeddingManager`, `ChunkingService`, PKL de embeddings substituídos por `store.py` → deletar
   - Arquivos de legado identificados como código morto na Fase 1 → já não foram migrados — confirmar ausência
2. **Atualizar imports** em todos os arquivos que referenciavam o original
3. **Rodar linter:**
   ```
   .venv/Scripts/ruff.exe check src
   .venv/Scripts/ruff.exe format src
   ```
4. **Rodar type check:**
   ```
   .venv/Scripts/mypy.exe --config-file=pyproject.toml src
   ```
5. Corrigir erros antes de passar para o próximo domínio

**Critério de conclusão por domínio:** `ruff check src` + `mypy src` passam.

---

## FASE FINAL — Registro de Feedback

Ao concluir, registrar entrada em `.claude/skills-feedback/migrate-domain.md`:

```markdown
## [YYYY-MM-DD] Projeto: <nome>

**Domínios criados:** <lista>
**Helpers extraídos:** <N>
**Utils extraídos:** <N>

**O que funcionou bem:**
- <ponto positivo>

**O que foi difícil:**
- <ponto de atrito (ex: imports circulares, constantes mal classificadas)>

**Sugestão de melhoria para esta SKILL:**
- <proposta>
```