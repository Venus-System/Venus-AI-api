# Router principal da v1: agrega os routers de cada endpoint (chat, health)
# em um único APIRouter, que é incluído em app/main.py com o prefixo /v1.

from fastapi import APIRouter

from venus_api.app.api.v1.endpoints.chat import router as chat_router
from venus_api.app.api.v1.endpoints.health import router as health_router

router = APIRouter()
router.include_router(health_router)
router.include_router(chat_router)
