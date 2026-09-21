# Contrato de autenticação da API.
#
# Usuario: dado mínimo do usuário autenticado (id).
# validar_token: valida o token (JWT/API key) recebido no header
# Authorization e devolve o Usuario correspondente. Implementação real fica
# a cargo do time; app/api/deps.py depende só dessa assinatura.

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import firebase_admin
from firebase_admin import auth, credentials

from venus_api.app.core.config import settings


@dataclass(frozen=True)
class Usuario:
    id: str


@lru_cache(maxsize=1)
def _inicializar_firebase() -> None:
    """Inicializa o Firebase Admin na primeira validação, não no startup.

    Preguiçoso de propósito: numa máquina sem a credencial configurada a
    aplicação ainda sobe e `/v1/health` responde — só o chat recusa. Se a
    credencial faltar, o erro levantado aqui já diz qual arquivo não foi
    encontrado.
    """
    credencial = (
        credentials.Certificate(settings.firebase_credentials)
        if settings.firebase_credentials
        else credentials.ApplicationDefault()
    )
    firebase_admin.initialize_app(credencial)


def validar_token(token: str | None) -> Usuario:
    """Valida o ID token do Firebase e devolve o Usuario correspondente.

    O `uid` vem assinado pelo Google dentro do próprio token, então o app não
    tem como mentir sobre quem é — diferente de mandar o uid no corpo da
    requisição.
    """
    if not token:
        raise ValueError("token ausente ou vazio")

    _inicializar_firebase()
    try:
        claims = auth.verify_id_token(token)
    except (
        auth.InvalidIdTokenError,
        auth.ExpiredIdTokenError,
        auth.RevokedIdTokenError,
        auth.UserDisabledError,
        ValueError,
    ) as erro:
        # Só erro do TOKEN vira 401. `CertificateFetchError` e falhas de
        # credencial ficam de fora de propósito: sobem como 500, pra não
        # mascarar problema de configuração do servidor como "token inválido".
        raise ValueError("token inválido ou expirado") from erro

    return Usuario(id=claims["uid"])
