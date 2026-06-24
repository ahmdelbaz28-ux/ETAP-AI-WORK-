import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react'

interface Notification {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  message: string
}

interface NotificationContextType {
  notifications: Notification[]
  notify: (type: Notification['type'], message: string) => void
  dismiss: (id: string) => void
}

const NotificationContext = createContext<NotificationContextType>({
  notifications: [],
  notify: () => {},
  dismiss: () => {},
})

const iconMap = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
}

const colorMap = {
  success: 'bg-green-600/90 border-green-400/30',
  error: 'bg-red-600/90 border-red-400/30',
  warning: 'bg-amber-600/90 border-amber-400/30',
  info: 'bg-brand-600/90 border-brand-400/30',
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([])

  const notify = useCallback((type: Notification['type'], message: string) => {
    const id = crypto.randomUUID()
    setNotifications(prev => [...prev, { id, type, message }])
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id))
    }, 5000)
  }, [])

  const dismiss = useCallback((id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id))
  }, [])

  return (
    <NotificationContext.Provider value={{ notifications, notify, dismiss }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[var(--z-notification)] flex flex-col gap-2 max-w-sm pointer-events-none">
        <AnimatePresence mode="popLayout">
          {notifications.map(n => {
            const Icon = iconMap[n.type]
            return (
              <motion.div
                key={n.id}
                layout
                initial={{ opacity: 0, x: 120, scale: 0.9 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: 120, scale: 0.9 }}
                transition={{ type: 'spring', damping: 20, stiffness: 300 }}
                onClick={() => dismiss(n.id)}
                className={`pointer-events-auto px-4 py-3 rounded-xl shadow-lg text-sm font-medium flex items-center gap-3 cursor-pointer border backdrop-blur-md ${colorMap[n.type]}`}
              >
                <Icon className="w-5 h-5 shrink-0 text-white" />
                <span className="flex-1 text-white">{n.message}</span>
                <X className="w-4 h-4 text-white/60 hover:text-white transition-colors shrink-0" />
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
    </NotificationContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useNotify() { return useContext(NotificationContext) }
