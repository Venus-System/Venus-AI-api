"""Item 2 da revisão técnica 3: health check detalhado com a saúde do
classificador do guardrail — protegido por chave, nunca público."""

from __future__ import annotations

import pytest
from venus_sdk.nodes import guardrails

from venus_api.app.core.config import settings

URL = "/v1/health/detalhado"
CHAVE = "chave-interna-de-teste"


@pytest.fixture
def com_chave(monkeypatch):
	monkeypatch.setattr(settings, "a2a_api_key", CHAVE)
	monkeypatch.setattr(settings, "health_api_key", None)


def test_health_simples_continua_publico(client):
	assert client.get("/v1/health").json() == {"status": "ok"}


def test_sem_chave_configurada_o_detalhado_nao_existe(client, monkeypatch):
	monkeypatch.setattr(settings, "health_api_key", None)
	assert client.get(URL, headers={"X-API-Key": "qualquer"}).status_code == 404


@pytest.mark.parametrize("cabecalhos", [{}, {"X-API-Key": "errada"}])
def test_sem_a_chave_certa_recusa(client, com_chave, cabecalhos):
	assert client.get(URL, headers=cabecalhos).status_code == 401


def test_devolve_as_estatisticas_do_guardrail_e_o_disjuntor(client, com_chave):
	resposta = client.get(URL, headers={"X-API-Key": CHAVE})
	assert resposta.status_code == 200
	guardrail = resposta.json()["guardrail_llm"]
	assert set(guardrails.estatisticas_guardrail_llm()) <= set(guardrail)
	assert "disjuntor_aberto" in guardrail and "fail_opens" in guardrail


def test_chave_propria_do_health_tem_prioridade(client, monkeypatch):
	monkeypatch.setattr(settings, "a2a_api_key", "a-do-a2a")
	monkeypatch.setattr(settings, "health_api_key", "a-do-health")
	assert client.get(URL, headers={"X-API-Key": "a-do-a2a"}).status_code == 401
	assert client.get(URL, headers={"X-API-Key": "a-do-health"}).status_code == 200
