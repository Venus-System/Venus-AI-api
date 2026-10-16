# Cliente do MongoDB compartilhado pela API (limite de mensagens e métricas).
#
# Um cliente só por processo: cada MongoClient abre o próprio pool de conexões
# e as próprias threads de monitoramento. O checkpointer e o store do SDK
# recebem a URL e montam o cliente deles.

from __future__ import annotations

from functools import lru_cache

from pymongo import MongoClient

from venus_api.app.core.config import settings

# Com o Mongo fora do ar, cada operação desiste em 2 s em vez dos 30 s padrão
# do pymongo: o limitador cai no contador em memória e a métrica é descartada.
TIMEOUT_MONGO_MS = 2000


@lru_cache(maxsize=1)
def cliente_mongo() -> MongoClient | None:
    """`None` sem MONGODB_URL. `connect=False`: o startup não espera o Mongo;
    a conexão abre no primeiro uso."""
    if not settings.mongodb_url:
        return None
    return MongoClient(settings.mongodb_url, connect=False, serverSelectionTimeoutMS=TIMEOUT_MONGO_MS)
