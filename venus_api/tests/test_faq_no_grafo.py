"""Item 1 da revisão técnica: o agente FAQ precisa do índice do RAG, e uma
pergunta de FAQ não pode virar 502."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from venus_api.app import main
from venus_api.app.core.config import settings


class LLMRoteirizado(BaseChatModel):
	"""LLM falso: cada item do roteiro é uma AIMessage ou uma função
	(mensagens) -> AIMessage; o último se repete."""

	roteiro: list[Any]
	posicao: int = 0

	@property
	def _llm_type(self) -> str:
		return "llm-roteirizado"

	def bind_tools(self, tools: Any, **kwargs: Any) -> "LLMRoteirizado":
		return self

	def _generate(self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None,
	              **kwargs: Any) -> ChatResult:
		item = self.roteiro[min(self.posicao, len(self.roteiro) - 1)]
		self.posicao += 1
		mensagem = item(messages) if callable(item) else item
		return ChatResult(generations=[ChatGeneration(message=mensagem)])


def _resposta_com_o_trecho_do_faq(mensagens: list[BaseMessage]) -> AIMessage:
	"""O especialista responde com o que o faq_retriever devolveu."""
	trechos = json.loads(next(m.content for m in mensagens if isinstance(m, ToolMessage)))
	return AIMessage(content=json.dumps({
		"dominio": "faq", "intencao": "consultar_faq", "resposta": trechos[0]["trecho"],
		"recomendacao": "", "fontes_usadas": [trechos[0]["fonte"]],
	}, ensure_ascii=False))


def _orquestrador_repete_o_especialista(mensagens: list[BaseMessage]) -> AIMessage:
	entrada = mensagens[-1].content
	especialista = json.loads(entrada.split("ESPECIALISTA_JSON=", 1)[1].split("\n", 1)[0])
	return AIMessage(content=especialista["resposta"])


@pytest.fixture
def grafo_real_com_llm_falso(monkeypatch):
	from venus_sdk.nodes import especialistas, juiz, memoria, orquestrador, roteador

	pergunta = "como funciona o score do Venus?"
	rapido = LLMRoteirizado(roteiro=[AIMessage(content=f"ROUTE=faq\nPERGUNTA_ORIGINAL={pergunta}"),
	                                 AIMessage(content="NADA")])
	especialista = LLMRoteirizado(roteiro=[
		AIMessage(content="", tool_calls=[{"name": "faq_retriever", "args": {"pergunta": pergunta}, "id": "c1"}]),
		_resposta_com_o_trecho_do_faq,
	])
	monkeypatch.setattr(roteador, "get_llm_rapido", lambda: rapido)
	monkeypatch.setattr(memoria, "get_llm_rapido", lambda: rapido)
	monkeypatch.setattr(especialistas, "get_llm_especialista", lambda: especialista)
	monkeypatch.setattr(juiz, "get_llm_juiz", lambda: LLMRoteirizado(roteiro=[AIMessage(content="RESULTADO=aprovado")]))
	monkeypatch.setattr(orquestrador, "get_llm_orquestrador",
	                    lambda: LLMRoteirizado(roteiro=[_orquestrador_repete_o_especialista]))
	monkeypatch.setattr(settings, "faq_dir", None)
	with TestClient(main.app) as cliente:
		# Desde a revisão técnica 3 o índice é construído em segundo plano:
		# este teste é sobre a resposta com o índice pronto.
		limite = time.monotonic() + 30
		while not main.app.state.indice_faq.pronto and time.monotonic() < limite:
			time.sleep(0.05)
		assert main.app.state.indice_faq.pronto
		yield cliente, pergunta


def test_pergunta_de_faq_responde_200_com_conteudo_do_faq(grafo_real_com_llm_falso, auth_headers):
	cliente, pergunta = grafo_real_com_llm_falso

	resposta = cliente.post("/v1/chat", json={"mensagem": pergunta}, headers=auth_headers)

	assert resposta.status_code == 200
	# O texto da resposta é um trecho de algum documento do FAQ (os do SDK).
	# Desde o SDK 0.2.0 cada trecho começa com o caminho de títulos da seção
	# ("Documento > Seção") e uma linha em branco: compara o corpo do trecho.
	from venus_sdk.config.settings import FAQ_DIR

	corpus = " ".join(p.read_text(encoding="utf-8") for p in Path(FAQ_DIR).glob("*.md"))
	corpo_do_trecho = resposta.json()["resposta"].split("\n\n", 1)[-1]
	inicio_da_resposta = " ".join(corpo_do_trecho.split())[:60]
	assert inicio_da_resposta and inicio_da_resposta in " ".join(corpus.split())


def test_lifespan_entrega_o_indice_do_faq_ao_grafo(monkeypatch, fluxo_falso):
	recebidos: dict[str, Any] = {}

	def compilar(**kwargs):
		recebidos.update(kwargs)
		return fluxo_falso

	monkeypatch.setattr(main, "compilar_grafo_venus", compilar)
	with TestClient(main.app):
		pass

	assert recebidos["indice_rag"] is not None
	assert "tools_faq_extras" in recebidos


def test_tools_externas_do_faq_so_carregam_se_configuradas(monkeypatch, fluxo_falso):
	from venus_api.app.infra import ferramentas_externas

	recebidos: dict[str, Any] = {}
	monkeypatch.setattr(main, "compilar_grafo_venus", lambda **kwargs: recebidos.update(kwargs) or fluxo_falso)
	monkeypatch.setattr(settings, "mcp_servers", None)
	monkeypatch.setattr(settings, "a2a_agentes_externos", None)
	with TestClient(main.app):
		pass
	assert recebidos["tools_faq_extras"] == []

	async def mcp_falso(servidores=None, **kwargs):
		return ["tool-mcp"]

	monkeypatch.setattr(ferramentas_externas, "get_mcp_tools", mcp_falso)
	monkeypatch.setattr(ferramentas_externas, "montar_tool_a2a", lambda agentes=None, **kwargs: ["tool-a2a"])
	monkeypatch.setattr(settings, "mcp_servers", '{"externo": {"transport": "streamable_http", "url": "http://x"}}')
	monkeypatch.setattr(settings, "a2a_agentes_externos", '{"outro": "http://y"}')
	with TestClient(main.app):
		pass
	assert recebidos["tools_faq_extras"] == ["tool-mcp", "tool-a2a"]
