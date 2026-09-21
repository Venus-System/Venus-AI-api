from typing import Any

import pytest
from fastapi.testclient import TestClient

from venus_api.app.api.deps import get_fluxo_venus
from venus_api.app.core import security
from venus_api.app.core.config import settings
from venus_api.app.main import app
from venus_api.app.observability import middleware, tracing

UID_DE_TESTE = "uid-de-teste"
TOKEN_VALIDO = "token-valido"
TOKEN_INVALIDO = "token-invalido"


class FluxoFalso:
	"""Grafo de mentira: os testes não devem chamar Gemini/Groq de verdade."""

	def __init__(self) -> None:
		self.resposta = "Oii, tudo bem?? Me conta como posso te ajudar hoje!!"
		self.chamadas: list[dict[str, Any]] = []

	async def ainvoke(self, estado: dict, config: dict | None = None) -> dict:
		self.chamadas.append({"estado": estado, "config": config})
		return {"resposta_final": self.resposta}


class ColecaoFalsa:
	"""Coleção de mentira pra capturar as métricas que o middleware grava."""

	def __init__(self) -> None:
		self.documentos: list[dict[str, Any]] = []

	def insert_one(self, documento: dict[str, Any]) -> None:
		self.documentos.append(documento)


@pytest.fixture(autouse=True)
def sem_mongo_real(monkeypatch):
	"""Teste nunca fala com um Mongo de verdade, mesmo com MONGODB_URL no
	`.env` da máquina — o startup cai na versão em RAM e o middleware não
	grava métrica."""
	monkeypatch.setattr(settings, "mongodb_url", None)
	# Guarda a função real: a fixture `metricas` troca ela por uma falsa (sem
	# cache), e o teardown aqui roda antes do monkeypatch desfazer a troca.
	colecao_real = middleware._colecao_metricas
	colecao_real.cache_clear()
	yield
	colecao_real.cache_clear()


@pytest.fixture(autouse=True)
def sem_langfuse_real(monkeypatch):
	"""Teste nunca manda trace pro Langfuse, mesmo com as chaves no `.env`."""
	monkeypatch.setattr(settings, "langfuse_public_key", None)
	monkeypatch.setattr(settings, "langfuse_secret_key", None)
	langfuse_real = tracing.get_langfuse
	langfuse_real.cache_clear()
	yield
	langfuse_real.cache_clear()


@pytest.fixture
def metricas(monkeypatch) -> ColecaoFalsa:
	colecao = ColecaoFalsa()
	monkeypatch.setattr(middleware, "_colecao_metricas", lambda: colecao)
	return colecao


@pytest.fixture(autouse=True)
def firebase_falso(monkeypatch):
	"""Substitui a verificação do Firebase, mantendo a lógica de
	`validar_token` sendo exercida de verdade nos testes."""

	def verify_id_token(token: str) -> dict[str, str]:
		if token != TOKEN_VALIDO:
			# Tipo real do firebase_admin de propósito: ele NÃO herda de
			# ValueError, e supor que herdava já transformou um 401 em 500.
			raise security.auth.InvalidIdTokenError("token de teste inválido")
		return {"uid": UID_DE_TESTE}

	monkeypatch.setattr(security, "_inicializar_firebase", lambda: None)
	monkeypatch.setattr(security.auth, "verify_id_token", verify_id_token)


@pytest.fixture
def fluxo_falso() -> FluxoFalso:
	return FluxoFalso()


@pytest.fixture
def client(fluxo_falso: FluxoFalso):
	app.dependency_overrides[get_fluxo_venus] = lambda: fluxo_falso
	# `with` dispara o lifespan; sem ele o startup não roda e o grafo real
	# nunca seria montado (o que também deixaria passar um erro de startup).
	with TestClient(app) as cliente:
		yield cliente
	app.dependency_overrides.clear()


@pytest.fixture
def client_http(fluxo_falso: FluxoFalso):
	"""Igual ao `client`, mas devolve a resposta 500 em vez de relançar a
	exceção — é o que um cliente HTTP de verdade receberia."""
	app.dependency_overrides[get_fluxo_venus] = lambda: fluxo_falso
	with TestClient(app, raise_server_exceptions=False) as cliente:
		yield cliente
	app.dependency_overrides.clear()


@pytest.fixture
def auth_headers() -> dict[str, str]:
	return {"Authorization": f"Bearer {TOKEN_VALIDO}"}
