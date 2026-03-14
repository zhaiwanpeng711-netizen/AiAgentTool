import os
from pathlib import Path

# LLM API Configuration
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")  # 留空则用官方 api.anthropic.com

OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")  # 留空则用官方 api.openai.com

# Preferred LLM provider: "anthropic" or "openai"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3-coder-plus")

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

# Codex model
CODEX_MODEL = os.getenv("CODEX_MODEL", "gpt-5.2-codex")

# Claude Code CLI model — leave empty to let Claude CLI auto-select
# Bailian Anthropic proxy supports: claude-3-5-sonnet-20241022 / claude-3-5-haiku-20241022
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")

# Codex multi-account profile support
# CODEX_DEFAULT_PROFILE: which profile to use by default ("personal" or "business")
CODEX_DEFAULT_PROFILE = os.getenv("CODEX_DEFAULT_PROFILE", "personal")
# Home directories for each profile (codex stores auth/config here)
CODEX_HOME_PERSONAL  = os.path.expanduser(os.getenv("CODEX_HOME_PERSONAL",  "~/.codex-personal"))
CODEX_HOME_BUSINESS  = os.path.expanduser(os.getenv("CODEX_HOME_BUSINESS",  "~/.codex-business"))

# Max parallel tasks per agent type
MAX_PARALLEL_TASKS = int(os.getenv("MAX_PARALLEL_TASKS", "5"))

# ── 千问 (Qwen) 配置 ──────────────────────────────────────
# API Key 从阿里云 DashScope 控制台获取: https://dashscope.console.aliyun.com
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
# 可用模型: qwen-max / qwen-plus / qwen-turbo / qwen-long / qwen-coder-plus
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-coder-plus")
# OpenAI 兼容接口地址（无需修改）
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

# Log retention (max log lines per task)
MAX_LOG_LINES = int(os.getenv("MAX_LOG_LINES", "1000"))
