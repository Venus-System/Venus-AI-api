from contextlib import asynccontextmanager

from fastapi import FastAPI
from venus_sdk.flows.venus_flow import compilar_grafo_venus

from venus_api.app.api.v1.router import router as v1_router
from venus_api.app.infra.checkpointer import criar_checkpointer
from venus_api.app.infra.store import criar_store
from venus_api.app.observability import tracing
from venus_api.app.observability.middleware import medir_requisicao


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.fluxo_venus = compilar_grafo_venus(
        checkpointer=criar_checkpointer(),
        store=criar_store(),
    )
    yield
    # O Langfuse envia os traces em lote, em segundo plano. Sem isso, o que
    # ainda não tinha sido enviado se perde quando a API desliga.
    langfuse = tracing.get_langfuse()
    if langfuse is not None:
        langfuse.shutdown()


app = FastAPI(title="Venus AI API", lifespan=lifespan)
app.middleware("http")(medir_requisicao)
app.include_router(v1_router, prefix="/v1")
