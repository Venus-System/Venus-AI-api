"""Campo `expressao` do /v1/chat: a cara da Veninha que a web mostra. Vem do
estado do grafo (SDK >= 0.4.0) e sai sempre de uma lista fechada."""

import pytest


def test_ofensa_devolve_magoada(client, fluxo_falso, auth_headers):
	fluxo_falso.estado_final = {"expressao": "magoada"}

	response = client.post("/v1/chat", json={"mensagem": "você é burra"}, headers=auth_headers)

	assert response.status_code == 200
	assert response.json()["expressao"] == "magoada"


def test_sem_expressao_no_estado_e_neutra(client, auth_headers):
	response = client.post("/v1/chat", json={"mensagem": "oi"}, headers=auth_headers)

	assert response.json()["expressao"] == "neutra"


@pytest.mark.parametrize("valor", ["furiosa", "", None, 3])
def test_valor_fora_da_lista_vira_neutra(client, fluxo_falso, auth_headers, valor):
	"""Um SDK mais novo com outra cara não pode quebrar a resposta (500) nem
	mandar para a web um valor que ela não conhece."""
	fluxo_falso.estado_final = {"expressao": valor}

	response = client.post("/v1/chat", json={"mensagem": "oi"}, headers=auth_headers)

	assert response.status_code == 200
	assert response.json()["expressao"] == "neutra"


def test_contrato_do_chat_documenta_a_lista_fechada(client):
	esquema = client.get("/openapi.json").json()["components"]["schemas"]["ChatResponse"]

	assert esquema["properties"]["expressao"]["enum"] == ["neutra", "magoada"]
