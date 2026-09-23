# Contrato de autenticação da API.
#
# Usuario: dado mínimo do usuário autenticado (id).
# validar_token: valida o token (JWT/API key) recebido no header
# Authorization e devolve o Usuario correspondente. Implementação real fica
# a cargo do time; app/api/deps.py depende só dessa assinatura.

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

import firebase_admin
from firebase_admin import auth, credentials

from venus_api.app.core.config import settings


@dataclass(frozen=True)
class Usuario:
    id: str


def _montar_credencial() -> credentials.Base:
    """Monta a credencial do Firebase a partir de `FIREBASE_CREDENTIALS`.

    Aceita o CONTEÚDO do JSON (começa com `{`) ou o CAMINHO do arquivo. Na
    nuvem não existe pasta pra deixar o arquivo, então o segredo entra como
    variável de ambiente; localmente é mais prático apontar pro arquivo.

    Todo erro aqui vira `RuntimeError` de propósito: `JSONDecodeError` e o
    erro de certificado inválido herdam de `ValueError`, e `deps.py` traduz
    `ValueError` em 401 — uma credencial quebrada se passaria por "token
    inválido" em vez de aparecer como o erro de configuração (500) que é.
    """
    valor = (settings.firebase_credentials or "").strip()
    if not valor:
        return credentials.ApplicationDefault()

    try:
        if valor.startswith("{"):
            return credentials.Certificate(json.loads(valor))
        return credentials.Certificate(valor)
    except ValueError as erro:
        raise RuntimeError(
            "FIREBASE_CREDENTIALS inválida: precisa ser o conteúdo do JSON da "
            "conta de serviço ou o caminho do arquivo."
        ) from erro


@lru_cache(maxsize=1)
def _inicializar_firebase() -> None:
    """Inicializa o Firebase Admin na primeira validação, não no startup.

    Preguiçoso de propósito: numa máquina sem a credencial configurada a
    aplicação ainda sobe e `/v1/health` responde — só o chat recusa. Se a
    credencial faltar, o erro levantado aqui já diz qual arquivo não foi
    encontrado.
    """
    firebase_admin.initialize_app(_montar_credencial())


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
