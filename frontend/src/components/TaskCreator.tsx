import { useState, useRef, KeyboardEvent } from 'react'
import { ParsedTask, AgentType } from '../types'
import clsx from 'clsx'

const AGENT_COLORS: Record<AgentType, string> = {
  cursor: 'text-[#4f9eff] bg-[#4f9eff]/10 border-[#4f9eff]/30',
  claude: 'text-[#a855f7] bg-[#a855f7]/10 border-[#a855f7]/30',
  codex:  'text-[#22d3a0] bg-[#22d3a0]/10 border-[#22d3a0]/30',
  qwen:   'text-[#f59e0b] bg-[#f59e0b]/10 border-[#f59e0b]/30',
}

const AGENT_ICONS: Record<AgentType, string> = {
  cursor: '⬡',
  claude: '◈',
  codex:  '◇',
  qwen:   '✦',
}

const EXAMPLE_PROMPTS = [
  '用通义千问生成一个简洁的 README.md，包含项目简介、安装步骤和使用说明',
  '用Claude Code实现一个REST API登录接口，同时用Codex生成对应的单元测试',
  '用Cursor打开项目并重构数据库层，用Claude Code更新相关文档',
  '用Codex生成一个排序算法库，用Claude Code写详细注释和README',
]

interface Props {
  onSubmit: (input: string, workspace: string) => Promise<void>
  onPreview: (input: string) => Promise<ParsedTask[]>
}

export function TaskCreator({ onSubmit, onPreview }: Props) {
  const [input, setInput] = useState('')
  const [workspace, setWorkspace] = useState('')
  const [preview, setPreview] = useState<ParsedTask[]>([])
  const [loading, setLoading] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [showWorkspace, setShowWorkspace] = useState(false)
  const previewTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  const triggerPreview = (text: string) => {
    if (previewTimeout.current) clearTimeout(previewTimeout.current)
    if (!text.trim()) {
      setPreview([])
      return
    }
    previewTimeout.current = setTimeout(async () => {
      setPreviewing(true)
      try {
        const result = await onPreview(text)
        setPreview(result)
      } catch {
        setPreview([])
      } finally {
        setPreviewing(false)
      }
    }, 800)
  }

  const handleInputChange = (v: string) => {
    setInput(v)
    triggerPreview(v)
  }

  const handleSubmit = async () => {
    if (!input.trim() || loading) return
    setLoading(true)
    try {
      await onSubmit(input.trim(), workspace.trim())
      setInput('')
      setPreview([])
      setWorkspace('')
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const useExample = (ex: string) => {
    setInput(ex)
    triggerPreview(ex)
  }

  return (
    <div className="space-y-3">
      {/* Main input */}
      <div className="relative rounded-xl border border-slate-700/60 bg-[#141720] overflow-hidden focus-within:border-slate-500/70 transition-colors duration-200">
        <textarea
          value={input}
          onChange={e => handleInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入自然语言指令，例如：用通义千问写 README；用Claude Code实现登录；用Cursor优化UI..."
          rows={3}
          className="w-full bg-transparent px-4 pt-4 pb-2 text-sm text-slate-200 placeholder-slate-600 resize-none outline-none"
        />

        {/* Bottom bar */}
        <div className="flex items-center justify-between px-4 py-2.5 border-t border-slate-700/40">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowWorkspace(v => !v)}
              className="text-xs text-slate-500 hover:text-slate-300 transition-colors flex items-center gap-1"
            >
              <span>⚙</span>
              <span>{showWorkspace ? '隐藏' : '工作目录'}</span>
            </button>
            <span className="text-slate-700 text-xs">·</span>
            <span className="text-xs text-slate-600">⌘ Enter 提交</span>
          </div>

          <button
            onClick={handleSubmit}
            disabled={!input.trim() || loading}
            className={clsx(
              'flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-medium transition-all duration-200',
              input.trim() && !loading
                ? 'bg-gradient-to-r from-[#4f9eff] to-[#a855f7] text-white hover:opacity-90 shadow-lg shadow-blue-500/20'
                : 'bg-slate-700 text-slate-500 cursor-not-allowed'
            )}
          >
            {loading ? (
              <>
                <span className="animate-spin inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full" />
                <span>调度中...</span>
              </>
            ) : (
              <>
                <span>▶</span>
                <span>调度任务</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Workspace input */}
      {showWorkspace && (
        <div className="animate-[slideUp_0.2s_ease-out]">
          <input
            type="text"
            value={workspace}
            onChange={e => setWorkspace(e.target.value)}
            placeholder="工作目录路径，例如：/Users/me/myproject（留空使用默认目录）"
            className="w-full bg-[#141720] border border-slate-700/60 rounded-lg px-3 py-2 text-sm text-slate-300 placeholder-slate-600 outline-none focus:border-slate-500 transition-colors font-mono"
          />
        </div>
      )}

      {/* Preview */}
      {(preview.length > 0 || previewing) && (
        <div className="rounded-xl border border-slate-700/40 bg-[#141720] p-3 space-y-2">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-slate-500 uppercase tracking-wide font-medium">任务解析预览</span>
            {previewing && (
              <span className="text-xs text-slate-600 flex items-center gap-1">
                <span className="animate-spin inline-block w-2.5 h-2.5 border border-slate-600 border-t-slate-400 rounded-full" />
                解析中...
              </span>
            )}
          </div>
          {preview.map((p, i) => (
            <div
              key={i}
              className={clsx(
                'flex items-start gap-3 px-3 py-2 rounded-lg border',
                AGENT_COLORS[p.agent]
              )}
            >
              <span className="text-base leading-none mt-0.5 flex-shrink-0">{AGENT_ICONS[p.agent]}</span>
              <div>
                <span className={clsx('text-[10px] font-mono uppercase font-bold', AGENT_COLORS[p.agent].split(' ')[0])}>
                  {p.agent}
                </span>
                <p className="text-xs text-slate-300 mt-0.5">{p.task}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Example prompts */}
      {!input && (
        <div className="space-y-1.5">
          <p className="text-xs text-slate-600">示例指令：</p>
          {EXAMPLE_PROMPTS.map((ex, i) => (
            <button
              key={i}
              onClick={() => useExample(ex)}
              className="w-full text-left text-xs text-slate-500 hover:text-slate-300 px-3 py-2 rounded-lg bg-[#141720] border border-slate-700/30 hover:border-slate-600/50 transition-all duration-150 truncate"
            >
              {ex}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
