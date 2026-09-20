# Modelos Pydantic do endpoint de chat: ChatRequest (mensagem enviada pelo
# usuário) e ChatResponse (resposta devolvida pelo grafo Venus).

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    mensagem: str = Field(min_length=1)
    # Omitido na primeira mensagem: a API devolve o id usado e o app o reenvia
    # nas seguintes (contrato combinado com o time do app, pra dar pra evoluir
    # pra histórico de várias conversas sem quebrar o contrato).
    conversation_id: str | None = None
    # Id numérico do usuário no Postgres, exigido pelas tools de alergia/score
    # personalizado. Hoje o app não tem como fornecer (o usuário do Firebase
    # não tem linha na tabela `users`); sem ele os especialistas não chamam
    # essas tools em vez de inventar um número.
    usuario_id_postgres: int | None = None


class ChatResponse(BaseModel):
    resposta: str
    conversation_id: str
