from contextlib import asynccontextmanager

from fastapi import FastAPI
from venus_sdk.flows.venus_flow import compilar_grafo_venus

from venus_api.app.api.v1.router import router as v1_router
from venus_api.app.infra.checkpointer import criar_checkpointer
from venus_api.app.infra.store import criar_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.fluxo_venus = compilar_grafo_venus(
        checkpointer=criar_checkpointer(),
        store=criar_store(),
    )
    yield


app = FastAPI(title="Venus AI API", lifespan=lifespan)
app.include_router(v1_router, prefix="/v1")
