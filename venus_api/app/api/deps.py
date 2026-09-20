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

from fastapi import Header, HTTPException, Request, status

from venus_api.app.core.security import validar_token


def get_fluxo_venus(request: Request) -> Any:
    """Devolve o grafo Venus compilado uma única vez no startup (ver
    `app.main::lifespan`) — nunca recompilado por request."""
    return request.app.state.fluxo_venus


def get_session_id(authorization: str | None = Header(default=None)) -> str:
    """Valida o token do header `Authorization` e devolve o `thread_id` da
    conversa (o `id` do usuário validado).

    Provisório: uma conversa por usuário (o `id` do usuário É o
    `thread_id`). Suportar múltiplas conversas por usuário exigiria um
    identificador adicional, vindo do corpo da requisição.
    """
    try:
        usuario = validar_token(authorization)
    except ValueError as erro:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(erro)) from erro
    return usuario.id
