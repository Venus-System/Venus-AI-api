# Modelos Pydantic do endpoint de chat: ChatRequest (mensagem enviada pelo
# usuário) e ChatResponse (resposta devolvida pelo grafo Venus).

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from venus_sdk.guardrail_rules import TAMANHO_MAXIMO_MENSAGEM
from venus_sdk.state import Expressao


class ChatRequest(BaseModel):
    # Campos desconhecidos são aceitos e ignorados (ver o aviso em
    # `endpoints/chat.py`): um app antigo que ainda mande
    # `usuario_id_postgres` continua funcionando, só sem esse efeito.
    model_config = ConfigDict(extra="allow")

    # Mesmo teto do guardrail do SDK: rejeita cedo (422), antes de gastar
    # qualquer chamada de LLM.
    mensagem: str = Field(min_length=1, max_length=TAMANHO_MAXIMO_MENSAGEM)
    # Omitido na primeira mensagem: a API devolve o id usado e o app o reenvia
    # nas seguintes (contrato combinado com o time do app, pra dar pra evoluir
    # pra histórico de várias conversas sem quebrar o contrato).
    conversation_id: str | None = None
    # Sem `usuario_id_postgres`: o cliente nunca informa identidade. A API
    # descobre o id pelo uid do Firebase (`infra/postgres.py`).


class ChatResponse(BaseModel):
    resposta: str
    conversation_id: str
    # Cara da Veninha que a web mostra junto da resposta: `magoada` quando a
    # mensagem ofendeu a Venus, `neutra` no resto. Lista fechada do SDK
    # (`venus_sdk.state.Expressao`), escolhida pelo código, nunca pelo modelo.
    expressao: Expressao = "neutra"
