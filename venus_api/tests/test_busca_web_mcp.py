"""Item 8 da revisão técnica 3: a busca na web do agente FAQ passa pelo
servidor MCP da Tavily (aqui, um servidor MCP simulado de verdade, por stdio);
sem o servidor, cai na busca direta, sem 502."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from venus_api.app import main
from venus_api.app.core.config import settings
from venus_api.app.infra import busca_web_mcp

SERVIDOR_FALSO = Path(__file__).with_name("servidor_mcp_tavily_falso.py")
URL_DO_MCP = "https://via-mcp.example/niacinamida"
URL_DIRETA = "https://busca-direta.example/niacinamida"
PERGUNTA = "o que a internet diz sobre niacinamida?"


def _resposta_com_a_fonte_da_web(mensagens: list[BaseMessage]) -> AIMessage:
	resultados = json.loads(next(m.content for m in reversed(mensagens) if isinstance(m, ToolMessage)))
	return AIMessage(content=json.dumps({
		"dominio": "faq", "intencao": "consultar_faq",
		"resposta": f"Segundo {resultados[0]['url']}: {resultados[0]['trecho']}",
		"recomendacao": "", "fontes_usadas": [resultados[0]["url"]],
	}, ensure_ascii=False))


@pytest.fixture
def grafo_com_busca_web(monkeypatch):
	from venus_sdk.nodes import especialistas, juiz, memoria, orquestrador, roteador
	from venus_sdk.rag import web

	from venus_api.tests.test_faq_no_grafo import LLMRoteirizado, _orquestrador_repete_o_especialista

	rapido = LLMRoteirizado(roteiro=[AIMessage(content=f"ROUTE=faq\nPERGUNTA_ORIGINAL={PERGUNTA}"),
	                                 AIMessage(content="NADA")])
	especialista = LLMRoteirizado(roteiro=[
		AIMessage(content="", tool_calls=[{"name": "buscar_na_web", "args": {"consulta": "niacinamida"}, "id": "w1"}]),
		_resposta_com_a_fonte_da_web,
	])
	monkeypatch.setattr(roteador, "get_llm_rapido", lambda: rapido)
	monkeypatch.setattr(memoria, "get_llm_rapido", lambda: rapido)
	monkeypatch.setattr(especialistas, "get_llm_especialista", lambda: especialista)
	monkeypatch.setattr(juiz, "get_llm_juiz", lambda: LLMRoteirizado(roteiro=[AIMessage(content="RESULTADO=aprovado")]))
	monkeypatch.setattr(orquestrador, "get_llm_orquestrador",
	                    lambda: LLMRoteirizado(roteiro=[_orquestrador_repete_o_especialista]))
	monkeypatch.setattr(web, "buscar_web", lambda consulta, max_resultados=3: [
		{"titulo": "direta", "trecho": "Resultado da busca direta.", "url": URL_DIRETA}])
	monkeypatch.setattr(settings, "tavily_api_key", "tvly-de-teste")


def _esperar(condicao, segundos=30.0) -> bool:
	limite = time.monotonic() + segundos
	while time.monotonic() < limite:
		if condicao():
			return True
		time.sleep(0.05)
	return False


def _perguntar(cliente, auth_headers):
	return cliente.post("/v1/chat", json={"mensagem": PERGUNTA}, headers=auth_headers)


def test_busca_web_passa_pela_tool_mcp_e_a_fonte_chega_a_resposta(grafo_com_busca_web, auth_headers, monkeypatch):
	monkeypatch.setattr(busca_web_mcp, "config_do_tavily_mcp", lambda: {
		"tavily": {"transport": "stdio", "command": sys.executable, "args": [str(SERVIDOR_FALSO)]}})
	with TestClient(main.app) as cliente:
		assert _esperar(lambda: main.app.state.tavily_mcp.tool is not None)
		resposta = _perguntar(cliente, auth_headers)
	assert resposta.status_code == 200
	assert URL_DO_MCP in resposta.json()["resposta"] and URL_DIRETA not in resposta.json()["resposta"]


def test_servidor_mcp_indisponivel_cai_na_busca_direta_sem_502(grafo_com_busca_web, auth_headers, monkeypatch):
	monkeypatch.setattr(busca_web_mcp, "config_do_tavily_mcp", lambda: {
		"tavily": {"transport": "stdio", "command": "comando-que-nao-existe-venus", "args": []}})
	with TestClient(main.app) as cliente:
		assert _esperar(lambda: main.app.state.tavily_mcp.encerrada)
		resposta = _perguntar(cliente, auth_headers)
	assert resposta.status_code == 200
	assert URL_DIRETA in resposta.json()["resposta"]


def test_sem_chave_da_tavily_nao_abre_sessao_mcp(monkeypatch, fluxo_falso):
	recebidos = {}
	monkeypatch.setattr(settings, "tavily_api_key", None)
	monkeypatch.setattr(main, "compilar_grafo_venus", lambda **kwargs: recebidos.update(kwargs) or fluxo_falso)
	with TestClient(main.app):
		pass
	assert recebidos["busca_web_faq"] is None


def test_config_usa_o_pacote_instalado_e_repassa_a_chave(monkeypatch):
	monkeypatch.setattr(settings, "tavily_api_key", "tvly-x")
	[(nome, config)] = busca_web_mcp.config_do_tavily_mcp().items()
	assert config["transport"] == "stdio" and config["command"] == settings.tavily_mcp_comando
	assert config["env"]["TAVILY_API_KEY"] == "tvly-x"
	assert "npx" not in config["command"]  # nada de baixar pacote no startup
