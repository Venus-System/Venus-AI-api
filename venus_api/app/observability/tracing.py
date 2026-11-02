# Rastreamento dos agentes no Langfuse: cada mensagem do chat vira um trace,
# com o tempo de cada nó do grafo, os tokens/custo de cada chamada de LLM e o
# resultado do turno (rota, Juiz, guardrails, alertas de alergia). É a visão
# "de dentro" — a "de fora" (tempo total e status HTTP) fica no
# `middleware.py`.

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from langfuse import Langfuse, propagate_attributes
from langfuse.langchain import CallbackHandler

from venus_api.app.core.config import settings

logger = logging.getLogger(__name__)


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


def resultado_do_turno(estado_final: dict[str, Any]) -> dict[str, Any]:
    """O que aconteceu no turno, lido do estado final do grafo: para onde a
    mensagem foi, o que o Juiz fez e o que os guardrails barraram.

    `juiz_decidiu_por` ("regra", "llm" ou "falha_llm") e
    `alertas_alergia_anexados` só existem em SDK posterior à v0.4.0; antes
    disso vêm `None`."""
    entrada_bloqueada = bool(estado_final.get("entrada_bloqueada"))
    return {
        # A entrada bloqueada não passa pelo roteador: a `rota` no estado seria
        # a do turno anterior (o SDK até a v0.4.0 não a zera).
        "rota": None if entrada_bloqueada else estado_final.get("rota"),
        "entrada_bloqueada": entrada_bloqueada,
        "saida_bloqueada": bool(estado_final.get("saida_bloqueada")),
        "aprovado_juiz": estado_final.get("aprovado_juiz"),
        "juiz_decidiu_por": estado_final.get("juiz_decidiu_por"),
        "tentativas_juiz": estado_final.get("tentativas_juiz") or 0,
        "alertas_alergia_anexados": estado_final.get("alertas_alergia_anexados"),
        "expressao": estado_final.get("expressao"),
    }


class TurnoNoTrace:
    """Observação raiz do trace de uma mensagem. Sem Langfuse, não faz nada."""

    def __init__(self, observacao: Any = None) -> None:
        self._observacao = observacao

    def registrar(self, estado_final: dict[str, Any]) -> None:
        """Grava a resposta e o resultado do turno no trace. Nunca derruba o
        chat: falha do Langfuse vira só um aviso no log."""
        if self._observacao is None:
            return
        try:
            self._observacao.update(
                output=estado_final.get("resposta_final"),
                metadata=resultado_do_turno(estado_final),
            )
        except Exception:
            logger.warning("Falha ao gravar o resultado do turno no Langfuse", exc_info=True)


@contextmanager
def turno_no_trace(usuario_id: str, conversation_id: str, mensagem: str) -> Iterator[TurnoNoTrace]:
    """Abre o trace da mensagem, marcado com o usuário e a conversa (sem isso o
    Langfuse mostra chamadas soltas, e o "custo por resolução" do relatório
    soma o custo por conversa). Os nós do grafo, que o `CallbackHandler`
    rastreia, ficam dentro desta observação; o resultado do turno entra nela
    com `TurnoNoTrace.registrar`."""
    langfuse = get_langfuse()
    if langfuse is None:
        yield TurnoNoTrace()
        return
    with propagate_attributes(user_id=usuario_id, session_id=conversation_id, trace_name="venus-chat"):
        with langfuse.start_as_current_observation(name="venus-chat", input=mensagem) as observacao:
            yield TurnoNoTrace(observacao)
