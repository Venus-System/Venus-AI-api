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


def descrever_indice(indice: Any) -> str:
    """Tipo do índice e do embedding, para o log do startup:
    `IndiceQdrant`, `IndiceRAG/FastEmbed` ou `IndiceRAG/EmbeddingsHash`."""
    embeddings = getattr(indice, "embeddings", None)
    if embeddings is None:
        return type(indice).__name__
    tipo = type(embeddings).__name__
    return f"{type(indice).__name__}/{'FastEmbed' if tipo == 'EmbeddingsFastEmbed' else tipo}"


def criar_indice_faq() -> Any | None:
    """Índice do FAQ, ou `None` se a pasta não existir ou não carregar.

    `None` não derruba a API (o resto do chat segue funcionando), mas o agente
    FAQ precisa do índice pra responder — por isso o log é `error`, pra
    aparecer no CloudWatch.
    """
    pasta = Path(settings.faq_dir) if settings.faq_dir else PASTA_FAQ_PADRAO
    try:
        indice = criar_indice_do_sdk(pasta)
    except Exception:
        logger.error(
            "Não consegui montar o índice do FAQ a partir de %s — o agente FAQ "
            "não vai conseguir responder.",
            pasta,
            exc_info=True,
        )
        return None
    descricao = descrever_indice(indice)
    logger.info("Índice do FAQ: %s", descricao)
    if descricao.endswith("/EmbeddingsHash") and settings.ambiente == "producao":
        # Busca por palavras, não semântica: responde pior e não sabe dizer
        # "não sei" (ver docs/avaliacao-rag.md no SDK). Na imagem o modelo já
        # vem baixado, então isso indica imagem ou extra `rag` quebrados.
        logger.error(
            "Índice do FAQ em produção com %s (FastEmbed indisponível) — o FAQ vai responder pior.",
            descricao,
        )
    return indice
