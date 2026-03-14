import { AgentUsage, AgentType } from '../types'
import clsx from 'clsx'

const AGENT_META: Record<AgentType, { label: string; color: string; bar: string; icon: string }> = {
  cursor: { label: 'Cursor IDE',  color: 'text-[#4f9eff]', bar: 'bg-[#4f9eff]', icon: '⬡' },
  claude: { label: 'Claude Code', color: 'text-[#a855f7]', bar: 'bg-[#a855f7]', icon: '◈' },
  codex:  { label: 'Codex CLI',   color: 'text-[#22d3a0]', bar: 'bg-[#22d3a0]', icon: '◇' },
  qwen:   { label: '通义千问',     color: 'text-[#f59e0b]', bar: 'bg-[#f59e0b]', icon: '✦' },
}

interface Props {
  usage: AgentUsage[]
  totalCostUsd: number
}

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function fmtCost(usd: number): string {
  if (usd === 0) return '$0.00'
  if (usd < 0.001) return `$${(usd * 1000).toFixed(4)}‰`  // show in milli-dollar
  return `$${usd.toFixed(4)}`
}

function fmtCostCny(usd: number): string {
  const cny = usd * 7.25
  if (cny === 0) return '¥0.00'
  if (cny < 0.001) return `<¥0.001`
  return `≈¥${cny.toFixed(4)}`
}

export function UsagePanel({ usage, totalCostUsd }: Props) {
  const maxTokens = Math.max(...usage.map(u => u.tokens_total), 1)
  const hasAnyUsage = usage.some(u => u.calls > 0)

  return (
    <div className="bg-[#141720] rounded-xl border border-slate-700/40 p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-slate-400 text-sm font-medium">用量统计</span>
          <span className="text-[10px] text-slate-600 bg-slate-800 px-1.5 py-0.5 rounded">本次运行</span>
        </div>
        <div className="text-right">
          <div className="text-sm font-mono font-semibold text-slate-200">
            {fmtCost(totalCostUsd)}
          </div>
          <div className="text-[10px] text-slate-500">{fmtCostCny(totalCostUsd)} · 累计</div>
        </div>
      </div>

      {!hasAnyUsage ? (
        <p className="text-xs text-slate-600 text-center py-3">暂无调用记录</p>
      ) : (
        <div className="space-y-3">
          {usage.map(u => {
            const meta = AGENT_META[u.agent_type as AgentType] ?? {
              label: u.agent_type, color: 'text-slate-400', bar: 'bg-slate-400', icon: '○'
            }
            const pct = maxTokens > 0 ? (u.tokens_total / maxTokens) * 100 : 0

            return (
              <div key={u.agent_type} className={clsx('space-y-1.5', u.calls === 0 && 'opacity-30')}>
                {/* Agent label row */}
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1.5">
                    <span className={meta.color}>{meta.icon}</span>
                    <span className="text-slate-400">{meta.label}</span>
                    {u.calls > 0 && (
                      <span className="text-[10px] text-slate-600 bg-slate-800 px-1 rounded">
                        {u.calls} 次
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 font-mono text-[11px]">
                    {u.tokens_total > 0 && (
                      <span className="text-slate-500">
                        ↑{fmt(u.tokens_input)} ↓{fmt(u.tokens_output)}
                      </span>
                    )}
                    <span className={clsx('font-semibold', u.cost_usd > 0 ? meta.color : 'text-slate-600')}>
                      {fmtCost(u.cost_usd)}
                    </span>
                  </div>
                </div>

                {/* Token bar */}
                <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className={clsx('h-full rounded-full transition-all duration-500', meta.bar, 'opacity-70')}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      )}

      <p className="text-[10px] text-slate-700 mt-4 border-t border-slate-800 pt-3">
        * 费用为估算值，实际以平台账单为准。CLI 工具（Claude/Codex）仅统计调用次数，不含 Token 明细。
      </p>
    </div>
  )
}
