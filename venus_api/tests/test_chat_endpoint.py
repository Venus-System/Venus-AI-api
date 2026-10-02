from venus_api.tests.conftest import TOKEN_INVALIDO, UID_DE_TESTE


def test_health_endpoint(client):
	response = client.get("/v1/health")

	assert response.status_code == 200
	assert response.json() == {"status": "ok"}


def test_chat_sem_token_e_recusado(client):
	response = client.post("/v1/chat", json={"mensagem": "oi"})

	assert response.status_code == 401


def test_chat_com_token_invalido_e_recusado(client):
	response = client.post(
		"/v1/chat",
		json={"mensagem": "oi"},
		headers={"Authorization": f"Bearer {TOKEN_INVALIDO}"},
	)

	assert response.status_code == 401


def test_chat_com_credencial_quebrada_nao_vira_401(client_http, monkeypatch, auth_headers):
	"""Falha de credencial/rede é problema de servidor (500), não de token
	(401) — senão um erro de configuração se disfarça de token inválido."""
	from venus_api.app.core import security

	def falha_credencial(token):
		raise security.auth.CertificateFetchError("sem credencial", None)

	monkeypatch.setattr(security.auth, "verify_id_token", falha_credencial)

	response = client_http.post("/v1/chat", json={"mensagem": "oi"}, headers=auth_headers)

	assert response.status_code == 500


def test_chat_com_token_responde(client, fluxo_falso, auth_headers):
	response = client.post("/v1/chat", json={"mensagem": "oi"}, headers=auth_headers)

	assert response.status_code == 200
	corpo = response.json()
	assert corpo["resposta"] == fluxo_falso.resposta
	assert corpo["conversation_id"] == UID_DE_TESTE

	estado = fluxo_falso.chamadas[0]["estado"]
	assert estado["mensagem_usuario"] == "oi"
	# O uid vem assinado dentro do token, nunca do corpo da requisição.
	assert estado["usuario_id"] == UID_DE_TESTE
	assert "usuario_id_postgres" not in estado


def test_chat_usa_conversation_id_enviado(client, fluxo_falso, auth_headers):
	response = client.post(
		"/v1/chat",
		json={"mensagem": "e aí", "conversation_id": "conversa-2"},
		headers=auth_headers,
	)

	assert response.status_code == 200
	assert response.json()["conversation_id"] == "conversa-2"

	config = fluxo_falso.chamadas[0]["config"]
	assert config["configurable"]["thread_id"] == f"{UID_DE_TESTE}:conversa-2"


def _mapear_uid(monkeypatch, mapa):
	"""Troca a consulta ao Postgres por um dicionário uid -> user_id."""
	from venus_api.app.api.v1.endpoints import chat

	async def resolver(pool, firebase_uid):
		return mapa.get(firebase_uid)

	monkeypatch.setattr(chat, "resolver_usuario_postgres", resolver)


def test_usuario_id_postgres_do_corpo_nunca_chega_ao_grafo(client, fluxo_falso, auth_headers, monkeypatch):
	"""IDOR: o app não informa identidade. Mandar o id de outra pessoa no
	corpo não pode dar acesso aos dados dela."""
	_mapear_uid(monkeypatch, {})
	response = client.post(
		"/v1/chat",
		json={"mensagem": "quais são minhas alergias?", "usuario_id_postgres": 5},
		headers=auth_headers,
	)

	assert response.status_code == 200
	assert "usuario_id_postgres" not in fluxo_falso.chamadas[0]["estado"]


def test_usuario_id_postgres_vem_do_uid_do_firebase(client, fluxo_falso, auth_headers, monkeypatch):
	_mapear_uid(monkeypatch, {UID_DE_TESTE: 7})
	response = client.post(
		"/v1/chat",
		json={"mensagem": "quais são minhas alergias?", "usuario_id_postgres": 5},
		headers=auth_headers,
	)

	assert response.status_code == 200
	assert fluxo_falso.chamadas[0]["estado"]["usuario_id_postgres"] == 7


def test_sem_mapeamento_o_estado_fica_sem_usuario_id_postgres(client, fluxo_falso, auth_headers, monkeypatch):
	_mapear_uid(monkeypatch, {})
	response = client.post("/v1/chat", json={"mensagem": "oi"}, headers=auth_headers)

	assert response.status_code == 200
	assert "usuario_id_postgres" not in fluxo_falso.chamadas[0]["estado"]


def test_chat_recusa_mensagem_vazia(client, auth_headers):
	response = client.post("/v1/chat", json={"mensagem": ""}, headers=auth_headers)

	assert response.status_code == 422
