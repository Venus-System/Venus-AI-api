# Conexão do Google Calendar do usuário (/v1/integracoes/google-calendar).
#
# O app faz o OAuth com PKCE no celular e manda só o `code` para cá; a troca
# pelo token acontece no servidor, que guarda o refresh_token cifrado no
# Postgres (funções do SDK em `integrations/google_calendar.py`). A identidade
# vem sempre do token do Firebase e o id do Postgres é resolvido aqui — nunca
# vem do corpo da requisição.

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from venus_sdk.integrations.google_calendar import (
	obter_credencial,
	pode_criar_eventos,
	remover_refresh_token,
	salvar_refresh_token,
	trocar_codigo_por_token,
)

from venus_api.app.api.deps import get_limitador, get_pool, get_session_id
from venus_api.app.core.config import settings
from venus_api.app.infra.ferramentas_rotina import google_calendar_configurado
from venus_api.app.infra.google_oauth import revogar_token_google
from venus_api.app.infra.postgres import resolver_usuario_postgres
from venus_api.app.schemas.google_calendar import ConexaoGoogleCalendar, EstadoGoogleCalendar

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integracoes/google-calendar", tags=["integrações"])


def _redirects_permitidos() -> set[str]:
	return {uri.strip() for uri in (settings.google_redirect_uris_permitidas or "").split(",") if uri.strip()}


async def _usuario_postgres(pool: Any, uid: str) -> int:
	if pool is None:
		raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Banco de dados indisponível.")
	user_id = await resolver_usuario_postgres(pool, uid)
	if user_id is None:
		raise HTTPException(status.HTTP_409_CONFLICT, "Usuário sem cadastro no Venus para este login.")
	return user_id


def _exigir_google_configurado() -> None:
	if not google_calendar_configurado():
		raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Integração com o Google Calendar não configurada.")


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def conectar(
	corpo: ConexaoGoogleCalendar,
	uid: str = Depends(get_session_id),
	pool: Any = Depends(get_pool),
	limitador: Any = Depends(get_limitador),
) -> Response:
	espera = await limitador.registrar(uid)
	if espera is not None:
		raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Muitas tentativas em pouco tempo.",
		                    headers={"Retry-After": str(espera)})
	if corpo.model_extra:
		# Só o nome dos campos (nunca o valor): a identidade vem do token.
		logger.warning("Campos ignorados no corpo da conexão do Google: %s", sorted(corpo.model_extra))
	if corpo.redirect_uri not in _redirects_permitidos():
		# Sem a lista, um code roubado poderia ser trocado com a URI de quem roubou.
		raise HTTPException(status.HTTP_400_BAD_REQUEST, "redirect_uri não permitida.")
	_exigir_google_configurado()
	user_id = await _usuario_postgres(pool, uid)

	try:
		token = await trocar_codigo_por_token(corpo.code, corpo.redirect_uri, code_verifier=corpo.code_verifier)
	except httpx.HTTPStatusError as erro:
		if erro.response is not None and erro.response.status_code < 500:
			raise HTTPException(status.HTTP_400_BAD_REQUEST, "Código do Google inválido ou expirado.") from erro
		raise HTTPException(status.HTTP_502_BAD_GATEWAY, "O Google não respondeu; tente de novo.") from erro
	except httpx.HTTPError as erro:
		raise HTTPException(status.HTTP_502_BAD_GATEWAY, "O Google não respondeu; tente de novo.") from erro

	escopo = token.get("scope") or ""
	if not pode_criar_eventos(escopo):
		raise HTTPException(
			status.HTTP_422_UNPROCESSABLE_ENTITY,
			"Permissão insuficiente: reconecte autorizando a Venus a criar eventos na sua agenda.",
		)
	refresh_token = token.get("refresh_token")
	if not refresh_token:
		# O Google só manda refresh_token com access_type=offline e
		# prompt=consent: sem ele, a Venus perderia o acesso em uma hora.
		raise HTTPException(
			status.HTTP_422_UNPROCESSABLE_ENTITY,
			"O Google não devolveu acesso contínuo: refaça a conexão pedindo acesso offline.",
		)
	await salvar_refresh_token(pool, user_id, refresh_token, escopo=escopo)
	logger.info("Google Calendar conectado (user_id=%s).", user_id)
	return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=EstadoGoogleCalendar)
async def consultar(uid: str = Depends(get_session_id), pool: Any = Depends(get_pool)) -> EstadoGoogleCalendar:
	user_id = await _usuario_postgres(pool, uid)
	try:
		credencial = await obter_credencial(pool, user_id)
	except Exception as erro:  # noqa: BLE001 — ex.: chave de cifra trocada
		logger.error("Não deu para ler a conexão do Google (user_id=%s): %s", user_id, type(erro).__name__)
		raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Não foi possível consultar a conexão agora.") from erro
	# Só o booleano: nem o token nem parte dele saem da API.
	return EstadoGoogleCalendar(conectado=credencial is not None)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def desconectar(uid: str = Depends(get_session_id), pool: Any = Depends(get_pool)) -> Response:
	user_id = await _usuario_postgres(pool, uid)
	try:
		credencial = await obter_credencial(pool, user_id)
	except Exception as erro:  # noqa: BLE001 — sem conseguir ler, apaga mesmo assim
		logger.warning("Não deu para ler o token antes de desconectar (%s); apagando sem revogar.",
		               type(erro).__name__)
		credencial = None
	if credencial is not None:
		try:
			await revogar_token_google(credencial[0])
		except Exception as erro:  # noqa: BLE001 — a desconexão local acontece de qualquer jeito
			logger.warning("Falha ao revogar o token no Google (%s); apagando o token local mesmo assim.",
			               type(erro).__name__)
	await remover_refresh_token(pool, user_id)
	logger.info("Google Calendar desconectado (user_id=%s).", user_id)
	return Response(status_code=status.HTTP_204_NO_CONTENT)
