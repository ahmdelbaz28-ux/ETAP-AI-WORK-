import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Bot, Send, User, Sparkles, Cpu, Copy, RotateCcw, Terminal,
  ShieldCheck, ShieldOff, Zap, ChevronDown, Check, Brain,
  Code2, FileText, Lightbulb, AlertCircle,
} from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import { chatWithAgent, fetchAgents, type AgentMeta } from '../lib/api'
import { Badge, Button, Toggle } from '../components/ui'
import { cn } from '../utils/helpers'
import { ContextHelpButton } from '../components/help/ContextHelpButton'

// ============================================================================
// Types
// ============================================================================
interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  thinking?: boolean
  copied?: boolean
}

interface AgentSetting {
  skipPermissions: boolean
  verboseMode: boolean
  autoExecute: boolean
}

// ============================================================================
// Markdown Renderer — renders **bold**, `code`, ```code blocks```, lists
// ============================================================================
function MarkdownText({ text }: { text: string }) {
  const parts = text.split(/(```[\s\S]*?```|`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\n)/g)
  return (
    <div className="text-sm leading-relaxed">
      {parts.map((part, i) => {
        // Code block
        if (part.startsWith('```') && part.endsWith('```')) {
          const code = part.slice(3, -3).replace(/^\w+\n/, '').trim()
          return (
            <div key={i} className="my-3 rounded-lg overflow-hidden border border-[var(--border-primary)] bg-[rgba(0,0,0,0.3)]">
              <div className="flex items-center justify-between px-3 py-1.5 bg-[var(--bg-elevated)] border-b border-[var(--border-primary)]">
                <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase tracking-wider">Code</span>
                <button
                  onClick={() => navigator.clipboard.writeText(code)}
                  className="p-1 rounded hover:bg-[var(--bg-card)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
                >
                  <Copy className="w-3 h-3" />
                </button>
              </div>
              <pre className="p-3 overflow-x-auto text-xs font-mono text-[var(--text-secondary)] leading-relaxed">
                <code>{code}</code>
              </pre>
            </div>
          )
        }
        // Inline code
        if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
          return (
            <code key={i} className="px-1.5 py-0.5 rounded bg-[var(--bg-elevated)] text-brand-400 text-xs font-mono border border-[var(--border-primary)]">
              {part.slice(1, -1)}
            </code>
          )
        }
        // Bold
        if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
          return <strong key={i} className="font-semibold text-[var(--text-primary)]">{part.slice(2, -2)}</strong>
        }
        // Italic
        if (part.startsWith('*') && part.endsWith('*') && part.length > 2 && !part.startsWith('**')) {
          return <em key={i} className="italic">{part.slice(1, -1)}</em>
        }
        // Newline
        if (part === '\n') return <br key={i} />
        // Regular text — render as paragraphs
        if (part.trim()) {
          // Check if it's a list item
          if (part.match(/^\s*[-•]\s/)) {
            return <div key={i} className="flex gap-2 my-0.5"><span className="text-brand-400">•</span><span>{part.replace(/^\s*[-•]\s/, '')}</span></div>
          }
          return <span key={i}>{part}</span>
        }
        return null
      })}
    </div>
  )
}

// ============================================================================
// Thinking Indicator — Claude Code style pulsing brain
// ============================================================================
function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-2 text-[var(--text-muted)]">
      <Brain className="w-4 h-4 text-brand-400 animate-pulse" />
      <span className="text-xs font-mono italic">thinking...</span>
      <div className="flex gap-1">
        <span className="w-1 h-1 bg-brand-400 rounded-full animate-bounce" />
        <span className="w-1 h-1 bg-brand-400 rounded-full animate-bounce [animation-delay:0.15s]" />
        <span className="w-1 h-1 bg-brand-400 rounded-full animate-bounce [animation-delay:0.3s]" />
      </div>
    </div>
  )
}

// ============================================================================
// Quick Prompt Buttons
// ============================================================================
const QUICK_PROMPTS = [
  { icon: Zap, label: 'Run load flow analysis', prompt: 'Run a Newton-Raphson load flow analysis on a 5-bus system and explain the results.' },
  { icon: AlertCircle, label: 'Short circuit calculation', prompt: 'Calculate the three-phase short circuit current for a typical 11kV system per IEC 60909.' },
  { icon: FileText, label: 'Explain arc flash study', prompt: 'Explain the IEEE 1584-2018 arc flash analysis methodology step by step.' },
  { icon: Code2, label: 'Write protection code', prompt: 'Write Python code for an overcurrent relay coordination check using IEC 60255 curves.' },
]

// ============================================================================
// Main Component
// ============================================================================
export default function AIAssistant() {
  const [agents, setAgents] = useState<AgentMeta[]>([])
  const [selectedAgent, setSelectedAgent] = useState<string>('power-system-coordinator-agent')
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [settings, setSettings] = useState<AgentSetting>({
    skipPermissions: false,
    verboseMode: false,
    autoExecute: false,
  })
  const [showSettings, setShowSettings] = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const { notify } = useNotify()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    fetchAgents().then(setAgents).catch(() => notify('error', 'Failed to load agents'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText])

  // Streaming effect — simulate character-by-character typing
  const streamResponse = useCallback((fullText: string, onComplete: () => void) => {
    let i = 0
    const words = fullText.split(' ')
    setStreamingText('')
    const interval = setInterval(() => {
      if (i >= words.length) {
        clearInterval(interval)
        setStreamingText('')
        onComplete()
        return
      }
      setStreamingText(prev => prev + (i === 0 ? '' : ' ') + words[i])
      i++
    }, 30) // 30ms per word — fast but visible
    return interval
  }, [])

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const userMsg: Message = { role: 'user', content: input.trim(), timestamp: Date.now() }
    setMessages(prev => [...prev, userMsg])
    const userQuery = input.trim()
    setInput('')
    setLoading(true)

    try {
      const reply = await chatWithAgent(
        selectedAgent,
        [...messages, userMsg].map(m => m.content).join('\n')
      )
      // Stream the response for a Claude Code-like experience
      const responseText = reply.response || 'No response received.'
      streamResponse(responseText, () => {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: responseText,
          timestamp: Date.now(),
        }])
        setLoading(false)
      })
    } catch (err) {
      notify('error', `Chat failed: ${err instanceof Error ? err.message : 'Unknown error'}`)
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Enter to send, Shift+Enter for newline
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleCopy = (index: number) => {
    const msg = messages[index]
    if (msg) {
      navigator.clipboard.writeText(msg.content)
      setMessages(prev => prev.map((m, i) => i === index ? { ...m, copied: true } : m))
      setTimeout(() => {
        setMessages(prev => prev.map((m, i) => i === index ? { ...m, copied: false } : m))
      }, 2000)
    }
  }

  const selectedAgentData = agents.find(a => a.id === selectedAgent)

  return (
    <div className="h-[calc(100vh-140px)] flex flex-col" data-help-context="ai-assistant.overview">
      {/* ─── Header ─── */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-gradient-to-br from-brand-500/15 to-brand-700/10 border border-brand-500/20">
            <Terminal className="w-5 h-5 text-brand-400" />
          </div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-[var(--text-primary)] tracking-tight">AI Assistant</h2>
            <ContextHelpButton contextId="ai-assistant.overview" />
            {settings.skipPermissions && (
              <Badge variant="warning" size="sm" className="ml-1">
                <ShieldOff className="w-3 h-3 mr-1" />
                Skip Perms
              </Badge>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Agent selector */}
          <div className="relative">
            <select
              value={selectedAgent}
              onChange={e => setSelectedAgent(e.target.value)}
              className="appearance-none pl-3 pr-8 py-2 bg-[var(--bg-card)] border border-[var(--border-primary)] rounded-lg text-[var(--text-primary)] text-sm focus:border-brand-500 outline-none cursor-pointer hover:border-[var(--border-secondary)] transition-colors"
            >
              {agents.map(a => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
            <ChevronDown className="w-4 h-4 text-[var(--text-muted)] absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          {/* Settings toggle */}
          <button
            onClick={() => setShowSettings(prev => !prev)}
            className={cn(
              'p-2 rounded-lg border transition-colors',
              showSettings
                ? 'bg-brand-500/10 border-brand-500/30 text-brand-400'
                : 'bg-[var(--bg-card)] border-[var(--border-primary)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            )}
            title="Agent settings"
          >
            <Cpu className="w-4 h-4" />
          </button>

          {/* Clear button */}
          {messages.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              icon={RotateCcw}
              onClick={() => { setMessages([]); setStreamingText('') }}
            >
              Clear
            </Button>
          )}
        </div>
      </div>

      {/* ─── Settings Panel (collapsible) ─── */}
      <AnimatePresence>
        {showSettings && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden mb-3"
          >
            <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-primary)] p-4 space-y-3">
              <div className="flex items-center gap-2 mb-2">
                <Cpu className="w-4 h-4 text-brand-400" />
                <span className="text-sm font-semibold text-[var(--text-primary)]">Agent Settings</span>
              </div>

              {/* Skip Permissions */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {settings.skipPermissions ? (
                    <ShieldOff className="w-4 h-4 text-amber-400" />
                  ) : (
                    <ShieldCheck className="w-4 h-4 text-green-400" />
                  )}
                  <div>
                    <div className="text-sm font-medium text-[var(--text-primary)]">
                      Skip Permissions
                    </div>
                    <div className="text-[11px] text-[var(--text-muted)]">
                      Allow agent to execute actions without asking for confirmation
                    </div>
                  </div>
                </div>
                <Toggle
                  checked={settings.skipPermissions}
                  onChange={(v) => setSettings(prev => ({ ...prev, skipPermissions: v }))}
                  size="sm"
                />
              </div>

              {/* Verbose Mode */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Terminal className="w-4 h-4 text-[var(--text-muted)]" />
                  <div>
                    <div className="text-sm font-medium text-[var(--text-primary)]">
                      Verbose Mode
                    </div>
                    <div className="text-[11px] text-[var(--text-muted)]">
                      Show detailed reasoning and intermediate steps
                    </div>
                  </div>
                </div>
                <Toggle
                  checked={settings.verboseMode}
                  onChange={(v) => setSettings(prev => ({ ...prev, verboseMode: v }))}
                  size="sm"
                />
              </div>

              {/* Auto Execute */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Zap className="w-4 h-4 text-[var(--text-muted)]" />
                  <div>
                    <div className="text-sm font-medium text-[var(--text-primary)]">
                      Auto-Execute Studies
                    </div>
                    <div className="text-[11px] text-[var(--text-muted)]">
                      Automatically run recommended studies without confirmation
                    </div>
                  </div>
                </div>
                <Toggle
                  checked={settings.autoExecute}
                  onChange={(v) => setSettings(prev => ({ ...prev, autoExecute: v }))}
                  size="sm"
                />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── Agent Info Bar ─── */}
      {selectedAgentData && (
        <div className="flex items-center gap-3 px-4 py-2 bg-[var(--bg-card)] rounded-lg border border-[var(--border-primary)] mb-3">
          <div className="w-7 h-7 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center shrink-0">
            <Bot className="w-3.5 h-3.5 text-brand-400" />
          </div>
          <div className="flex-1 min-w-0">
            <span className="text-sm font-medium text-[var(--text-primary)]">{selectedAgentData.name}</span>
            {selectedAgentData.standard && (
              <span className="text-xs text-[var(--text-muted)] ml-2 font-mono">{selectedAgentData.standard}</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1 text-[10px] text-green-400">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
              Active
            </span>
            <Badge variant="brand" size="sm">{selectedAgentData.provider || 'native'}</Badge>
          </div>
        </div>
      )}

      {/* ─── Messages Area ─── */}
      <div className="flex-1 bg-[var(--bg-card)] rounded-xl border border-[var(--border-primary)] overflow-hidden flex flex-col">
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {/* Empty state */}
          {messages.length === 0 && !loading && (
            <div className="text-center py-12">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-500/15 to-brand-700/10 flex items-center justify-center mx-auto mb-4 border border-brand-500/15">
                <Sparkles className="w-8 h-8 text-brand-400" />
              </div>
              <h3 className="text-base font-semibold text-[var(--text-primary)] mb-1">
                How can I help you today?
              </h3>
              <p className="text-xs text-[var(--text-muted)] max-w-[400px] mx-auto mb-6">
                I'm your AI engineering assistant. Ask me about power systems, run studies, or write code.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-[520px] mx-auto">
                {QUICK_PROMPTS.map(qp => (
                  <button
                    key={qp.label}
                    onClick={() => { setInput(qp.prompt); inputRef.current?.focus() }}
                    className="flex items-center gap-2.5 px-3 py-2.5 text-left bg-[var(--bg-elevated)] hover:bg-brand-500/8 border border-[var(--border-primary)] hover:border-brand-500/30 rounded-lg transition-all group"
                  >
                    <qp.icon className="w-4 h-4 text-[var(--text-muted)] group-hover:text-brand-400 transition-colors shrink-0" />
                    <span className="text-xs text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition-colors">
                      {qp.label}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Messages */}
          {messages.map((m, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              className={cn(
                'flex gap-3',
                m.role === 'user' ? 'justify-end' : 'justify-start'
              )}
            >
              {/* Assistant avatar */}
              {m.role === 'assistant' && (
                <div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center shrink-0 mt-0.5">
                  <Bot className="w-4 h-4 text-brand-400" />
                </div>
              )}

              {/* Message bubble */}
              <div className={cn(
                'max-w-[78%] rounded-xl px-4 py-3',
                m.role === 'user'
                  ? 'bg-brand-600 text-white'
                  : 'bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-primary)]'
              )}>
                {m.role === 'assistant' ? (
                  <MarkdownText text={m.content} />
                ) : (
                  <p className="text-sm whitespace-pre-wrap">{m.content}</p>
                )}

                {/* Footer */}
                <div className={cn(
                  'flex items-center gap-2 mt-2 pt-2 border-t',
                  m.role === 'user' ? 'border-white/10' : 'border-[var(--border-primary)]'
                )}>
                  <span className="text-[10px] opacity-40 font-mono">
                    {new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  {m.role === 'assistant' && (
                    <button
                      onClick={() => handleCopy(i)}
                      className="ml-auto flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)] transition-colors"
                    >
                      {m.copied ? (
                        <><Check className="w-3 h-3 text-green-400" /> Copied</>
                      ) : (
                        <><Copy className="w-3 h-3" /> Copy</>
                      )}
                    </button>
                  )}
                </div>
              </div>

              {/* User avatar */}
              {m.role === 'user' && (
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shrink-0 mt-0.5">
                  <User className="w-4 h-4 text-white" />
                </div>
              )}
            </motion.div>
          ))}

          {/* Streaming response (Claude Code style) */}
          {loading && streamingText && (
            <div className="flex gap-3 justify-start">
              <div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center shrink-0 mt-0.5">
                <Bot className="w-4 h-4 text-brand-400" />
              </div>
              <div className="max-w-[78%] rounded-xl px-4 py-3 bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-primary)]">
                <MarkdownText text={streamingText} />
                <span className="inline-block w-1.5 h-4 bg-brand-400 animate-pulse ml-0.5 align-middle" />
              </div>
            </div>
          )}

          {/* Thinking indicator (before streaming starts) */}
          {loading && !streamingText && (
            <div className="flex gap-3 justify-start">
              <div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center shrink-0 mt-0.5">
                <Bot className="w-4 h-4 text-brand-400" />
              </div>
              <div className="rounded-xl px-4 py-3 bg-[var(--bg-elevated)] border border-[var(--border-primary)]">
                <ThinkingIndicator />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* ─── Input Area ─── */}
        <div className="border-t border-[var(--border-primary)] p-3 bg-[var(--bg-secondary)]">
          <form
            onSubmit={e => { e.preventDefault(); handleSend() }}
            className="flex gap-2 items-end"
          >
            <div className="flex-1 relative">
              <input
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={loading}
                placeholder={loading ? 'AI is responding...' : 'Ask about power systems engineering...  (Enter to send, Shift+Enter for newline)'}
                className="w-full px-4 py-2.5 bg-[var(--bg-card)] border border-[var(--border-primary)] rounded-xl text-[var(--text-primary)] text-sm outline-none placeholder:text-[var(--text-muted)] focus:border-brand-500/50 focus:ring-1 focus:ring-brand-500/20 transition-all disabled:opacity-50"
              />
            </div>
            <Button
              type="submit"
              variant="primary"
              size="icon"
              disabled={loading || !input.trim()}
              icon={Send}
              className="shrink-0"
            />
          </form>

          {/* Status bar */}
          <div className="flex items-center justify-between mt-2 px-1">
            <div className="flex items-center gap-3 text-[10px] text-[var(--text-muted)] font-mono">
              <span className="flex items-center gap-1">
                <span className={cn('w-1.5 h-1.5 rounded-full', loading ? 'bg-amber-400 animate-pulse' : 'bg-green-400')} />
                {loading ? 'Processing' : 'Ready'}
              </span>
              <span>•</span>
              <span>{selectedAgentData?.name || 'No agent'}</span>
              {settings.skipPermissions && (
                <>
                  <span>•</span>
                  <span className="text-amber-400">⚠ Skip Perms ON</span>
                </>
              )}
              {settings.verboseMode && (
                <>
                  <span>•</span>
                  <span className="text-blue-400">Verbose</span>
                </>
              )}
            </div>
            <div className="text-[10px] text-[var(--text-muted)] font-mono">
              {messages.length} message{messages.length !== 1 ? 's' : ''}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
