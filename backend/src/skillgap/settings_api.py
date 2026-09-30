"""Rotas para configurar a chave da API Anthropic em runtime (somente memória).

Notas de comportamento:
- DELETE remove apenas a chave de sessão; uma ANTHROPIC_API_KEY do ambiente continua
  valendo e `source` passa a reportar "environment".
- clear() não interrompe uma extração já em andamento: ela segue com a chave lida
  no início da chamada; só as chamadas seguintes usam o novo estado.
- Origin/Host são verificados em um middleware ASGI puro (GuardMiddleware), antes de
  qualquer leitura de corpo ou validação, para que o 403 vença sempre o 422.
"""
import logging
import re
from collections.abc import Callable

import anthropic
from fastapi import APIRouter, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, SecretStr

from skillgap.keystore import KeyStore

logger = logging.getLogger(__name__)

SETTINGS_PREFIX = "/settings/api-key"
_HOST_RE = re.compile(r"(localhost|127\.0\.0\.1|\[::1\])(:\d{1,5})?", re.IGNORECASE)


def is_allowed_host(host: str) -> bool:
    return _HOST_RE.fullmatch(host) is not None


class ApiKeyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: SecretStr


def default_client_factory(key: str):
    return anthropic.Anthropic(api_key=key, timeout=10.0, max_retries=0)


class GuardMiddleware:
    """Middleware ASGI puro: nunca lê o corpo da requisição.

    - Host: allow-list em toda a API (bloqueia DNS rebinding).
    - Origin: obrigatório e restrito a `allowed_origins` apenas sob /settings.
    - Respostas de /settings recebem `Cache-Control: no-store`.
    """

    def __init__(self, app, allowed_origins: list[str], allowed_hosts: list[str] | None = None):
        self.app = app
        self.allowed_origins = list(allowed_origins)
        self.allowed_hosts = (None if allowed_hosts is None
                              else {h.lower() for h in allowed_hosts})

    def _host_ok(self, host: str) -> bool:
        if self.allowed_hosts is None:
            return is_allowed_host(host)
        return host.lower() in self.allowed_hosts

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1")
                   for k, v in scope.get("headers", [])}
        is_settings = scope["path"] == SETTINGS_PREFIX or scope["path"].startswith(SETTINGS_PREFIX + "/")
        detail = None
        if not self._host_ok(headers.get("host", "")):
            detail = "Host não permitido."
        elif is_settings and headers.get("origin") not in self.allowed_origins:
            detail = "Origem não permitida."
        if detail is not None:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            await JSONResponse({"detail": detail}, status_code=403,
                               headers={"Cache-Control": "no-store"} if is_settings else None,
                               )(scope, receive, send)
            return
        if not is_settings or scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_no_store(message):
            if message["type"] == "http.response.start":
                hdrs = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"cache-control"]
                hdrs.append((b"cache-control", b"no-store"))
                message = {**message, "headers": hdrs}
            await send(message)

        await self.app(scope, receive, send_no_store)


def build_settings_router(keystore: KeyStore,
                          client_factory: Callable | None = None) -> APIRouter:
    factory = client_factory or default_client_factory
    router = APIRouter(prefix=SETTINGS_PREFIX)

    @router.get("")
    def get_status():
        return keystore.status()

    @router.put("")
    def set_key(body: ApiKeyBody):
        try:
            keystore.set(body.api_key.get_secret_value())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return keystore.status()

    @router.delete("")
    def clear_key():
        keystore.clear()
        return keystore.status()

    @router.post("/test")
    def test_key():
        key = keystore.get()
        if not key:
            raise HTTPException(409, "Nenhuma chave configurada.")
        try:
            factory(key).models.list(limit=1)
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            _log_failure(exc)
            return {"status": "invalid"}
        except anthropic.APIConnectionError as exc:  # inclui APITimeoutError
            _log_failure(exc)
            return {"status": "unreachable"}
        except anthropic.APIError as exc:
            _log_failure(exc)
            return {"status": "error"}
        return {"status": "valid"}

    return router


def _log_failure(exc: Exception) -> None:
    logger.warning("Teste da chave falhou: %s (status=%s)",
                   type(exc).__name__, getattr(exc, "status_code", None))


async def settings_validation_handler(request: Request, exc: RequestValidationError):
    """Nunca devolve o valor enviado (o handler padrão ecoa `input`)."""
    if not request.url.path.startswith(SETTINGS_PREFIX):
        from fastapi.exception_handlers import request_validation_exception_handler
        return await request_validation_exception_handler(request, exc)
    # Só nomes constantes: chaves do JSON enviado pelo cliente nunca são devolvidas.
    known = {"body", "api_key"}
    fields = sorted({(".".join(p for p in err.get("loc", ()) if p in known)
                      if all(p in known for p in err.get("loc", ())) else "campo desconhecido")
                     or "body" for err in exc.errors()})
    return JSONResponse(status_code=422, content={
        "detail": "Requisição inválida: envie apenas o campo api_key com a chave.",
        "fields": fields})
