# Health checks.
#
# /v1/health é público e simples: o ECS só precisa saber se a API responde.
# /v1/health/detalhado mostra a saúde interna (ex.: o classificador do
# guardrail em fail-open) e por isso exige uma chave interna no header
# `X-API-Key` — HEALTH_API_KEY ou, sem ela, a mesma do A2A. Sem nenhuma
# chave configurada, o endpoint nem existe (404).

from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from venus_sdk.nodes.guardrails import estatisticas_guardrail_llm

from venus_api.app.core.config import settings

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
	return {"status": "ok"}


def _chave_do_health() -> str | None:
	return settings.health_api_key or settings.a2a_api_key


def _exigir_chave(recebida: str | None) -> None:
	chave = _chave_do_health()
	if not chave:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
	# compare_digest: tempo de resposta igual acertando ou errando a chave.
	if not hmac.compare_digest((recebida or "").encode(), chave.encode()):
		raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Chave ausente ou inválida")


@router.get("/health/detalhado")
def health_detalhado(request: Request, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
	_exigir_chave(x_api_key)
	return {
		"status": "ok",
		# Contadores por processo (por task do ECS): chamadas, falhas,
		# fail-opens e o disjuntor do classificador LLM do guardrail.
		"guardrail_llm": estatisticas_guardrail_llm(),
		# O índice do FAQ é construído em segundo plano depois do startup.
		"faq": _estado_do_faq(request),
	}


def _estado_do_faq(request: Request) -> dict[str, Any]:
	indice = getattr(request.app.state, "indice_faq", None)
	return indice.estado() if indice is not None else {"pronto": False, "tipo": None}
