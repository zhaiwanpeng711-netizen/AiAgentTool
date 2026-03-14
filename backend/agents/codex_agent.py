import asyncio
import logging
import os
import shutil
from typing import List, Optional

from backend.agents.base_agent import BaseAgent, LogCallback
from backend.config import (
    CODEX_CLI_PATH, WORKSPACE_DIR, OPENAI_API_KEY, CODEX_MODEL,
    CODEX_DEFAULT_PROFILE, CODEX_HOME_PERSONAL, CODEX_HOME_BUSINESS,
)
from backend.scheduler.models import AgentType, Task
from backend.scheduler.usage_tracker import usage_tracker

logger = logging.getLogger(__name__)

# Profile name → CODEX_HOME directory
PROFILE_HOMES = {
    "personal": CODEX_HOME_PERSONAL,
    "business": CODEX_HOME_BUSINESS,
}


def _translate_codex_error(text: str) -> str:
    """Make common Codex errors more actionable."""
    t = text.lower()
    if "usage limit" in t and "try again" in t:
        return (
            f"{text}\n"
            "⚠️  该账号 Codex 配额已用完，等待重置后重试，\n"
            "   或切换到另一个账号（在 .env 修改 CODEX_DEFAULT_PROFILE）。"
        )
    if "model is not supported" in t:
        return (
            f"{text}\n"
            "⚠️  模型不被支持。请在 .env 调整 CODEX_MODEL，\n"
            "   可选值：gpt-5.2-codex / gpt-5.1-codex-mini / auto"
        )
    if "not logged in" in t:
        return f"{text}\n⚠️  该 profile 未登录，请按说明运行登录命令。"
    return text


def _resolve_auth(profile: str, profile_home: str):
    """
    Find the best CODEX_HOME that has a valid auth.json.

    Returns (codex_home_path, description) or (None, None) if no login found.

    Priority:
      1. Profile-specific home  (e.g. ~/.codex-personal/auth.json)
      2. Default codex home     (~/.codex/auth.json)
    """
    candidates = [
        (profile_home,                    f"saved login for '{profile}' profile"),
        (os.path.expanduser("~/.codex"),  "default codex login (~/.codex)"),
    ]
    for home, desc in candidates:
        auth = os.path.join(home, "auth.json")
        if os.path.isfile(auth):
            return home, desc
    return None, None


def _resolve_codex_cmd() -> Optional[List[str]]:
    """Return the codex command list, or None if not found."""
    if shutil.which(CODEX_CLI_PATH):
        return [CODEX_CLI_PATH]
    for candidate in [
        os.path.expanduser("~/.local/bin/codex"),
        "/usr/local/bin/codex",
        "/opt/homebrew/bin/codex",
    ]:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return [candidate]
    if shutil.which("npx"):
        return ["npx", "--yes", "@openai/codex"]
    return None


def _get_profile_for_task(task: Task) -> str:
    """
    Determine which profile to use for this task.
    Tasks can specify a profile via description prefix:
      [personal] do something  →  use personal account
      [business] do something  →  use business account
    Otherwise use CODEX_DEFAULT_PROFILE.
    """
    desc = task.description.strip()
    if desc.startswith("[personal]"):
        return "personal"
    if desc.startswith("[business]"):
        return "business"
    return CODEX_DEFAULT_PROFILE


def _strip_profile_prefix(description: str) -> str:
    """Remove [personal] or [business] prefix from task description."""
    for prefix in ("[personal]", "[business]"):
        if description.strip().startswith(prefix):
            return description.strip()[len(prefix):].strip()
    return description


class CodexAgent(BaseAgent):
    """
    Adapter for OpenAI Codex CLI with dual-account support.

    Profiles:
      personal  → CODEX_HOME=~/.codex-personal  (personal ChatGPT account)
      business  → CODEX_HOME=~/.codex-business  (ChatGPT Business account)

    Setup (run once in your terminal):
      # Personal account
      CODEX_HOME=~/.codex-personal codex login

      # Business account
      CODEX_HOME=~/.codex-business codex login

    Task-level override (prefix your task description):
      [personal] 用Codex生成排序算法
      [business] 用Codex重构认证模块
    """

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
                "Codex CLI 未找到，请在终端运行：npm install -g @openai/codex",
                "error"
            )
            return 1

        # Determine profile and codex home
        profile = _get_profile_for_task(task)
        codex_home = PROFILE_HOMES.get(profile, CODEX_HOME_PERSONAL)
        actual_description = _strip_profile_prefix(task.description)

        await on_log(f"Working directory: {workspace}", "system")
        await on_log(f"Invoking: {' '.join(cmd_prefix)}", "system")

        # Resolve which CODEX_HOME to actually use:
        # Priority: profile-specific home (if auth.json exists) → default ~/.codex → API key
        #
        # Strip OPENAI_BASE_URL so Codex CLI does NOT hit the Bailian proxy.
        # Codex CLI uses the newer /v1/responses endpoint which Bailian doesn't support.
        # The Python NLP parser uses OPENAI_BASE_URL internally; the CLI should not.
        env = {k: v for k, v in os.environ.items() if k != "OPENAI_BASE_URL"}
        resolved_home, auth_source = _resolve_auth(profile, codex_home)

        if resolved_home:
            env["CODEX_HOME"] = resolved_home
            await on_log(f"Account profile: {profile} (CODEX_HOME={resolved_home})", "system")
            await on_log(f"Auth: {auth_source}", "system")
            env.pop("OPENAI_API_KEY", None)
        elif OPENAI_API_KEY:
            # Don't set CODEX_HOME — let codex use its default location
            env.pop("CODEX_HOME", None)
            env["OPENAI_API_KEY"] = OPENAI_API_KEY
            await on_log(f"Account profile: {profile} — no saved login found, using OPENAI_API_KEY", "system")
        else:
            default_home = os.path.expanduser("~/.codex")
            await on_log(
                f"未找到任何登录凭证！\n"
                f"请在终端运行以下命令登录个人账号：\n"
                f"  CODEX_HOME={codex_home} codex login\n"
                f"或登录到默认目录：\n"
                f"  codex login",
                "error"
            )
            return 1

        # Build command
        model_args = [] if CODEX_MODEL.lower() == "auto" else ["-m", CODEX_MODEL]
        cmd = cmd_prefix + [
            "exec",
            "--full-auto",
            "--skip-git-repo-check",
            *model_args,
            actual_description,
        ]
        await on_log(f"Model: {CODEX_MODEL}", "system")

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
                        await on_log(_translate_codex_error(text), level)

            await asyncio.gather(
                stream_reader(proc.stdout, "info"),
                stream_reader(proc.stderr, "error"),
            )
            await proc.wait()
            rc = proc.returncode or 0
            usage_tracker.record(
                agent_type=AgentType.CODEX,
                model=CODEX_MODEL,
            )
            return rc

        except FileNotFoundError:
            await on_log("Codex CLI 未找到，请运行：npm install -g @openai/codex", "error")
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
