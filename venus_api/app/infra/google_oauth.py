# Revogação do acesso ao Google Calendar quando o usuário desconecta.
#
# Apagar o refresh_token do nosso banco não basta: no Google, a Venus
# continuaria autorizada na conta do usuário até ele remover manualmente.
# Revogar primeiro tira o acesso dos dois lados.

from __future__ import annotations

from typing import Any

import httpx

URL_REVOGACAO = "https://oauth2.googleapis.com/revoke"
_TIMEOUT_SEGUNDOS = 10


async def revogar_token_google(token: str, *, transporte: Any | None = None) -> bool:
	"""Revoga o token no Google. Levanta em falha de rede ou resposta de erro;
	quem chama decide (o DELETE apaga o token local mesmo assim)."""
	async with httpx.AsyncClient(timeout=_TIMEOUT_SEGUNDOS, transport=transporte) as cliente:
		resposta = await cliente.post(URL_REVOGACAO, data={"token": token})
		resposta.raise_for_status()
	return True
