# Índice do RAG do agente FAQ.
#
# `venus_sdk.rag.criar_indice_faq` escolhe o índice: a coleção do Qdrant
# quando `QDRANT_URL` está configurada (o conteúdo vem da ingestão do SDK), ou
# o índice local em memória sobre uma pasta de documentos. Os documentos do
# FAQ vêm empacotados no SDK (`venus_sdk.config.settings.FAQ_DIR`): uma fonte
# da verdade só, sem cópia aqui na API. `FAQ_DIR` no ambiente aponta para
# outra pasta.

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from venus_sdk.config.settings import FAQ_DIR as FAQ_DO_SDK
from venus_sdk.rag import criar_indice_faq as criar_indice_do_sdk

from venus_api.app.core.config import settings

logger = logging.getLogger(__name__)

PASTA_FAQ_PADRAO = Path(FAQ_DO_SDK)


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


class IndiceDoFaqEmSegundoPlano:
    """Índice do FAQ construído depois de a API começar a responder.

    Criar o índice local pode levar segundos (modelo de embeddings, trechos
    do FAQ): feito no startup, atrasava o health check do ECS. Este objeto vai
    para o grafo na hora, com `pronto=False`; o SDK não monta as tools do FAQ
    enquanto ele não fica pronto, e o agente FAQ responde a mensagem de
    indisponibilidade (`erro_tecnico`), tentando de novo na pergunta seguinte."""

    def __init__(self) -> None:
        self.indice: Any | None = None
        self.pronto = False
        self.falhou = False
        self.tipo: str | None = None

    def buscar(self, consulta: str, k: int = 3, score_minimo: float | None = None) -> list[dict[str, Any]]:
        if self.indice is None:
            raise RuntimeError("o índice do FAQ ainda não está pronto")
        return self.indice.buscar(consulta, k=k, score_minimo=score_minimo)

    async def construir(self) -> None:
        """Roda numa thread (a criação é síncrona e pesada) e marca pronto."""
        indice = await asyncio.to_thread(criar_indice_faq)
        if indice is None:
            # criar_indice_faq já logou o error; o FAQ segue indisponível.
            self.falhou = True
            return
        self.indice, self.tipo, self.pronto = indice, descrever_indice(indice), True

    def estado(self) -> dict[str, Any]:
        """Para o health check detalhado."""
        estado: dict[str, Any] = {"pronto": self.pronto, "tipo": self.tipo}
        if self.falhou:
            estado["falhou"] = True
        return estado
