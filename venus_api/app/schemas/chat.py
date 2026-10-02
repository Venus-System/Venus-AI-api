# Modelos Pydantic do endpoint de chat: ChatRequest (mensagem enviada pelo
# usuário) e ChatResponse (resposta devolvida pelo grafo Venus).

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    # Campos desconhecidos são aceitos e ignorados (ver o aviso em
    # `endpoints/chat.py`): um app antigo que ainda mande
    # `usuario_id_postgres` continua funcionando, só sem esse efeito.
    model_config = ConfigDict(extra="allow")

    mensagem: str = Field(min_length=1)
    # Omitido na primeira mensagem: a API devolve o id usado e o app o reenvia
    # nas seguintes (contrato combinado com o time do app, pra dar pra evoluir
    # pra histórico de várias conversas sem quebrar o contrato).
    conversation_id: str | None = None
    # Sem `usuario_id_postgres`: o cliente nunca informa identidade. A API
    # descobre o id pelo uid do Firebase (`infra/postgres.py`).


class ChatResponse(BaseModel):
    resposta: str
    conversation_id: str
