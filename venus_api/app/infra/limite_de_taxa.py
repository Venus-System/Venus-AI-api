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
#
# O Mongo fora do ar nunca derruba a API, como já acontece com a memória e
# as métricas: o startup não conecta, o índice é criado na primeira mensagem
# (e tentado de novo se falhar), e uma falha na contagem cai no contador em
# memória daquela instância.

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
_TIMEOUT_MONGO_MS = 2000


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
        self._indice_criado = False
        # Decisão: com o Mongo fora do ar, conta em memória (limite por
        # instância) em vez de devolver 500 ou liberar sem limite nenhum.
        # Mantém alguma proteção de custo sem bloquear usuários por falha de
        # infraestrutura.
        self._reserva = LimitadorEmMemoria()

    async def registrar(self, uid: str) -> int | None:
        try:
            return await asyncio.to_thread(self._registrar, uid)
        except Exception:
            logger.error(
                "Limite de mensagens: Mongo indisponível — contando em memória nesta instância.",
                exc_info=True,
            )
            return await self._reserva.registrar(uid)

    def _garantir_indice(self) -> None:
        """O Mongo apaga cada documento quando a janela dele acaba. Criado na
        primeira mensagem, não no startup; se falhar, tenta na seguinte."""
        if self._indice_criado:
            return
        try:
            self._colecao.create_index("expira_em", expireAfterSeconds=0)
            self._indice_criado = True
        except Exception:
            logger.warning("Limite de mensagens: não deu para criar o índice TTL; tento de novo na próxima.",
                           exc_info=True)

    def _registrar(self, uid: str) -> int | None:
        from pymongo import ReturnDocument

        self._garantir_indice()
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

    # connect=False: o startup não espera o Mongo; a conexão abre na primeira
    # mensagem, e se falhar o limitador cai no contador em memória. Timeout
    # curto: com o Mongo fora do ar, cada mensagem esperaria os 30 s padrão
    # do pymongo antes de cair no fallback.
    cliente = MongoClient(settings.mongodb_url, connect=False, serverSelectionTimeoutMS=_TIMEOUT_MONGO_MS)
    return LimitadorMongo(cliente["venus"][COLECAO_LIMITES])
