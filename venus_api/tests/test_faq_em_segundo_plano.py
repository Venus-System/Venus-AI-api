"""Item 4 da revisão técnica 3: o índice do FAQ é construído em segundo plano,
depois de a API já responder. Até ficar pronto, o FAQ responde a mensagem de
indisponibilidade (200, nunca 502)."""

from __future__ import annotations

import threading
import time

import pytest
from fastapi.testclient import TestClient

from venus_api.app import main
from venus_api.app.core.config import settings
from venus_api.app.infra import rag

CHAVE = "chave-do-health"


@pytest.fixture
def fabrica_lenta(monkeypatch):
	"""O índice só fica pronto quando o teste liberar."""
	liberar = threading.Event()
	criar_de_verdade = rag.criar_indice_faq

	def criar_devagar():
		liberar.wait(10)
		return criar_de_verdade()

	monkeypatch.setattr(rag, "criar_indice_faq", criar_devagar)
	monkeypatch.setattr(settings, "faq_dir", None)
	monkeypatch.setattr(settings, "health_api_key", CHAVE)
	yield liberar
	liberar.set()


def _esperar(condicao, segundos=10.0) -> bool:
	limite = time.monotonic() + segundos
	while time.monotonic() < limite:
		if condicao():
			return True
		time.sleep(0.05)
	return False


def test_health_responde_enquanto_o_indice_e_construido(fabrica_lenta, fluxo_falso, monkeypatch):
	monkeypatch.setattr(main, "compilar_grafo_venus", lambda **kwargs: fluxo_falso)
	inicio = time.monotonic()
	with TestClient(main.app) as cliente:
		assert cliente.get("/v1/health").json() == {"status": "ok"}
		assert time.monotonic() - inicio < 5  # não esperou os 10 s da fábrica
		faq = cliente.get("/v1/health/detalhado", headers={"X-API-Key": CHAVE}).json()["faq"]
		assert faq == {"pronto": False, "tipo": None}

		fabrica_lenta.set()
		assert _esperar(lambda: main.app.state.indice_faq.pronto)
		faq = cliente.get("/v1/health/detalhado", headers={"X-API-Key": CHAVE}).json()["faq"]
		assert faq["pronto"] is True and faq["tipo"].startswith("IndiceRAG/")


def test_lifespan_entrega_ao_grafo_o_indice_que_fica_pronto_depois(fabrica_lenta, fluxo_falso, monkeypatch):
	recebidos = {}
	monkeypatch.setattr(main, "compilar_grafo_venus", lambda **kwargs: recebidos.update(kwargs) or fluxo_falso)
	with TestClient(main.app):
		indice = recebidos["indice_rag"]
		assert indice is main.app.state.indice_faq and indice.pronto is False
		fabrica_lenta.set()
		assert _esperar(lambda: indice.pronto)
		assert indice.buscar("como funciona o score", k=1)


def test_falha_ao_construir_fica_registrada_e_o_faq_segue_indisponivel(monkeypatch, fluxo_falso):
	monkeypatch.setattr(rag, "criar_indice_faq", lambda: None)  # criar_indice_faq já loga o error
	monkeypatch.setattr(main, "compilar_grafo_venus", lambda **kwargs: fluxo_falso)
	monkeypatch.setattr(settings, "health_api_key", CHAVE)
	with TestClient(main.app) as cliente:
		assert _esperar(lambda: main.app.state.indice_faq.falhou)
		faq = cliente.get("/v1/health/detalhado", headers={"X-API-Key": CHAVE}).json()["faq"]
		assert faq == {"pronto": False, "tipo": None, "falhou": True}


def test_pergunta_de_faq_antes_do_indice_responde_200_com_indisponibilidade(fabrica_lenta, auth_headers, monkeypatch):
	from langchain_core.messages import AIMessage
	from venus_sdk.nodes import especialistas, juiz, memoria, orquestrador, roteador

	from venus_api.tests.test_faq_no_grafo import LLMRoteirizado

	pergunta = "como funciona o score do Venus?"
	rapido = LLMRoteirizado(roteiro=[AIMessage(content=f"ROUTE=faq\nPERGUNTA_ORIGINAL={pergunta}"),
	                                 AIMessage(content="NADA")])
	especialista = LLMRoteirizado(roteiro=[AIMessage(content="não deveria ser chamado")])
	monkeypatch.setattr(roteador, "get_llm_rapido", lambda: rapido)
	monkeypatch.setattr(memoria, "get_llm_rapido", lambda: rapido)
	monkeypatch.setattr(especialistas, "get_llm_especialista", lambda: especialista)
	monkeypatch.setattr(juiz, "get_llm_juiz", lambda: LLMRoteirizado(roteiro=[AIMessage(content="RESULTADO=aprovado")]))
	monkeypatch.setattr(orquestrador, "get_llm_orquestrador",
	                    lambda: LLMRoteirizado(roteiro=[AIMessage(content="não deveria ser chamado")]))

	with TestClient(main.app) as cliente:
		resposta = cliente.post("/v1/chat", json={"mensagem": pergunta}, headers=auth_headers)

	assert resposta.status_code == 200
	assert resposta.json()["resposta"] == orquestrador._RESPOSTA_ORQUESTRADOR_FALLBACK
	assert especialista.posicao == 0  # o agente FAQ nem foi montado
