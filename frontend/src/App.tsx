import { useState, useCallback, useEffect, useRef } from 'react'
import { TaskSummary, TaskDetail, AgentInfo, AgentType, LogEntry, ParsedTask, WsEvent } from './types'
import { useWebSocket } from './hooks/useWebSocket'
import { AgentCard } from './components/AgentCard'
import { TaskCreator } from './components/TaskCreator'
import { TaskList } from './components/TaskList'
import { LogViewer } from './components/LogViewer'
import clsx from 'clsx'

const API = '/api'

export default function App() {
  const [tasks, setTasks] = useState<Map<string, TaskSummary>>(new Map())
  const [agents, setAgents] = useState<Map<AgentType, AgentInfo>>(new Map())
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
  const [taskDetail, setTaskDetail] = useState<TaskDetail | null>(null)
  const [liveLog, setLiveLog] = useState<LogEntry[]>([])
  const [activeTab, setActiveTab] = useState<'dashboard' | 'tasks'>('dashboard')
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)
  const liveLogRef = useRef<Map<string, LogEntry[]>>(new Map())

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3000)
  }

  // WebSocket message handler
  const handleWsMessage = useCallback((event: WsEvent) => {
    switch (event.event) {
      case 'task_created':
      case 'task_updated':
      case 'task_snapshot':
        setTasks(prev => {
          const next = new Map(prev)
          next.set(event.data.id, event.data)
          return next
        })
        break

      case 'task_deleted':
        setTasks(prev => {
          const next = new Map(prev)
          next.delete(event.data.task_id)
          return next
        })
        if (selectedTaskId === event.data.task_id) {
          setSelectedTaskId(null)
          setTaskDetail(null)
        }
        break

      case 'task_log': {
        const { task_id, log } = event.data
        const logs = liveLogRef.current.get(task_id) ?? []
        logs.push(log)
        liveLogRef.current.set(task_id, logs)
        // If this task is selected, update live log display
        setSelectedTaskId(prev => {
          if (prev === task_id) {
            setLiveLog([...logs])
          }
          return prev
        })
        break
      }

      case 'agent_info':
        setAgents(prev => {
          const next = new Map(prev)
          next.set(event.data.agent_type, event.data)
          return next
        })
        break
    }
  }, [selectedTaskId])

  const { connected } = useWebSocket(handleWsMessage)

  // Load initial data
  useEffect(() => {
    fetch(`${API}/tasks`).then(r => r.json()).then(d => {
      setTasks(new Map(d.tasks.map((t: TaskSummary) => [t.id, t])))
    }).catch(() => {})
    fetch(`${API}/agents`).then(r => r.json()).then(d => {
      setAgents(new Map(d.agents.map((a: AgentInfo) => [a.agent_type, a])))
    }).catch(() => {})
  }, [])

  // Load task detail when selected
  useEffect(() => {
    if (!selectedTaskId) {
      setTaskDetail(null)
      setLiveLog([])
      return
    }
    fetch(`${API}/tasks/${selectedTaskId}`)
      .then(r => r.json())
      .then(d => {
        setTaskDetail(d)
        // Merge with any buffered live logs
        const buffered = liveLogRef.current.get(selectedTaskId) ?? []
        const existing = new Set(d.logs.map((l: LogEntry) => `${l.timestamp}${l.message}`))
        const newLogs = buffered.filter(l => !existing.has(`${l.timestamp}${l.message}`))
        setLiveLog(newLogs)
      })
      .catch(() => setTaskDetail(null))
  }, [selectedTaskId])

  const handleSelectTask = (id: string) => {
    setSelectedTaskId(id)
    setActiveTab('tasks')
  }

  const handleSubmit = async (input: string, workspace: string) => {
    const res = await fetch(`${API}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ natural_language: input, workspace: workspace || null }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      showToast(err.detail || '创建任务失败', 'error')
      throw new Error('Failed')
    }
    const data = await res.json()
    showToast(`已创建并调度 ${data.tasks.length} 个任务`, 'success')
  }

  const handlePreview = async (input: string): Promise<ParsedTask[]> => {
    const res = await fetch(`${API}/tasks/parse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ natural_language: input }),
    })
    if (!res.ok) return []
    const data = await res.json()
    return data.tasks
  }

  const handleStop = async (taskId: string) => {
    await fetch(`${API}/tasks/${taskId}/stop`, { method: 'POST' })
    showToast('任务已停止')
  }

  const handleRetry = async (taskId: string) => {
    liveLogRef.current.delete(taskId)
    setLiveLog([])
    await fetch(`${API}/tasks/${taskId}/start`, { method: 'POST' })
    showToast('任务已重新启动')
  }

  const handleDelete = async (taskId: string) => {
    await fetch(`${API}/tasks/${taskId}`, { method: 'DELETE' })
    showToast('任务已删除')
  }

  const taskList = Array.from(tasks.values())
  const agentList = Array.from(agents.values())

  // Running tasks count for the header badge
  const runningCount = taskList.filter(t => t.status === 'running').length

  return (
    <div className="min-h-screen bg-[#0f1117] flex flex-col">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-slate-800/70 bg-[#0a0c12]/80 backdrop-blur-sm sticky top-0 z-20">
        <div className="max-w-[1600px] mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[#4f9eff] to-[#a855f7] flex items-center justify-center text-white text-sm font-bold">
                A
              </div>
              <h1 className="text-base font-semibold gradient-text">AI Agent Scheduler</h1>
            </div>
            <span className="text-slate-700">|</span>
            <span className="text-xs text-slate-600">自然语言任务调度平台</span>
          </div>

          <div className="flex items-center gap-4">
            {runningCount > 0 && (
              <div className="flex items-center gap-1.5 text-xs text-yellow-400">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-yellow-400" />
                </span>
                {runningCount} 个任务运行中
              </div>
            )}
            <div className={clsx(
              'flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full',
              connected ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
            )}>
              <span className={clsx('w-1.5 h-1.5 rounded-full', connected ? 'bg-emerald-400' : 'bg-red-400', connected && 'animate-pulse')} />
              {connected ? '已连接' : '重连中...'}
            </div>
          </div>
        </div>
      </header>

      <div className="flex-1 max-w-[1600px] mx-auto w-full px-6 py-6 flex flex-col gap-6">
        {/* Task Creator */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <h2 className="text-xs text-slate-500 uppercase tracking-widest font-medium">任务调度</h2>
            <div className="flex-1 h-px bg-slate-800" />
          </div>
          <TaskCreator onSubmit={handleSubmit} onPreview={handlePreview} />
        </section>

        {/* Main content */}
        <section className="flex-1 flex flex-col gap-6 min-h-0">
          {/* Tab switcher */}
          <div className="flex items-center gap-1 bg-[#141720] rounded-lg p-1 w-fit">
            <TabBtn active={activeTab === 'dashboard'} onClick={() => setActiveTab('dashboard')}>
              Dashboard
            </TabBtn>
            <TabBtn active={activeTab === 'tasks'} onClick={() => setActiveTab('tasks')}>
              任务列表
              {taskList.length > 0 && (
                <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded-full bg-slate-600 text-slate-300">{taskList.length}</span>
              )}
            </TabBtn>
          </div>

          {/* Dashboard tab: Agent cards */}
          {activeTab === 'dashboard' && (
            <div className="space-y-6 animate-[fadeIn_0.2s_ease-out]">
              {/* Agent overview grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {(['cursor', 'claude', 'codex'] as AgentType[]).map(agentType => {
                  const info = agents.get(agentType) ?? {
                    agent_type: agentType,
                    running_tasks: 0,
                    total_tasks: 0,
                    available: false,
                    description: 'Loading...',
                  }
                  const agentTasks = taskList.filter(t => t.agent_type === agentType)
                  return (
                    <AgentCard
                      key={agentType}
                      info={info}
                      tasks={agentTasks}
                      onSelectTask={handleSelectTask}
                      selectedTaskId={selectedTaskId}
                    />
                  )
                })}
              </div>

              {/* Summary stats */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <SummaryCard label="全部任务" value={taskList.length} color="text-slate-300" />
                <SummaryCard label="运行中" value={taskList.filter(t => t.status === 'running').length} color="text-yellow-400" />
                <SummaryCard label="已完成" value={taskList.filter(t => t.status === 'completed').length} color="text-emerald-400" />
                <SummaryCard label="失败" value={taskList.filter(t => t.status === 'failed').length} color="text-red-400" />
                <SummaryCard label="已停止" value={taskList.filter(t => t.status === 'stopped').length} color="text-orange-400" />
              </div>
            </div>
          )}

          {/* Tasks tab: task list + log viewer */}
          {activeTab === 'tasks' && (
            <div className="flex gap-4 flex-1 min-h-0 animate-[fadeIn_0.2s_ease-out]" style={{ height: 'calc(100vh - 420px)', minHeight: '400px' }}>
              {/* Task list */}
              <div className="w-80 flex-shrink-0 flex flex-col overflow-hidden">
                <TaskList
                  tasks={taskList}
                  selectedId={selectedTaskId}
                  onSelect={handleSelectTask}
                  onStop={handleStop}
                  onRetry={handleRetry}
                  onDelete={handleDelete}
                />
              </div>

              {/* Log viewer */}
              <div className="flex-1 rounded-xl border border-slate-700/50 bg-[#141720] p-4 overflow-hidden flex flex-col">
                <LogViewer
                  task={taskDetail}
                  liveLog={liveLog}
                  onClose={() => { setSelectedTaskId(null); setTaskDetail(null) }}
                  onStop={() => selectedTaskId && handleStop(selectedTaskId)}
                  onRetry={() => selectedTaskId && handleRetry(selectedTaskId)}
                />
              </div>
            </div>
          )}
        </section>
      </div>

      {/* Toast notification */}
      {toast && (
        <div className={clsx(
          'fixed bottom-6 right-6 z-50 px-4 py-3 rounded-xl text-sm font-medium shadow-xl animate-[slideUp_0.3s_ease-out] flex items-center gap-2',
          toast.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'
        )}>
          {toast.type === 'success' ? '✓' : '✗'} {toast.message}
        </div>
      )}
    </div>
  )
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        'px-4 py-1.5 text-sm rounded-md transition-all duration-150 flex items-center',
        active ? 'bg-slate-600 text-slate-100 font-medium' : 'text-slate-500 hover:text-slate-300'
      )}
    >
      {children}
    </button>
  )
}

function SummaryCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="bg-[#141720] rounded-xl border border-slate-700/40 p-4 text-center">
      <div className={clsx('text-2xl font-bold font-mono', color)}>{value}</div>
      <div className="text-xs text-slate-600 mt-1">{label}</div>
    </div>
  )
}
