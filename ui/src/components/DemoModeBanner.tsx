/**
 * DemoModeBanner — visible when the API client is in demo mode.
 *
 * In demo mode, all API responses are canned data (DEMO_AGENTS, DEMO_STUDIES,
 * etc.) — there is NO real backend. This banner makes that fact obvious so
 * users don't mistake demo data for live production data.
 */

import { useEffect, useState } from 'react'
import { isDemoMode } from '../lib/api'

export function DemoModeBanner() {
  const [demo, setDemo] = useState<boolean>(isDemoMode())

  // Re-check on mount and on window focus (in case the API client flipped
  // into demo mode due to a transient network failure in development).
  useEffect(() => {
    const check = () => setDemo(isDemoMode())
    check()
    window.addEventListener('focus', check)
    return () => window.removeEventListener('focus', check)
  }, [])

  if (!demo) return null

  return (
    <div
      role="alert"
      aria-live="polite"
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 1000,
        width: '100%',
        background: 'linear-gradient(90deg, #f59e0b 0%, #dc2626 100%)',
        color: '#fff',
        padding: '8px 16px',
        fontSize: '13px',
        fontWeight: 600,
        textAlign: 'center',
        boxShadow: '0 2px 8px rgba(0,0,0,0.18)',
        letterSpacing: '0.2px',
      }}
    >
      ⚠ DEMO MODE — Backend غير متصل. البيانات المعروضة تجريبية ولن تُحفظ.
      <span style={{ opacity: 0.85, marginRight: '8px', fontWeight: 400 }}>  // NOSONAR — S6772: inline spacing; cosmetic
        {' '}.Configure VITE_API_URL to enable the live backend.
      </span>
    </div>
  )
}
