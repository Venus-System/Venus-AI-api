"""Item 1 da revisão técnica 3: endpoints para o app conectar, consultar e
desconectar o Google Calendar. A identidade vem do token do Firebase e o id do
Postgres é resolvido pela API — nunca vem do corpo."""

from __future__ import annotations

from typing import Any

import pytest

from venus_api.app.api.deps import get_pool
from venus_api.app.api.v1.endpoints import google_calendar as endpoint
from venus_api.app.core.config import settings
from venus_api.app.main import app

URL = "/v1/integracoes/google-calendar"
REDIRECT_OK = "com.venus.app:/oauth2redirect"
ESCOPO_COMPLETO = "https://www.googleapis.com/auth/calendar.freebusy https://www.googleapis.com/auth/calendar.events"
REFRESH_TOKEN = "1//refresh-token-secreto"


class _Registro:
	def __init__(self) -> None:
		self.salvos: list[tuple] = []
		self.removidos: list[int] = []
		self.trocas: list[tuple] = []
		self.revogados: list[str] = []
		self.resolvidos: list[str] = []
		self.verificadores: list[str | None] = []


@pytest.fixture
def google(monkeypatch) -> _Registro:
	registro = _Registro()
	for variavel in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_TOKEN_ENCRYPTION_KEY"):
		monkeypatch.setenv(variavel, "valor-de-teste")
	monkeypatch.setattr(settings, "google_redirect_uris_permitidas", f"{REDIRECT_OK}, https://app.venus.example/cb")
	app.dependency_overrides[get_pool] = lambda: object()

	async def resolver(pool, uid):
		registro.resolvidos.append(uid)
		return 7

	async def trocar(code, redirect_uri, **kwargs):
		registro.trocas.append((code, redirect_uri))
		registro.verificadores.append(kwargs.get("code_verifier"))
		return {"access_token": "at", "refresh_token": REFRESH_TOKEN, "scope": ESCOPO_COMPLETO}

	async def salvar(pool, user_id, refresh_token, *, escopo):
		registro.salvos.append((user_id, refresh_token, escopo))

	async def obter(pool, user_id):
		return (REFRESH_TOKEN, ESCOPO_COMPLETO) if registro.salvos or user_id == 7 else None

	async def remover(pool, user_id):
		registro.removidos.append(user_id)

	async def revogar(token):
		registro.revogados.append(token)
		return True

	monkeypatch.setattr(endpoint, "resolver_usuario_postgres", resolver)
	monkeypatch.setattr(endpoint, "trocar_codigo_por_token", trocar)
	monkeypatch.setattr(endpoint, "salvar_refresh_token", salvar)
	monkeypatch.setattr(endpoint, "obter_credencial", obter)
	monkeypatch.setattr(endpoint, "remover_refresh_token", remover)
	monkeypatch.setattr(endpoint, "revogar_token_google", revogar)
	yield registro
	app.dependency_overrides.pop(get_pool, None)


def _post(client, headers, **corpo: Any):
	return client.post(URL, json={"code": "codigo-do-google", "redirect_uri": REDIRECT_OK, **corpo}, headers=headers)


# --- POST --------------------------------------------------------------------


def test_conectar_troca_o_codigo_e_salva_cifrado(client, auth_headers, google):
	resposta = _post(client, auth_headers)
	assert resposta.status_code == 204
	assert google.trocas == [("codigo-do-google", REDIRECT_OK)]
	assert google.salvos == [(7, REFRESH_TOKEN, ESCOPO_COMPLETO)]


def test_code_verifier_do_pkce_vai_para_a_troca(client, auth_headers, google):
	verificador = "v" * 43
	assert _post(client, auth_headers, code_verifier=verificador).status_code == 204
	assert google.verificadores == [verificador]


def test_escopo_insuficiente_devolve_422(client, auth_headers, google, monkeypatch):
	async def trocar(code, redirect_uri, **kwargs):
		return {"refresh_token": REFRESH_TOKEN, "scope": "https://www.googleapis.com/auth/calendar.freebusy"}

	monkeypatch.setattr(endpoint, "trocar_codigo_por_token", trocar)
	resposta = _post(client, auth_headers)
	assert resposta.status_code == 422 and "criar eventos" in resposta.json()["detail"]
	assert google.salvos == []


def test_redirect_uri_fora_da_lista_devolve_400(client, auth_headers, google):
	resposta = _post(client, auth_headers, redirect_uri="https://atacante.example/cb")
	assert resposta.status_code == 400 and google.trocas == []


