# Contrato de autenticação da API.
#
# Usuario: dado mínimo do usuário autenticado (id).
# validar_token: valida o token (JWT/API key) recebido no header
# Authorization e devolve o Usuario correspondente. Implementação real fica
# a cargo do time; app/api/deps.py depende só dessa assinatura.

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Usuario:
    id: str


def validar_token(token: str | None) -> Usuario:
    """Valida o token e devolve o Usuario correspondente.

    Provisório (Parte 1 — destravar o fluxo ponta a ponta): só exige que o
    token exista e não esteja vazio, usando-o como o próprio id do usuário.
    A validação real por API key é escopo da Parte 2; como deps.py depende
    só desta assinatura, trocar a implementação aqui não deve exigir mudar
    deps.py.
    """
    if not token:
        raise ValueError("token ausente ou vazio")
    return Usuario(id=token)
