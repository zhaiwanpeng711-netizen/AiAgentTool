from abc import ABC, abstractmethod
from typing import Callable, Awaitable, Optional
from backend.scheduler.models import Task

LogCallback = Callable[[str, str], Awaitable[None]]


class BaseAgent(ABC):
    """Abstract base class for all AI agent adapters."""

    @abstractmethod
    async def run(self, task: Task, on_log: LogCallback) -> int:
        """
        Execute the task. Stream output via on_log(message, level).
        Returns exit code (0 = success).
        """
        ...

    async def stop(self, task_id: str):
        """Stop a running task by ID. Default is no-op (handled by CancelledError)."""
        pass

    @property
    @abstractmethod
    def agent_type(self) -> str:
        ...
