# Busca na web do agente FAQ pelo servidor MCP oficial da Tavily.
#
# O servidor (`tavily-mcp`, versão fixada no Dockerfile) é instalado na
# imagem no build e roda como subprocesso stdio — o container nunca baixa
# pacote no startup. A sessão é aberta em segundo plano no `lifespan` (não
# segura o health check) e fica aberta enquanto a API roda; o SDK
# (`rag.web.BuscaWebMcp`) usa a tool `tavily_search` quando ela está pronta e,
# se a sessão não abriu ou caiu, faz a busca direta.
#
# Só a busca na web passa por aqui: nenhuma tool MCP de banco de dados é
# exposta ao LLM.

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from venus_api.app.core.config import settings

logger = logging.getLogger(__name__)

NOME_DO_SERVIDOR = "tavily"
NOME_DA_TOOL = "tavily_search"
_ESPERA_PARA_FECHAR_SEGUNDOS = 5


def config_do_tavily_mcp() -> dict[str, Any]:
	"""Servidor MCP da Tavily por stdio, com a chave no ambiente dele."""
	return {
		NOME_DO_SERVIDOR: {
			"transport": "stdio",
			"command": settings.tavily_mcp_comando,
			"args": [],
			# O subprocesso herda o PATH (para achar o node) e recebe a chave.
			"env": {**os.environ, "TAVILY_API_KEY": settings.tavily_api_key or ""},
		}
	}


class SessaoTavilyMcp:
	"""Mantém uma sessão MCP aberta com o servidor da Tavily.

	`tool` é a `tavily_search` carregada, ou `None` enquanto a sessão não abriu
	(ou se falhou — `encerrada` fica True). `abrir()` roda até `fechar()`."""

	def __init__(self) -> None:
		self.tool: Any | None = None
		self.encerrada = False
		self._fechar = asyncio.Event()

	async def abrir(self) -> None:
		from langchain_mcp_adapters.tools import load_mcp_tools
		from venus_sdk.mcp.tools import get_mcp_client

		try:
			cliente = get_mcp_client(config_do_tavily_mcp())
			async with cliente.session(NOME_DO_SERVIDOR) as sessao:
				tools = await load_mcp_tools(sessao)
				self.tool = next((tool for tool in tools if tool.name == NOME_DA_TOOL), None)
				if self.tool is None:
					logger.warning("Servidor MCP da Tavily sem a tool %s; busca web direta.", NOME_DA_TOOL)
					return
				logger.info("Busca web via MCP (Tavily) ativa.")
				await self._fechar.wait()
		except Exception as erro:  # noqa: BLE001 — sem o servidor, a busca é direta
			# Fechada no desligamento enquanto ainda abria (o node leva alguns
			# segundos para subir): não é falha.
			if not self._fechar.is_set():
				logger.warning("Não deu para abrir o servidor MCP da Tavily (%s); busca web direta.",
				               type(erro).__name__)
		finally:
			self.tool = None
			self.encerrada = True

	async def fechar(self, tarefa: asyncio.Task | None) -> None:
		self._fechar.set()
		if tarefa is not None:
			try:
				await asyncio.wait_for(tarefa, _ESPERA_PARA_FECHAR_SEGUNDOS)
			except (asyncio.TimeoutError, asyncio.CancelledError):
				tarefa.cancel()
