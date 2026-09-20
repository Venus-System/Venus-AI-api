from contextlib import asynccontextmanager

from fastapi import FastAPI
from venus_sdk.flows.venus_flow import compilar_grafo_venus
from venus_sdk.memory.checkpointer import criar_checkpointer_em_memoria

from venus_api.app.api.v1.endpoints.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Checkpointer provisório em RAM — só pra destravar o fluxo ponta a
    # ponta (Parte 1 do roteiro); troca pelo checkpointer de produção com
    # Mongo na Parte 3 (ver app/infra/checkpointer.py).
    app.state.fluxo_venus = compilar_grafo_venus(checkpointer=criar_checkpointer_em_memoria())
    yield


app = FastAPI(title="Venus AI API", lifespan=lifespan)
app.include_router(health_router, prefix="/v1")
