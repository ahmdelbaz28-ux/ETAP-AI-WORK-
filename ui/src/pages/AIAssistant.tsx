import { useState, useRef, useEffect } from 'react'
import { MdSmartToy, MdSend, MdPerson } from 'react-icons/md'
import { useNotify } from '../context/NotificationContext'
import { chatWithAgent, fetchAgents, type AgentMeta } from '../lib/api'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

export function AIAssistant() {
  const [agents, setAgents] = useState<AgentMeta[]>([])
  const [selectedAgent, setSelectedAgent] = useState<string>('power-system-coordinator-agent')
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const { notify } = useNotify()
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetchAgents().then(setAgents).catch(() => notify('error', 'Failed to load agents'))
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
      const reply = await chatWithAgent(selectedAgent,
        [...messages, userMsg].map(m => ({ role: m.role, content: m.content })))
      setMessages(prev => [...prev, { role: 'assistant', content: reply, timestamp: Date.now() }])
    } catch (err) {
      notify('error', `Chat failed: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4 h-[calc(100vh-120px)] flex flex-col">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl font-bold text-white">AI Assistant</h2>
        <select value={selectedAgent} onChange={e => setSelectedAgent(e.target.value)}
          className="px-3 py-1.5 bg-surface-800 border border-surface-600 rounded-lg text-white text-sm">
          {agents.map(a => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </select>
      </div>

      <div className="flex-1 bg-surface-800 rounded-xl border border-surface-700 p-4 overflow-y-auto space-y-4">
        {messages.length === 0 && (
          <div className="text-center py-12 text-surface-500">
            <MdSmartToy className="text-5xl mx-auto mb-3 opacity-30" />
            <p>Start a conversation with the {agents.find(a => a.id === selectedAgent)?.name || 'AI agent'}</p>
            <p className="text-xs mt-1">Ask about power systems, studies, or engineering analysis</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : ''}`}>
            {m.role === 'assistant' && <MdSmartToy className="text-brand-400 text-xl mt-0.5 shrink-0" />}
            <div className={`max-w-[80%] rounded-xl px-4 py-3 ${
              m.role === 'user' ? 'bg-brand-600 text-white' : 'bg-surface-700 text-surface-100'
            }`}>
              <p className="text-sm whitespace-pre-wrap">{m.content}</p>
              <p className="text-[10px] mt-1 opacity-50">
                {new Date(m.timestamp).toLocaleTimeString()}
              </p>
            </div>
            {m.role === 'user' && <MdPerson className="text-surface-400 text-xl mt-0.5 shrink-0" />}
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <MdSmartToy className="text-brand-400 text-xl mt-0.5" />
            <div className="bg-surface-700 rounded-xl px-4 py-3">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-surface-400 rounded-full animate-bounce" />
                <span className="w-2 h-2 bg-surface-400 rounded-full animate-bounce [animation-delay:0.1s]" />
                <span className="w-2 h-2 bg-surface-400 rounded-full animate-bounce [animation-delay:0.2s]" />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={e => { e.preventDefault(); handleSend() }}
        className="flex gap-2 bg-surface-800 rounded-xl border border-surface-700 p-2">
        <input value={input} onChange={e => setInput(e.target.value)} disabled={loading}
          placeholder="Ask about power systems engineering..."
          className="flex-1 px-3 py-2 bg-transparent text-white text-sm outline-none placeholder:text-surface-500" />
        <button type="submit" disabled={loading || !input.trim()}
          className="p-2 bg-brand-600 hover:bg-brand-500 disabled:opacity-40 text-white rounded-lg transition-colors">
          <MdSend />
        </button>
      </form>
    </div>
  )
}
