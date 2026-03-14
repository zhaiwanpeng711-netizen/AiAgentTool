import asyncio
import logging
import platform
import subprocess
import tempfile
import os

from backend.agents.base_agent import BaseAgent, LogCallback
from backend.config import CURSOR_APP_NAME, WORKSPACE_DIR
from backend.scheduler.models import AgentType, Task

logger = logging.getLogger(__name__)

SYSTEM = platform.system()  # "Darwin" or "Linux"


class CursorAgent(BaseAgent):
    """
    Adapter for Cursor IDE via GUI automation.
    - macOS: AppleScript to activate window, open Agent panel, type prompt
    - Linux: xdotool to perform the same operations
    """

    def __init__(self):
        self._stop_flags: dict[str, bool] = {}

    @property
    def agent_type(self) -> str:
        return AgentType.CURSOR

    async def run(self, task: Task, on_log: LogCallback) -> int:
        self._stop_flags[task.id] = False
        workspace = task.workspace or WORKSPACE_DIR
        os.makedirs(workspace, exist_ok=True)

        await on_log(f"Preparing Cursor agent for task...", "system")
        await on_log(f"Workspace: {workspace}", "system")

        try:
            if SYSTEM == "Darwin":
                return await self._run_macos(task, workspace, on_log)
            elif SYSTEM == "Linux":
                return await self._run_linux(task, workspace, on_log)
            else:
                await on_log(f"Unsupported OS: {SYSTEM}", "error")
                return 1
        finally:
            self._stop_flags.pop(task.id, None)

    # ------------------------------------------------------------------
    # macOS via AppleScript
    # ------------------------------------------------------------------

    async def _run_macos(self, task: Task, workspace: str, on_log: LogCallback) -> int:
        await on_log("Activating Cursor (macOS)...", "system")

        # 1. Open workspace in Cursor
        open_result = await self._run_shell(
            ["open", "-a", CURSOR_APP_NAME, workspace],
            on_log
        )
        if open_result != 0:
            await on_log(f"Failed to open Cursor with workspace: {workspace}", "error")

        await asyncio.sleep(2.0)  # Wait for Cursor to focus

        if self._stop_flags.get(task.id):
            return 0

        # 2. Open Agent/Composer panel (Cmd+I)
        applescript_open_panel = f'''
tell application "{CURSOR_APP_NAME}"
    activate
end tell
delay 0.5
tell application "System Events"
    keystroke "i" using command down
end tell
delay 1.0
'''
        await self._run_applescript(applescript_open_panel, on_log)

        if self._stop_flags.get(task.id):
            return 0

        # 3. Type the task into the input field and submit
        safe_task = task.description.replace('"', '\\"').replace("'", "\\'")
        applescript_type = f'''
tell application "System Events"
    -- Clear any existing content and type the task
    key code 0 using command down
    delay 0.2
    set the clipboard to "{safe_task}"
    keystroke "v" using command down
    delay 0.5
    key code 36
end tell
'''
        await self._run_applescript(applescript_type, on_log)
        await on_log("Task submitted to Cursor Agent. Monitoring for completion...", "system")

        # 4. Monitor for completion by polling Cursor window title / accessibility
        return await self._monitor_cursor_macos(task, on_log)

    async def _monitor_cursor_macos(self, task: Task, on_log: LogCallback) -> int:
        """Poll every 5 seconds for task completion signals."""
        max_wait = 3600  # 1 hour timeout
        elapsed = 0
        check_interval = 5

        while elapsed < max_wait:
            if self._stop_flags.get(task.id):
                await on_log("Cursor task stopped by user.", "system")
                return 0

            # Check if Cursor is still processing (look for "Working..." in title or UI)
            script = f'''
tell application "System Events"
    tell process "{CURSOR_APP_NAME}"
        set frontWindow to front window
        set wTitle to title of frontWindow
        return wTitle
    end tell
end tell
'''
            result = await self._run_applescript_capture(script)
            if result:
                await on_log(f"[Cursor] Window: {result.strip()}", "info")

            await asyncio.sleep(check_interval)
            elapsed += check_interval

            # Heuristic: if window title no longer shows "Generating" or "Working"
            if result and not any(kw in result.lower() for kw in ["generating", "working", "running"]):
                if elapsed > 10:  # Give it at least 10 seconds
                    await on_log("Cursor Agent appears to have completed the task.", "system")
                    return 0

        await on_log("Cursor task monitoring timed out.", "error")
        return 1

    # ------------------------------------------------------------------
    # Linux via xdotool
    # ------------------------------------------------------------------

    async def _run_linux(self, task: Task, workspace: str, on_log: LogCallback) -> int:
        await on_log("Activating Cursor (Linux/xdotool)...", "system")

        # Check xdotool is available
        check = await self._run_shell(["which", "xdotool"], on_log, capture=True)
        if check != 0:
            await on_log("xdotool not found. Install: sudo apt install xdotool", "error")
            return 1

        # Open workspace in cursor
        await self._run_shell(["cursor", workspace], on_log)
        await asyncio.sleep(3.0)

        if self._stop_flags.get(task.id):
            return 0

        # Find Cursor window ID
        win_id_result = subprocess.run(
            ["xdotool", "search", "--name", "Cursor"],
            capture_output=True, text=True
        )
        win_ids = win_id_result.stdout.strip().split("\n")
        if not win_ids or not win_ids[0]:
            await on_log("Could not find Cursor window via xdotool", "error")
            return 1

        win_id = win_ids[-1]  # Use last (most recent)
        await on_log(f"Found Cursor window ID: {win_id}", "system")

        # Focus window and open Agent panel (Ctrl+I on Linux)
        await self._run_shell(["xdotool", "windowactivate", "--sync", win_id], on_log)
        await asyncio.sleep(0.5)
        await self._run_shell(["xdotool", "key", "--window", win_id, "ctrl+i"], on_log)
        await asyncio.sleep(1.0)

        if self._stop_flags.get(task.id):
            return 0

        # Type the task
        safe_task = task.description.replace("'", "'\\''")
        await self._run_shell(
            ["xdotool", "type", "--window", win_id, "--clearmodifiers", "--delay", "30", task.description],
            on_log
        )
        await asyncio.sleep(0.3)
        await self._run_shell(["xdotool", "key", "--window", win_id, "Return"], on_log)

        await on_log("Task submitted to Cursor Agent (Linux). Monitoring for completion...", "system")
        return await self._monitor_cursor_linux(task, win_id, on_log)

    async def _monitor_cursor_linux(self, task: Task, win_id: str, on_log: LogCallback) -> int:
        max_wait = 3600
        elapsed = 0
        check_interval = 5

        while elapsed < max_wait:
            if self._stop_flags.get(task.id):
                return 0

            result = subprocess.run(
                ["xdotool", "getwindowname", win_id],
                capture_output=True, text=True
            )
            title = result.stdout.strip()
            if title:
                await on_log(f"[Cursor] Window: {title}", "info")

            await asyncio.sleep(check_interval)
            elapsed += check_interval

            if elapsed > 10 and not any(kw in title.lower() for kw in ["generating", "working", "running"]):
                await on_log("Cursor Agent appears to have completed the task.", "system")
                return 0

        await on_log("Cursor task monitoring timed out.", "error")
        return 1

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _run_shell(self, cmd: list, on_log: LogCallback, capture: bool = False) -> int:
        try:
            if capture:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
            _, stderr = await proc.communicate()
            if stderr:
                decoded = stderr.decode("utf-8", errors="replace").strip()
                if decoded:
                    await on_log(decoded, "error")
            return proc.returncode or 0
        except Exception as e:
            await on_log(f"Shell error: {e}", "error")
            return 1

    async def _run_applescript(self, script: str, on_log: LogCallback) -> int:
        try:
            proc = await asyncio.create_subprocess_exec(
                "osascript", "-e", script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if stderr:
                decoded = stderr.decode("utf-8", errors="replace").strip()
                if decoded:
                    await on_log(f"AppleScript: {decoded}", "error")
            return proc.returncode or 0
        except Exception as e:
            await on_log(f"AppleScript error: {e}", "error")
            return 1

    async def _run_applescript_capture(self, script: str) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                "osascript", "-e", script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return stdout.decode("utf-8", errors="replace").strip()
        except Exception:
            return ""

    async def stop(self, task_id: str):
        self._stop_flags[task_id] = True
