# Modelos Pydantic da conexão do Google Calendar.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ConexaoGoogleCalendar(BaseModel):
	# Campos desconhecidos são aceitos e IGNORADOS (ex.: `user_id`): a
	# identidade vem só do token do Firebase. O endpoint loga os nomes.
	model_config = ConfigDict(extra="allow")

	# `code` devolvido pelo Google ao app depois do consentimento (OAuth com PKCE).
	code: str = Field(min_length=1, max_length=2048)
	# A mesma redirect_uri usada no pedido de autorização; precisa estar em
	# GOOGLE_REDIRECT_URIS_PERMITIDAS.
	redirect_uri: str = Field(min_length=1, max_length=2048)
	# O verificador do PKCE gerado pelo app: o Google exige o mesmo na troca.
	code_verifier: str | None = Field(default=None, min_length=43, max_length=128)


class EstadoGoogleCalendar(BaseModel):
	conectado: bool
