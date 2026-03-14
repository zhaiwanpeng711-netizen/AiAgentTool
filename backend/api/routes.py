import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.scheduler.models import (
    CreateTaskRequest, AgentType, TaskStatus, ParsedTask
)
from backend.scheduler.task_manager import task_manager
from backend.nlp.parser import parse_natural_language
from backend.api.ws_handler import manager

logger = logging.getLogger(__name__)
router = APIRouter()


# ------------------------------------------------------------------
# WebSocket
# ------------------------------------------------------------------

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        # Send current state on connect
        tasks = task_manager.list_tasks()
        for task in tasks:
            await manager.send_personal(ws, {"event": "task_snapshot", "data": task.to_summary()})

        agents = task_manager.get_agent_info()
        for agent in agents:
            await manager.send_personal(ws, {"event": "agent_info", "data": agent.dict()})

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
# Health
# ------------------------------------------------------------------

@router.get("/api/health")
async def health():
    return {"status": "ok", "tasks": len(task_manager.list_tasks())}
