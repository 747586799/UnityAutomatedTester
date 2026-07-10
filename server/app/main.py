import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.agents.routes import router as agents_router
from app.agents.websocket import router as agent_socket_router
from app.api.unity_routes import router as unity_router
from app.automation.routes import router as automation_router
from app.dependencies import get_auto_task_scheduler
from app.websocket.unity_socket import router as unity_socket_router

WEB_DIR = Path(__file__).parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = get_auto_task_scheduler()
    scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")
    app = FastAPI(title="UnityAutomatedTester", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(agents_router)
    app.include_router(unity_router)
    app.include_router(automation_router)
    app.include_router(agent_socket_router)
    app.include_router(unity_socket_router)

    if WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

    return app


app = create_app()
