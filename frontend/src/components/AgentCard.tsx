import { AgentInfo, AgentType, TaskSummary } from '../types'
import clsx from 'clsx'

const AGENT_META: Record<AgentType, { label: string; color: string; glowClass: string; icon: string }> = {
  cursor: {
    label: 'Cursor IDE',
    color: 'text-[#4f9eff]',
    glowClass: 'glow-blue',
    icon: '⬡',
  },
  claude: {
    label: 'Claude Code',
    color: 'text-[#a855f7]',
    glowClass: 'glow-purple',
    icon: '◈',
  },
  codex: {
    label: 'Codex CLI',
    color: 'text-[#22d3a0]',
    glowClass: 'glow-green',
    icon: '◇',
  },
  qwen: {
    label: '通义千问',
    color: 'text-[#f59e0b]',
    glowClass: 'glow-amber',
    icon: '✦',
  },
}

interface Props {
  info: AgentInfo
  tasks: TaskSummary[]
  onSelectTask: (id: string) => void
  selectedTaskId: string | null
}

export function AgentCard({ info, tasks, onSelectTask, selectedTaskId }: Props) {
  const meta = AGENT_META[info.agent_type]
  const runningTasks = tasks.filter(t => t.status === 'running')
  const hasRunning = runningTasks.length > 0

  return (
    <div
      className={clsx(
        'rounded-xl border border-slate-700/50 bg-[#141720] p-4 flex flex-col gap-3 transition-all duration-200',
        hasRunning && meta.glowClass,
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={clsx('text-xl leading-none', meta.color)}>{meta.icon}</span>
          <div>
            <h3 className={clsx('font-semibold text-sm', meta.color)}>{meta.label}</h3>
            <p className="text-xs text-slate-500 mt-0.5">{info.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          {hasRunning && (
            <span className="relative flex h-2.5 w-2.5">
              <span className={clsx('animate-ping absolute inline-flex h-full w-full rounded-full opacity-75', meta.color.replace('text-', 'bg-'))} />
              <span className={clsx('relative inline-flex rounded-full h-2.5 w-2.5', meta.color.replace('text-', 'bg-'))} />
            </span>
          )}
          <span className={clsx(
            'text-xs px-2 py-0.5 rounded-full font-mono',
            info.available ? 'bg-slate-700 text-slate-300' : 'bg-red-900/30 text-red-400'
          )}>
            {info.available ? 'available' : 'unavailable'}
          </span>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-2">
        <Stat label="Running" value={info.running_tasks} highlight={info.running_tasks > 0} color={meta.color} />
        <Stat label="Total" value={info.total_tasks} />
        <Stat label="Done" value={tasks.filter(t => t.status === 'completed').length} />
      </div>

      {/* Task list */}
      <div className="flex flex-col gap-1.5 max-h-48 overflow-y-auto">
        {tasks.length === 0 ? (
          <p className="text-xs text-slate-600 text-center py-3">No tasks assigned</p>
        ) : (
          tasks.map(task => (
            <TaskRow
              key={task.id}
              task={task}
              accentColor={meta.color}
              selected={selectedTaskId === task.id}
              onClick={() => onSelectTask(task.id)}
            />
          ))
        )}
      </div>
    </div>
  )
}

function Stat({ label, value, highlight = false, color = 'text-slate-300' }: {
  label: string; value: number; highlight?: boolean; color?: string
}) {
  return (
    <div className="bg-[#0f1117] rounded-lg px-2 py-1.5 text-center">
      <div className={clsx('text-lg font-bold font-mono', highlight ? color : 'text-slate-300')}>
        {value}
      </div>
      <div className="text-[10px] text-slate-500 uppercase tracking-wide">{label}</div>
    </div>
  )
}

function TaskRow({ task, accentColor, selected, onClick }: {
  task: TaskSummary; accentColor: string; selected: boolean; onClick: () => void
}) {
  const statusConfig: Record<string, { dot: string; badge: string; text: string }> = {
    running:   { dot: 'animate-pulse bg-yellow-400', badge: 'bg-yellow-400/10 text-yellow-400', text: 'RUNNING' },
    pending:   { dot: 'bg-slate-500',                badge: 'bg-slate-700 text-slate-400',      text: 'PENDING' },
    completed: { dot: 'bg-emerald-400',              badge: 'bg-emerald-400/10 text-emerald-400', text: 'DONE' },
    failed:    { dot: 'bg-red-400',                  badge: 'bg-red-400/10 text-red-400',        text: 'FAILED' },
    stopped:   { dot: 'bg-orange-400',               badge: 'bg-orange-400/10 text-orange-400',  text: 'STOPPED' },
  }
  const sc = statusConfig[task.status] ?? statusConfig.pending

  return (
    <button
      onClick={onClick}
      className={clsx(
        'w-full text-left rounded-lg px-2.5 py-2 flex items-start gap-2 transition-colors duration-150 group',
        selected ? 'bg-slate-700/60 ring-1 ring-slate-500/40' : 'bg-[#0f1117] hover:bg-slate-800/60',
      )}
    >
      <div className={clsx('mt-1.5 h-1.5 w-1.5 rounded-full flex-shrink-0', sc.dot)} />
      <div className="flex-1 min-w-0">
        <p className="text-xs text-slate-300 truncate group-hover:text-slate-100 transition-colors">
          {task.description}
        </p>
        <div className="flex items-center gap-1.5 mt-0.5">
          <span className={clsx('text-[10px] px-1.5 py-0.5 rounded font-mono', sc.badge)}>{sc.text}</span>
          {task.log_count > 0 && (
            <span className="text-[10px] text-slate-600">{task.log_count} logs</span>
          )}
        </div>
      </div>
    </button>
  )
}
