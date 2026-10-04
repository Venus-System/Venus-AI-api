# Tools extras do agente de Rotina: Google Calendar e check-up da rotina (Neo4j).
#
# O SDK monta as tools (`montar_tools_calendario`, `montar_tools_checkup`);
# aqui só decidimos QUAIS entram, pelo que está configurado. Tool que não pode
# funcionar não é registrada: descrever ao LLM uma tool inútil gasta tokens em
# toda mensagem e o convida a chamá-la à toa.

from __future__ import annotations

import logging
import os
from typing import Any

from venus_sdk.integrations.grafo_neo4j import neo4j_configurado
from venus_sdk.tools.calendario import montar_tools_calendario
from venus_sdk.tools.checkup import montar_tools_checkup

logger = logging.getLogger(__name__)

# Lidas pelo SDK com os.getenv (`integrations/google_calendar.py::_credenciais`
# e `_fernet`): precisam estar no ambiente do processo (variáveis do ECS ou
# `uvicorn --env-file .env`).
VARIAVEIS_GOOGLE_CALENDAR = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_TOKEN_ENCRYPTION_KEY")


def variaveis_google_ausentes() -> list[str]:
	return [nome for nome in VARIAVEIS_GOOGLE_CALENDAR if not os.getenv(nome)]


def google_calendar_configurado() -> bool:
	return not variaveis_google_ausentes()


def montar_tools_rotina_extras(pool: Any) -> list[Any]:
	"""Tools do Calendar e do check-up para o agente de Rotina, ou `[]`.
	Loga no startup o que ficou ligado e, se não, por quê."""
	tools: list[Any] = []

	sem_banco = [] if pool is not None else ["DATABASE_URL"]
	faltam_google = sem_banco + variaveis_google_ausentes()
	if faltam_google:
		logger.info("Google Calendar desligado: faltam %s.", ", ".join(faltam_google))
	else:
		tools += montar_tools_calendario(pool)
		logger.info("Google Calendar ligado: consultar horários e agendar a rotina com confirmação.")

	# As duas integrações leem o Postgres (tokens do Google; rotina do usuário).
	faltam_neo4j = sem_banco + ([] if neo4j_configurado() else ["NEO4J_URI"])
	if faltam_neo4j:
		logger.info("Check-up (Neo4j) desligado: faltam %s.", ", ".join(faltam_neo4j))
	else:
		tools += montar_tools_checkup(pool)
		logger.info("Check-up (Neo4j) ligado: avisos de conflito e ordem na rotina.")
	return tools
