import os
from pathlib import Path

# LLM API Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Preferred LLM provider: "anthropic" or "openai"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022")

# Workspace directory where agents will operate
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", str(Path.home() / "workspace"))

# Server configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Cursor application name (used by AppleScript/xdotool)
CURSOR_APP_NAME = os.getenv("CURSOR_APP_NAME", "Cursor")

# Agent CLI paths (override if not in PATH)
CLAUDE_CLI_PATH = os.getenv("CLAUDE_CLI_PATH", "claude")
CODEX_CLI_PATH = os.getenv("CODEX_CLI_PATH", "codex")

# Codex model — gpt-4o works with standard API keys; gpt-5.3-codex needs special access
CODEX_MODEL = os.getenv("CODEX_MODEL", "gpt-4o")

# Max parallel tasks per agent type
MAX_PARALLEL_TASKS = int(os.getenv("MAX_PARALLEL_TASKS", "5"))

# Log retention (max log lines per task)
MAX_LOG_LINES = int(os.getenv("MAX_LOG_LINES", "1000"))
