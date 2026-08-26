# Dependências injetadas nos endpoints via Depends().
#
# get_fluxo_venus: devolve o grafo Venus já compilado uma vez no startup
# (guardado em app.state), evitando recompilar o grafo a cada request.
#
# get_session_id: extrai e valida o token de autorização (via
# app.core.security.validar_token) e gera o thread_id/session_id usado pelo
# checkpointer do LangGraph para manter o histórico da conversa por usuário.
