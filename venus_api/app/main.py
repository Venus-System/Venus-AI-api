import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from venus_sdk.flows.venus_flow import compilar_grafo_venus
from venus_sdk.rag.web import BuscaWebMcp

from venus_api.app.api.a2a import ROTA_A2A, A2ADinamico, criar_app_a2a
from venus_api.app.api.v1.router import router as v1_router
from venus_api.app.core.config import settings
from venus_api.app.infra.busca_web_mcp import SessaoTavilyMcp
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
    # Busca web do FAQ pelo MCP da Tavily: a sessão abre em segundo plano;
    # enquanto não abre (ou se falhar), o SDK busca direto. Ver infra/busca_web_mcp.py.
    tavily_mcp = SessaoTavilyMcp()
    app.state.tavily_mcp = tavily_mcp
    tarefa_do_mcp = asyncio.create_task(tavily_mcp.abrir()) if settings.tavily_api_key else None
    busca_web_faq = BuscaWebMcp(lambda: tavily_mcp.tool) if tarefa_do_mcp is not None else None
    try:
        app.state.fluxo_venus = compilar_grafo_venus(
            checkpointer=criar_checkpointer(),
            store=criar_store(),
            pool=pool,
            indice_rag=indice_faq,
            tools_faq_extras=await carregar_tools_faq_extras(),
            tools_rotina_extras=montar_tools_rotina_extras(pool),
            busca_web_faq=busca_web_faq,
        )
        app.state.a2a_app = criar_app_a2a(app.state.fluxo_venus)
        yield
    finally:
        tarefa_do_faq.cancel()
        await tavily_mcp.fechar(tarefa_do_mcp)
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


def _origens_cors() -> list[str]:
    """Origens de CORS_ORIGENS_PERMITIDAS. Sem a barra final: o `Origin` do
    navegador nunca tem barra, e `https://x.app/` no env nunca casaria."""
    return [origem.strip().rstrip("/") for origem in (settings.cors_origens_permitidas or "").split(",")
            if origem.strip()]


app = FastAPI(title="Venus AI API", lifespan=lifespan)
app.middleware("http")(medir_requisicao)
# Registrado depois do medir_requisicao: no Starlette o último registrado fica
# por fora, então o preflight (OPTIONS) do navegador é respondido aqui, sem
# virar métrica. O token vai no Authorization (sem cookie), por isso sem
# allow_credentials. O Retry-After exposto deixa a web ler a espera do 429.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origens_cors(),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Retry-After"],
)
app.include_router(v1_router, prefix="/v1")
app.mount(ROTA_A2A, A2ADinamico())
