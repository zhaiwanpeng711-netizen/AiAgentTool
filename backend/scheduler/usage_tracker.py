"""
UsageTracker — 各 Agent 用量和费用统计（内存级，服务重启后清零）

支持：
  - Token 用量（输入 / 输出 / 合计）
  - 估算费用（USD）
  - 调用次数 / 任务数
  - 最后使用时间
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict

from backend.scheduler.models import AgentType

# ── 各模型定价（USD / 1K tokens）────────────────────────────────────────────
# 仅用于粗略估算，实际以平台账单为准
PRICING: Dict[str, Dict[str, float]] = {
    # 千问系列（DashScope 官网 / 百炼 Coding Plan）
    "qwen3-coder-plus":          {"input": 0.00014, "output": 0.00056},
    "qwen3-coder-next":          {"input": 0.00056, "output": 0.00224},
    "qwen3-max-2026-01-23":      {"input": 0.00056, "output": 0.00224},
    "qwen-coder-plus":           {"input": 0.00014, "output": 0.00056},
    "qwen-plus":                 {"input": 0.00011, "output": 0.00044},
    "qwen-turbo":                {"input": 0.000042, "output": 0.000168},
    "qwen-max":                  {"input": 0.00056,  "output": 0.00224},
    # Claude（Anthropic 官网）
    "claude-3-5-sonnet-20241022": {"input": 0.003,  "output": 0.015},
    "claude-3-5-haiku-20241022":  {"input": 0.0008, "output": 0.004},
    # OpenAI Codex / GPT
    "gpt-4o":          {"input": 0.0025, "output": 0.01},
    "gpt-5.2-codex":   {"input": 0.003,  "output": 0.015},
    "gpt-5.1-codex-mini": {"input": 0.0015, "output": 0.006},
    # 默认兜底
    "_default":        {"input": 0.001,  "output": 0.003},
}


def _price(model: str, tokens_input: int, tokens_output: int) -> float:
    p = PRICING.get(model, PRICING["_default"])
    return (tokens_input * p["input"] + tokens_output * p["output"]) / 1000


@dataclass
class AgentUsage:
    agent_type: str
    calls: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    last_used: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "agent_type": self.agent_type,
            "calls": self.calls,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "tokens_total": self.tokens_input + self.tokens_output,
            "cost_usd": round(self.cost_usd, 6),
            "last_used": self.last_used.isoformat() if self.last_used else None,
        }


class UsageTracker:
    """
    内存级用量统计单例。
    服务运行期间数据持续累加，服务重启后归零。
    浏览器刷新不影响统计（数据在服务端）。
    """

    def __init__(self):
        self._usage: Dict[str, AgentUsage] = {
            t.value: AgentUsage(agent_type=t.value) for t in AgentType
        }
        self._broadcast_callback = None

    def set_broadcast_callback(self, cb):
        self._broadcast_callback = cb

    def record(
        self,
        agent_type: str,
        model: str = "_default",
        tokens_input: int = 0,
        tokens_output: int = 0,
    ):
        """记录一次调用的用量。"""
        u = self._usage.setdefault(agent_type, AgentUsage(agent_type=agent_type))
        u.calls += 1
        u.tokens_input += tokens_input
        u.tokens_output += tokens_output
        u.cost_usd += _price(model, tokens_input, tokens_output)
        u.last_used = datetime.utcnow()

        # 异步广播（非阻塞，忽略失败）
        if self._broadcast_callback:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._async_broadcast())
            except Exception:
                pass

    async def _async_broadcast(self):
        if self._broadcast_callback:
            try:
                await self._broadcast_callback({
                    "event": "usage_updated",
                    "data": self.get_stats(),
                })
            except Exception:
                pass

    def get_stats(self) -> list[dict]:
        return [u.to_dict() for u in self._usage.values()]

    def get_total_cost(self) -> float:
        return round(sum(u.cost_usd for u in self._usage.values()), 6)


# 全局单例
usage_tracker = UsageTracker()