def test_sem_lista_de_redirect_nenhuma_uri_e_aceita(client, auth_headers, google, monkeypatch):
	monkeypatch.setattr(settings, "google_redirect_uris_permitidas", None)
	assert _post(client, auth_headers).status_code == 400


def test_sem_token_do_firebase_devolve_401(client, google):
	assert _post(client, {}).status_code == 401
	assert client.get(URL).status_code == 401
	assert client.delete(URL).status_code == 401


def test_usuario_sem_cadastro_no_postgres_devolve_409(client, auth_headers, google, monkeypatch):
	async def sem_mapeamento(pool, uid):
		return None

	monkeypatch.setattr(endpoint, "resolver_usuario_postgres", sem_mapeamento)
	assert _post(client, auth_headers).status_code == 409
	assert client.get(URL, headers=auth_headers).status_code == 409
	assert client.delete(URL, headers=auth_headers).status_code == 409


def test_campos_de_identidade_no_corpo_sao_ignorados(client, auth_headers, google):
	resposta = _post(client, auth_headers, user_id=99, usuario_id_postgres=99)
	assert resposta.status_code == 204
	assert google.salvos[0][0] == 7  # o id resolvido pelo token, não o 99 do corpo
	assert google.resolvidos == ["uid-de-teste"]


def test_codigo_invalido_devolve_400(client, auth_headers, google, monkeypatch):
	import httpx

	async def recusado(code, redirect_uri, **kwargs):
		requisicao = httpx.Request("POST", "https://oauth2.googleapis.com/token")
		raise httpx.HTTPStatusError("invalid_grant", request=requisicao, response=httpx.Response(400, request=requisicao))

	monkeypatch.setattr(endpoint, "trocar_codigo_por_token", recusado)
	assert _post(client, auth_headers).status_code == 400


def test_post_respeita_o_limite_de_mensagens(client, auth_headers, google, monkeypatch):
	monkeypatch.setattr(settings, "chat_limite_por_minuto", 2)
	assert [_post(client, auth_headers).status_code for _ in range(3)] == [204, 204, 429]


def test_google_nao_configurado_devolve_503(client, auth_headers, google, monkeypatch):
	monkeypatch.delenv("GOOGLE_CLIENT_SECRET")
	assert _post(client, auth_headers).status_code == 503


# --- GET ---------------------------------------------------------------------


def test_get_diz_so_se_esta_conectado_e_nunca_expoe_token(client, auth_headers, google):
	resposta = client.get(URL, headers=auth_headers)
	assert resposta.status_code == 200 and resposta.json() == {"conectado": True}
	assert REFRESH_TOKEN not in resposta.text and "refresh" not in resposta.text


def test_get_sem_conexao(client, auth_headers, google, monkeypatch):
	async def nada(pool, user_id):
		return None

	monkeypatch.setattr(endpoint, "obter_credencial", nada)
	assert client.get(URL, headers=auth_headers).json() == {"conectado": False}


# --- DELETE ------------------------------------------------------------------


def test_delete_revoga_e_apaga(client, auth_headers, google):
	assert client.delete(URL, headers=auth_headers).status_code == 204
	assert google.revogados == [REFRESH_TOKEN] and google.removidos == [7]


def test_delete_apaga_mesmo_com_a_revogacao_falhando(client, auth_headers, google, monkeypatch, caplog):
	async def revogacao_quebrada(token):
		raise RuntimeError("Google fora do ar")

	monkeypatch.setattr(endpoint, "revogar_token_google", revogacao_quebrada)
	assert client.delete(URL, headers=auth_headers).status_code == 204
	assert google.removidos == [7]
	assert any(r.levelname == "WARNING" and "revog" in r.getMessage() for r in caplog.records)
	assert all(REFRESH_TOKEN not in r.getMessage() for r in caplog.records)


def test_delete_sem_conexao_e_idempotente(client, auth_headers, google, monkeypatch):
	async def nada(pool, user_id):
		return None

	monkeypatch.setattr(endpoint, "obter_credencial", nada)
	assert client.delete(URL, headers=auth_headers).status_code == 204
	assert google.revogados == [] and google.removidos == [7]


# --- revogação no Google ----------------------------------------------------------


def test_revogar_token_chama_o_endpoint_do_google(monkeypatch):
	import asyncio

	import httpx

	from venus_api.app.infra import google_oauth

	pedidos = []

	def responder(requisicao):
		pedidos.append(requisicao)
		return httpx.Response(200)

	transporte = httpx.MockTransport(responder)
	assert asyncio.run(google_oauth.revogar_token_google("tok", transporte=transporte)) is True
	assert str(pedidos[0].url) == "https://oauth2.googleapis.com/revoke"
	assert pedidos[0].content == b"token=tok"
