# Índice do RAG do agente FAQ.
#
# `venus_sdk.rag.criar_indice_faq` escolhe o índice: a coleção do Qdrant
# quando `QDRANT_URL` está configurada (o conteúdo vem da ingestão do SDK), ou
# o índice local em memória sobre uma pasta de documentos. Para o índice
# local, o SDK não sabe onde a pasta fica (o pacote instalado via pip não leva
# a pasta `data/` do repositório do SDK), então os documentos do FAQ ficam aqui
# na API, em `venus_api/data/faq/` — dentro de `venus_api/`, que o Dockerfile
# já copia pra imagem.

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from venus_sdk.rag import criar_indice_faq as criar_indice_do_sdk

from venus_api.app.core.config import settings

logger = logging.getLogger(__name__)

PASTA_FAQ_PADRAO = Path(__file__).resolve().parents[2] / "data" / "faq"


def criar_indice_faq() -> Any | None:
    """Índice do FAQ, ou `None` se a pasta não existir ou não carregar.

    `None` não derruba a API (o resto do chat segue funcionando), mas o agente
    FAQ precisa do índice pra responder — por isso o log é `error`, pra
    aparecer no CloudWatch.
    """
    pasta = Path(settings.faq_dir) if settings.faq_dir else PASTA_FAQ_PADRAO
    try:
        return criar_indice_do_sdk(pasta)
    except Exception:
        logger.error(
            "Não consegui montar o índice do FAQ a partir de %s — o agente FAQ "
            "não vai conseguir responder.",
            pasta,
            exc_info=True,
        )
        return None
