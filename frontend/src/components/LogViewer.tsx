import { useEffect, useRef, useState } from 'react'
import { LogEntry, TaskDetail, AgentType } from '../types'
import clsx from 'clsx'

const AGENT_COLORS: Record<AgentType, string> = {
  cursor: '#4f9eff',
  claude: '#a855f7',
  codex:  '#22d3a0',
}

interface Props {
  task: TaskDetail | null
  liveLog: LogEntry[]
  onClose: () => void
  onStop: () => void
  onRetry: () => void
}

export function LogViewer({ task, liveLog, onClose, onStop, onRetry }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const [filter, setFilter] = useState<'all' | 'info' | 'error' | 'system'>('all')

  const allLogs: LogEntry[] = [
    ...(task?.logs ?? []),
    ...liveLog,
  ]

  const filteredLogs = filter === 'all' ? allLogs : allLogs.filter(l => l.level === filter)

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [filteredLogs.length, autoScroll])

  if (!task) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-slate-600">
        <span className="text-4xl">◎</span>
        <p className="text-sm">点击左侧任务查看日志</p>
      </div>
    )
  }

  const accentColor = AGENT_COLORS[task.agent_type] ?? '#4f9eff'
  const isRunning = task.status === 'running'

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 pb-3 border-b border-slate-700/50 flex-shrink-0">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className="text-xs font-mono px-2 py-0.5 rounded uppercase font-bold"
              style={{ color: accentColor, backgroundColor: `${accentColor}15` }}
            >
              {task.agent_type}
            </span>
            <StatusBadge status={task.status} />
          </div>
          <p className="text-sm text-slate-200 mt-1.5 line-clamp-2">{task.description}</p>
          <p className="text-xs text-slate-600 mt-1 font-mono">{task.id.slice(0, 8)}...</p>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {isRunning && (
            <button
              onClick={onStop}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors"
            >
              ■ Stop
            </button>
          )}
          {(task.status === 'failed' || task.status === 'stopped') && (
            <button
              onClick={onRetry}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20 hover:bg-blue-500/20 transition-colors"
            >
              ↺ Retry
            </button>
          )}
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-700/50 transition-colors text-lg"
          >
            ×
          </button>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-1.5 py-2 flex-shrink-0">
        {(['all', 'info', 'error', 'system'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={clsx(
              'text-[10px] px-2 py-0.5 rounded font-mono uppercase transition-colors',
              filter === f ? 'bg-slate-600 text-slate-100' : 'text-slate-600 hover:text-slate-400'
            )}
          >
            {f}
          </button>
        ))}
        <div className="flex-1" />
        <button
          onClick={() => setAutoScroll(v => !v)}
          className={clsx(
            'text-[10px] px-2 py-0.5 rounded font-mono transition-colors',
            autoScroll ? 'bg-emerald-500/10 text-emerald-400' : 'text-slate-600 hover:text-slate-400'
          )}
        >
          {autoScroll ? '⬇ auto' : '⬇ off'}
        </button>
        <span className="text-[10px] text-slate-700 font-mono">{filteredLogs.length} lines</span>
      </div>

      {/* Log content */}
      <div
        className="flex-1 overflow-y-auto rounded-lg bg-[#0a0c12] p-3 space-y-0.5"
        onScroll={e => {
          const el = e.currentTarget
          const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 40
          setAutoScroll(atBottom)
        }}
      >
        {filteredLogs.length === 0 ? (
          <p className="text-xs text-slate-700 text-center py-8">暂无日志</p>
        ) : (
          filteredLogs.map((log, i) => <LogLine key={i} log={log} accentColor={accentColor} />)
        )}
        {isRunning && (
          <div className="flex items-center gap-1.5 pt-1">
            <span className="inline-flex">
              {[0, 1, 2].map(j => (
                <span
                  key={j}
                  className="w-1 h-1 rounded-full bg-slate-500 mx-0.5 animate-bounce"
                  style={{ animationDelay: `${j * 150}ms` }}
                />
              ))}
            </span>
            <span className="text-xs text-slate-600">运行中...</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function LogLine({ log, accentColor }: { log: LogEntry; accentColor: string }) {
  const levelStyles: Record<string, string> = {
    info:   'text-slate-300',
    error:  'text-red-400',
    system: 'text-slate-500',
  }
  const prefixStyles: Record<string, string> = {
    info:   'text-slate-600',
    error:  'text-red-600',
    system: 'text-slate-700',
  }

  const time = new Date(log.timestamp).toLocaleTimeString('zh-CN', { hour12: false })

  return (
    <div className={clsx('log-line flex items-start gap-2 hover:bg-white/2 rounded px-1 py-0.5 group')}>
      <span className={clsx('flex-shrink-0 select-none', prefixStyles[log.level] ?? prefixStyles.info)}>
        {time}
      </span>
      <span className={clsx('flex-shrink-0 w-3 select-none', prefixStyles[log.level])}>
        {log.level === 'error' ? '✗' : log.level === 'system' ? '·' : '›'}
      </span>
      <span className={clsx('flex-1 break-all whitespace-pre-wrap', levelStyles[log.level] ?? levelStyles.info)}>
        {log.message}
      </span>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    running:   'bg-yellow-400/10 text-yellow-400 border-yellow-400/20',
    pending:   'bg-slate-700 text-slate-400 border-slate-600',
    completed: 'bg-emerald-400/10 text-emerald-400 border-emerald-400/20',
    failed:    'bg-red-400/10 text-red-400 border-red-400/20',
    stopped:   'bg-orange-400/10 text-orange-400 border-orange-400/20',
  }
  return (
    <span className={clsx('text-[10px] px-2 py-0.5 rounded border font-mono uppercase', styles[status] ?? styles.pending)}>
      {status}
    </span>
  )
}
