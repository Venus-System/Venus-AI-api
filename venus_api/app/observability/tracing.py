# Rastreamento dos agentes no Langfuse: cada mensagem do chat vira um trace,
# com o tempo de cada nó do grafo e os tokens/custo de cada chamada de LLM.
# É a visão "de dentro" — a "de fora" (tempo total e status HTTP) fica no
# `middleware.py`.

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from functools import lru_cache
from typing import Any

from langfuse import Langfuse, propagate_attributes
from langfuse.langchain import CallbackHandler

from venus_api.app.core.config import settings


@lru_cache(maxsize=1)
def get_langfuse() -> Langfuse | None:
    """Cliente do Langfuse, criado uma vez. `None` sem as chaves configuradas —
    aí o chat roda sem rastreamento, sem erro."""
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        base_url=settings.langfuse_base_url,
    )


def callbacks_do_trace() -> list[Any]:
    """Callbacks a passar no `config` do `ainvoke` do grafo."""
    if get_langfuse() is None:
        return []
    return [CallbackHandler(public_key=settings.langfuse_public_key)]


def atributos_do_trace(usuario_id: str, conversation_id: str) -> AbstractContextManager:
    """Marca o trace com o usuário e a conversa. Sem isso o Langfuse mostra
    chamadas soltas — e o "custo por resolução" do relatório depende de somar
    o custo por conversa."""
    if get_langfuse() is None:
        return nullcontext()
    return propagate_attributes(
        user_id=usuario_id,
        session_id=conversation_id,
        trace_name="venus-chat",
    )
