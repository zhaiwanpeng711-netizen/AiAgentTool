import asyncio
import logging
import os
import shutil
from typing import Optional

from backend.agents.base_agent import BaseAgent, LogCallback
from backend.config import CLAUDE_CLI_PATH, WORKSPACE_DIR, ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, OPENAI_API_KEY, CLAUDE_MODEL
from backend.scheduler.models import AgentType, Task
from backend.scheduler.usage_tracker import usage_tracker

logger = logging.getLogger(__name__)


class ClaudeAgent(BaseAgent):
    """Adapter for Claude Code CLI (claude)."""

    def __init__(self):
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    @property
    def agent_type(self) -> str:
        return AgentType.CLAUDE

    async def run(self, task: Task, on_log: LogCallback) -> int:
        workspace = task.workspace or WORKSPACE_DIR
        os.makedirs(workspace, exist_ok=True)

        # Check Anthropic API key is configured
        if not ANTHROPIC_API_KEY:
            await on_log(
                "ANTHROPIC_API_KEY is not set.\n"
                "Get a free API key at: https://console.anthropic.com\n"
                "Then add it to your .env file: ANTHROPIC_API_KEY=sk-ant-...",
                "error"
            )
            return 1

        # Check claude CLI is available
        if not shutil.which(CLAUDE_CLI_PATH):
            await on_log(
                f"Claude CLI not found at '{CLAUDE_CLI_PATH}'.\n"
                "Install it with: npm install -g @anthropic-ai/claude-code",
                "error"
            )
            return 1

        await on_log(f"Working directory: {workspace}", "system")
        await on_log(f"Invoking: {CLAUDE_CLI_PATH}", "system")

        cmd = [
            CLAUDE_CLI_PATH,
            "--print",          # non-interactive, print output
            "--dangerously-skip-permissions",  # skip confirmation prompts
        ]
        if CLAUDE_MODEL:
            cmd += ["--model", CLAUDE_MODEL]
        cmd.append(task.description)

        # Build environment — inject API keys and optional base URLs
        env = {**os.environ}
        if ANTHROPIC_API_KEY:
            env["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY
        if ANTHROPIC_BASE_URL:
            # Redirect Claude Code CLI to use the proxy (e.g. Bailian Coding Plan)
            env["ANTHROPIC_BASE_URL"] = ANTHROPIC_BASE_URL
            await on_log(f"Using Anthropic proxy: {ANTHROPIC_BASE_URL}", "system")
        if OPENAI_API_KEY:
            env["OPENAI_API_KEY"] = OPENAI_API_KEY

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace,
                env=env,
            )
            self._processes[task.id] = proc

            async def stream_reader(stream, level: str):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    text = line.decode("utf-8", errors="replace").rstrip()
                    if text:
                        await on_log(text, level)

            await asyncio.gather(
                stream_reader(proc.stdout, "info"),
                stream_reader(proc.stderr, "error"),
            )

            await proc.wait()
            rc = proc.returncode or 0
            usage_tracker.record(
                agent_type=AgentType.CLAUDE,
                model=CLAUDE_MODEL or "claude-3-5-sonnet-20241022",
            )
            return rc

        except FileNotFoundError:
            await on_log(
                f"Claude CLI not found at '{CLAUDE_CLI_PATH}'. "
                "Install it with: npm install -g @anthropic-ai/claude-code",
                "error"
            )
            return 1
        finally:
            self._processes.pop(task.id, None)

    async def stop(self, task_id: str):
        proc = self._processes.get(task_id)
        if proc:
            try:
                proc.terminate()
                await asyncio.sleep(0.5)
                if proc.returncode is None:
                    proc.kill()
            except ProcessLookupError:
                pass
            self._processes.pop(task_id, None)
