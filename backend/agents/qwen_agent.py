"""
QwenAgent — 千问大模型编码 Agent

使用阿里云 DashScope OpenAI 兼容接口，直接调用千问 API 执行编码任务。
支持：
  - 流式输出（实时显示 token）
  - 自动解析响应中的代码块，并将文件写入工作目录
  - 多轮工具调用（文件读写、创建目录等）
"""
import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Optional

from backend.agents.base_agent import BaseAgent, LogCallback
from backend.config import QWEN_API_KEY, QWEN_MODEL, QWEN_BASE_URL, WORKSPACE_DIR
from backend.scheduler.models import AgentType, Task
from backend.scheduler.usage_tracker import usage_tracker

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位资深全栈工程师，请根据用户的需求完成编码任务。

## 输出规范
- 直接输出可运行的完整代码，不要省略
- 每个文件用以下格式标注（紧贴代码块上方）：
  ### 文件: <相对路径>
  ```<语言>
  <完整代码>
  ```
- 如果需要多个文件，依次输出每个文件
- 在所有文件之后，用中文简要说明实现思路和使用方法

## 注意
- 工作目录中的文件会被自动保存，请确保路径合法
- 代码要有完整的错误处理和注释
- 优先使用成熟稳定的依赖库
"""


class QwenAgent(BaseAgent):
    """
    千问大模型 Agent，通过 OpenAI 兼容接口调用 DashScope。
    自动将响应中的代码块保存为文件到工作目录。
    """

    def __init__(self):
        self._stop_flags: dict[str, bool] = {}

    @property
    def agent_type(self) -> str:
        return AgentType.QWEN

    async def run(self, task: Task, on_log: LogCallback) -> int:
        self._stop_flags[task.id] = False
        workspace = task.workspace or WORKSPACE_DIR
        os.makedirs(workspace, exist_ok=True)

        if not QWEN_API_KEY or QWEN_API_KEY == "your_qwen_api_key_here":
            await on_log(
                "QWEN_API_KEY 未配置！\n"
                "请在 .env 文件中设置：QWEN_API_KEY=your_key\n"
                "API Key 获取地址：https://dashscope.console.aliyun.com/apiKey",
                "error"
            )
            return 1

        await on_log(f"Working directory: {workspace}", "system")
        await on_log(f"Model: {QWEN_MODEL}", "system")
        await on_log(f"Endpoint: {QWEN_BASE_URL}", "system")

        try:
            from openai import AsyncOpenAI
        except ImportError:
            await on_log("openai 库未安装，运行：pip install openai", "error")
            return 1

        client = AsyncOpenAI(
            api_key=QWEN_API_KEY,
            base_url=QWEN_BASE_URL,
        )

        await on_log(f"正在调用千问 API ({QWEN_BASE_URL})...", "system")

        full_response = []
        tokens_input = tokens_output = 0
        try:
            stream = await client.chat.completions.create(
                model=QWEN_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": task.description},
                ],
                stream=True,
                stream_options={"include_usage": True},
                max_tokens=8192,
                temperature=0.1,
            )

            async for chunk in stream:
                if self._stop_flags.get(task.id):
                    await on_log("任务已被用户停止。", "system")
                    return 0

                # Capture token counts from the final usage chunk
                if chunk.usage:
                    tokens_input = chunk.usage.prompt_tokens or 0
                    tokens_output = chunk.usage.completion_tokens or 0

                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    full_response.append(delta.content)
                    await on_log(delta.content, "info")

        except Exception as e:
            err = str(e)
            if "api_key" in err.lower() or "authentication" in err.lower():
                await on_log(f"API Key 无效或已过期：{err}", "error")
            elif "quota" in err.lower() or "balance" in err.lower():
                await on_log(f"账号余额不足，请前往控制台充值：{err}", "error")
            elif "model" in err.lower():
                await on_log(f"模型不存在，请检查 QWEN_MODEL 配置：{err}", "error")
            else:
                await on_log(f"API 调用失败：{err}", "error")
            return 1

        # ── 上报 token 用量 ──────────────────────────────────────────
        if tokens_input or tokens_output:
            usage_tracker.record(
                agent_type=AgentType.QWEN,
                model=QWEN_MODEL,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
            )
            await on_log(
                f"Token 用量：输入 {tokens_input} / 输出 {tokens_output} / 合计 {tokens_input + tokens_output}",
                "system",
            )

        # ── 解析并保存代码文件 ────────────────────────────────────────
        response_text = "".join(full_response)
        saved_files = await _extract_and_save_files(response_text, workspace, on_log)

        if saved_files:
            await on_log(
                f"\n✓ 共保存 {len(saved_files)} 个文件到 {workspace}：\n"
                + "\n".join(f"  • {f}" for f in saved_files),
                "system"
            )
        else:
            await on_log(
                "\n提示：响应中未检测到标准文件格式，代码未自动保存。\n"
                "可在上方日志中手动复制代码。",
                "system"
            )

        return 0

    async def stop(self, task_id: str):
        self._stop_flags[task_id] = True


# ── 文件解析工具 ──────────────────────────────────────────────────────────────

async def _extract_and_save_files(
    text: str, workspace: str, on_log: LogCallback
) -> list[str]:
    """
    从响应文本中提取代码块并保存为文件。

    支持的格式：
      ### 文件: path/to/file.py      ← 中文格式
      ### File: path/to/file.py       ← 英文格式
      ```python filepath: path/file   ← 内联 filepath 格式
    """
    saved = []

    # Pattern 1: ### 文件: / ### File: 前置标注
    pattern1 = re.compile(
        r'###\s*(?:文件|File|filepath)\s*[：:]\s*([^\n]+)\n'
        r'```[^\n]*\n(.*?)```',
        re.DOTALL | re.IGNORECASE,
    )

    # Pattern 2: ```lang\n# filepath: xxx 内嵌在首行注释
    pattern2 = re.compile(
        r'```[a-z]*\n(?:#|//|<!--)\s*(?:filepath|file)[：:]\s*([^\n]+)\n(.*?)```',
        re.DOTALL | re.IGNORECASE,
    )

    matches = []
    for m in pattern1.finditer(text):
        matches.append((m.group(1).strip(), m.group(2)))
    for m in pattern2.finditer(text):
        matches.append((m.group(1).strip(), m.group(2)))

    for rel_path, code in matches:
        # Security: prevent path traversal
        rel_path = rel_path.lstrip("/").replace("..", "")
        full_path = Path(workspace) / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            full_path.write_text(code.rstrip(), encoding="utf-8")
            saved.append(rel_path)
            await on_log(f"  ✓ 已保存: {rel_path}", "system")
        except Exception as e:
            await on_log(f"  ✗ 保存失败 {rel_path}: {e}", "error")

    return saved
