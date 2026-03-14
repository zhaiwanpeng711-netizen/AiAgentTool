import asyncio
import logging
from datetime import datetime
from typing import Optional, Callable, Awaitable

from backend.scheduler.models import Task, TaskStatus, AgentType, AgentInfo
from backend.config import MAX_PARALLEL_TASKS

logger = logging.getLogger(__name__)


class TaskManager:
    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._running: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._broadcast_callback: Optional[Callable[[dict], Awaitable[None]]] = None
        self._agents: dict[AgentType, any] = {}

    def set_broadcast_callback(self, callback: Callable[[dict], Awaitable[None]]):
        """Register the WebSocket broadcast function."""
        self._broadcast_callback = callback

    def register_agent(self, agent_type: AgentType, agent):
        self._agents[agent_type] = agent

    async def _broadcast(self, event: str, data: dict):
        if self._broadcast_callback:
            try:
                await self._broadcast_callback({"event": event, "data": data})
            except Exception as e:
                logger.error(f"Broadcast error: {e}")

    # ------------------------------------------------------------------
    # Task CRUD
    # ------------------------------------------------------------------

    async def create_task(self, description: str, agent_type: AgentType, workspace: Optional[str] = None) -> Task:
        task = Task(description=description, agent_type=agent_type, workspace=workspace)
        async with self._lock:
            self._tasks[task.id] = task
        await self._broadcast("task_created", task.to_summary())
        logger.info(f"Task created: {task.id} [{agent_type}] {description[:60]}")
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[Task]:
        return list(self._tasks.values())

    def get_agent_info(self) -> list[AgentInfo]:
        infos = []
        for agent_type in AgentType:
            tasks = [t for t in self._tasks.values() if t.agent_type == agent_type]
            running = sum(1 for t in tasks if t.status == TaskStatus.RUNNING)
            agent = self._agents.get(agent_type)
            infos.append(AgentInfo(
                agent_type=agent_type,
                running_tasks=running,
                total_tasks=len(tasks),
                available=agent is not None,
                description=self._agent_description(agent_type),
            ))
        return infos

    def _agent_description(self, agent_type: AgentType) -> str:
        descriptions = {
            AgentType.CURSOR: "Cursor IDE (GUI automation)",
            AgentType.CLAUDE: "Claude Code CLI",
            AgentType.CODEX: "OpenAI Codex CLI",
        }
        return descriptions.get(agent_type, "Unknown")

    # ------------------------------------------------------------------
    # Task lifecycle
    # ------------------------------------------------------------------

    async def start_task(self, task_id: str) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False
        if task.status == TaskStatus.RUNNING:
            return True
        if task.status not in (TaskStatus.PENDING, TaskStatus.FAILED, TaskStatus.STOPPED):
            return False

        # Check parallel limit
        running_count = sum(
            1 for t in self._tasks.values()
            if t.agent_type == task.agent_type and t.status == TaskStatus.RUNNING
        )
        if running_count >= MAX_PARALLEL_TASKS:
            task.add_log(f"Max parallel tasks ({MAX_PARALLEL_TASKS}) reached for {task.agent_type}", "system")
            return False

        agent = self._agents.get(task.agent_type)
        if not agent:
            task.status = TaskStatus.FAILED
            task.add_log(f"No agent registered for type: {task.agent_type}", "error")
            await self._broadcast("task_updated", task.to_summary())
            return False

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        task.logs.clear()
        task.add_log(f"Starting task on {task.agent_type} agent...", "system")
        await self._broadcast("task_updated", task.to_summary())

        async def run():
            try:
                async def on_log(message: str, level: str = "info"):
                    entry = task.add_log(message, level)
                    await self._broadcast("task_log", {
                        "task_id": task.id,
                        "log": {"timestamp": entry.timestamp.isoformat(), "level": entry.level, "message": entry.message}
                    })

                exit_code = await agent.run(task, on_log)
                task.exit_code = exit_code
                task.completed_at = datetime.utcnow()
                if task.status == TaskStatus.RUNNING:
                    task.status = TaskStatus.COMPLETED if exit_code == 0 else TaskStatus.FAILED
                task.add_log(f"Task finished with exit code {exit_code}", "system")
            except asyncio.CancelledError:
                task.status = TaskStatus.STOPPED
                task.completed_at = datetime.utcnow()
                task.add_log("Task was stopped.", "system")
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.utcnow()
                task.add_log(f"Task error: {e}", "error")
                logger.exception(f"Task {task.id} failed")
            finally:
                self._running.pop(task.id, None)
                await self._broadcast("task_updated", task.to_summary())

        async_task = asyncio.create_task(run())
        self._running[task.id] = async_task
        return True

    async def stop_task(self, task_id: str) -> bool:
        task = self.get_task(task_id)
        if not task or task.status != TaskStatus.RUNNING:
            return False

        agent = self._agents.get(task.agent_type)
        if agent and hasattr(agent, "stop"):
            await agent.stop(task_id)

        async_task = self._running.get(task_id)
        if async_task:
            async_task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(async_task), timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        task.status = TaskStatus.STOPPED
        task.completed_at = datetime.utcnow()
        await self._broadcast("task_updated", task.to_summary())
        return True

    async def delete_task(self, task_id: str) -> bool:
        await self.stop_task(task_id)
        async with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                await self._broadcast("task_deleted", {"task_id": task_id})
                return True
        return False

    async def start_all_pending(self):
        """Auto-start all pending tasks."""
        for task in list(self._tasks.values()):
            if task.status == TaskStatus.PENDING:
                await self.start_task(task.id)


# Singleton
task_manager = TaskManager()
