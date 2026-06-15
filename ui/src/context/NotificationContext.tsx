import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

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
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
        {notifications.map(n => (
          <div
            key={n.id}
            className={`px-4 py-3 rounded-lg shadow-lg text-sm font-medium flex items-center gap-2 cursor-pointer animate-[slideIn_0.3s_ease-out] ${
              n.type === 'success' ? 'bg-green-600 text-white' :
              n.type === 'error' ? 'bg-red-600 text-white' :
              n.type === 'warning' ? 'bg-amber-600 text-white' :
              'bg-brand-600 text-white'
            }`}
            onClick={() => dismiss(n.id)}
          >
            <span className="flex-1">{n.message}</span>
            <span className="opacity-60 text-xs">✕</span>
          </div>
        ))}
      </div>
    </NotificationContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useNotify() { return useContext(NotificationContext) }
