<<<<<<< HEAD
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { fetchHealth, type HealthResponse } from '../../lib/api';
import { StatusIndicator } from '../ui/Visual';

export function StatusBar() {
  const { i18n } = useTranslation();
  const lang = (i18n.language === 'ar' ? 'ar' : 'en') as 'en' | 'ar';
  const [status, setStatus] = useState<'online' | 'offline' | 'checking'>('checking');
  const [latency, setLatency] = useState<number | null>(null);
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const check = async () => {
      const start = Date.now();
      try {
        const h: HealthResponse = await fetchHealth();
        setLatency(Date.now() - start);
        setStatus(h.ok ? 'online' : 'offline');
      } catch {
        setStatus('offline');
        setLatency(null);
      }
    };
    check();
    const interval = setInterval(check, 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
=======
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Wifi, WifiOff, Clock } from 'lucide-react'
import { fetchHealth, type HealthResponse } from '../../lib/api'
import { cn } from '../../utils/helpers'
import { StatusIndicator } from '../ui/Visual'

export function StatusBar() {
  const { i18n } = useTranslation()
  const lang = (i18n.language === 'ar' ? 'ar' : 'en') as 'en' | 'ar'
  const [status, setStatus] = useState<'online' | 'offline' | 'checking'>('checking')
  const [latency, setLatency] = useState<number | null>(null)
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const check = async () => {
      const start = Date.now()
      try {
        const h: HealthResponse = await fetchHealth()
        setLatency(Date.now() - start)
        setStatus(h.ok ? 'online' : 'offline')
      } catch {
        setStatus('offline')
        setLatency(null)
      }
    }
    check()
    const interval = setInterval(check, 15000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])
>>>>>>> origin/fix/scenario-tests-properly

  return (
    <div className="h-6 flex items-center justify-between px-4 bg-[var(--bg-secondary)] border-t border-[var(--border-primary)] text-[10px] text-[var(--text-muted)] shrink-0">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <StatusIndicator
<<<<<<< HEAD
            status={status === 'checking' ? 'loading' : status === 'online' ? 'online' : 'offline'} // NOSONAR — S3358: nested ternary; refactor to named variable (tech debt)
=======
            status={status === 'checking' ? 'loading' : status === 'online' ? 'online' : 'offline'}
>>>>>>> origin/fix/scenario-tests-properly
            size="sm"
            showLabel={false}
          />
          <span>{lang === 'ar' ? 'الخدمة' : 'Service'}</span>
<<<<<<< HEAD
          {latency !== null && <span className="text-[var(--text-muted)]">({latency}ms)</span>}
=======
          {latency !== null && (
            <span className="text-[var(--text-muted)]">({latency}ms)</span>
          )}
>>>>>>> origin/fix/scenario-tests-properly
        </div>
      </div>

      <div className="flex items-center gap-4">
        <span className="mono-engineering">
<<<<<<< HEAD
          {time.toLocaleTimeString(lang === 'ar' ? 'ar-EG' : 'en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          })}
=======
          {time.toLocaleTimeString(lang === 'ar' ? 'ar-EG' : 'en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
>>>>>>> origin/fix/scenario-tests-properly
        </span>
        <span>Ahmed etap v1.0.0</span>
      </div>
    </div>
<<<<<<< HEAD
  );
=======
  )
>>>>>>> origin/fix/scenario-tests-properly
}
