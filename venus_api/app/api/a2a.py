# Servidor A2A: deixa outros agentes conversarem com a Venus pelo protocolo
# A2A (https://a2a-protocol.org/). O servidor em si vem pronto do SDK
# (`venus_sdk.a2a_server`); aqui ficam as duas coisas que ele não faz:
#
# - autenticação: o SDK não tem nenhuma, então sem isso qualquer pessoa que
#   descobrisse a URL gastaria os créditos de LLM. A2A é conversa de servidor
#   pra servidor, então uma chave fixa no header `X-API-Key` basta (o Firebase
#   é pra usuário de celular).
# - o ciclo de vida: o grafo só existe depois do startup, mas as rotas
#   precisam ser registradas antes. `A2ADinamico` fica montado desde o início
#   e entrega cada requisição ao app A2A que o `lifespan` criou.
#
# O tráfego A2A é medido pelo middleware HTTP (Mongo), mas não aparece no
# Langfuse: o executor do SDK não passa os callbacks do rastreamento.

from __future__ import annotations

import hmac
import logging
from typing import Any

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from venus_sdk.a2a_server import montar_app_a2a

from venus_api.app.core.config import settings

logger = logging.getLogger(__name__)

# Onde o servidor A2A fica montado na API. Termina em barra porque o
# JSON-RPC responde na raiz do sub-app: sem a barra, o Starlette responde
# com um redirecionamento, que a maioria dos clientes A2A não segue em POST.
ROTA_A2A = "/a2a"

# Só o Agent Card é público: é ele que diz onde e como chamar a Venus, e o
# protocolo espera que quem chega seja capaz de ler isso antes de ter a chave.
_AGENT_CARD = "/.well-known/agent-card.json"


class ExigirChave:
    """Recusa com 401 toda requisição sem a chave certa, exceto a leitura do
    Agent Card."""

    def __init__(self, app: ASGIApp, chave: str) -> None:
        self._app = app
        self._chave = chave.encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and not self._e_agent_card(scope):
            recebida = Headers(scope=scope).get("x-api-key", "").encode()
            # compare_digest: tempo de resposta igual, acertando ou errando, pra
            # ninguém adivinhar a chave letra por letra.
            if not hmac.compare_digest(recebida, self._chave):
                resposta = JSONResponse(
                    {"detail": "Chave A2A ausente ou inválida"}, status_code=401
                )
                await resposta(scope, receive, send)
                return
        await self._app(scope, receive, send)

    @staticmethod
    def _e_agent_card(scope: Scope) -> bool:
        # Dentro de um `Mount`, `path` continua sendo o caminho completo
        # (com o prefixo `/a2a`); o prefixo vem em `root_path`.
        caminho = scope["path"].removeprefix(scope.get("root_path", ""))
        return scope["method"] == "GET" and caminho == _AGENT_CARD


def criar_app_a2a(grafo: Any) -> ASGIApp | None:
    """Monta o app A2A já protegido, ou `None` se ele deve ficar desligado.

    Desligado por padrão e sem a chave: expor um servidor que gasta dinheiro
    sem autenticação, só porque faltou uma variável, seria o pior erro
    possível de configuração.
    """
    chave = settings.a2a_api_key
    url_base = (settings.a2a_base_url or "").rstrip("/")

    if not chave:
        logger.info("A2A_API_KEY não configurada — servidor A2A desligado.")
        return None
    if not url_base:
        logger.warning(
            "A2A_API_KEY configurada, mas A2A_BASE_URL não — servidor A2A "
            "desligado. Ela é a URL pública da API e só existe depois do "
            "primeiro deploy."
        )
        return None

    app_a2a = montar_app_a2a(grafo=grafo, base_url=f"{url_base}{ROTA_A2A}/")
    return ExigirChave(app_a2a, chave)


class A2ADinamico:
    """Ponto de montagem fixo do A2A: entrega a requisição ao app criado no
    `lifespan` (guardado em `app.state.a2a_app`), ou responde 404 se o A2A
    está desligado."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        app_a2a = getattr(scope["app"].state, "a2a_app", None)
        if app_a2a is None:
            resposta = JSONResponse({"detail": "A2A desligado"}, status_code=404)
            await resposta(scope, receive, send)
            return
        await app_a2a(scope, receive, send)
