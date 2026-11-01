# Cliente do MongoDB compartilhado pela API (limite de mensagens e métricas).
#
# Um cliente só por processo: cada MongoClient abre o próprio pool de conexões
# e as próprias threads de monitoramento. O checkpointer e o store do SDK
# recebem a URL e montam o cliente deles.

from __future__ import annotations

from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pymongo import MongoClient

from venus_api.app.core.config import settings

# Com o Mongo fora do ar, cada operação desiste em 2 s em vez dos 30 s padrão
# do pymongo: o limitador cai no contador em memória e a métrica é descartada.
TIMEOUT_MONGO_MS = 2000


def mongodb_url_com_timeout_curto(url: str) -> str:
    """Adiciona timeouts de socket à URI sem alterar credenciais existentes."""
    partes = urlsplit(url)
    parametros = parse_qsl(partes.query, keep_blank_values=True)
    presentes = {chave.lower() for chave, _ in parametros}
    parametros += [
        (chave, str(TIMEOUT_MONGO_MS))
        for chave in ("socketTimeoutMS", "waitQueueTimeoutMS")
        if chave.lower() not in presentes
    ]
    return urlunsplit((partes.scheme, partes.netloc, partes.path, urlencode(parametros), partes.fragment))


@lru_cache(maxsize=1)
def cliente_mongo() -> MongoClient | None:
    """`None` sem MONGODB_URL. `connect=False`: o startup não espera o Mongo;
    a conexão abre no primeiro uso."""
    if not settings.mongodb_url:
        return None
    return MongoClient(
        mongodb_url_com_timeout_curto(settings.mongodb_url),
        connect=False,
        serverSelectionTimeoutMS=TIMEOUT_MONGO_MS,
        connectTimeoutMS=TIMEOUT_MONGO_MS,
    )
