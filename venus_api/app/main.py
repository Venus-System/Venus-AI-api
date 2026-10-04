import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from venus_sdk.flows.venus_flow import compilar_grafo_venus

from venus_api.app.api.a2a import ROTA_A2A, A2ADinamico, criar_app_a2a
from venus_api.app.api.v1.router import router as v1_router
from venus_api.app.infra.checkpointer import criar_checkpointer
from venus_api.app.infra.ferramentas_externas import carregar_tools_faq_extras
from venus_api.app.infra.ferramentas_rotina import montar_tools_rotina_extras
from venus_api.app.infra.limite_de_taxa import criar_limitador
from venus_api.app.infra.postgres import criar_pool
from venus_api.app.infra.rag import IndiceDoFaqEmSegundoPlano
from venus_api.app.infra.store import criar_store
from venus_api.app.observability import tracing
from venus_api.app.observability.middleware import medir_requisicao


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await criar_pool()
    # O /v1/chat usa o pool para descobrir o user_id pelo uid do Firebase.
    app.state.pool = pool
    app.state.limitador = criar_limitador()
    # O índice do FAQ fica pronto depois: o startup (e o health check do ECS)
    # não espera o modelo de embeddings. Ver infra/rag.py.
    indice_faq = IndiceDoFaqEmSegundoPlano()
    app.state.indice_faq = indice_faq
    tarefa_do_faq = asyncio.create_task(indice_faq.construir())
    try:
        app.state.fluxo_venus = compilar_grafo_venus(
            checkpointer=criar_checkpointer(),
            store=criar_store(),
            pool=pool,
            indice_rag=indice_faq,
            tools_faq_extras=await carregar_tools_faq_extras(),
            tools_rotina_extras=montar_tools_rotina_extras(pool),
        )
        app.state.a2a_app = criar_app_a2a(app.state.fluxo_venus)
        yield
    finally:
        tarefa_do_faq.cancel()
        if pool is not None:
            await pool.close()
        await _fechar_neo4j()
        # O Langfuse envia os traces em lote, em segundo plano. Sem isso, o que
        # ainda não tinha sido enviado se perde quando a API desliga.
        langfuse = tracing.get_langfuse()
        if langfuse is not None:
            langfuse.shutdown()


async def _fechar_neo4j() -> None:
    """O driver do Neo4j do check-up é criado no primeiro uso (lru_cache do
    SDK); se foi criado, fecha as conexões no desligamento."""
    from venus_sdk.integrations.grafo_neo4j import get_neo4j_driver

    if get_neo4j_driver.cache_info().currsize:
        await get_neo4j_driver().close()


app = FastAPI(title="Venus AI API", lifespan=lifespan)
app.middleware("http")(medir_requisicao)
app.include_router(v1_router, prefix="/v1")
app.mount(ROTA_A2A, A2ADinamico())
