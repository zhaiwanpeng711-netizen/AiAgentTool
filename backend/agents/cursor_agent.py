import asyncio
import logging
import platform
import subprocess
import os
from pathlib import Path

from backend.agents.base_agent import BaseAgent, LogCallback
from backend.config import CURSOR_APP_NAME, WORKSPACE_DIR
from backend.scheduler.models import AgentType, Task

logger = logging.getLogger(__name__)

SYSTEM = platform.system()  # "Darwin" or "Linux"

# Directories / extensions to ignore when watching for file changes
_IGNORE_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv',
                'dist', 'build', '.next', '.nuxt', '.cache'}
_IGNORE_EXT  = {'.pyc', '.pyo', '.log', '.DS_Store'}
# Max bytes to preview per file in the result summary
_PREVIEW_BYTES = 2000

_LANG_MAP = {
    '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
    '.tsx': 'tsx', '.jsx': 'jsx', '.html': 'html', '.css': 'css',
    '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml', '.sh': 'bash',
    '.md': 'markdown', '.go': 'go', '.rs': 'rust', '.java': 'java',
    '.cpp': 'cpp', '.c': 'c', '.sql': 'sql', '.toml': 'toml',
}

def _guess_lang(filename: str) -> str:
    return _LANG_MAP.get(Path(filename).suffix.lower(), '')


def _workspace_snapshot(workspace: str) -> dict[str, float]:
    """Return {rel_path: mtime} for all tracked files in workspace."""
    snap = {}
    base = Path(workspace)
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith('.')]
        for f in files:
            if any(f.endswith(ext) for ext in _IGNORE_EXT):
                continue
            full = Path(root) / f
            try:
                snap[str(full.relative_to(base))] = full.stat().st_mtime
            except (OSError, ValueError):
                pass
    return snap


def _workspace_diff(before: dict[str, float], workspace: str) -> dict:
    """Diff current workspace against before snapshot."""
    after = _workspace_snapshot(workspace)
    added    = sorted(p for p in after if p not in before)
    modified = sorted(p for p in after if p in before and after[p] != before[p])
    deleted  = sorted(p for p in before if p not in after)
    return {"added": added, "modified": modified, "deleted": deleted, "after": after}


