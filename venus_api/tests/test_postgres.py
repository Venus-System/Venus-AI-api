import asyncio

import asyncpg
import pytest
from fastapi.testclient import TestClient

from venus_api.app import main
from venus_api.app.core.config import settings
from venus_api.app.infra import postgres

URL_DE_TESTE = "postgresql://usuario:senha@banco.exemplo.com:5432/venus"


class PoolFalso:
	def __init__(self) -> None:
		self.fechado = False

	async def close(self) -> None:
		self.fechado = True


@pytest.fixture
def com_url(monkeypatch):
	monkeypatch.setattr(settings, "database_url", URL_DE_TESTE)


def test_sem_database_url_nao_tenta_conectar(monkeypatch):
	async def nao_deveria_chamar(*args, **kwargs):
		raise AssertionError("não devia tentar conectar sem DATABASE_URL")

	monkeypatch.setattr(postgres.asyncpg, "create_pool", nao_deveria_chamar)

	assert asyncio.run(postgres.criar_pool()) is None


def test_pool_usa_poucas_conexoes(com_url, monkeypatch):
	"""O banco aceita 20 conexões e o CRUD já usa até 10 — o pool da API
	precisa ficar pequeno."""
	chamadas = []
	pool = PoolFalso()

	async def create_pool(dsn, **kwargs):
		chamadas.append((dsn, kwargs))
		return pool

	monkeypatch.setattr(postgres.asyncpg, "create_pool", create_pool)

	assert asyncio.run(postgres.criar_pool()) is pool
	dsn, kwargs = chamadas[0]
	assert dsn == URL_DE_TESTE
	assert kwargs["min_size"] == 1
	assert kwargs["max_size"] == 2


@pytest.mark.parametrize(
	"erro",
	[
		# Tipos reais do que o asyncpg levanta: banco fora do ar, senha errada
		# e demora pra conectar.
		ConnectionRefusedError("banco fora do ar"),
		asyncpg.InvalidPasswordError("senha errada"),
		TimeoutError("demorou demais pra conectar"),
	],
)
def test_falha_de_conexao_devolve_none_sem_derrubar(com_url, monkeypatch, erro, caplog):
	async def create_pool(dsn, **kwargs):
		raise erro

	monkeypatch.setattr(postgres.asyncpg, "create_pool", create_pool)

	with caplog.at_level("ERROR"):
		assert asyncio.run(postgres.criar_pool()) is None
	assert "Não foi possível conectar ao Postgres" in caplog.text


def test_startup_entrega_o_pool_ao_grafo_e_fecha_no_desligamento(monkeypatch):
	pool = PoolFalso()
	recebido = {}

	async def criar_pool_falso():
		return pool

	def compilar_falso(**kwargs):
		recebido.update(kwargs)
		return object()

	monkeypatch.setattr(main, "criar_pool", criar_pool_falso)
	monkeypatch.setattr(main, "compilar_grafo_venus", compilar_falso)

	with TestClient(main.app):
		assert recebido["pool"] is pool
		assert pool.fechado is False

	assert pool.fechado is True


def test_startup_sem_postgres_ainda_sobe(monkeypatch):
	"""Sem pool a API sobe do mesmo jeito — chat e health não dependem dele."""
	recebido = {}

	def compilar_falso(**kwargs):
		recebido.update(kwargs)
		return object()

	monkeypatch.setattr(main, "compilar_grafo_venus", compilar_falso)

	with TestClient(main.app) as cliente:
		assert cliente.get("/v1/health").status_code == 200

	assert recebido["pool"] is None
