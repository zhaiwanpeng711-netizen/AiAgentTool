# AI Agent Scheduler

通过**自然语言指令**并行调度多个 AI 编码 Agent（Cursor IDE、Claude Code CLI、OpenAI Codex CLI、通义千问），提供实时可视化监控面板。

## 目录

- [功能特性](#功能特性)
- [支持的 Agent](#支持的-agent)
- [架构概览](#架构概览)
- [环境要求](#环境要求)
- [安装说明](#安装说明)
- [配置说明](#配置说明)
- [使用方法](#使用方法)
- [REST API 参考](#rest-api-参考)
- [项目结构](#项目结构)
- [扩展新 Agent](#扩展新-agent)
- [常见问题](#常见问题)

---

## 功能特性

- **自然语言调度**：输入一句话，LLM 自动解析意图并分配给最合适的 Agent
- **并行多任务**：同时运行多个不同 Agent 的开发任务，互不阻塞
- **实时日志流**：通过 WebSocket 实时查看每个任务的 stdout/stderr 输出
- **任务生命周期管理**：随时启动、停止、重试任何任务
- **可视化面板**：深色主题 Dashboard，Agent 状态卡片，任务列表与日志过滤器
- **多 LLM 后端**：NLP 解析层支持 Anthropic Claude、OpenAI 及 OpenAI 兼容接口（阿里云灵积）
- **智能回退解析**：未配置 LLM API Key 时自动降级为基于关键词的规则解析

---

## 支持的 Agent

| Agent | 标识符 | 类型 | 控制方式 | 适用场景 |
|-------|--------|------|---------|---------|
| Cursor IDE | `cursor` | GUI 自动化 | AppleScript (macOS) / xdotool (Linux) | 交互式编码、UI 开发、文件编辑 |
| Claude Code | `claude` | CLI | `claude` 命令行工具 | 重构、写测试、后端逻辑、文档 |
| OpenAI Codex | `codex` | CLI | `codex` 命令行工具 | 代码生成、算法实现、补全 |
| 通义千问 (Qwen) | `qwen` | API | DashScope OpenAI 兼容接口 | 通用编码、推理任务（无需安装 CLI）|

---

## 架构概览

```
自然语言输入
     │
     ▼
┌─────────────────────────────────────┐
│         NLP Parser (LLM)            │  ← Anthropic / OpenAI / 灵积
│   解析意图 → [{agent, task}, ...]   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│           Task Manager              │
│   创建任务 → 分发 → 追踪状态        │
└──────┬──────────┬──────────┬────────┘
       │          │          │
  ClaudeAgent  CodexAgent  CursorAgent  QwenAgent
  (subprocess) (subprocess) (GUI Auto)  (API call)
       │          │          │          │
       └──────────┴──────────┴──────────┘
                       │
                  WebSocket 广播
                       │
              React Dashboard (前端)
```

---

## 环境要求

| 依赖 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.11+ | 后端运行环境 |
| Node.js | 18+ | 前端构建 |
| npm | 9+ | 前端包管理 |
| macOS / Linux | — | Windows 暂不支持（GUI 自动化依赖 AppleScript/xdotool）|

---

## 安装说明

### 方式一：一键启动（推荐）

```bash
# 克隆项目
git clone <repo-url>
cd AiAgentToolDevlop

# 配置环境变量
cp .env.example .env
# 编辑 .env 填写 API Key（见下方配置说明）

# 一键构建并启动（自动安装 Python/Node 依赖、编译前端）
./start.sh
```

访问 [http://localhost:8000](http://localhost:8000) 打开控制面板。

### 方式二：开发模式（前后端热重载）

```bash
./start_dev.sh
# 后端 API:  http://localhost:8000
# 前端 Dev:  http://localhost:5173
```

### 方式三：手动安装

**后端**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 启动后端
.venv/bin/python -m uvicorn backend.main:app --reload --port 8000
```

**前端**

```bash
cd frontend
npm install
npm run dev       # 开发模式
# 或
npm run build     # 生产构建，输出到 frontend/dist/
```

### 安装 AI CLI 工具（按需）

```bash
# Claude Code CLI（使用 claude agent 时必须）
npm install -g @anthropic-ai/claude-code

# OpenAI Codex CLI（使用 codex agent 时必须）
npm install -g @openai/codex

# Cursor IDE 从官网下载安装（使用 cursor agent 时必须）
# https://cursor.sh

# Linux 用户：安装 xdotool（Cursor GUI 自动化依赖）
sudo apt install xdotool   # Ubuntu/Debian
sudo yum install xdotool   # CentOS/RHEL
```

---

## 配置说明

在项目根目录创建 `.env` 文件（可从 `.env.example` 复制）：

```bash
# ── LLM（自然语言解析引擎）─────────────────────────────────
# 选择 NLP 解析所用的 Provider: "anthropic" 或 "openai"
LLM_PROVIDER=openai
LLM_MODEL=qwen3-coder-plus

# Anthropic（Claude）
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_BASE_URL=              # 留空使用官方接口；填入代理地址可走第三方兼容接口

# OpenAI / OpenAI 兼容接口（阿里云灵积、其他代理等）
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=                 # 留空使用官方接口

# ── 通义千问（Qwen Agent）────────────────────────────────────
# 从 https://dashscope.console.aliyun.com 获取 API Key
QWEN_API_KEY=sk-...
QWEN_MODEL=qwen-coder-plus
# QWEN_BASE_URL 默认为阿里云 DashScope OpenAI 兼容接口，无需修改

# ── Agent CLI 路径（不在 PATH 时手动指定）────────────────────
CLAUDE_CLI_PATH=claude
CODEX_CLI_PATH=codex
CLAUDE_MODEL=claude-3-5-sonnet-20241022
CODEX_MODEL=gpt-5.2-codex

# Codex 多账号支持
CODEX_DEFAULT_PROFILE=personal
CODEX_HOME_PERSONAL=~/.codex-personal
CODEX_HOME_BUSINESS=~/.codex-business

# ── 服务器配置 ────────────────────────────────────────────────
HOST=0.0.0.0
PORT=8000

# ── 工作目录（Agent 执行任务的默认目录）──────────────────────
WORKSPACE_DIR=/Users/yourname/my-project

# ── 其他 ─────────────────────────────────────────────────────
MAX_PARALLEL_TASKS=5   # 每种 Agent 最大并发任务数
MAX_LOG_LINES=1000     # 每任务最大日志保留行数
CURSOR_APP_NAME=Cursor # Cursor 应用名称（AppleScript 使用）
```

> **最小配置**：至少需要配置一个 LLM API Key（`ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY` 或 `QWEN_API_KEY`）用于自然语言解析。未配置时系统将使用基于规则的回退解析器。

---

## 使用方法

### 1. 自然语言调度

在 Dashboard 的任务输入框中输入指令，系统会自动解析并分配给对应 Agent：

```
# 示例一：指定 Agent
用 Claude Code 实现一个 REST API 登录接口，同时用 Codex 生成单元测试

# 示例二：混合 Agent 并行开发
用 Cursor 打开项目优化 UI 界面，用 Claude Code 重构后端数据库层

# 示例三：使用通义千问
用千问帮我写一个 Python 爬虫，抓取新闻列表并存入 SQLite

# 示例四：不指定 Agent（系统自动选择）
实现一个支持分页的商品列表接口
```

**操作流程**：
1. 在"任务输入"区填写自然语言指令
2. 点击**「解析预览」**查看系统理解的任务拆分结果
3. 确认后点击**「调度任务」**正式创建并启动
4. 在任务列表中查看实时状态，点击任务查看完整日志

### 2. 界面功能说明

| 区域 | 功能 |
|------|------|
| Agent 状态卡片 | 显示每个 Agent 的运行任务数、总任务数及可用状态 |
| 任务调度区 | 输入自然语言、解析预览、创建任务 |
| 任务列表 | 按状态/Agent 类型过滤，查看任务摘要 |
| 日志面板 | 实时流式日志，支持按 info / error / system 级别过滤 |

### 3. 通过 REST API 使用

```bash
# 使用自然语言创建并启动任务
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"natural_language": "用 Claude 实现用户注册接口", "workspace": "/path/to/project"}'

# 手动创建单个任务（跳过 NLP 解析）
curl -X POST "http://localhost:8000/api/tasks/manual?description=重构认证模块&agent_type=claude&workspace=/path/to/project"

# 停止任务
curl -X POST http://localhost:8000/api/tasks/{task_id}/stop

# 查看任务详情及日志
curl http://localhost:8000/api/tasks/{task_id}

# 查看所有 Agent 状态
curl http://localhost:8000/api/agents
```

---

## REST API 参考

完整交互式文档：启动后访问 [http://localhost:8000/docs](http://localhost:8000/docs)

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/health` | 健康检查 |
| `GET` | `/api/agents` | 获取所有 Agent 状态 |
| `POST` | `/api/tasks/parse` | 解析自然语言（仅预览，不创建任务）|
| `POST` | `/api/tasks` | 解析自然语言并创建/启动任务 |
| `POST` | `/api/tasks/manual` | 手动创建单个任务 |
| `GET` | `/api/tasks` | 查询任务列表（支持按状态/Agent 过滤）|
| `GET` | `/api/tasks/{id}` | 获取任务详情及完整日志 |
| `POST` | `/api/tasks/{id}/start` | 启动指定任务 |
| `POST` | `/api/tasks/{id}/stop` | 停止指定任务 |
| `DELETE` | `/api/tasks/{id}` | 删除任务 |
| `WS` | `/ws` | WebSocket 实时推送任务状态与日志 |

---

## 项目结构

```
AiAgentToolDevlop/
├── backend/
│   ├── main.py                  # FastAPI 应用入口，Agent 注册
│   ├── config.py                # 全量环境变量读取与默认值
│   ├── scheduler/
│   │   ├── models.py            # Task / AgentInfo / LogEntry 数据模型
│   │   └── task_manager.py      # 任务队列、调度、生命周期管理
│   ├── agents/
│   │   ├── base_agent.py        # BaseAgent 抽象基类
│   │   ├── claude_agent.py      # Claude Code CLI 适配器
│   │   ├── codex_agent.py       # OpenAI Codex CLI 适配器
│   │   ├── cursor_agent.py      # Cursor IDE GUI 自动化适配器
│   │   └── qwen_agent.py        # 通义千问 API 适配器（流式输出）
│   ├── nlp/
│   │   └── parser.py            # 自然语言 → 结构化任务（LLM + 规则回退）
│   └── api/
│       ├── routes.py            # REST API + WebSocket 路由定义
│       └── ws_handler.py        # WebSocket 连接池管理与广播
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # 主应用与路由
│   │   ├── components/
│   │   │   ├── AgentCard.tsx    # Agent 状态卡片
│   │   │   ├── TaskCreator.tsx  # 任务输入与调度控件
│   │   │   ├── TaskList.tsx     # 任务列表与过滤器
│   │   │   └── LogViewer.tsx    # 实时日志查看器
│   │   ├── hooks/
│   │   │   └── useWebSocket.ts  # WebSocket 连接 Hook
│   │   └── types/
│   │       └── index.ts         # TypeScript 类型定义
│   ├── package.json
│   └── vite.config.ts
├── .env.example                 # 环境变量配置模板
├── requirements.txt             # Python 依赖清单
├── start.sh                     # 生产一键启动脚本
└── start_dev.sh                 # 开发模式启动脚本
```

---

## 扩展新 Agent

1. **创建 Agent 类**：继承 `backend/agents/base_agent.py` 中的 `BaseAgent`，实现 `run()` 和 `stop()` 方法

```python
from backend.agents.base_agent import BaseAgent, LogCallback
from backend.scheduler.models import Task

class MyAgent(BaseAgent):
    @property
    def agent_type(self) -> str:
        return "my_agent"

    async def run(self, task: Task, on_log: LogCallback) -> int:
        await on_log("Starting my agent...", "system")
        # 执行任务逻辑
        return 0  # 返回退出码

    async def stop(self, task_id: str):
        # 停止正在运行的任务
        pass
```

2. **注册 Agent 类型**：在 `backend/scheduler/models.py` 的 `AgentType` 枚举中添加新值

```python
class AgentType(str, Enum):
    MY_AGENT = "my_agent"
    # ...
```

3. **注册实例**：在 `backend/main.py` 的 `lifespan` 函数中注册

```python
from backend.agents.my_agent import MyAgent
task_manager.register_agent(AgentType.MY_AGENT, MyAgent())
```

4. 更新 `backend/nlp/parser.py` 中的 `SYSTEM_PROMPT`，让 LLM 了解新 Agent 的能力与适用场景。

---

## Cursor GUI 自动化说明

Cursor IDE 没有编程 API，通过操作系统 GUI 自动化方式控制：

- **macOS**：使用 `osascript`（AppleScript）激活 Cursor 窗口、打开 Agent 面板（`Cmd+I`）、输入任务文本并提交
- **Linux**：使用 `xdotool` 模拟键盘/鼠标操作完成相同流程

> **macOS 权限**：首次运行时需要在「系统设置 → 隐私与安全性 → 辅助功能」中为运行脚本的终端应用（如 Terminal、iTerm2）授予辅助功能权限。

---

## 常见问题

**Q: 启动时提示 `ANTHROPIC_API_KEY is not set`**

使用 Claude Agent 需要配置 Anthropic API Key。若只使用 Qwen Agent，配置 `QWEN_API_KEY` 即可。

**Q: 自然语言解析总是分配给错误的 Agent**

检查 `.env` 中的 `LLM_PROVIDER` 和对应的 API Key 是否正确。无 API Key 时系统使用关键词规则匹配，可在指令中明确指定 Agent 名称（如"用千问..."、"用 Claude..."）。

**Q: Cursor Agent 任务失败，提示辅助功能权限**

前往 macOS「系统设置 → 隐私与安全性 → 辅助功能」，将你的终端应用加入授权列表并重新运行。

**Q: 如何使用阿里云代理访问 Claude/OpenAI？**

在 `.env` 中设置 `ANTHROPIC_BASE_URL` 或 `OPENAI_BASE_URL` 为代理地址，系统会自动将请求转发到该地址。

**Q: 前端构建失败**

确保 Node.js 版本 ≥ 18，然后手动执行：

```bash
cd frontend
npm install
npm run build
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 实时通信 | WebSocket（fastapi / websockets）|
| NLP 解析 | Anthropic Claude API / OpenAI API |
| 前端框架 | React 18 + TypeScript |
| 前端构建 | Vite 5 |
| 样式 | Tailwind CSS |
| 数据模型 | Pydantic v2 |

---

## License

MIT
