# Monta o checkpointer do LangGraph (memória de curto prazo / sessão).
#
# Em produção, um RedisSaver apontando para a URL de Redis das settings.
# Em testes, é substituído por MemorySaver() via dependency override do
# FastAPI (ver tests/conftest.py), sem alterar o resto da aplicação.
