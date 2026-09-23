import pytest
from fastapi.testclient import TestClient

from venus_api.app import main
from venus_api.app.core.config import settings

CHAVE = "chave-a2a-de-teste"
URL_BASE = "https://api.exemplo.com"
AGENT_CARD = "/a2a/.well-known/agent-card.json"
# Todo cliente A2A 1.0 manda este header; sem ele o servidor assume a 0.3.
HEADERS_A2A = {"X-API-Key": CHAVE, "A2A-Version": "1.0"}

MENSAGEM = {
	"jsonrpc": "2.0",
	"id": 1,
	"method": "SendMessage",
	"params": {
		"message": {
			"messageId": "m1",
			"contextId": "conversa-a2a",
			"role": "ROLE_USER",
			"parts": [{"text": "oi"}],
		}
	},
}


@pytest.fixture
def a2a_ligado(monkeypatch, fluxo_falso):
	"""Sobe a API com o A2A configurado e o grafo falso — o servidor A2A usa o
	grafo criado no startup, não a dependência que o `client` troca."""
	monkeypatch.setattr(settings, "a2a_api_key", CHAVE)
	monkeypatch.setattr(settings, "a2a_base_url", URL_BASE)
	monkeypatch.setattr(main, "compilar_grafo_venus", lambda **kwargs: fluxo_falso)
	with TestClient(main.app) as cliente:
		yield cliente


def test_sem_chave_configurada_o_a2a_fica_desligado(client):
	assert client.get(AGENT_CARD).status_code == 404
	assert client.post("/a2a/", json=MENSAGEM).status_code == 404


def test_chave_sem_url_base_tambem_deixa_desligado(monkeypatch, fluxo_falso):
	monkeypatch.setattr(settings, "a2a_api_key", CHAVE)
	monkeypatch.setattr(main, "compilar_grafo_venus", lambda **kwargs: fluxo_falso)

	with TestClient(main.app) as cliente:
		assert cliente.get(AGENT_CARD).status_code == 404


def test_agent_card_e_publico_e_aponta_pra_url_da_api(a2a_ligado):
	response = a2a_ligado.get(AGENT_CARD)

	assert response.status_code == 200
	card = response.json()
	assert card["name"] == "Venus"
	assert card["supportedInterfaces"][0]["url"] == f"{URL_BASE}/a2a/"


def test_url_base_com_barra_no_fim_nao_duplica(monkeypatch, fluxo_falso):
	monkeypatch.setattr(settings, "a2a_api_key", CHAVE)
	monkeypatch.setattr(settings, "a2a_base_url", f"{URL_BASE}/")
	monkeypatch.setattr(main, "compilar_grafo_venus", lambda **kwargs: fluxo_falso)

	with TestClient(main.app) as cliente:
		card = cliente.get(AGENT_CARD).json()

	assert card["supportedInterfaces"][0]["url"] == f"{URL_BASE}/a2a/"


def test_mensagem_sem_chave_e_recusada(a2a_ligado, fluxo_falso):
	response = a2a_ligado.post("/a2a/", json=MENSAGEM)

	assert response.status_code == 401
	assert fluxo_falso.chamadas == []


def test_mensagem_com_chave_errada_e_recusada(a2a_ligado, fluxo_falso):
	response = a2a_ligado.post("/a2a/", json=MENSAGEM, headers={"X-API-Key": "outra-chave"})

	assert response.status_code == 401
	assert fluxo_falso.chamadas == []


def test_chave_tambem_protege_o_que_nao_e_o_agent_card(a2a_ligado):
	"""Só a leitura do Agent Card é pública; nada mais no `/a2a` responde sem
	chave, nem um GET em outro caminho."""
	assert a2a_ligado.get("/a2a/qualquer-coisa").status_code == 401
	assert a2a_ligado.post(AGENT_CARD, json={}).status_code == 401


def test_mensagem_com_chave_certa_chega_ao_grafo_e_volta(a2a_ligado, fluxo_falso):
	response = a2a_ligado.post("/a2a/", json=MENSAGEM, headers=HEADERS_A2A)

	assert response.status_code == 200
	resposta = response.json()["result"]["message"]
	assert resposta["parts"][0]["text"] == fluxo_falso.resposta

	chamada = fluxo_falso.chamadas[0]
	assert chamada["estado"]["mensagem_usuario"] == "oi"
	# O `contextId` do A2A é o `thread_id` do histórico da conversa.
	assert chamada["config"]["configurable"]["thread_id"] == "conversa-a2a"


def test_a2a_e_chat_nao_aceitam_a_credencial_um_do_outro(a2a_ligado, auth_headers):
	"""A chave do A2A não abre o chat, e o token do Firebase não abre o A2A."""
	chat_com_chave_a2a = a2a_ligado.post(
		"/v1/chat", json={"mensagem": "oi"}, headers={"X-API-Key": CHAVE}
	)
	assert chat_com_chave_a2a.status_code == 401

	a2a_com_firebase = a2a_ligado.post("/a2a/", json=MENSAGEM, headers=auth_headers)
	assert a2a_com_firebase.status_code == 401
