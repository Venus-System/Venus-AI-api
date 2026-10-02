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


# --- Revisão técnica 2, item 4: Mongo fora do ar não derruba a API -----------


class _ColecaoForaDoAr(_ColecaoFalsa):
	"""Coleção cujo Mongo caiu: toda operação levanta erro de conexão."""

	def __init__(self, falha_no_indice=True, falha_na_contagem=True):
		super().__init__()
		self.falha_no_indice, self.falha_na_contagem = falha_no_indice, falha_na_contagem
		self.tentativas_de_indice = 0

	def create_index(self, campo, **opcoes):
		self.tentativas_de_indice += 1
		if self.falha_no_indice:
			raise ConnectionError("Mongo fora do ar")
		super().create_index(campo, **opcoes)

	def find_one_and_update(self, *args, **kwargs):
		if self.falha_na_contagem:
			raise ConnectionError("Mongo fora do ar")
		return super().find_one_and_update(*args, **kwargs)


def test_create_index_falhando_nao_impede_criar_o_limitador():
	colecao = _ColecaoForaDoAr()
	limite_de_taxa.LimitadorMongo(colecao)  # não levanta
	assert colecao.tentativas_de_indice == 0  # o índice só é criado no primeiro registrar


def test_indice_e_tentado_de_novo_na_chamada_seguinte_se_falhar(monkeypatch):
	monkeypatch.setattr(settings, "chat_limite_por_minuto", 100)
	colecao = _ColecaoForaDoAr(falha_no_indice=True, falha_na_contagem=False)
	limitador = limite_de_taxa.LimitadorMongo(colecao)
	asyncio.run(limitador.registrar("uid-1"))
	colecao.falha_no_indice = False
	asyncio.run(limitador.registrar("uid-1"))
	asyncio.run(limitador.registrar("uid-1"))
	assert colecao.tentativas_de_indice == 2
	assert ("expira_em", {"expireAfterSeconds": 0}) in colecao.indices


def test_mongo_falhando_na_contagem_cai_no_limite_em_memoria(monkeypatch, caplog):
	monkeypatch.setattr(settings, "chat_limite_por_minuto", 20)
	monkeypatch.setattr(settings, "chat_limite_por_dia", 300)
	limitador = limite_de_taxa.LimitadorMongo(_ColecaoForaDoAr())

	resultados = [asyncio.run(limitador.registrar("uid-1")) for _ in range(21)]
	assert resultados[:20] == [None] * 20
	assert resultados[20] is not None and resultados[20] >= 1
	assert any(r.levelname == "ERROR" and "memória" in r.getMessage() for r in caplog.records)


def test_chat_nao_devolve_500_com_o_limitador_falhando(client_http, auth_headers):
	from venus_api.app.api.deps import get_limitador
	from venus_api.app.main import app

	app.dependency_overrides[get_limitador] = lambda: limite_de_taxa.LimitadorMongo(_ColecaoForaDoAr())
	resposta = client_http.post("/v1/chat", json={"mensagem": "oi"}, headers=auth_headers)
	assert resposta.status_code == 200


def test_criar_limitador_nao_conecta_no_mongo_no_startup(monkeypatch):
	import time

	# Porta fechada: com uma conexão bloqueante no startup, isso levaria o
	# timeout de seleção de servidor do pymongo (30 s) e depois levantaria.
	monkeypatch.setattr(settings, "mongodb_url", "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=3000")
	inicio = time.monotonic()
	limitador = limite_de_taxa.criar_limitador()
	assert isinstance(limitador, limite_de_taxa.LimitadorMongo)
	assert time.monotonic() - inicio < 2
