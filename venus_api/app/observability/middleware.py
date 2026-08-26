# Middleware HTTP que mede latência total e status de erro de cada request.
#
# Cobre só a visão de fora (latência de borda e erros não tratados antes de
# rodar o grafo); latência por agente/interagente é instrumentada dentro do
# próprio grafo (SDK Venus). TODO: persistir esses logs em Postgres para o
# dashboard de observabilidade.
