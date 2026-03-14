# AI Agent Scheduler

通过自然语言指令并行调度 **Cursor IDE**、**Claude Code CLI**、**OpenAI Codex CLI** 等 AI 编辑器，提供实时可视化监控面板。

## 功能特性

- **自然语言调度**：输入一句话，自动解析并分配给最合适的 Agent
- **并行多任务**：同时运行多个不同 Agent 的开发任务
- **实时日志流**：通过 WebSocket 实时查看每个任务的输出
- **任务生命周期管理**：随时启动/停止/重试任何任务
- **可视化面板**：深色主题 Dashboard，Agent 状态卡片，任务过滤器

## 支持的 Agent

| Agent | 类型 | 控制方式 |
|-------|------|---------|
| Cursor IDE | GUI 自动化 | AppleScript (Mac) / xdotool (Linux) |
| Claude Code | CLI | `claude` 命令行工具 |
| OpenAI Codex | CLI | `codex` 命令行工具 |

## 快速开始

### 1. 环境准备

**系统要求**：macOS 或 Linux，Python 3.11+，Node.js 18+

```bash
# 克隆/进入项目目录
cd /Users/winn/AiAgentToolDevlop

# 复制环境变量配置
cp .env.example .env
```

### 2. 配置 API Keys

编辑 `.env` 文件：

```bash
# 必填：至少配置一个 LLM API Key（用于自然语言解析）
ANTHROPIC_API_KEY=sk-ant-...       # Anthropic Claude API Key
OPENAI_API_KEY=sk-...              # OpenAI API Key（备选）

# 设置工作目录（Agent 执行任务的默认目录）
WORKSPACE_DIR=/Users/yourname/my-project
```

### 3. 安装 AI CLI 工具（按需）

```bash
# Claude Code CLI
npm install -g @anthropic-ai/claude-code

# OpenAI Codex CLI  
npm install -g @openai/codex

# macOS: Cursor 从官网下载安装 https://cursor.sh
# Linux: 安装 xdotool (用于 Cursor GUI 控制)
sudo apt install xdotool  # Ubuntu/Debian
```

### 4. 启动服务

**生产模式**（推荐，前端已编译内置）：
```bash
./start.sh
# 访问 http://localhost:8000
```

**开发模式**（前后端热重载）：
```bash
./start_dev.sh
# 后端: http://localhost:8000
# 前端: http://localhost:5173
```

**手动启动**：
```bash
# 后端
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn backend.main:app --reload --port 8000

# 前端（新终端）
cd frontend
npm install
npm run dev
```

## 使用说明

### 自然语言指令示例

```
用Claude Code实现一个REST API登录接口，同时用Codex生成单元测试

用Cursor打开项目优化UI界面，用Claude Code重构后端数据库层

用Codex生成一个排序算法库，然后用Claude Code添加完整注释
```

### 界面功能

- **任务调度区**：输入自然语言指令，点击解析预览，确认后点击"调度任务"
- **Dashboard**：查看三个 Agent 的实时状态和运行中的任务
- **任务列表**：按状态/Agent 过滤，点击任务查看完整日志
- **日志面板**：实时流式日志，支持按 info/error/system 过滤

### 手动创建单个任务（API）

```bash
# 创建并立即启动一个 Claude Code 任务
curl -X POST http://localhost:8000/api/tasks/manual \
  -H "Content-Type: application/json" \
  -d '{"description": "重构用户认证模块", "agent_type": "claude", "workspace": "/path/to/project"}'

# 停止任务
curl -X POST http://localhost:8000/api/tasks/{task_id}/stop

# 查看任务日志
curl http://localhost:8000/api/tasks/{task_id}
```

## API 文档

启动后访问 [http://localhost:8000/docs](http://localhost:8000/docs) 查看完整 Swagger API 文档。

## 项目结构

```
AiAgentToolDevlop/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 环境变量配置
│   ├── scheduler/
│   │   ├── models.py        # Task/AgentInfo 数据模型
│   │   └── task_manager.py  # 任务队列与生命周期
│   ├── agents/
│   │   ├── base_agent.py    # 抽象基类
│   │   ├── claude_agent.py  # Claude Code CLI 适配器
│   │   ├── codex_agent.py   # Codex CLI 适配器
│   │   └── cursor_agent.py  # Cursor GUI 自动化适配器
│   ├── nlp/
│   │   └── parser.py        # 自然语言 → 结构化任务解析
│   └── api/
│       ├── routes.py        # REST API + WebSocket 路由
│       └── ws_handler.py    # WebSocket 连接管理
├── frontend/
│   └── src/
│       ├── App.tsx          # 主应用
│       ├── components/      # AgentCard, TaskCreator, LogViewer, TaskList
│       ├── hooks/           # useWebSocket
│       └── types/           # TypeScript 类型定义
├── .env.example             # 环境变量模板
├── requirements.txt         # Python 依赖
├── start.sh                 # 生产启动脚本
└── start_dev.sh             # 开发启动脚本
```

## Cursor GUI 自动化说明

Cursor 没有编程 API，通过 GUI 自动化控制：

- **macOS**：使用 `osascript` (AppleScript) 激活窗口、打开 Agent 面板 (`Cmd+I`)、输入任务
- **Linux**：使用 `xdotool` 完成相同操作

> **注意**：运行 Cursor GUI 自动化时，macOS 需要在「系统设置 → 隐私与安全性 → 辅助功能」中为终端/Python 授权。

## 扩展新 Agent

1. 继承 `backend/agents/base_agent.py` 中的 `BaseAgent`
2. 实现 `run(task, on_log)` 方法
3. 在 `backend/main.py` 的 `lifespan` 函数中注册
4. 在 `backend/scheduler/models.py` 的 `AgentType` 枚举中添加新类型