class CursorAgent(BaseAgent):
    """
    Cursor IDE Agent via GUI automation.

    macOS flow:
      1. pbcopy → set clipboard safely (handles all special chars)
      2. open -a Cursor <workspace>  →  open/focus workspace
      3. AppleScript: Cmd+L  →  open/focus Chat panel
      4. AppleScript: Cmd+A + Delete  →  clear input
      5. AppleScript: Cmd+V  →  paste task
      6. AppleScript: Return  →  submit
      7. Poll window state for completion

    Linux flow: xdotool equivalent steps
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
    # macOS
    # ------------------------------------------------------------------

    async def _run_macos(self, task: Task, workspace: str, on_log: LogCallback) -> int:
        # ── Step 0: snapshot workspace before submission ───────────────
        before_snap = _workspace_snapshot(workspace)
        await on_log(f"Workspace snapshot: {len(before_snap)} existing files tracked.", "system")

        # ── Step 1: set clipboard via pbcopy (safe for any text) ──────
        await on_log("Setting clipboard content...", "system")
        try:
            pbcopy = await asyncio.create_subprocess_exec(
                "pbcopy",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await pbcopy.communicate(input=task.description.encode("utf-8"))
        except Exception as e:
            await on_log(f"pbcopy failed: {e}", "error")
            return 1

        # ── Step 2: open workspace in Cursor ──────────────────────────
        await on_log("Opening workspace in Cursor...", "system")
        ret = await self._shell(["open", "-a", CURSOR_APP_NAME, workspace])
        if ret != 0:
            # Fallback: try 'cursor' CLI
            ret = await self._shell(["cursor", workspace])
        if ret != 0:
            await on_log("Failed to open Cursor. Make sure Cursor is installed.", "error")
            return 1

        # Wait for Cursor to load the workspace
        await on_log("Waiting for Cursor to load...", "system")
        await asyncio.sleep(3.0)

        if self._stop_flags.get(task.id):
            return 0

        # ── Step 3: activate + open Chat panel with Cmd+L ────────────
        await on_log("Opening Cursor Chat panel (Cmd+L)...", "system")
        script_open_chat = f'''
tell application "{CURSOR_APP_NAME}"
    activate
end tell
delay 1.0
tell application "System Events"
    tell process "{CURSOR_APP_NAME}"
        -- Cmd+L opens/focuses the AI chat sidebar
        keystroke "l" using command down
    end tell
end tell
delay 1.5
'''
        rc = await self._applescript(script_open_chat, on_log)
        if rc != 0:
            await on_log("Could not open Cursor chat panel via AppleScript. "
                         "Check: System Preferences → Privacy → Accessibility (grant terminal access).",
                         "error")
            return 1

        if self._stop_flags.get(task.id):
            return 0

        # ── Step 4 & 5: clear input field + paste task ────────────────
        await on_log("Pasting task into Cursor Agent input...", "system")
        script_paste = f'''
tell application "System Events"
    tell process "{CURSOR_APP_NAME}"
        -- Select all existing text in the input and delete it
        keystroke "a" using command down
        delay 0.2
        key code 51
        delay 0.2
        -- Paste the task from clipboard
        keystroke "v" using command down
        delay 0.5
    end tell
end tell
'''
        await self._applescript(script_paste, on_log)

        if self._stop_flags.get(task.id):
            return 0

        # ── Step 6: submit with Return ────────────────────────────────
        await on_log("Submitting task to Cursor Agent...", "system")
        script_submit = f'''
tell application "System Events"
    tell process "{CURSOR_APP_NAME}"
        key code 36
    end tell
end tell
'''
        await self._applescript(script_submit, on_log)
        await on_log("✓ Task submitted to Cursor Agent chat.", "system")
        await on_log(
            "Cursor Agent is now working on the task.\n"
            "Watch progress in the Cursor window.\n"
            "Click [Stop] in this panel when Cursor finishes — results will appear here.",
            "system"
        )

        # ── Step 7: monitor + capture file results ────────────────────
        rc = await self._monitor_macos(task, workspace, before_snap, on_log)
        await self._report_results(workspace, before_snap, on_log)
        return rc

    async def _monitor_macos(
        self, task: Task, workspace: str, before_snap: dict, on_log: LogCallback
    ) -> int:
        """
        Poll Cursor window + workspace every 10s.
        Reports file changes in real-time; user clicks Stop when satisfied.
        Auto-completes after 1h timeout.
        """
        max_wait = 3600
        elapsed = 0
        interval = 10
        last_title = ""
        reported_files: set[str] = set()

        while elapsed < max_wait:
            if self._stop_flags.get(task.id):
                await on_log("Cursor task stopped by user.", "system")
                return 0

            # ── Check window title ────────────────────────────────────
            script = f'''
try
    tell application "System Events"
        tell process "{CURSOR_APP_NAME}"
            return title of front window
        end tell
    end tell
on error
    return ""
end try
'''
            title = await self._applescript_capture(script)
            if title and title != last_title:
                await on_log(f"[Cursor] {title}", "info")
                last_title = title

            # ── Report newly created/modified files ───────────────────
            diff = _workspace_diff(before_snap, workspace)
            new_files = [f for f in (diff["added"] + diff["modified"]) if f not in reported_files]
            for rel in new_files:
                reported_files.add(rel)
                action = "新增" if rel in diff["added"] else "修改"
                await on_log(f"[文件{action}] {rel}", "info")

            # ── Heuristic: auto-complete if Cursor goes to background ──
            is_busy = any(kw in title.lower() for kw in
                          ["generating", "working", "running", "thinking", "loading"])
            if not is_busy and elapsed >= 30:
                front_app = await self._applescript_capture(
                    'tell application "System Events" to return name of first process whose frontmost is true'
                )
                if front_app and CURSOR_APP_NAME.lower() not in front_app.lower():
                    await on_log("Cursor 已切到后台 — 任务标记为完成。", "system")
                    return 0

            await asyncio.sleep(interval)
            elapsed += interval

        await on_log("Cursor task monitoring timed out (1 hour). Marking complete.", "system")
        return 0

    # ------------------------------------------------------------------
    # Linux via xdotool
    # ------------------------------------------------------------------

    async def _run_linux(self, task: Task, workspace: str, on_log: LogCallback) -> int:
        before_snap = _workspace_snapshot(workspace)
        await on_log(f"Workspace snapshot: {len(before_snap)} existing files tracked.", "system")
        await on_log("Activating Cursor (Linux/xdotool)...", "system")

        import shutil
        if not shutil.which("xdotool"):
            await on_log("xdotool not found. Install: sudo apt install xdotool", "error")
            return 1

        # Open workspace
        await self._shell(["cursor", workspace])
        await asyncio.sleep(3.0)

        if self._stop_flags.get(task.id):
            return 0

        # Find Cursor window
        result = subprocess.run(
            ["xdotool", "search", "--name", "Cursor"],
            capture_output=True, text=True
        )
        win_ids = [w for w in result.stdout.strip().split("\n") if w]
        if not win_ids:
            await on_log("Could not find Cursor window via xdotool.", "error")
            return 1
        win_id = win_ids[-1]
        await on_log(f"Found Cursor window: {win_id}", "system")

        # Focus + open Chat (Ctrl+L on Linux)
        subprocess.run(["xdotool", "windowactivate", "--sync", win_id])
        await asyncio.sleep(0.5)
        subprocess.run(["xdotool", "key", "--window", win_id, "ctrl+l"])
        await asyncio.sleep(1.5)

        if self._stop_flags.get(task.id):
            return 0

        # Set clipboard using xclip/xsel
        import shutil as _sh
        clip_cmd = None
        if _sh.which("xclip"):
            clip_cmd = ["xclip", "-selection", "clipboard"]
        elif _sh.which("xsel"):
            clip_cmd = ["xsel", "--clipboard", "--input"]
        if clip_cmd:
            p = subprocess.Popen(clip_cmd, stdin=subprocess.PIPE)
            p.communicate(input=task.description.encode("utf-8"))
        else:
            await on_log("xclip/xsel not found, using xdotool type (may be slow).", "system")

        # Clear + paste
        subprocess.run(["xdotool", "key", "--window", win_id, "ctrl+a"])
        await asyncio.sleep(0.2)
        if clip_cmd:
            subprocess.run(["xdotool", "key", "--window", win_id, "ctrl+v"])
        else:
            subprocess.run([
                "xdotool", "type", "--window", win_id,
                "--clearmodifiers", "--delay", "20", task.description
            ])
        await asyncio.sleep(0.5)

        # Submit
        subprocess.run(["xdotool", "key", "--window", win_id, "Return"])
        await on_log("✓ Task submitted to Cursor Agent (Linux).", "system")
        await on_log(
            "Watch progress in the Cursor window.\nClick [Stop] when Cursor finishes — results will appear here.",
            "system"
        )

        rc = await self._monitor_linux(task, win_id, workspace, before_snap, on_log)
        await self._report_results(workspace, before_snap, on_log)
        return rc

    async def _monitor_linux(
        self, task: Task, win_id: str, workspace: str, before_snap: dict, on_log: LogCallback
    ) -> int:
        max_wait = 3600
        elapsed = 0
        interval = 10
        last_title = ""
        reported_files: set[str] = set()

        while elapsed < max_wait:
            if self._stop_flags.get(task.id):
                return 0

            r = subprocess.run(["xdotool", "getwindowname", win_id],
                               capture_output=True, text=True)
            title = r.stdout.strip()
            if title and title != last_title:
                await on_log(f"[Cursor] {title}", "info")
                last_title = title

            # Report newly created/modified files
            diff = _workspace_diff(before_snap, workspace)
            new_files = [f for f in (diff["added"] + diff["modified"]) if f not in reported_files]
            for rel in new_files:
                reported_files.add(rel)
                action = "新增" if rel in diff["added"] else "修改"
                await on_log(f"[文件{action}] {rel}", "info")

            is_busy = any(kw in title.lower() for kw in
                          ["generating", "working", "running", "thinking"])
            if not is_busy and elapsed >= 30:
                await on_log("Cursor appears idle — marking task as completed.", "system")
                return 0

            await asyncio.sleep(interval)
            elapsed += interval

        return 0

    # ------------------------------------------------------------------
    # Results reporting
    # ------------------------------------------------------------------

    async def _report_results(
        self, workspace: str, before_snap: dict, on_log: LogCallback
    ) -> None:
        """
        After Cursor finishes, diff the workspace and log:
        - list of added / modified / deleted files
        - content preview for each changed file (up to _PREVIEW_BYTES)
        """
        diff = _workspace_diff(before_snap, workspace)
        added    = diff["added"]
        modified = diff["modified"]
        deleted  = diff["deleted"]

        if not added and not modified and not deleted:
            await on_log(
                "\n📂 工作区无文件变化。\n"
                "Cursor 可能将结果直接回复在对话中，请在 Cursor 窗口查看。",
                "system"
            )
            return

        lines = [f"\n{'─'*48}", "📋 Cursor 执行结果摘要", f"{'─'*48}"]
        if added:
            lines.append(f"\n✅ 新增文件 ({len(added)} 个):")
            for rel in added:
                lines.append(f"  + {rel}")
        if modified:
            lines.append(f"\n✏️  修改文件 ({len(modified)} 个):")
            for rel in modified:
                lines.append(f"  ~ {rel}")
        if deleted:
            lines.append(f"\n🗑️  删除文件 ({len(deleted)} 个):")
            for rel in deleted:
                lines.append(f"  - {rel}")

        await on_log("\n".join(lines), "system")

        # ── Per-file content preview ───────────────────────────────────
        preview_targets = added + modified
        for rel in preview_targets:
            full = Path(workspace) / rel
            try:
                raw = full.read_bytes()
                # Skip binary files
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    await on_log(f"\n[{rel}] (二进制文件，跳过预览)", "system")
                    continue

                size = len(text)
                preview = text[:_PREVIEW_BYTES]
                truncated = size > _PREVIEW_BYTES
                lang = _guess_lang(rel)
                header = f"\n📄 {rel}  ({size} 字节{', 已截断' if truncated else ''})"
                body = f"```{lang}\n{preview}{'...' if truncated else ''}\n```"
                await on_log(header + "\n" + body, "info")
            except Exception as e:
                await on_log(f"\n[{rel}] 读取失败: {e}", "error")


    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _shell(self, cmd: list) -> int:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode or 0
        except Exception:
            return 1

    async def _applescript(self, script: str, on_log: LogCallback) -> int:
        try:
            proc = await asyncio.create_subprocess_exec(
                "osascript", "-e", script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if stderr:
                msg = stderr.decode("utf-8", errors="replace").strip()
                if msg:
                    await on_log(f"AppleScript: {msg}", "error")
            return proc.returncode or 0
        except Exception as e:
            await on_log(f"AppleScript error: {e}", "error")
            return 1

    async def _applescript_capture(self, script: str) -> str:
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
