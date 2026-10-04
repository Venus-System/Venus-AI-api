"""Item 1 da revisão técnica 3: o agente de Rotina recebe as tools do Google
Calendar e do check-up (Neo4j) quando — e só quando — estão configurados."""

from __future__ import annotations

import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient
from venus_sdk.integrations import grafo_neo4j

from venus_api.app import main

VARIAVEIS_GOOGLE = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_TOKEN_ENCRYPTION_KEY")


class _PoolFalso:
	async def close(self) -> None:
		pass


@pytest.fixture
def kwargs_do_grafo(monkeypatch, fluxo_falso) -> dict[str, Any]:
	recebidos: dict[str, Any] = {}

	def compilar(**kwargs):
		recebidos.update(kwargs)
		return fluxo_falso

	monkeypatch.setattr(main, "compilar_grafo_venus", compilar)
	return recebidos


def _sem_integracoes(monkeypatch) -> None:
	for variavel in VARIAVEIS_GOOGLE:
		monkeypatch.delenv(variavel, raising=False)
	monkeypatch.setattr(grafo_neo4j, "NEO4J_URI", None)


def _com_integracoes(monkeypatch) -> None:
	for variavel in VARIAVEIS_GOOGLE:
		monkeypatch.setenv(variavel, f"valor-de-teste-{variavel.lower()}")
	monkeypatch.setattr(grafo_neo4j, "NEO4J_URI", "bolt://neo4j-de-teste:7687")


def test_sem_configuracao_o_agente_de_rotina_nao_recebe_tools_extras(monkeypatch, kwargs_do_grafo, caplog):
	_sem_integracoes(monkeypatch)
	caplog.set_level(logging.INFO)
	with TestClient(main.app):
		pass
	assert not kwargs_do_grafo["tools_rotina_extras"]
	mensagens = " ".join(r.getMessage() for r in caplog.records)
	assert "Google Calendar desligado" in mensagens and "GOOGLE_CLIENT_ID" in mensagens
	assert "Check-up (Neo4j) desligado" in mensagens and "NEO4J_URI" in mensagens


def test_com_configuracao_recebe_calendario_e_checkup(monkeypatch, kwargs_do_grafo, caplog):
	_com_integracoes(monkeypatch)

	async def criar_pool():
		return _PoolFalso()

	monkeypatch.setattr(main, "criar_pool", criar_pool)
	caplog.set_level(logging.INFO)
	with TestClient(main.app):
		pass
	nomes = {tool.name for tool in kwargs_do_grafo["tools_rotina_extras"]}
	assert {"check_availability", "prepare_routine_schedule", "prepare_routine_removal"} <= nomes
	assert "check_routine_health" in nomes
	mensagens = " ".join(r.getMessage() for r in caplog.records)
	assert "Google Calendar ligado" in mensagens and "Check-up (Neo4j) ligado" in mensagens


def test_sem_postgres_as_integracoes_ficam_desligadas(monkeypatch, kwargs_do_grafo):
	# As duas leem o Postgres (tokens do Google; rotina do usuário no check-up).
	_com_integracoes(monkeypatch)
	with TestClient(main.app):
		pass
	assert not kwargs_do_grafo["tools_rotina_extras"]
