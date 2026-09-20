# Dependências injetadas nos endpoints via Depends().
#
# get_fluxo_venus: devolve o grafo Venus já compilado uma vez no startup
# (guardado em app.state), evitando recompilar o grafo a cada request.
#
# get_session_id: extrai e valida o token de autorização (via
# app.core.security.validar_token) e gera o thread_id/session_id usado pelo
# checkpointer do LangGraph para manter o histórico da conversa por usuário.

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from venus_api.app.core.security import validar_token

# auto_error=False: sem o header, queremos responder 401 (e não o 403 que o
# HTTPBearer devolve por padrão).
_bearer = HTTPBearer(auto_error=False)


def get_fluxo_venus(request: Request) -> Any:
    """Devolve o grafo Venus compilado uma única vez no startup (ver
    `app.main::lifespan`) — nunca recompilado por request."""
    return request.app.state.fluxo_venus


def get_session_id(
    credenciais: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Valida o `Authorization: Bearer <ID token do Firebase>` e devolve o
    `uid` do usuário — usado como identidade e como base do `thread_id` da
    conversa."""
    try:
        usuario = validar_token(credenciais.credentials if credenciais else None)
    except ValueError as erro:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(erro)) from erro
    return usuario.id
