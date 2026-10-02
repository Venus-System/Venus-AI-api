# Pool de conexões com o Postgres do CRUD.
#
# As tools de produto, ingrediente e alergia do SDK consultam o banco por um
# `asyncpg.Pool` que quem monta o grafo precisa criar e entregar
# (`compilar_grafo_venus(pool=...)`) — o SDK nunca abre conexão sozinho.

from __future__ import annotations

import logging
from typing import Any

import asyncpg

from venus_api.app.core.config import settings

logger = logging.getLogger(__name__)

# O banco aceita só 20 conexões no total e o CRUD já usa até 10 delas. Uma
# API só, com 1 a 2 conexões, cabe folgada; subir isso aqui é pedir pra
# derrubar o CRUD.
_CONEXOES_MIN = 1
_CONEXOES_MAX = 2
_SEGUNDOS_PRA_CONECTAR = 10


async def criar_pool() -> asyncpg.Pool | None:
    """Abre o pool do Postgres, ou devolve `None` se não der.

    `None` não derruba a API: o chat continua respondendo, e os especialistas
    de produto e ingrediente avisam ao usuário que não conseguiram consultar
    os dados (é o que o SDK faz sem pool). Por isso o log é `error` — é uma
    degradação que precisa aparecer no CloudWatch, não passar batido.
    """
    if not settings.database_url:
        logger.warning(
            "DATABASE_URL não configurada — sem Postgres. Os especialistas de "
            "produto e ingrediente não vão conseguir consultar os dados."
        )
        return None

    try:
        return await asyncpg.create_pool(
            settings.database_url,
            min_size=_CONEXOES_MIN,
            max_size=_CONEXOES_MAX,
            timeout=_SEGUNDOS_PRA_CONECTAR,
        )
    except Exception:
        logger.error(
            "Não foi possível conectar ao Postgres — seguindo sem ele. "
            "Confira a DATABASE_URL e se o banco aceita conexões deste servidor.",
            exc_info=True,
        )
        return None


# Quem está no chat é o dono do token do Firebase: o id do Postgres sai daqui,
# nunca do corpo da requisição (o app mandar "usuario_id_postgres: 5" deixava
# qualquer usuário ler alergias, perfil e favoritos do usuário 5).
_SQL_USUARIO_POR_FIREBASE_UID = "SELECT user_id FROM venus.users WHERE firebase_uid = $1"


async def resolver_usuario_postgres(pool: Any, firebase_uid: str) -> int | None:
    """`user_id` em `venus.users` do dono desse uid do Firebase, ou `None`
    (sem pool, sem cadastro com esse uid ou banco fora do ar). `None` não é
    erro: o SDK atende sem acesso aos dados da conta."""
    if pool is None or not firebase_uid:
        return None
    try:
        async with pool.acquire() as conexao:
            linha = await conexao.fetchrow(_SQL_USUARIO_POR_FIREBASE_UID, firebase_uid)
    except Exception:
        logger.error("Não consegui resolver o usuário do Postgres pelo uid do Firebase.", exc_info=True)
        return None
    return int(linha["user_id"]) if linha else None
