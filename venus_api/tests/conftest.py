# Fixtures de teste compartilhadas.
#
# `client`: monta um grafo Venus de teste com MemorySaver/InMemoryStore,
# sobrescreve as dependências get_fluxo_venus/get_session_id do FastAPI
# para usar esse grafo e um session_id fixo, e devolve um TestClient
# pronto para os testes de endpoint.
