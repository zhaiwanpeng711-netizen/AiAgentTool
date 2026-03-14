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

# Claude Code CLI model
# - 使用百炼 Anthropic 代理时：必须填千问模型名（如 qwen3-coder-plus），百炼不支持原生 Claude 模型
# - 使用官方 api.anthropic.com 时：可填 claude-3-5-sonnet-20241022，或留空让 CLI 自选
_bailian = "dashscope" in (os.getenv("ANTHROPIC_BASE_URL") or "").lower() or "aliyuncs" in (os.getenv("ANTHROPIC_BASE_URL") or "").lower()
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "qwen3-coder-plus" if _bailian else "claude-3-5-sonnet-20241022")

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

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
