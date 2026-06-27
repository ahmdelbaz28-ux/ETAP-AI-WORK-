import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Bot, Send, User, Sparkles, Cpu, Copy, RotateCcw, MessageSquare } from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import { chatWithAgent, fetchAgents, type AgentMeta } from '../lib/api'
import { Badge, Button } from '../components/ui'
import { cn } from '../utils/helpers'

import { ContextHelpButton } from '../components/help/ContextHelpButton'
interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

export default function AIAssistant() {
  const [agents, setAgents] = useState<AgentMeta[]>([])
  const [selectedAgent, setSelectedAgent] = useState<string>('power-system-coordinator-agent')
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const { notify } = useNotify()
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetchAgents().then(setAgents).catch(() => notify('error', 'Failed to load agents'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const userMsg: Message = { role: 'user', content: input.trim(), timestamp: Date.now() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const reply = await chatWithAgent(
        selectedAgent,
        [...messages, userMsg].map(m => m.content).join('\n')
      )
      setMessages(prev => [...prev, { role: 'assistant', content: reply.response, timestamp: Date.now() }])
    } catch (err) {
      notify('error', `Chat failed: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  const selectedAgentData = agents.find(a => a.id === selectedAgent)

  return (
    <div className="space-y-4 h-[calc(100vh-140px)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <MessageSquare className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">AI Assistant</h2>
          <ContextHelpButton contextId="ai-assistant.overview" />
            <p className="text-xs text-[var(--text-muted)]">Power systems engineering AI agent</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={selectedAgent}
            onChange={e => setSelectedAgent(e.target.value)}
            className="px-3 py-2 bg-[var(--bg-card)] border border-[var(--border-primary)] rounded-lg text-[var(--text-primary)] text-sm focus:border-brand-500 outline-none"
          >
            {agents.map(a => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          {messages.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              icon={RotateCcw}
              onClick={() => setMessages([])}
            >
              Clear
            </Button>
          )}
        </div>
      </div>

      {/* Agent info bar */}
      {selectedAgentData && (
        <div className="flex items-center gap-3 px-4 py-2.5 bg-[var(--bg-card)] rounded-lg border border-[var(--border-primary)]">
          <Cpu className="w-4 h-4 text-brand-400" />
          <div className="flex-1">
            <span className="text-sm font-medium text-[var(--text-primary)]">{selectedAgentData.name}</span>
            <span className="text-xs text-[var(--text-muted)] ml-2">
              {selectedAgentData.capabilities.slice(0, 3).join(' \u2022 ')}
            </span>
          </div>
          <Badge variant="brand" size="sm">{selectedAgentData.provider || 'active'}</Badge>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 bg-[var(--bg-card)] rounded-xl border border-[var(--border-primary)] p-4 overflow-y-auto space-y-4">
        {messages.length === 0 && (
          <div className="text-center py-16">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-brand-500/20 to-brand-700/20 flex items-center justify-center mx-auto mb-4 border border-brand-500/10">
              <Sparkles className="w-10 h-10 text-brand-400" />
            </div>
            <h3 className="text-lg font-semibold text-[var(--text-primary)]">Start a Conversation</h3>
            <p className="text-sm text-[var(--text-tertiary)] mt-1 max-w-[480px] mx-auto w-full">
              Ask about power systems analysis, load flow studies, fault calculations, or any engineering topic.
            </p>
            <div className="flex flex-wrap gap-2 justify-center mt-4">
              {['Run a load flow analysis', 'Explain short circuit types', 'Calculate arc flash energy', 'Analyze protection coordination'].map(q => (
                <button
                  key={q}
                  onClick={() => setInput(q)}
                  className="px-3 py-1.5 text-xs text-[var(--text-secondary)] bg-[var(--bg-elevated)] hover:bg-brand-500/10 hover:text-brand-400 border border-[var(--border-primary)] hover:border-brand-500/30 rounded-lg transition-all"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn('flex gap-3', m.role === 'user' ? 'justify-end' : '')}
          >
            {m.role === 'assistant' && (
              <div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center shrink-0 mt-0.5">
                <Bot className="w-4 h-4 text-brand-400" />
              </div>
            )}
            <div className={cn(
              'max-w-[80%] rounded-xl px-4 py-3',
              m.role === 'user'
                ? 'bg-brand-600 text-white'
                : 'bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-primary)]'
            )}>
              <p className="text-sm whitespace-pre-wrap">{m.content}</p>
              <div className={cn(
                'flex items-center gap-2 mt-2 pt-2 border-t',
                m.role === 'user' ? 'border-white/10' : 'border-[var(--border-primary)]'
              )}>
                <span className="text-[10px] opacity-50">
                  {new Date(m.timestamp).toLocaleTimeString()}
                </span>
                {m.role === 'assistant' && (
                  <button
                    onClick={() => navigator.clipboard.writeText(m.content)}
                    className="ml-auto p-1 rounded hover:bg-[var(--bg-card)] text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors"
                  >
                    <Copy className="w-3 h-3" />
                  </button>
                )}
              </div>
            </div>
            {m.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shrink-0 mt-0.5">
                <User className="w-4 h-4 text-white" />
              </div>
            )}
          </motion.div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-brand-400" />
            </div>
            <div className="bg-[var(--bg-elevated)] rounded-xl px-4 py-3 border border-[var(--border-primary)]">
              <div className="flex gap-1.5">
                <span className="w-2 h-2 bg-brand-400 rounded-full animate-bounce" />
                <span className="w-2 h-2 bg-brand-400 rounded-full animate-bounce [animation-delay:0.15s]" />
                <span className="w-2 h-2 bg-brand-400 rounded-full animate-bounce [animation-delay:0.3s]" />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={e => { e.preventDefault(); handleSend() }}
        className="flex gap-2 bg-[var(--bg-card)] rounded-xl border border-[var(--border-primary)] p-2 focus-within:border-brand-500/50 focus-within:ring-1 focus-within:ring-brand-500/20 transition-all"
      >
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          disabled={loading}
          placeholder="Ask about power systems engineering..."
          className="flex-1 px-3 py-2 bg-transparent text-[var(--text-primary)] text-sm outline-none placeholder:text-[var(--text-muted)]"
        />
        <Button
          type="submit"
          variant="primary"
          size="icon"
          disabled={loading || !input.trim()}
          icon={Send}
        />
      </form>
    </div>
  )
}
