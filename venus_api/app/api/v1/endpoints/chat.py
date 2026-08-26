# Endpoint POST /chat.
#
# Recebe a mensagem do usuário (ChatRequest), monta o estado inicial do grafo
# Venus, invoca o grafo (fluxo_venus.ainvoke) usando o session_id como
# thread_id para manter contexto entre chamadas, e devolve a última mensagem
# do estado final como resposta (ChatResponse).
