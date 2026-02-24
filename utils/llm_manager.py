"""
LLM Manager - Gerenciador Unificado de Clientes LLM via LangChain.

100% STANDALONE - Reutilizável em qualquer projeto Python!
Configurado via variáveis de ambiente (.env) seguindo 12 Factor App principles.
Zero dependências internas - usa apenas stdlib (logging) + LangChain.

QUANDO USAR:
  ✅ Agentes com structured output (Pydantic schemas)
  ✅ Workflows complexos que precisam de cleanup de recursos
  ✅ Casos que precisam de retry/fallback automático do LangChain
  ✅ RAG queries ou workflows multi-step

RESPONSABILIDADES:
  - Criação e reuso de instâncias LLM (singleton pattern para evitar resource leaks)
  - Cleanup de recursos HTTP (previne AsyncClient leaks)
  - Monitoramento automático de chamadas via LLMUsageTrackingCallback (tokens reais)

CONFIGURAÇÃO (via environment variables):
  OBRIGATÓRIAS:
  - AI_PROVIDER: "openai" | "gemini" | "gpt-oss" (define qual biblioteca LangChain usar)
    NOTA: Este valor é normalizado por initialization.py antes de chegar aqui
  - AI_MODEL: Nome do modelo (ex: "gpt-4o-mini", "gemini-2.0-flash-exp")
  - AI_API_KEY: Chave de API do provider escolhido
  - AI_API_ENDPOINT: URL base da API (ex: "https://api.openai.com/v1")

  OPCIONAIS:
  - AI_MAX_RETRIES: Número de tentativas em caso de falha (default: 3)
  - AI_TEMPERATURE: Criatividade do modelo, 0.0-1.0 (default: 0.0 = determinístico)
  - AI_MAX_TOKENS: Limite de tokens na resposta (default: 4096)
  - AI_TIMEOUT: Timeout em segundos para chamadas (default: 120)

TRACKING (opcional):
  - Passe `tracked_modules` ao criar LLMMonitor() para rastrear módulos específicos
  - Exemplo: LLMMonitor(tracked_modules=["RAG_PROCESSOR", "RAP_AGENT"])

NOTA: O monitoramento é AUTOMÁTICO via callback LangChain. Estatísticas disponíveis
via llm_monitor.get_summary_text() e llm_monitor.reset().
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from langchain_core.callbacks.base import BaseCallbackHandler

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# SEÇÃO 1: CALL MONITORING (estatísticas de uso)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class LLMCallStats:
    """Estatísticas de uma chamada ao LLM"""

    call_id: int
    module: str
    model: str
    real_tokens: int | None  # Tokens reais retornados pela API (usage_metadata)
    start_time: float
    end_time: float
    duration: float
    success: bool
    error: str | None = None


@dataclass
class LLMMonitorStats:
    """Estatísticas consolidadas do monitor"""

    total_calls: int = 0
    calls_by_module: dict[str, int] = field(default_factory=dict)
    calls_by_model: dict[str, int] = field(default_factory=dict)
    total_duration: float = 0.0
    total_real_tokens: int = 0  # Soma de tokens reais retornados pelas APIs
    successful_calls: int = 0
    failed_calls: int = 0
    # Estatísticas detalhadas por módulo
    tokens_by_module: dict[str, int] = field(default_factory=dict)
    duration_by_module: dict[str, float] = field(default_factory=dict)


class LLMMonitor:
    """
    Monitor centralizado de chamadas ao LLM.

    Rastreia todas as chamadas e mede performance real (tokens, duração, sucesso/falha).
    """

    def __init__(
        self, enable_tracking: bool = True, max_history: int = 1000, tracked_modules: list[str] | None = None
    ) -> None:
        """
        Inicializa o monitor de chamadas LLM.

        Args:
            enable_tracking: Se True, rastreia chamadas (pode ser desabilitado para performance)
            max_history: Número máximo de chamadas mantidas em histórico (evita memory leak)
            tracked_modules: Lista de módulos a rastrear (ex: ["RAG_PROCESSOR", "RAP_AGENT"]).
                           Se None, todos os módulos chamados serão exibidos no sumário.
        """
        self.enable_tracking = enable_tracking
        self.max_history = max_history
        self.tracked_modules = tracked_modules or []
        self.call_count = 0
        self.call_history: list[LLMCallStats] = []
        self.stats = LLMMonitorStats()

    def _start_call(self, module: str, model: str) -> int:
        """
        Inicia monitoramento de uma chamada ao LLM (método privado).

        Args:
            module: Nome do módulo que está fazendo a chamada (ex: "RAG_PROCESSOR")
            model: Nome do modelo LLM (ex: "gpt-4", "gemini-2.0-flash")

        Returns:
            ID único da chamada (use em _end_call para finalizar)
        """
        # Se tracking desabilitado, retorna ID dummy
        if not self.enable_tracking:
            return -1

        self.call_count += 1
        start_time = time.time()

        call_stats = LLMCallStats(
            call_id=self.call_count,
            module=module,
            model=model,
            real_tokens=None,
            start_time=start_time,
            end_time=0.0,
            duration=0.0,
            success=False,
        )

        self.call_history.append(call_stats)

        # Limita tamanho do histórico para evitar memory leak
        if len(self.call_history) > self.max_history:
            self.call_history.pop(0)  # Remove chamada mais antiga

        return self.call_count

    def _end_call(
        self, call_id: int, success: bool = True, error: str | None = None, real_tokens: int | None = None
    ) -> None:
        """
        Finaliza monitoramento de uma chamada ao LLM (método privado).

        Args:
            call_id: ID retornado por _start_call()
            success: Se a chamada foi bem-sucedida
            error: Mensagem de erro (se success=False)
            real_tokens: Tokens reais retornados pela API (usage_metadata.total_tokens)
        """
        # Se tracking desabilitado, ignora
        if not self.enable_tracking or call_id == -1:
            return

        end_time = time.time()

        # Encontrar a chamada correspondente no histórico
        for call_stats in self.call_history:
            if call_stats.call_id == call_id:
                # Atualiza dados da chamada
                call_stats.end_time = end_time
                call_stats.duration = end_time - call_stats.start_time
                call_stats.success = success
                call_stats.error = error
                call_stats.real_tokens = real_tokens

                # Atualizar estatísticas consolidadas
                self._update_stats(call_stats)
                break

    def _update_stats(self, call_stats: LLMCallStats) -> None:
        """
        Atualiza estatísticas consolidadas após finalizar uma chamada.

        Args:
            call_stats: Dados da chamada finalizada
        """
        # Incrementa contadores gerais
        self.stats.total_calls += 1
        self.stats.total_duration += call_stats.duration

        # Atualiza tokens reais se disponível
        if call_stats.real_tokens is not None:
            self.stats.total_real_tokens += call_stats.real_tokens

        # Contadores por módulo (quem chamou)
        self.stats.calls_by_module[call_stats.module] = self.stats.calls_by_module.get(call_stats.module, 0) + 1

        # Tokens e tempo por módulo
        self.stats.tokens_by_module[call_stats.module] = self.stats.tokens_by_module.get(call_stats.module, 0) + (
            call_stats.real_tokens or 0
        )
        self.stats.duration_by_module[call_stats.module] = (
            self.stats.duration_by_module.get(call_stats.module, 0.0) + call_stats.duration
        )

        # Contadores por modelo (qual LLM usado)
        self.stats.calls_by_model[call_stats.model] = self.stats.calls_by_model.get(call_stats.model, 0) + 1

        # Contadores de sucesso/falha
        if call_stats.success:
            self.stats.successful_calls += 1
        else:
            self.stats.failed_calls += 1

    def get_stats(self) -> LLMMonitorStats:
        """
        Retorna objeto com estatísticas consolidadas.

        Returns:
            LLMMonitorStats com totais e contadores
        """
        return self.stats

    def get_summary_text(self) -> str:
        """
        Retorna resumo formatado das estatísticas para logging/display.

        Returns:
            String formatada com resumo completo das estatísticas
        """
        lines = []

        # Visão Geral
        lines.append("Visão Geral")
        lines.append(
            f"→ Total: {self.stats.total_calls} chamadas | "
            f"Sucesso: {self.stats.successful_calls} | "
            f"Falhas: {self.stats.failed_calls}"
        )
        lines.append(f"→ Tempo total: {self.stats.total_duration:.2f}s")

        # Tokens reais
        if self.stats.total_real_tokens > 0:
            lines.append(f"→ Tokens reais: {self.stats.total_real_tokens}")

        # Seção Por Modelo
        lines.append("Por Modelo")
        if self.stats.calls_by_model:
            for model, count in sorted(self.stats.calls_by_model.items()):
                lines.append(f"→ {model}: {count} chamadas")
        else:
            lines.append("→ (nenhuma chamada)")

        # Seção Por Módulo
        lines.append("Por Módulo")
        if self.tracked_modules:
            # Se tracked_modules definido: exibir TODOS (mesmo com 0 chamadas) em ordem alfabética
            for module in sorted(self.tracked_modules):
                calls = self.stats.calls_by_module.get(module, 0)
                tokens = self.stats.tokens_by_module.get(module, 0)
                duration = self.stats.duration_by_module.get(module, 0.0)
                lines.append(f"→ {module}: {calls} chamadas | {tokens} tokens | {duration:.2f}s")
        else:
            # Se tracked_modules vazio: exibir apenas módulos que fizeram chamadas
            if self.stats.calls_by_module:
                for module in sorted(self.stats.calls_by_module.keys()):
                    calls = self.stats.calls_by_module[module]
                    tokens = self.stats.tokens_by_module.get(module, 0)
                    duration = self.stats.duration_by_module.get(module, 0.0)
                    lines.append(f"→ {module}: {calls} chamadas | {tokens} tokens | {duration:.2f}s")
            else:
                lines.append("→ (nenhuma chamada)")

        return "\n".join(lines)

    def reset(self) -> None:
        """
        Reseta completamente o monitor (limpa histórico e estatísticas).

        Útil para testes ou para começar novo ciclo de monitoramento.
        """
        self.call_count = 0
        self.call_history.clear()
        self.stats = LLMMonitorStats()


# ═════════════════════════════════════════════════════════════════════════════
# SEÇÃO 1.5: LANGCHAIN CALLBACK (integração automática com LangChain)
# ═════════════════════════════════════════════════════════════════════════════


class LLMUsageTrackingCallback(BaseCallbackHandler):
    """
    Callback LangChain para tracking automático de tokens e chamadas LLM.

    Intercepta automaticamente chamadas LLM e registra estatísticas no monitor global.
    Usa usage_metadata das APIs para obter tokens reais (não estimados).

    Usage:
        >>> from utils.llm_manager import LLMUsageTrackingCallback
        >>> callback = LLMUsageTrackingCallback(module="RAP_AGENT")
        >>> chain = (prompt | llm).with_config(callbacks=[callback])
        >>> result = chain.invoke({"input": "..."})

    Attributes:
        module: Nome do módulo que faz a chamada (ex: "RAP_AGENT", "RAG_PROCESSOR")
    """

    def __init__(self, module: str):
        """
        Inicializa callback de tracking.

        Args:
            module: Nome do módulo (usado para estatísticas por módulo)
        """
        super().__init__()
        self.module = module
        self.call_id: int | None = None

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        """
        Callback chamado quando LLM começa a processar.

        Args:
            serialized: Dados serializados do LLM
            prompts: Lista de prompts enviados
            **kwargs: Argumentos adicionais (contém invocation_params)
        """
        # Extrair modelo dos parâmetros de invocação
        model = kwargs.get("invocation_params", {}).get("model", "unknown")

        # Inicia tracking no monitor global
        self.call_id = llm_monitor._start_call(self.module, model)

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """
        Callback chamado quando LLM termina com sucesso.

        Args:
            response: Resposta do LLM (LLMResult)
            **kwargs: Argumentos adicionais
        """
        if self.call_id is None:
            return

        # Extrair tokens reais de usage_metadata
        real_tokens = None
        try:
            # LangChain 0.3+: usage_metadata está em generations[0][0].message.usage_metadata
            if hasattr(response, "generations") and response.generations:
                first_gen = response.generations[0][0]
                if hasattr(first_gen, "message") and hasattr(first_gen.message, "usage_metadata"):
                    usage = first_gen.message.usage_metadata
                    if isinstance(usage, dict):
                        real_tokens = usage.get("total_tokens")
                    else:
                        real_tokens = getattr(usage, "total_tokens", None)

            # Fallback: tentar llm_output (OpenAI antigo)
            if real_tokens is None and hasattr(response, "llm_output") and response.llm_output:
                usage = response.llm_output.get("usage_metadata", {}) if isinstance(response.llm_output, dict) else {}
                real_tokens = usage.get("total_tokens")

        except Exception as e:
            # Se falhar ao extrair tokens, continua sem eles
            logger.debug(f"Erro ao extrair usage_metadata: {e}")

        # Finaliza tracking com tokens reais (se disponível)
        llm_monitor._end_call(self.call_id, success=True, real_tokens=real_tokens)

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        """
        Callback chamado quando LLM falha.

        Args:
            error: Exceção que ocorreu
            **kwargs: Argumentos adicionais (run_id, parent_run_id, etc)
        """
        if self.call_id is None:
            return

        # Finaliza tracking com erro
        llm_monitor._end_call(self.call_id, success=False, error=str(error))


# ═════════════════════════════════════════════════════════════════════════════
# SEÇÃO 2: CLIENT LIFECYCLE MANAGEMENT (criação, reuso, cleanup)
# ═════════════════════════════════════════════════════════════════════════════


class LLMClientManager:
    """
    Gerenciador singleton de clientes LLM para evitar resource leaks.

    PROBLEMA: LangChain cria novos httpx.AsyncClient/google.genai.AsyncClient
    a cada instância de ChatOpenAI/ChatGoogleGenerativeAI, mas NÃO fecha
    automaticamente ao final, gerando resource leaks.

    SOLUÇÃO: Singleton que:
    1. Reutiliza clientes (1 cliente por provider/model)
    2. Invalida cache via cleanup_all() (GC fecha recursos automaticamente)
    3. Thread-safe via Lock em get_client() e cleanup_all()
    """

    _instance: "LLMClientManager | None" = None
    _clients: dict[str, Any] = {}

    def __new__(cls) -> "LLMClientManager":
        if cls._instance is None:
            # Lazy import para evitar circular dependency
            import threading

            # Initialize lock at class level (shared by all instances)
            if not hasattr(cls, "_lock"):
                cls._lock: threading.Lock = threading.Lock()

            # Double-check locking para thread-safety
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def get_client(
        self,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        api_endpoint: str | None = None,
        max_retries: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: int | None = None,
    ) -> Any:
        """
        Retorna cliente LLM reutilizável.

        Args:
            provider: Provider normalizado ("openai" | "google"). Se None, lê de AI_PROVIDER
            model: Nome do modelo. Se None, lê de AI_MODEL
            api_key: API key. Se None, lê de AI_API_KEY
            api_endpoint: API endpoint. Se None, lê de AI_API_ENDPOINT
            max_retries: Max retries. Se None, lê de AI_MAX_RETRIES (default 3)
            temperature: Temperature. Se None, lê de AI_TEMPERATURE (default 0.0)
            max_tokens: Max tokens. Se None, lê de AI_MAX_TOKENS (default 4096)
            timeout: Timeout em segundos. Se None, lê de AI_TIMEOUT (default 120)

        Returns:
            Cliente LLM configurado (ChatOpenAI ou ChatGoogleGenerativeAI)

        Raises:
            ValueError: Se provider/model/api_key/api_endpoint não fornecidos e não configurados no .env
        """
        # Fallback para os.getenv se parâmetros não fornecidos
        if provider is None:
            provider = os.getenv("AI_PROVIDER")
            if not provider:
                raise ValueError("Variável AI_PROVIDER não configurada no .env")

        if model is None:
            model = os.getenv("AI_MODEL")
            if not model:
                raise ValueError("Variável AI_MODEL não configurada no .env")

        # Chave única por provider (reutilizar cliente)
        cache_key = f"{provider}:{model}"

        # Thread-safe: lock para evitar race condition ao criar cliente
        with self.__class__._lock:
            # Criar cliente se não existe no cache
            if cache_key not in self._clients:
                logger.debug(f"Criando novo cliente LLM: {cache_key}")
                self._clients[cache_key] = self._create_client(
                    provider=provider,
                    model=model,
                    api_key=api_key,
                    api_endpoint=api_endpoint,
                    max_retries=max_retries,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
            else:
                logger.debug(f"Reutilizando cliente LLM do cache: {cache_key}")

            # CONTRATO: Cliente no cache SEMPRE está válido e pronto para uso
            return self._clients[cache_key]

    def _create_client(
        self,
        provider: str,
        model: str,
        api_key: str | None = None,
        api_endpoint: str | None = None,
        max_retries: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: int | None = None,
    ) -> Any:
        """
        Factory method para criar cliente baseado no provider.

        Args:
            provider: Provider a usar ("openai", "google")
            model: Nome do modelo a usar
            api_key: API key. Se None, lê de AI_API_KEY
            api_endpoint: API endpoint. Se None, lê de AI_API_ENDPOINT
            max_retries: Max retries. Se None, lê de AI_MAX_RETRIES
            temperature: Temperature. Se None, lê de AI_TEMPERATURE
            max_tokens: Max tokens. Se None, lê de AI_MAX_TOKENS
            timeout: Timeout. Se None, lê de AI_TIMEOUT

        Returns:
            Instância do cliente LLM (ChatOpenAI ou ChatGoogleGenerativeAI)

        Raises:
            ValueError: Se provider desconhecido ou credenciais não fornecidas/configuradas
        """
        from pydantic import SecretStr

        # Fallback para os.getenv se não fornecidos
        if api_key is None:
            api_key = os.getenv("AI_API_KEY")
            if not api_key:
                raise ValueError("Variável AI_API_KEY não configurada no .env")

        if api_endpoint is None:
            api_endpoint = os.getenv("AI_API_ENDPOINT")
            if not api_endpoint:
                raise ValueError("Variável AI_API_ENDPOINT não configurada no .env")

        # ═════════════════════════════════════════════════════════════════════════════
        # Lê configurações opcionais com fallback para .env
        # ═════════════════════════════════════════════════════════════════════════════

        if max_retries is None:
            max_retries_str = os.getenv("AI_MAX_RETRIES", "3").strip()
            try:
                max_retries = int(max_retries_str)
                if max_retries < 0:
                    raise ValueError(f"Valor negativo não permitido: {max_retries}")
            except ValueError as e:
                raise ValueError(
                    f"AI_MAX_RETRIES inválido: '{max_retries_str}'\n"
                    f"Esperado: número inteiro >= 0 (ex: 0, 1, 3)\n"
                    f"Erro: {str(e)}"
                ) from e

        if temperature is None:
            temperature_str = os.getenv("AI_TEMPERATURE", "0.0").strip()
            try:
                temperature = float(temperature_str)
                if not 0.0 <= temperature <= 1.0:
                    raise ValueError(f"Valor fora do intervalo [0.0, 1.0]: {temperature}")
            except ValueError as e:
                raise ValueError(
                    f"AI_TEMPERATURE inválido: '{temperature_str}'\n"
                    f"Esperado: número decimal entre 0.0 e 1.0 (ex: 0.0, 0.5, 1.0)\n"
                    f"Erro: {str(e)}"
                ) from e

        if max_tokens is None:
            max_tokens_str = os.getenv("AI_MAX_TOKENS", "4096").strip()
            try:
                max_tokens = int(max_tokens_str)
                if max_tokens <= 0:
                    raise ValueError(f"Valor deve ser positivo: {max_tokens}")
            except ValueError as e:
                raise ValueError(
                    f"AI_MAX_TOKENS inválido: '{max_tokens_str}'\n"
                    f"Esperado: número inteiro > 0 (ex: 4096, 8192, 16384)\n"
                    f"Erro: {str(e)}"
                ) from e

        if timeout is None:
            timeout_str = os.getenv("AI_TIMEOUT", "120").strip()
            try:
                timeout = int(timeout_str)
                if timeout <= 0:
                    raise ValueError(f"Valor deve ser positivo: {timeout}")
            except ValueError as e:
                raise ValueError(
                    f"AI_TIMEOUT inválido: '{timeout_str}'\n"
                    f"Esperado: número inteiro > 0 em segundos (ex: 60, 120, 300)\n"
                    f"Erro: {str(e)}"
                ) from e

        if provider == "openai":
            # ChatOpenAI suporta OpenAI oficial e qualquer API compatível (Ollama, etc.)
            from langchain_openai import ChatOpenAI

            # WORKAROUND: Mypy stubs desatualizados - parâmetros válidos em runtime
            # Usar cast para Any pois max_tokens/timeout existem mas não nos type stubs
            client: Any = ChatOpenAI(
                model=model,
                temperature=temperature,
                api_key=SecretStr(api_key),
                base_url=api_endpoint,
                max_retries=max_retries,
            )
            # Configurar via atributos (contorna limitação dos stubs)
            object.__setattr__(client, "max_tokens", max_tokens)
            object.__setattr__(client, "timeout", timeout)
            return client

        elif provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(
                model=model,
                temperature=temperature,
                max_output_tokens=max_tokens,
                google_api_key=api_key,
                client_args={"api_endpoint": api_endpoint},
                max_retries=max_retries,
                timeout=timeout,
            )

        else:
            raise ValueError(f"Provider desconhecido: '{provider}'. Valores válidos: 'openai', 'google'")

    async def cleanup_all(self) -> None:
        """
        Fecha conexões HTTP dos clientes LLM e invalida cache.

        O que acontece:
        1. Fecha cliente async do Gemini explicitamente (client.aio.aclose())
        2. Fecha cliente sync (client.close())
        3. Remove clientes do cache (_clients.clear())
        4. Próximo get_client() cria novo cliente (sempre válido)

        IMPORTANTE: O cliente Gemini (ChatGoogleGenerativeAI) usa google.genai.Client
        que tem um AsyncClient interno. Se não fecharmos explicitamente ANTES de
        limpar o cache, o __del__ tenta criar uma task para aclose() que falha
        com "Event loop is closed" porque o loop fecha logo depois.

        Uso:
        - Chamar ao final do pipeline para liberar recursos
        - Próximo job recria clientes automaticamente
        """
        with self.__class__._lock:
            num_clients = len(self._clients)

            if num_clients == 0:
                logger.debug("Nenhum cliente LLM no cache")
                return

            logger.info(f"Fechando {num_clients} cliente(s) LLM")

            for cache_key, llm_client in list(self._clients.items()):
                try:
                    # Gemini: ChatGoogleGenerativeAI tem client (google.genai.Client)
                    if hasattr(llm_client, "client") and llm_client.client is not None:
                        inner_client = llm_client.client
                        # Fecha async client PRIMEIRO (evita erro no __del__)
                        if hasattr(inner_client, "aio") and inner_client.aio is not None:
                            try:
                                await inner_client.aio.aclose()
                                logger.debug(f"Cliente async fechado: {cache_key}")
                            except RuntimeError as e:
                                # "Event loop is closed" ocorre quando o transport foi criado
                                # em um loop diferente (ex: execução anterior da UI).
                                # Neste caso, ignoramos silenciosamente - o __del__ do cliente
                                # também vai falhar mas é tratado internamente pelo SDK.
                                if "Event loop is closed" in str(e):
                                    logger.debug(f"Cliente async ignorado (loop diferente): {cache_key}")
                                else:
                                    raise
                        # Fecha sync client
                        if hasattr(inner_client, "close"):
                            inner_client.close()
                            logger.debug(f"Cliente sync fechado: {cache_key}")
                except Exception as e:
                    logger.warning(f"Erro ao fechar cliente {cache_key}: {e}")

            self._clients.clear()
            logger.info("Cache de clientes LLM invalidado")


# ═════════════════════════════════════════════════════════════════════════════
# API PÚBLICA - Singletons e funções utilitárias
# ═════════════════════════════════════════════════════════════════════════════

# Singletons globais - acesso direto
llm_client_manager = LLMClientManager()
llm_monitor = LLMMonitor()


# ─── Funções Utilitárias ───


def get_structured_output_method(provider: str | None = None) -> tuple[str, dict[str, Any]]:
    """
    Retorna método de structured output e kwargs baseado no provider.

    Args:
        provider: Provider normalizado ("openai" | "google"). Se None, lê de AI_PROVIDER

    Returns:
        Tuple de (method: str, kwargs: dict) para with_structured_output()

    Raises:
        ValueError: Se provider não fornecido e AI_PROVIDER não configurado ou desconhecido

    MÉTODO CORRETO POR PROVIDER:
    - Google (gemini_personal, gemini_natura): "json_schema" - constrained decoding nativo
    - OpenAI (openai_numen, gpt-oss_numen): "json_schema" + strict=True - Structured Outputs API

    IMPORTANTE: "function_calling" NÃO tem enforcement de schema - é soft constraint via tool calling.
    Usar json_schema garante 100% conformidade ao schema Pydantic (vs ~95% com function_calling).

    Referências:
    - OpenAI Structured Outputs: https://platform.openai.com/docs/guides/structured-outputs
    - Gemini JSON Mode: https://ai.google.dev/gemini-api/docs/json-mode
    - LangChain docs: https://python.langchain.com/docs/how_to/structured_output/

    Example:
        >>> from utils.llm_manager import get_structured_output_method
        >>> method, kwargs = get_structured_output_method()
        >>> llm_with_structure = llm.with_structured_output(Schema, method=method, **kwargs)
    """
    # Fallback para os.getenv se não fornecido
    if provider is None:
        provider = os.getenv("AI_PROVIDER")
        if not provider:
            raise ValueError("Variável AI_PROVIDER não configurada no .env")

    if provider == "google":
        # Google (gemini_personal, gemini_natura, etc.)
        # - json_schema é default e MELHOR opção
        # - Usa constrained decoding nativo (token-level enforcement)
        # - Ignora strict parameter (sempre enforçado internamente)
        # - Garante 100% conformidade ao schema
        return "json_schema", {}

    elif provider == "openai":
        # OpenAI (openai_numen, gpt-oss_numen, etc.)
        # - json_schema + strict=True ativa Structured Outputs API
        # - Valida schema em build-time, enforça em runtime
        # - Garante 100% conformidade (vs ~95% com function_calling)
        # - Funciona para OpenAI oficial E APIs compatíveis (Ollama/GPT-OSS)
        return "json_schema", {"strict": True}

    else:
        raise ValueError(
            f"Provider desconhecido: '{provider}'. "
            f"Valores válidos após normalização: 'openai', 'google'. "
            f"Verifique initialization.py:_PROVIDER_CONFIG"
        )
