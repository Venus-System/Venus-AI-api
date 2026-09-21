# Middleware HTTP: mede o tempo total e o status de cada requisição — a visão
# "de fora" da API, de onde sai a taxa de erro. O que acontece dentro do grafo
# (tempo de cada agente, tokens, custo) fica no Langfuse, ver `tracing.py`.
#
# Cada medição é gravada no Mongo (coleção `metricas_requisicoes`), o mesmo
# banco do histórico de conversa — não exige conexão nova.

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Awaitable, Callable

from fastapi import Request, Response
from pymongo import MongoClient

from venus_api.app.core.config import settings

logger = logging.getLogger(__name__)

COLECAO_METRICAS = "metricas_requisicoes"

# O balanceador de carga chama o health check a cada poucos segundos em
# produção — gravar isso afogaria as métricas de verdade do chat.
_ROTAS_IGNORADAS = frozenset({"/v1/health"})


@lru_cache(maxsize=1)
def _colecao_metricas() -> Any:
    if not settings.mongodb_url:
        return None
    return MongoClient(settings.mongodb_url)["venus"][COLECAO_METRICAS]


async def _registrar(documento: dict[str, Any]) -> None:
    """Grava a medição. Nunca levanta: observabilidade com defeito não pode
    derrubar o chat que ela está medindo."""
    try:
        colecao = _colecao_metricas()
        if colecao is not None:
            await asyncio.to_thread(colecao.insert_one, documento)
    except Exception:
        logger.warning("Não foi possível gravar a métrica da requisição", exc_info=True)


async def medir_requisicao(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    inicio = time.perf_counter()
    # Se `call_next` levantar (erro não tratado), o status fica 500 — é
    # justamente o caso que mais importa contar na taxa de erro.
    status = 500
    try:
        resposta = await call_next(request)
        status = resposta.status_code
        return resposta
    finally:
        duracao_ms = (time.perf_counter() - inicio) * 1000
        if request.url.path not in _ROTAS_IGNORADAS:
            await _registrar(
                {
                    "metodo": request.method,
                    "rota": request.url.path,
                    "status": status,
                    "duracao_ms": round(duracao_ms, 2),
                    "momento": datetime.now(timezone.utc),
                }
            )
