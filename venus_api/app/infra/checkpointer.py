# Monta o checkpointer do LangGraph (memória de curto prazo / sessão).
#
# O SDK do Venus já entrega as duas implementações prontas
# (`venus_sdk.memory.checkpointer`); aqui só escolhemos qual usar conforme a
# configuração. Sem `MONGODB_URL`, cai na versão em RAM — que é o que permite
# rodar os testes e subir a API localmente sem banco.

from __future__ import annotations

import logging
from typing import Any

from venus_sdk.memory.checkpointer import (
    criar_checkpointer_em_memoria,
    criar_checkpointer_mongo,
)

from venus_api.app.core.config import settings

logger = logging.getLogger(__name__)


def criar_checkpointer() -> Any:
    """Checkpointer do grafo: histórico de UMA conversa, por `thread_id`.

    Com Mongo, a conversa sobrevive a restart da API e funciona com várias
    instâncias ao mesmo tempo. A versão em RAM perde tudo ao reiniciar, então
    o aviso abaixo é gritante de propósito: em produção isso seria um erro de
    configuração silencioso.
    """
    if not settings.mongodb_url:
        logger.warning(
            "MONGODB_URL não configurada — usando checkpointer em RAM. "
            "O histórico das conversas será perdido ao reiniciar a API."
        )
        return criar_checkpointer_em_memoria()

    return criar_checkpointer_mongo(settings.mongodb_url)
