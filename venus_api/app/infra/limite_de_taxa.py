# Limite de mensagens por usuário no /v1/chat.
#
# Cada mensagem dispara de 6 a 12 chamadas de LLM: sem limite, um único
# usuário autenticado esgota a cota (e os créditos) dos provedores. Conta por
# `uid` do Firebase em duas janelas — por minuto e por dia (UTC) — com os
# limites de `settings`.
#
# Com Mongo, o contador é compartilhado entre as instâncias da API (um
# documento por uid e janela, apagado sozinho pelo índice TTL). Sem Mongo, cai
# num contador em memória que só vale por instância: com várias tasks no ECS,
# cada uma conta separado e o limite real vira limite x instâncias.

from __future__ import annotations

import asyncio
import logging
import math
import time
from datetime import datetime, timezone
from typing import Any

from venus_api.app.core.config import settings

logger = logging.getLogger(__name__)

COLECAO_LIMITES = "limites_chat"
_JANELAS = (("minuto", 60), ("dia", 86_400))


def _limite(janela: str) -> int:
    return settings.chat_limite_por_minuto if janela == "minuto" else settings.chat_limite_por_dia


def _janela_atual(segundos: int, agora: float) -> tuple[int, float]:
    """(início da janela, segundos até ela acabar)."""
    inicio = int(agora // segundos) * segundos
    return inicio, inicio + segundos - agora


class LimitadorEmMemoria:
    """Contador por processo — só para uma instância (dev, testes)."""

    def __init__(self) -> None:
        self._contadores: dict[tuple[str, str, int], int] = {}

    async def registrar(self, uid: str) -> int | None:
        """Conta a mensagem; devolve `None` se está dentro do limite ou os
        segundos para tentar de novo (`Retry-After`)."""
        agora = time.time()
        espera = None
        for janela, segundos in _JANELAS:
            inicio, restante = _janela_atual(segundos, agora)
            chave = (uid, janela, inicio)
            self._contadores[chave] = self._contadores.get(chave, 0) + 1
            if self._contadores[chave] > _limite(janela):
                espera = max(espera or 0, math.ceil(restante))
        self._esquecer_janelas_antigas(agora)
        return espera

    def _esquecer_janelas_antigas(self, agora: float) -> None:
        antigas = [chave for chave in self._contadores if chave[2] + dict(_JANELAS)[chave[1]] <= agora]
        for chave in antigas:
            del self._contadores[chave]


class LimitadorMongo:
    """Contador compartilhado entre instâncias, numa coleção do Mongo."""

    def __init__(self, colecao: Any) -> None:
        self._colecao = colecao
        # O Mongo apaga cada documento quando a janela dele acaba.
        self._colecao.create_index("expira_em", expireAfterSeconds=0)

    async def registrar(self, uid: str) -> int | None:
        return await asyncio.to_thread(self._registrar, uid)

    def _registrar(self, uid: str) -> int | None:
        from pymongo import ReturnDocument

        agora = time.time()
        espera = None
        for janela, segundos in _JANELAS:
            inicio, restante = _janela_atual(segundos, agora)
            documento = self._colecao.find_one_and_update(
                {"_id": f"{uid}:{janela}:{inicio}"},
                {"$inc": {"contador": 1},
                 "$setOnInsert": {"expira_em": datetime.fromtimestamp(inicio + segundos, tz=timezone.utc)}},
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            if documento["contador"] > _limite(janela):
                espera = max(espera or 0, math.ceil(restante))
        return espera


def criar_limitador() -> LimitadorEmMemoria | LimitadorMongo:
    if not settings.mongodb_url:
        logger.warning(
            "MONGODB_URL não configurada — limite de mensagens em memória, por instância. "
            "Com várias instâncias da API, cada uma conta separado."
        )
        return LimitadorEmMemoria()
    from pymongo import MongoClient

    return LimitadorMongo(MongoClient(settings.mongodb_url)["venus"][COLECAO_LIMITES])
