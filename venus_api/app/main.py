# Ponto de entrada da aplicação FastAPI.
#
# No lifespan, sobe checkpointer e store reais (Redis/Mongo) e monta o grafo
# Venus uma única vez, guardando-o em app.state para reuso em todo request.
# Registra o middleware de observabilidade e o router da v1 (prefixo /v1).
