# Endpoint POST /chat.
#
# Recebe a mensagem do usuário (ChatRequest), monta o estado inicial do grafo
# Venus, invoca o grafo (fluxo_venus.ainvoke) usando o session_id como
# thread_id para manter contexto entre chamadas, e devolve a última mensagem
# do estado final como resposta (ChatResponse).

from __future__ import annotations

import logging
from typing import Any, get_args

from fastapi import APIRouter, Depends, HTTPException, status
from venus_sdk.state import Expressao

from venus_api.app.api.deps import get_fluxo_venus, get_limitador, get_pool, get_session_id
from venus_api.app.infra.postgres import resolver_usuario_postgres
from venus_api.app.observability import tracing
from venus_api.app.schemas.chat import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter()

_RESPOSTA_VAZIA = "Não consegui responder agora — pode tentar de novo em instantes?"


@router.post("/chat", response_model=ChatResponse)
async def chat(
    requisicao: ChatRequest,
    fluxo: Any = Depends(get_fluxo_venus),
    usuario_id: str = Depends(get_session_id),
    pool: Any = Depends(get_pool),
    limitador: Any = Depends(get_limitador),
) -> ChatResponse:
    espera = await limitador.registrar(usuario_id)
    if espera is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas mensagens em pouco tempo. Tente de novo daqui a pouco.",
            headers={"Retry-After": str(espera)},
        )

    # Sem conversation_id, o id do próprio usuário serve de conversa contínua —
    # assim o histórico não se perde nem se o app ignorar o id devolvido.
    conversation_id = requisicao.conversation_id or usuario_id
    thread_id = f"{usuario_id}:{conversation_id}"

    estado: dict[str, Any] = {
        "mensagem_usuario": requisicao.mensagem,
        "usuario_id": usuario_id,
    }
    if "usuario_id_postgres" in (requisicao.model_extra or {}):
        # App antigo: o valor é ignorado — a identidade vem do token.
        logger.warning("Campo usuario_id_postgres enviado pelo cliente foi ignorado (uid=%s)", usuario_id)
    usuario_id_postgres = await resolver_usuario_postgres(pool, usuario_id)
    if usuario_id_postgres is not None:
        estado["usuario_id_postgres"] = usuario_id_postgres

    try:
        with tracing.atributos_do_trace(usuario_id, conversation_id):
            resultado = await fluxo.ainvoke(
                estado,
                config={
                    "configurable": {"thread_id": thread_id},
                    "callbacks": tracing.callbacks_do_trace(),
                },
            )
    except Exception as erro:
        logger.exception("Falha ao invocar o grafo Venus (thread_id=%s)", thread_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Falha ao processar a mensagem",
        ) from erro

    expressao = resultado.get("expressao")
    return ChatResponse(
        resposta=resultado.get("resposta_final") or _RESPOSTA_VAZIA,
        conversation_id=conversation_id,
        # Fora da lista (ex.: um SDK com uma cara nova) vira `neutra`: nem 500
        # nem um valor que a web não conhece.
        expressao=expressao if expressao in get_args(Expressao) else "neutra",
    )
