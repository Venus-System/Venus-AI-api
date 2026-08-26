# Monta o store do LangGraph (memória de longo prazo, entre sessões).
#
# Em produção, deveria devolver um adapter MongoDB -> BaseStore (ainda não
# implementado; não existe um pronto oficial do LangGraph para Mongo). Em
# testes, é substituído por InMemoryStore() via dependency override. Esse
# arquivo é o ponto único onde o store é instanciado.
