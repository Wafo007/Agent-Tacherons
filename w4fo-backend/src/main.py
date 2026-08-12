"""
Point d'entrée de l'application W4FO Backend.

Assemble l'application FastAPI : middlewares, CORS, routers, cycle de vie du
scheduler de tâches proactives (réveil intelligent). Aucune logique métier ici
— uniquement du câblage d'infrastructure HTTP et de démarrage/arrêt de services.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import get_settings
from src.infrastructure.scheduler.proactive_jobs import start_scheduler, stop_scheduler
from src.presentation.api.v1.auth_router import router as auth_router
from src.presentation.api.v1.calendar_router import router as calendar_router
from src.presentation.api.v1.conversation_router import router as conversation_router
from src.presentation.api.v1.notifications_router import router as notifications_router
from src.presentation.api.v1.settings_router import router as settings_router
from src.presentation.api.v1.tasks_router import router as tasks_router
from src.presentation.api.websocket.voice_ws import router as voice_ws_router

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Démarre le scheduler au lancement de l'application, l'arrête proprement à la fermeture."""
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title=settings.app_name,
    description="Backend de l'assistant IA personnel W4FO",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(tasks_router)
app.include_router(calendar_router)
app.include_router(settings_router)
app.include_router(notifications_router)
app.include_router(conversation_router)
app.include_router(voice_ws_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Endpoint de vérification de santé du service."""
    return {"status": "ok", "app": settings.app_name}
