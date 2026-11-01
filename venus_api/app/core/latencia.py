"""Ajustes seguros para manter o caminho de chat dentro do timeout do cliente.

O SDK monta o grafo a partir das variáveis de ambiente no startup. A EC2 já
possui uma cadeia configurada, mas a configuração antiga colocava o modelo de
raciocínio gpt-oss antes dos modelos Mistral de baixa latência. Como o deploy
automático não sobrescreve segredos/variáveis da máquina, fazemos uma migração
compatível no startup: apenas reordenamos uma cadeia que já contenha os
modelos rápidos conhecidos e preservamos os demais modelos como fallback.
"""

from __future__ import annotations

import os


_VARIAVEIS_DE_CADEIA = ("LLM_CADEIA_RAPIDO", "LLM_CADEIA_ESPECIALISTA")
_MODELOS_RAPIDOS = (
    "mistral:ministral-8b-latest",
    "mistral:ministral-14b-latest",
)


def priorizar_modelos_rapidos() -> None:
    """Coloca Mistral rápido antes de modelos lentos, sem trocar credenciais.

    A migração é ativada por padrão para corrigir a configuração antiga da
    EC2. Pode ser desativada explicitamente com
    ``VENUS_PRIORIZAR_MODELOS_RAPIDOS=0`` se alguma instalação precisar
    manter uma ordem própria.
    """

    if os.getenv("VENUS_PRIORIZAR_MODELOS_RAPIDOS", "1").strip().lower() in {
        "0",
        "false",
        "nao",
        "não",
        "no",
    }:
        return

    for variavel in _VARIAVEIS_DE_CADEIA:
        cadeia = os.getenv(variavel)
        if not cadeia:
            continue

        modelos = [modelo.strip() for modelo in cadeia.split(",") if modelo.strip()]
        rapidos = [modelo for modelo in _MODELOS_RAPIDOS if modelo in modelos]
        if not rapidos:
            continue

        restantes = [modelo for modelo in modelos if modelo not in rapidos]
        os.environ[variavel] = ",".join(rapidos + restantes)
