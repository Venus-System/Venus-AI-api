"""Item 5 da revisão técnica: limite de mensagens por usuário no /v1/chat e
tamanho máximo da mensagem."""

from __future__ import annotations

import asyncio

import pytest

from venus_api.app.core import security
from venus_api.app.core.config import settings
from venus_api.app.infra import limite_de_taxa

OUTRO_TOKEN = "token-de-outra-pessoa"


@pytest.fixture
def dois_usuarios(monkeypatch):
	"""Dois tokens válidos, de dois uids diferentes."""
	uids = {"token-valido": "uid-de-teste", OUTRO_TOKEN: "uid-de-outra-pessoa"}

	def verify_id_token(token):
		if token not in uids:
			raise security.auth.InvalidIdTokenError("token de teste inválido")
		return {"uid": uids[token]}

	monkeypatch.setattr(security.auth, "verify_id_token", verify_id_token)


def test_a_21a_mensagem_no_minuto_recebe_429_so_para_quem_passou(client, auth_headers, dois_usuarios, monkeypatch):
	monkeypatch.setattr(settings, "chat_limite_por_minuto", 20)
	for _ in range(20):
		assert client.post("/v1/chat", json={"mensagem": "oi"}, headers=auth_headers).status_code == 200

	excedeu = client.post("/v1/chat", json={"mensagem": "oi"}, headers=auth_headers)
	assert excedeu.status_code == 429
	assert 1 <= int(excedeu.headers["Retry-After"]) <= 60

	outro = client.post("/v1/chat", json={"mensagem": "oi"}, headers={"Authorization": f"Bearer {OUTRO_TOKEN}"})
	assert outro.status_code == 200


def test_limite_diario(client, auth_headers, monkeypatch):
	monkeypatch.setattr(settings, "chat_limite_por_minuto", 100)
	monkeypatch.setattr(settings, "chat_limite_por_dia", 3)
	for _ in range(3):
		assert client.post("/v1/chat", json={"mensagem": "oi"}, headers=auth_headers).status_code == 200
	excedeu = client.post("/v1/chat", json={"mensagem": "oi"}, headers=auth_headers)
	assert excedeu.status_code == 429 and int(excedeu.headers["Retry-After"]) > 60


def test_mensagem_acima_de_4000_caracteres_recebe_422(client, auth_headers):
	assert client.post("/v1/chat", json={"mensagem": "a" * 4001}, headers=auth_headers).status_code == 422
	assert client.post("/v1/chat", json={"mensagem": "a" * 4000}, headers=auth_headers).status_code == 200


class _ColecaoFalsa:
	"""Faz o papel da coleção do Mongo: find_one_and_update com $inc/upsert."""

	def __init__(self):
		self.documentos, self.indices = {}, []

	def create_index(self, campo, **opcoes):
		self.indices.append((campo, opcoes))

	def find_one_and_update(self, filtro, atualizacao, upsert, return_document):
		documento = self.documentos.setdefault(filtro["_id"], {"_id": filtro["_id"], "contador": 0,
		                                                       **atualizacao["$setOnInsert"]})
		documento["contador"] += atualizacao["$inc"]["contador"]
		return documento


def test_limitador_mongo_conta_por_janela_e_expira_sozinho(monkeypatch):
	monkeypatch.setattr(settings, "chat_limite_por_minuto", 2)
	monkeypatch.setattr(settings, "chat_limite_por_dia", 300)
	colecao = _ColecaoFalsa()
	limitador = limite_de_taxa.LimitadorMongo(colecao)

	resultados = [asyncio.run(limitador.registrar("uid-1")) for _ in range(3)]
	assert resultados[:2] == [None, None] and resultados[2] is not None
	assert asyncio.run(limitador.registrar("uid-2")) is None
	assert ("expira_em", {"expireAfterSeconds": 0}) in colecao.indices
