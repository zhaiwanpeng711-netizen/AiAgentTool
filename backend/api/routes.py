import logging
from typing import Optional
from datetime import timedelta
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from backend.security import (
    Token,
    User,
    fake_users_db,
    authenticate_user,
    create_access_token,
    decode_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

from backend.scheduler.models import (
    CreateTaskRequest, AgentType, TaskStatus, ParsedTask
)
from backend.scheduler.task_manager import task_manager
from backend.scheduler.usage_tracker import usage_tracker
from backend.nlp.parser import parse_natural_language
from backend.api.ws_handler import manager


class LoginRequest(BaseModel):
    username: str
    password: str


logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()


# ------------------------------------------------------------------
# WebSocket
# ------------------------------------------------------------------

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        # Signal frontend to clear stale state before receiving fresh snapshots.
        # This handles backend reloads (uvicorn hot-reload) that wipe in-memory tasks.
        current_tasks = task_manager.list_tasks()
        await manager.send_personal(ws, {
            "event": "state_reset",
            "data": {"task_count": len(current_tasks)}
        })

        # Send current state on connect (survives browser refresh)
        for task in current_tasks:
            await manager.send_personal(ws, {"event": "task_snapshot", "data": task.to_summary()})

        agents = task_manager.get_agent_info()
        for agent in agents:
            await manager.send_personal(ws, {"event": "agent_info", "data": agent.dict()})

        # Send usage stats snapshot
        await manager.send_personal(ws, {
            "event": "usage_updated",
            "data": usage_tracker.get_stats(),
        })

        # Keep connection alive, handle pings
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.disconnect(ws)


# ------------------------------------------------------------------
# Tasks
# ------------------------------------------------------------------

@router.post("/api/tasks/parse")
async def parse_tasks(request: CreateTaskRequest):
    """Parse natural language into task list (preview, no creation)."""
    parsed = await parse_natural_language(request.natural_language, request.workspace)
    return {"tasks": [p.dict() for p in parsed]}


@router.post("/api/tasks")
async def create_tasks(request: CreateTaskRequest):
    """Parse natural language, create tasks, and auto-start them."""
    parsed: list[ParsedTask] = await parse_natural_language(
        request.natural_language, request.workspace
    )
    if not parsed:
        raise HTTPException(status_code=400, detail="Could not parse any tasks from input")

    created = []
    for p in parsed:
        task = await task_manager.create_task(
            description=p.task,
            agent_type=p.agent,
            workspace=p.workspace,
        )
        created.append(task.to_summary())

    # Auto-start all created tasks
    for task_summary in created:
        await task_manager.start_task(task_summary["id"])

    return {"tasks": created}


@router.post("/api/tasks/manual")
async def create_task_manual(
    description: str,
    agent_type: AgentType,
    workspace: Optional[str] = None,
    auto_start: bool = True,
):
    """Manually create a single task without NLP parsing."""
    task = await task_manager.create_task(description, agent_type, workspace)
    if auto_start:
        await task_manager.start_task(task.id)
    return task.to_summary()


@router.get("/api/tasks")
async def list_tasks(
    status: Optional[TaskStatus] = None,
    agent_type: Optional[AgentType] = None,
):
    tasks = task_manager.list_tasks()
    if status:
        tasks = [t for t in tasks if t.status == status]
    if agent_type:
        tasks = [t for t in tasks if t.agent_type == agent_type]
    return {"tasks": [t.to_summary() for t in tasks]}


@router.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    data = task.to_summary()
    data["logs"] = [
        {"timestamp": l.timestamp.isoformat(), "level": l.level, "message": l.message}
        for l in task.logs
    ]
    return data


@router.post("/api/tasks/{task_id}/start")
async def start_task(task_id: str):
    ok = await task_manager.start_task(task_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Cannot start task")
    return {"status": "started"}


@router.post("/api/tasks/{task_id}/stop")
async def stop_task(task_id: str):
    ok = await task_manager.stop_task(task_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Task is not running")
    return {"status": "stopped"}


@router.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    ok = await task_manager.delete_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "deleted"}


# ------------------------------------------------------------------
# Agents
# ------------------------------------------------------------------

@router.get("/api/agents")
async def get_agents():
    agents = task_manager.get_agent_info()
    return {"agents": [a.dict() for a in agents]}


# ------------------------------------------------------------------
# Usage & Cost Statistics
# ------------------------------------------------------------------

@router.get("/api/usage")
async def get_usage():
    """Return per-agent token usage and estimated cost (in-memory, resets on server restart)."""
    return {
        "usage": usage_tracker.get_stats(),
        "total_cost_usd": usage_tracker.get_total_cost(),
    }


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------

@router.get("/api/health")
async def health():
    return {"status": "ok", "tasks": len(task_manager.list_tasks())}


# ------------------------------------------------------------------
# Authentication
# ------------------------------------------------------------------

@router.post("/api/login", response_model=Token)
async def login(request: LoginRequest):
    """Login endpoint that authenticates user and returns JWT token."""
    user = authenticate_user(fake_users_db, request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/api/users/me", response_model=User)
async def read_users_me(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user info."""
    token = credentials.credentials
    token_data = decode_access_token(token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = fake_users_db.get(token_data.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
