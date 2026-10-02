# Tools externas do agente FAQ: servidores MCP e agentes A2A de terceiros.
#
# O SDK monta as tools (`get_mcp_tools`, `montar_tool_a2a`); aqui só decidimos
# QUAIS carregar, a partir das variáveis de ambiente. As duas são opcionais e
# nunca derrubam o startup: servidor fora do ar ou JSON inválido viram lista
# vazia e um log.

from __future__ import annotations

import json
import logging
from typing import Any

from venus_sdk.a2a_client import montar_tool_a2a
from venus_sdk.mcp.tools import get_mcp_tools

from venus_api.app.core.config import settings

logger = logging.getLogger(__name__)


def _json_de(variavel: str, valor: str | None) -> dict[str, Any] | None:
    if not valor:
        return None
    try:
        dados = json.loads(valor)
    except ValueError:
        logger.error("%s não é um JSON válido — ignorando.", variavel)
        return None
    return dados if isinstance(dados, dict) and dados else None


async def carregar_tools_faq_extras() -> list[Any]:
    """Tools MCP (de `MCP_SERVERS`) e A2A (de `A2A_AGENTES_EXTERNOS`) para o
    agente FAQ, ou `[]` se nada estiver configurado."""
    tools: list[Any] = []

    # TODO(produto): só carrega MCP com MCP_SERVERS configurado. Sem a
    # variável, o SDK sobe o próprio servidor MCP da Venus num subprocesso
    # (`config_padrao_venus`) — dentro do container isso duplicaria as tools
    # que o grafo já tem e gastaria memória. Se um dia quiserem expor as tools
    # da Venus por MCP também aqui, é decisão consciente, não padrão.
    servidores = _json_de("MCP_SERVERS", settings.mcp_servers)
    if servidores:
        tools += await get_mcp_tools(servidores)

    agentes = _json_de("A2A_AGENTES_EXTERNOS", settings.a2a_agentes_externos)
    if agentes:
        tools += montar_tool_a2a(agentes)

    if tools:
        logger.info("Agente FAQ com %d tool(s) externa(s).", len(tools))
    return tools
