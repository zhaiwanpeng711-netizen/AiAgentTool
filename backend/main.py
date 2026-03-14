import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pathlib

from backend.config import HOST, PORT
from backend.scheduler.task_manager import task_manager
from backend.scheduler.usage_tracker import usage_tracker
from backend.scheduler.models import AgentType
from backend.agents.claude_agent import ClaudeAgent
from backend.agents.codex_agent import CodexAgent
from backend.agents.cursor_agent import CursorAgent
from backend.agents.qwen_agent import QwenAgent
from backend.api.ws_handler import manager
from backend.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register agents
    task_manager.register_agent(AgentType.CLAUDE, ClaudeAgent())
    task_manager.register_agent(AgentType.CODEX, CodexAgent())
    task_manager.register_agent(AgentType.CURSOR, CursorAgent())
    task_manager.register_agent(AgentType.QWEN, QwenAgent())

    # Wire up WebSocket broadcast to task manager and usage tracker
    task_manager.set_broadcast_callback(manager.broadcast)
    usage_tracker.set_broadcast_callback(manager.broadcast)

    logger.info("AI Agent Scheduler started. Agents registered: claude, codex, cursor, qwen")
    yield
    logger.info("Shutting down AI Agent Scheduler...")


app = FastAPI(
    title="AI Agent Scheduler",
    description="Schedule and monitor AI coding agents (Cursor, Claude Code, Codex)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Serve frontend build if available
frontend_dist = pathlib.Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        index = frontend_dist / "index.html"
        return FileResponse(str(index))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)
