# Middleware HTTP: mede o tempo total e o status de cada requisição — a visão
# "de fora" da API, de onde sai a taxa de erro. O que acontece dentro do grafo
# (tempo de cada agente, tokens, custo) fica no Langfuse, ver `tracing.py`.
#
# Cada medição é gravada no Mongo (coleção `metricas_requisicoes`), o mesmo
# banco do histórico de conversa — não exige conexão nova. A gravação roda
# depois que a resposta sai: com o Mongo lento ou fora do ar, quem espera é a
# métrica, não o usuário.

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Awaitable, Callable

from fastapi import Request, Response
from starlette.background import BackgroundTasks

from venus_api.app.infra.mongo import cliente_mongo

logger = logging.getLogger(__name__)

COLECAO_METRICAS = "metricas_requisicoes"

# O balanceador de carga chama o health check a cada poucos segundos em
# produção — gravar isso afogaria as métricas de verdade do chat.
_ROTAS_IGNORADAS = frozenset({"/v1/health"})


@lru_cache(maxsize=1)
def _colecao_metricas() -> Any:
    cliente = cliente_mongo()
    return cliente["venus"][COLECAO_METRICAS] if cliente is not None else None


async def _registrar(documento: dict[str, Any]) -> None:
    """Grava a medição. Nunca levanta: observabilidade com defeito não pode
    derrubar o chat que ela está medindo."""
    try:
        colecao = _colecao_metricas()
        if colecao is not None:
            await asyncio.to_thread(colecao.insert_one, documento)
    except Exception:
        logger.warning("Não foi possível gravar a métrica da requisição", exc_info=True)


def _medicao(request: Request, status: int, inicio: float) -> dict[str, Any]:
    return {
        "metodo": request.method,
        "rota": request.url.path,
        "status": status,
        "duracao_ms": round((time.perf_counter() - inicio) * 1000, 2),
        "momento": datetime.now(timezone.utc),
    }


async def medir_requisicao(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    inicio = time.perf_counter()
    medir = request.url.path not in _ROTAS_IGNORADAS
    try:
        resposta = await call_next(request)
    except Exception:
        # Erro não tratado: não há resposta para pendurar a gravação, então
        # grava aqui mesmo. É o caso que mais importa contar na taxa de erro.
        if medir:
            await _registrar(_medicao(request, 500, inicio))
        raise
    if medir:
        tarefas = BackgroundTasks()
        if resposta.background is not None:
            # A tarefa de segundo plano da própria rota continua rodando.
            tarefas.add_task(resposta.background)
        tarefas.add_task(_registrar, _medicao(request, resposta.status_code, inicio))
        resposta.background = tarefas
    return resposta
