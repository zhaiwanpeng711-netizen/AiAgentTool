from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class AgentType(str, Enum):
    CURSOR = "cursor"
    CLAUDE = "claude"
    CODEX = "codex"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class LogEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    level: str = "info"  # info | error | system
    message: str


class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str
    agent_type: AgentType
    workspace: Optional[str] = None  # working directory for this task
    status: TaskStatus = TaskStatus.PENDING
    logs: list[LogEntry] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    exit_code: Optional[int] = None

    def add_log(self, message: str, level: str = "info") -> LogEntry:
        from backend.config import MAX_LOG_LINES
        entry = LogEntry(message=message, level=level)
        self.logs.append(entry)
        if len(self.logs) > MAX_LOG_LINES:
            self.logs = self.logs[-MAX_LOG_LINES:]
        return entry

    def to_summary(self) -> dict:
        """Lightweight summary without full logs."""
        return {
            "id": self.id,
            "description": self.description,
            "agent_type": self.agent_type,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "exit_code": self.exit_code,
            "log_count": len(self.logs),
        }


class CreateTaskRequest(BaseModel):
    natural_language: str
    workspace: Optional[str] = None


class ParsedTask(BaseModel):
    agent: AgentType
    task: str
    workspace: Optional[str] = None


class AgentInfo(BaseModel):
    agent_type: AgentType
    running_tasks: int
    total_tasks: int
    available: bool
    description: str
