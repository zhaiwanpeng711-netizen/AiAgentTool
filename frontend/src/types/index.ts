export type AgentType = 'cursor' | 'claude' | 'codex' | 'qwen'
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'stopped'

export interface LogEntry {
  timestamp: string
  level: 'info' | 'error' | 'system'
  message: string
}

export interface TaskSummary {
  id: string
  description: string
  agent_type: AgentType
  status: TaskStatus
  created_at: string
  started_at: string | null
  completed_at: string | null
  exit_code: number | null
  log_count: number
}

export interface TaskDetail extends TaskSummary {
  logs: LogEntry[]
}

export interface AgentInfo {
  agent_type: AgentType
  running_tasks: number
  total_tasks: number
  available: boolean
  description: string
}

export interface ParsedTask {
  agent: AgentType
  task: string
  workspace?: string
}

export interface AgentUsage {
  agent_type: AgentType
  calls: number
  tokens_input: number
  tokens_output: number
  tokens_total: number
  cost_usd: number
  last_used: string | null
}

export type WsEvent =
  | { event: 'task_created'; data: TaskSummary }
  | { event: 'task_updated'; data: TaskSummary }
  | { event: 'task_deleted'; data: { task_id: string } }
  | { event: 'task_snapshot'; data: TaskSummary }
  | { event: 'task_log'; data: { task_id: string; log: LogEntry } }
  | { event: 'agent_info'; data: AgentInfo }
  | { event: 'usage_updated'; data: AgentUsage[] }
  | { event: 'state_reset'; data: { task_count: number } }
