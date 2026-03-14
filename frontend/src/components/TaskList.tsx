import { TaskSummary, AgentType, TaskStatus } from '../types'
import clsx from 'clsx'
import { useState } from 'react'

const AGENT_COLOR: Record<AgentType, string> = {
  cursor: 'text-[#4f9eff]',
  claude: 'text-[#a855f7]',
  codex:  'text-[#22d3a0]',
}

const STATUS_BADGE: Record<TaskStatus, string> = {
  running:   'bg-yellow-400/10 text-yellow-400 border-yellow-400/20',
  pending:   'bg-slate-700 text-slate-400 border-slate-600',
  completed: 'bg-emerald-400/10 text-emerald-400 border-emerald-400/20',
  failed:    'bg-red-400/10 text-red-400 border-red-400/20',
  stopped:   'bg-orange-400/10 text-orange-400 border-orange-400/20',
}

interface Props {
  tasks: TaskSummary[]
  selectedId: string | null
  onSelect: (id: string) => void
  onStop: (id: string) => void
  onRetry: (id: string) => void
  onDelete: (id: string) => void
}

type FilterStatus = 'all' | TaskStatus

export function TaskList({ tasks, selectedId, onSelect, onStop, onRetry, onDelete }: Props) {
  const [filter, setFilter] = useState<FilterStatus>('all')
  const [agentFilter, setAgentFilter] = useState<AgentType | 'all'>('all')

  const filtered = tasks.filter(t => {
    const statusOk = filter === 'all' || t.status === filter
    const agentOk = agentFilter === 'all' || t.agent_type === agentFilter
    return statusOk && agentOk
  }).sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

  const counts: Record<FilterStatus, number> = {
    all: tasks.length,
    running: tasks.filter(t => t.status === 'running').length,
    pending: tasks.filter(t => t.status === 'pending').length,
    completed: tasks.filter(t => t.status === 'completed').length,
    failed: tasks.filter(t => t.status === 'failed').length,
    stopped: tasks.filter(t => t.status === 'stopped').length,
  }

  return (
    <div className="flex flex-col h-full gap-3">
      {/* Filters */}
      <div className="space-y-2 flex-shrink-0">
        <div className="flex flex-wrap gap-1">
          {(['all', 'running', 'pending', 'completed', 'failed', 'stopped'] as FilterStatus[]).map(s => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={clsx(
                'text-[10px] px-2 py-0.5 rounded border font-mono uppercase transition-colors',
                filter === s
                  ? 'bg-slate-600 text-slate-100 border-slate-500'
                  : 'text-slate-600 border-slate-700/50 hover:text-slate-400 hover:border-slate-600'
              )}
            >
              {s} {counts[s] > 0 && <span className="opacity-60">({counts[s]})</span>}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {(['all', 'cursor', 'claude', 'codex'] as const).map(a => (
            <button
              key={a}
              onClick={() => setAgentFilter(a)}
              className={clsx(
                'text-[10px] px-2 py-0.5 rounded font-mono uppercase transition-colors',
                agentFilter === a
                  ? 'bg-slate-700 text-slate-100'
                  : 'text-slate-600 hover:text-slate-400',
                a !== 'all' && agentFilter === a && AGENT_COLOR[a as AgentType]
              )}
            >
              {a}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto space-y-1.5 pr-0.5">
        {filtered.length === 0 ? (
          <div className="text-center py-12 text-slate-700">
            <p className="text-2xl mb-2">◎</p>
            <p className="text-xs">暂无匹配任务</p>
          </div>
        ) : (
          filtered.map(task => (
            <TaskItem
              key={task.id}
              task={task}
              selected={selectedId === task.id}
              onSelect={() => onSelect(task.id)}
              onStop={() => onStop(task.id)}
              onRetry={() => onRetry(task.id)}
              onDelete={() => onDelete(task.id)}
            />
          ))
        )}
      </div>
    </div>
  )
}

function TaskItem({ task, selected, onSelect, onStop, onRetry, onDelete }: {
  task: TaskSummary
  selected: boolean
  onSelect: () => void
  onStop: () => void
  onRetry: () => void
  onDelete: () => void
}) {
  const [hovering, setHovering] = useState(false)

  const duration = task.started_at && task.completed_at
    ? Math.round((new Date(task.completed_at).getTime() - new Date(task.started_at).getTime()) / 1000)
    : task.started_at && task.status === 'running'
    ? Math.round((Date.now() - new Date(task.started_at).getTime()) / 1000)
    : null

  return (
    <div
      className={clsx(
        'rounded-xl border p-3 cursor-pointer transition-all duration-150 animate-[fadeIn_0.2s_ease-out]',
        selected
          ? 'border-slate-500/60 bg-slate-700/40'
          : 'border-slate-700/40 bg-[#141720] hover:border-slate-600/50 hover:bg-slate-800/30'
      )}
      onClick={onSelect}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-1">
            <span className={clsx('text-[10px] font-mono font-bold uppercase', AGENT_COLOR[task.agent_type])}>
              {task.agent_type}
            </span>
            <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border font-mono uppercase', STATUS_BADGE[task.status])}>
              {task.status}
            </span>
            {task.status === 'running' && (
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-yellow-400" />
              </span>
            )}
          </div>
          <p className="text-xs text-slate-300 leading-relaxed line-clamp-2">
            {task.description}
          </p>
          <div className="flex items-center gap-2 mt-1.5">
            <span className="text-[10px] text-slate-600 font-mono">
              {new Date(task.created_at).toLocaleTimeString('zh-CN', { hour12: false })}
            </span>
            {duration !== null && (
              <span className="text-[10px] text-slate-700">
                {duration >= 60 ? `${Math.floor(duration / 60)}m${duration % 60}s` : `${duration}s`}
              </span>
            )}
            {task.log_count > 0 && (
              <span className="text-[10px] text-slate-700">{task.log_count} lines</span>
            )}
          </div>
        </div>

        {/* Action buttons */}
        {hovering && (
          <div className="flex items-center gap-1 flex-shrink-0" onClick={e => e.stopPropagation()}>
            {task.status === 'running' && (
              <ActionBtn onClick={onStop} title="Stop" className="text-red-400 hover:bg-red-400/10">■</ActionBtn>
            )}
            {(task.status === 'failed' || task.status === 'stopped') && (
              <ActionBtn onClick={onRetry} title="Retry" className="text-blue-400 hover:bg-blue-400/10">↺</ActionBtn>
            )}
            {task.status !== 'running' && (
              <ActionBtn onClick={onDelete} title="Delete" className="text-slate-500 hover:bg-red-400/10 hover:text-red-400">✕</ActionBtn>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function ActionBtn({ onClick, title, className, children }: {
  onClick: () => void; title: string; className?: string; children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={clsx(
        'w-6 h-6 flex items-center justify-center rounded text-xs transition-colors',
        className
      )}
    >
      {children}
    </button>
  )
}
