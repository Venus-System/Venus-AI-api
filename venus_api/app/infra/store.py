# Monta o store do LangGraph (memória de longo prazo, entre sessões).
#
# O adaptador MongoDB -> BaseStore já existe no SDK do Venus
# (`venus_sdk.memory.store.MongoDBStore`, implementação própria do time — o
# LangGraph não publica um store oficial pra Mongo). Aqui só escolhemos entre
# ele e a versão em RAM, conforme a configuração.

from __future__ import annotations

import logging
from typing import Any

from venus_sdk.memory.store import criar_store_em_memoria, criar_store_mongo

from venus_api.app.core.config import settings

logger = logging.getLogger(__name__)


def criar_store() -> Any:
    """Store do grafo: memória de longo prazo por `usuario_id`.

    É o que faz a Venus lembrar da pessoa entre conversas diferentes (nome,
    tipo de pele, alergias que ela mencionou). O `usuario_id` que chega aqui é
    o UID do Firebase, enviado pelo endpoint de chat.
    """
    if not settings.mongodb_url:
        logger.warning(
            "MONGODB_URL não configurada — usando store em RAM. "
            "A Venus não vai lembrar de nada entre conversas."
        )
        return criar_store_em_memoria()

    return criar_store_mongo(settings.mongodb_url)
