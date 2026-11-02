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


class TurnoFalso:
	def __init__(self) -> None:
		self.registrados: list[dict] = []

	def registrar(self, estado_final):
		self.registrados.append(estado_final)


def _trace_falso(monkeypatch):
	"""Troca o trace do Langfuse por um que só anota o que recebeu."""
	marcador = object()
	turno = TurnoFalso()
	aberturas = []

	@contextmanager
	def turno_falso(usuario_id, conversation_id, mensagem):
		aberturas.append((usuario_id, conversation_id, mensagem))
		yield turno

	monkeypatch.setattr(tracing, "callbacks_do_trace", lambda: [marcador])
	monkeypatch.setattr(tracing, "turno_no_trace", turno_falso)
	return marcador, turno, aberturas


def test_chat_com_langfuse_marca_usuario_e_conversa(client, fluxo_falso, monkeypatch, auth_headers):
	marcador, _, aberturas = _trace_falso(monkeypatch)

	response = client.post(
		"/v1/chat",
		json={"mensagem": "oi", "conversation_id": "conversa-7"},
		headers=auth_headers,
	)

	assert response.status_code == 200
	assert fluxo_falso.chamadas[0]["config"]["callbacks"] == [marcador]
	assert aberturas == [(UID_DE_TESTE, "conversa-7", "oi")]


def test_chat_registra_o_estado_final_no_trace(client, fluxo_falso, monkeypatch, auth_headers):
	_, turno, _ = _trace_falso(monkeypatch)
	fluxo_falso.estado_final = {"rota": "produto", "aprovado_juiz": True, "tentativas_juiz": 1}

	client.post("/v1/chat", json={"mensagem": "esse sérum serve pra mim?"}, headers=auth_headers)

	[estado_final] = turno.registrados
	assert estado_final["rota"] == "produto"
	assert estado_final["resposta_final"] == fluxo_falso.resposta


# --- Resultado do turno no trace ---------------------------------------------------


def test_resultado_do_turno_le_o_estado_final():
	resultado = tracing.resultado_do_turno({
		"rota": "produto",
		"aprovado_juiz": False,
		"juiz_decidiu_por": "llm",
		"tentativas_juiz": 2,
		"alertas_alergia_anexados": 1,
		"expressao": "neutra",
		"resposta_final": "texto que não vai para o metadata",
		"historico": ["nem o histórico"],
	})

	assert resultado == {
		"rota": "produto",
		"entrada_bloqueada": False,
		"saida_bloqueada": False,
		"aprovado_juiz": False,
		"juiz_decidiu_por": "llm",
		"tentativas_juiz": 2,
		"alertas_alergia_anexados": 1,
		"expressao": "neutra",
	}


def test_resultado_do_turno_com_sdk_sem_os_campos_novos():
	"""SDK v0.4.0: sem `juiz_decidiu_por` nem `alertas_alergia_anexados`. O resto
	continua indo para o trace."""
	resultado = tracing.resultado_do_turno({"rota": "faq", "aprovado_juiz": True, "tentativas_juiz": 1})

	assert resultado["rota"] == "faq"
	assert resultado["juiz_decidiu_por"] is None
	assert resultado["alertas_alergia_anexados"] is None


def test_entrada_bloqueada_nao_repete_a_rota_do_turno_anterior():
	"""A entrada bloqueada não passa pelo roteador; a `rota` que volta pelo
	checkpointer é a da mensagem anterior."""
	resultado = tracing.resultado_do_turno({"entrada_bloqueada": True, "rota": "produto"})

	assert resultado["entrada_bloqueada"] is True
	assert resultado["rota"] is None
	assert resultado["tentativas_juiz"] == 0


def test_turno_grava_resposta_e_resultado_na_observacao():
	class Observacao:
		def update(self, **campos):
			self.campos = campos

	observacao = Observacao()

	tracing.TurnoNoTrace(observacao).registrar({"resposta_final": "Oi!", "rota": "rotina"})

	assert observacao.campos["output"] == "Oi!"
	assert observacao.campos["metadata"]["rota"] == "rotina"


def test_falha_do_langfuse_ao_registrar_nao_derruba_o_chat():
	class ObservacaoQuebrada:
		def update(self, **campos):
			raise ConnectionError("Langfuse fora do ar")

	tracing.TurnoNoTrace(ObservacaoQuebrada()).registrar({"rota": "faq"})


def test_sem_langfuse_o_turno_nao_faz_nada(monkeypatch):
	monkeypatch.setattr(tracing, "get_langfuse", lambda: None)

	with tracing.turno_no_trace(UID_DE_TESTE, "conversa", "oi") as turno:
		turno.registrar({"rota": "faq"})


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
