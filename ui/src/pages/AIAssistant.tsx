import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Bot, Send, User, Sparkles, Cpu, Copy, RotateCcw, MessageSquare, Check, ChevronDown } from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import { chatWithAgent, fetchAgents, type AgentMeta } from '../lib/api'
import { cn } from '../utils/helpers'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface Message {
  id: string
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
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const { notify } = useNotify()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    fetchAgents().then(setAgents).catch(() => notify('error', 'Failed to load agents'))
    // focus input on mount
    setTimeout(() => inputRef.current?.focus(), 100)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: input.trim(), timestamp: Date.now() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const reply = await chatWithAgent(
        selectedAgent,
        [...messages, userMsg].map(m => m.content).join('\n')
      )
      setMessages(prev => [...prev, { id: Date.now().toString(), role: 'assistant', content: reply.response, timestamp: Date.now() }])
    } catch (err) {
      notify('error', `Chat failed: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setLoading(false)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleCopy = (id: string, content: string) => {
    navigator.clipboard.writeText(content)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const selectedAgentData = agents.find(a => a.id === selectedAgent)

  return (
    <div className="flex flex-col h-[calc(100vh-64px)] bg-[#fdfdfc] dark:bg-[#1a1b1e] text-[#1f2937] dark:text-[#e5e7eb] font-sans -mx-4 -my-4 sm:-mx-8 sm:-my-6">
      {/* Top Header / Model Selector */}
      <header className="flex items-center justify-between px-4 sm:px-8 py-4 border-b border-gray-200 dark:border-gray-800/50 bg-white/50 dark:bg-black/20 backdrop-blur-md sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <div className="relative group cursor-pointer flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
            <Sparkles className="w-4 h-4 text-brand-500" />
            <select
              value={selectedAgent}
              onChange={e => setSelectedAgent(e.target.value)}
              className="appearance-none bg-transparent font-medium text-sm text-gray-800 dark:text-gray-200 outline-none cursor-pointer pr-6"
            >
              {agents.length > 0 ? (
                agents.map(a => <option key={a.id} value={a.id} className="dark:bg-gray-800">{a.name}</option>)
              ) : (
                <option value="default" className="dark:bg-gray-800">Claude 3.5 Sonnet</option>
              )}
            </select>
            <ChevronDown className="w-4 h-4 text-gray-500 absolute right-2 pointer-events-none" />
          </div>
          {selectedAgentData && (
            <span className="hidden sm:inline-block px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-[10px] font-medium text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-700">
              {selectedAgentData.provider || 'Anthropic'}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {messages.length > 0 && (
            <button
              onClick={() => setMessages([])}
              className="px-3 py-1.5 flex items-center gap-2 text-xs font-medium text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset Chat
            </button>
          )}
        </div>
      </header>

      {/* Main Chat Area */}
      <main className="flex-1 overflow-y-auto px-4 sm:px-8 py-8 w-full">
        <div className="max-w-3xl mx-auto w-full space-y-8 pb-32">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full pt-16 sm:pt-32 text-center animate-in fade-in slide-in-from-bottom-4 duration-700">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-[#d97706] to-[#f59e0b] flex items-center justify-center mb-6 shadow-xl shadow-amber-500/20">
                <Sparkles className="w-8 h-8 text-white" />
              </div>
              <h1 className="text-3xl font-semibold tracking-tight text-gray-900 dark:text-white mb-3">
                How can I help you today?
              </h1>
              <p className="text-gray-500 dark:text-gray-400 max-w-md mx-auto text-sm">
                I can write code, analyze power systems, solve short circuits, and help with ETAP integrations.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-10 w-full max-w-2xl">
                {['Run a Newton-Raphson load flow', 'Calculate arc flash incident energy', 'Write a Python script for GIS', 'Explain protective relay coordination'].map(q => (
                  <button
                    key={q}
                    onClick={() => setInput(q)}
                    className="p-4 text-left text-sm text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700/50 hover:border-[#d97706] dark:hover:border-[#d97706] hover:shadow-md rounded-xl transition-all"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m) => (
              <motion.div
                key={m.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className={cn('flex flex-col', m.role === 'user' ? 'items-end' : 'items-start')}
              >
                {m.role === 'user' ? (
                  <div className="bg-[#f3f4f6] dark:bg-[#27272a] text-gray-900 dark:text-gray-100 px-5 py-3.5 rounded-2xl max-w-[85%] text-[15px] leading-relaxed shadow-sm">
                    {m.content}
                  </div>
                ) : (
                  <div className="flex gap-4 w-full">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-[#d97706] to-[#f59e0b] flex items-center justify-center shrink-0 shadow-md">
                      <Bot className="w-4 h-4 text-white" />
                    </div>
                    <div className="flex-1 space-y-4 max-w-[100%] overflow-hidden">
                      <div className="prose prose-sm sm:prose-base dark:prose-invert prose-p:leading-relaxed prose-pre:bg-[#1e1e1e] prose-pre:p-0 prose-pre:rounded-xl overflow-hidden max-w-none text-[15px]">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            code({ node, inline, className, children, ...props }: any) {
                              const match = /language-(\w+)/.exec(className || '')
                              return !inline && match ? (
                                <div className="rounded-xl overflow-hidden border border-gray-200 dark:border-gray-700 my-4 shadow-sm bg-[#1e1e1e]">
                                  <div className="flex items-center justify-between px-4 py-2 bg-[#2d2d2d] text-gray-400 text-xs font-mono border-b border-gray-700">
                                    <span>{match[1]}</span>
                                    <button
                                      onClick={() => handleCopy(m.id + children, String(children))}
                                      className="hover:text-white transition-colors flex items-center gap-1.5"
                                    >
                                      {copiedId === m.id + children ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
                                      {copiedId === m.id + children ? 'Copied' : 'Copy'}
                                    </button>
                                  </div>
                                  <pre
                                    className="p-4 overflow-x-auto text-sm font-mono text-gray-200 dark:text-gray-300"
                    {...props}
                  >
                    {String(children).replace(/\n$/, '')}
                  </pre>
                                </div>
                              ) : (
                                <code className={cn('bg-gray-100 dark:bg-gray-800 text-[#d97706] dark:text-[#fbbf24] px-1.5 py-0.5 rounded-md text-[0.9em] font-mono', className)} {...props}>
                                  {children}
                                </code>
                              )
                            }
                          }}
                        >
                          {m.content}
                        </ReactMarkdown>
                      </div>
                      <div className="flex items-center gap-2 pt-1 opacity-0 hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => handleCopy(m.id, m.content)}
                          className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors flex items-center gap-1.5 text-xs font-medium"
                        >
                          {copiedId === m.id ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                          {copiedId === m.id ? 'Copied!' : 'Copy text'}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </motion.div>
            ))
          )}

          {loading && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex gap-4 w-full"
            >
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-[#d97706] to-[#f59e0b] flex items-center justify-center shrink-0 shadow-md">
                <Bot className="w-4 h-4 text-white" />
              </div>
              <div className="flex-1 mt-1">
                <div className="flex flex-col gap-2">
                  <span className="text-xs font-medium text-amber-600 dark:text-amber-500 flex items-center gap-2">
                    <LoaderIcon className="w-3.5 h-3.5 animate-spin" />
                    Thinking...
                  </span>
                  <div className="flex flex-col gap-2 w-full max-w-sm opacity-50">
                    <div className="h-4 bg-gray-200 dark:bg-gray-800 rounded animate-pulse w-3/4"></div>
                    <div className="h-4 bg-gray-200 dark:bg-gray-800 rounded animate-pulse w-1/2"></div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
          <div ref={messagesEndRef} className="h-4" />
        </div>
      </main>

      {/* Bottom Input Area */}
      <div className="absolute bottom-0 left-0 w-full bg-gradient-to-t from-white via-white to-transparent dark:from-[#1a1b1e] dark:via-[#1a1b1e] dark:to-transparent pt-10 pb-6 px-4 sm:px-8 z-10">
        <div className="max-w-3xl mx-auto w-full relative">
          <form
            onSubmit={e => { e.preventDefault(); handleSend() }}
            className="relative flex flex-col bg-white dark:bg-[#27272a] border border-gray-300 dark:border-gray-700 rounded-2xl shadow-sm focus-within:border-[#d97706] focus-within:ring-1 focus-within:ring-[#d97706] transition-all overflow-hidden"
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
              placeholder="Message AI Assistant..."
              className="w-full max-h-48 min-h-[56px] px-4 pt-4 pb-12 bg-transparent text-[#1f2937] dark:text-[#e5e7eb] text-[15px] resize-none outline-none placeholder:text-gray-400 dark:placeholder:text-gray-500 leading-relaxed"
              rows={input.split('\n').length > 1 ? Math.min(input.split('\n').length, 8) : 1}
            />
            <div className="absolute bottom-2 right-2 flex items-center justify-between left-4">
              <div className="flex items-center gap-2 text-xs text-gray-400">
                <Cpu className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">ETAP Engineering Engine</span>
              </div>
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className={cn(
                  "p-2 rounded-xl transition-all duration-200 flex items-center justify-center",
                  loading || !input.trim()
                    ? "bg-gray-100 dark:bg-gray-800 text-gray-400 cursor-not-allowed"
                    : "bg-[#d97706] hover:bg-[#b45309] text-white shadow-md shadow-amber-500/20"
                )}
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </form>
          <div className="text-center mt-3">
            <span className="text-[10px] text-gray-400 dark:text-gray-500">
              AI Assistant can make mistakes. Please verify critical engineering decisions.
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

function LoaderIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  )
}
