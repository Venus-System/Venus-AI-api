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


def test_chat_repassa_usuario_id_postgres(client, fluxo_falso, auth_headers):
	response = client.post(
		"/v1/chat",
		json={"mensagem": "esse produto serve pra mim?", "usuario_id_postgres": 42},
		headers=auth_headers,
	)

	assert response.status_code == 200
	assert fluxo_falso.chamadas[0]["estado"]["usuario_id_postgres"] == 42


def test_chat_recusa_mensagem_vazia(client, auth_headers):
	response = client.post("/v1/chat", json={"mensagem": ""}, headers=auth_headers)

	assert response.status_code == 422
