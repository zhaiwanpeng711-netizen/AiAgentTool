import json
import logging
import re
from typing import Optional

from backend.config import (
    LLM_PROVIDER, LLM_MODEL,
    ANTHROPIC_API_KEY, OPENAI_API_KEY
)
from backend.scheduler.models import AgentType, ParsedTask

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI task dispatcher. Given a natural language instruction, 
break it down into a list of specific tasks, each assigned to the most appropriate AI agent.

Available agents:
- "cursor": Cursor IDE agent — best for interactive coding, UI development, file editing with visual context
- "claude": Claude Code CLI — best for coding, refactoring, writing tests, backend logic, documentation
- "codex": OpenAI Codex CLI — best for code generation, completion, algorithmic problems

Return a JSON array only (no markdown, no explanation). Each item must have:
- "agent": one of "cursor", "claude", "codex"  
- "task": clear, specific description of what to do (in the same language as the user's input)

If the user doesn't specify an agent, pick the most suitable one.
If the user specifies multiple tasks, split them into separate items.
If the task is ambiguous, assign it to "claude" as default.

Example input: "用Cursor实现登录页面，同时用Claude Code写单元测试"
Example output:
[
  {"agent": "cursor", "task": "实现用户登录页面，包括登录表单、验证和样式"},
  {"agent": "claude", "task": "为登录模块编写完整的单元测试"}
]"""


async def parse_natural_language(text: str, workspace: Optional[str] = None) -> list[ParsedTask]:
    """Parse a natural language instruction into structured tasks using LLM."""
    try:
        if LLM_PROVIDER == "anthropic" and ANTHROPIC_API_KEY:
            return await _parse_with_anthropic(text, workspace)
        elif LLM_PROVIDER == "openai" and OPENAI_API_KEY:
            return await _parse_with_openai(text, workspace)
        else:
            logger.warning("No LLM API key configured, using fallback parser")
            return _fallback_parse(text, workspace)
    except Exception as e:
        logger.error(f"NLP parsing error: {e}")
        return _fallback_parse(text, workspace)


async def _parse_with_anthropic(text: str, workspace: Optional[str]) -> list[ParsedTask]:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    message = await client.messages.create(
        model=LLM_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}]
    )
    raw = message.content[0].text.strip()
    return _parse_json_response(raw, workspace)


async def _parse_with_openai(text: str, workspace: Optional[str]) -> list[ParsedTask]:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        max_tokens=1024,
    )
    raw = response.choices[0].message.content.strip()
    return _parse_json_response(raw, workspace)


def _parse_json_response(raw: str, workspace: Optional[str]) -> list[ParsedTask]:
    # Strip markdown code fences if present
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
    raw = raw.rstrip("```").strip()

    data = json.loads(raw)
    tasks = []
    for item in data:
        agent_str = item.get("agent", "claude").lower()
        try:
            agent_type = AgentType(agent_str)
        except ValueError:
            agent_type = AgentType.CLAUDE
        tasks.append(ParsedTask(
            agent=agent_type,
            task=item.get("task", ""),
            workspace=workspace,
        ))
    return tasks


def _fallback_parse(text: str, workspace: Optional[str]) -> list[ParsedTask]:
    """
    Smart rule-based fallback when no LLM is available.
    Splits on conjunctions, detects agent keywords, handles multiple tasks.
    """
    # Split into sub-tasks on common conjunctions
    import re
    parts = re.split(
        r'[,，；;]\s*(?:同时|并且|并|然后|接着|另外|还有|以及|and|then|also|meanwhile)?\s*|'
        r'\s+(?:同时|并且|并|然后|接着|另外|还有|以及|and|then|also|meanwhile)\s+',
        text,
        flags=re.IGNORECASE
    )
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        parts = [text]

    results = []
    for part in parts:
        part_lower = part.lower()
        agent = _detect_agent(part_lower)
        results.append(ParsedTask(agent=agent, task=part, workspace=workspace))

    return results if results else [ParsedTask(agent=AgentType.CLAUDE, task=text, workspace=workspace)]


def _detect_agent(text_lower: str) -> AgentType:
    """Detect which agent to use based on keywords."""
    cursor_kw = ["cursor", "界面", "ui", "前端", "页面", "样式", "设计", "布局",
                 "组件", "html", "css", "react", "vue", "svelte", "界面优化"]
    codex_kw  = ["codex", "生成代码", "算法", "数据结构", "排序", "补全",
                 "openai codex", "代码生成", "生成函数", "生成类"]
    claude_kw = ["claude", "claude code", "重构", "单元测试", "测试", "文档",
                 "readme", "注释", "优化", "分析", "review", "后端", "api",
                 "接口", "数据库", "登录", "认证", "实现"]

    cursor_score = sum(1 for kw in cursor_kw if kw in text_lower)
    codex_score  = sum(1 for kw in codex_kw  if kw in text_lower)
    claude_score = sum(1 for kw in claude_kw if kw in text_lower)

    # Explicit agent name always wins
    if "cursor" in text_lower:
        return AgentType.CURSOR
    if "codex" in text_lower:
        return AgentType.CODEX
    if "claude" in text_lower:
        return AgentType.CLAUDE

    # Otherwise pick highest score
    scores = {AgentType.CURSOR: cursor_score, AgentType.CODEX: codex_score, AgentType.CLAUDE: claude_score}
    return max(scores, key=lambda k: scores[k]) if max(scores.values()) > 0 else AgentType.CLAUDE
