from fastapi import FastAPI

from venus_api.app.api.v1.endpoints.health import router as health_router

app = FastAPI(title="Venus AI API")
app.include_router(health_router, prefix="/v1")
