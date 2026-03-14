import asyncio
import logging
import os
import shutil
from typing import List, Optional

from backend.agents.base_agent import BaseAgent, LogCallback
from backend.config import CODEX_CLI_PATH, WORKSPACE_DIR, OPENAI_API_KEY, CODEX_MODEL
from backend.scheduler.models import AgentType, Task

logger = logging.getLogger(__name__)


def _resolve_codex_cmd() -> Optional[List[str]]:
    """Return the command list to invoke codex, or None if unavailable."""
    # 1. Explicit config path or 'codex' in PATH
    if shutil.which(CODEX_CLI_PATH):
        return [CODEX_CLI_PATH]
    # 2. Common manual install locations
    for candidate in [
        os.path.expanduser("~/.local/bin/codex"),
        "/usr/local/bin/codex",
        "/opt/homebrew/bin/codex",
    ]:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return [candidate]
    # 3. npx fallback (no global install required)
    if shutil.which("npx"):
        return ["npx", "--yes", "@openai/codex"]
    return None


class CodexAgent(BaseAgent):
    """Adapter for OpenAI Codex CLI (codex)."""

    def __init__(self):
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    @property
    def agent_type(self) -> str:
        return AgentType.CODEX

    async def run(self, task: Task, on_log: LogCallback) -> int:
        workspace = task.workspace or WORKSPACE_DIR
        os.makedirs(workspace, exist_ok=True)

        cmd_prefix: Optional[List[str]] = _resolve_codex_cmd()
        if cmd_prefix is None:
            await on_log(
                "Codex CLI not found. Install it by running in your terminal:\n"
                "  npm install -g @openai/codex\n"
                "Then restart the backend.",
                "error"
            )
            return 1

        await on_log(f"Working directory: {workspace}", "system")
        await on_log(f"Invoking: {' '.join(cmd_prefix)}", "system")

        # Build environment:
        # If the user ran `codex login` (ChatGPT Business), do NOT inject OPENAI_API_KEY
        # so codex uses the stored OAuth credentials (~/.codex/auth.json).
        # If OPENAI_API_KEY is set AND codex login is NOT present, use the API key.
        env = {**os.environ}
        codex_auth_file = os.path.expanduser("~/.codex/auth.json")
        using_login = os.path.isfile(codex_auth_file)

        if using_login:
            # Remove API key from env so codex falls back to login credentials
            env.pop("OPENAI_API_KEY", None)
            await on_log("Using codex login credentials (ChatGPT account)", "system")
        elif OPENAI_API_KEY:
            env["OPENAI_API_KEY"] = OPENAI_API_KEY
            await on_log("Using OPENAI_API_KEY for authentication", "system")
        else:
            await on_log(
                "No authentication found. Run `codex login` in your terminal "
                "to log in with your ChatGPT account, or set OPENAI_API_KEY in .env",
                "error"
            )
            return 1

        # codex v0.114+ uses subcommand syntax:
        # codex exec --full-auto --skip-git-repo-check -m gpt-4o "<prompt>"
        cmd = cmd_prefix + [
            "exec",
            "--full-auto",
            "--skip-git-repo-check",
            "-m", CODEX_MODEL,
            task.description,
        ]

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
            return proc.returncode or 0

        except FileNotFoundError:
            await on_log(
                "Codex CLI not found. Install it by running in your terminal:\n"
                "  npm install -g @openai/codex",
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
