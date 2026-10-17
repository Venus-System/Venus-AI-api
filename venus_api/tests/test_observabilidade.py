from contextlib import contextmanager

from venus_api.app.core import security
from venus_api.app.observability import middleware, tracing
from venus_api.tests.conftest import UID_DE_TESTE


def test_middleware_registra_chat_com_sucesso(client, metricas, auth_headers):
	client.post("/v1/chat", json={"mensagem": "oi"}, headers=auth_headers)

	assert len(metricas.documentos) == 1
	registro = metricas.documentos[0]
	assert registro["metodo"] == "POST"
	assert registro["rota"] == "/v1/chat"
	assert registro["status"] == 200
	assert registro["duracao_ms"] >= 0


def test_middleware_registra_recusa_de_autenticacao(client, metricas):
	client.post("/v1/chat", json={"mensagem": "oi"})

	assert metricas.documentos[0]["status"] == 401


def test_middleware_registra_erro_nao_tratado_como_500(client_http, metricas, monkeypatch, auth_headers):
	"""Erro que escapa sem virar resposta HTTP é o que mais importa contar na
	taxa de erro — e é justamente o caso em que `call_next` levanta."""

	def falha_credencial(token):
		raise security.auth.CertificateFetchError("sem credencial", None)

	monkeypatch.setattr(security.auth, "verify_id_token", falha_credencial)

	response = client_http.post("/v1/chat", json={"mensagem": "oi"}, headers=auth_headers)

	assert response.status_code == 500
	assert metricas.documentos[0]["status"] == 500


def test_middleware_ignora_health(client, metricas):
	client.get("/v1/health")

	assert metricas.documentos == []


def test_middleware_nao_derruba_requisicao_se_gravacao_falhar(client, monkeypatch, auth_headers):
	class ColecaoQuebrada:
		def insert_one(self, documento):
			raise ConnectionError("Mongo fora do ar")

	monkeypatch.setattr(middleware, "_colecao_metricas", lambda: ColecaoQuebrada())

	response = client.post("/v1/chat", json={"mensagem": "oi"}, headers=auth_headers)

	assert response.status_code == 200


def test_chat_sem_langfuse_nao_passa_callbacks(client, fluxo_falso, auth_headers):
	client.post("/v1/chat", json={"mensagem": "oi"}, headers=auth_headers)

	assert fluxo_falso.chamadas[0]["config"]["callbacks"] == []


def test_chat_com_langfuse_marca_usuario_e_conversa(client, fluxo_falso, monkeypatch, auth_headers):
	marcador = object()
	atributos = []

	@contextmanager
	def atributos_falsos(usuario_id, conversation_id):
		atributos.append((usuario_id, conversation_id))
		yield

	monkeypatch.setattr(tracing, "callbacks_do_trace", lambda: [marcador])
	monkeypatch.setattr(tracing, "atributos_do_trace", atributos_falsos)

	response = client.post(
		"/v1/chat",
		json={"mensagem": "oi", "conversation_id": "conversa-7"},
		headers=auth_headers,
	)

	assert response.status_code == 200
	assert fluxo_falso.chamadas[0]["config"]["callbacks"] == [marcador]
	assert atributos == [(UID_DE_TESTE, "conversa-7")]


# --- Revisão técnica 4: a métrica não segura a resposta --------------------------


def _pedido(caminho: str = "/v1/chat"):
	from starlette.requests import Request

	return Request({
		"type": "http", "method": "POST", "path": caminho, "root_path": "", "scheme": "http",
		"server": ("teste", 80), "headers": [], "query_string": b"",
	})


def test_metrica_e_gravada_depois_que_a_resposta_sai(metricas):
	"""Gravar no Mongo antes de devolver a resposta atrasava toda requisição
	(até o timeout do Mongo, com ele fora do ar). A gravação vai como tarefa
	de segundo plano da resposta."""
	import asyncio

	from starlette.responses import Response

	async def call_next(_pedido):
		return Response("ok", status_code=201)

	resposta = asyncio.run(middleware.medir_requisicao(_pedido(), call_next))

	assert metricas.documentos == []
	asyncio.run(resposta.background())
	assert metricas.documentos[0]["status"] == 201
	assert metricas.documentos[0]["rota"] == "/v1/chat"


def test_metrica_preserva_a_tarefa_de_segundo_plano_da_propria_resposta(metricas):
	import asyncio

	from starlette.background import BackgroundTask
	from starlette.responses import Response

	executadas = []

	async def call_next(_pedido):
		return Response("ok", background=BackgroundTask(executadas.append, "da rota"))

	resposta = asyncio.run(middleware.medir_requisicao(_pedido(), call_next))
	asyncio.run(resposta.background())

	assert executadas == ["da rota"]
	assert len(metricas.documentos) == 1
