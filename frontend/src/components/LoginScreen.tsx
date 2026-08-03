import { useState } from 'react'
import type { CSSProperties } from 'react'
import { useChatStore } from '../store/chatStore'

export function LoginScreen() {
  const { authLoading, authError, login, register } = useChatStore()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')

  const submit = async () => {
    if (!email.trim() || !password) return
    mode === 'login'
      ? await login(email.trim(), password)
      : await register(email.trim(), password, displayName.trim() || undefined)
  }

  return (
    <div style={s.wrap}>
      <div style={s.card}>
        <h1 style={s.title}>Interactive AI Chatbot</h1>
        <p style={s.subtitle}>Sign in to start chatting with your AI agent</p>

        <div style={s.tabs}>
          <button
            onClick={() => setMode('login')}
            style={{ ...s.tab, ...(mode === 'login' ? s.tabActive : null) }}
          >
            Login
          </button>
          <button
            onClick={() => setMode('register')}
            style={{ ...s.tab, ...(mode === 'register' ? s.tabActive : null) }}
          >
            Register
          </button>
        </div>

        {mode === 'register' && (
          <input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Display name"
            style={s.input}
          />
        )}
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
          style={s.input}
          onKeyDown={(e) => {
            if (e.key === 'Enter') void submit()
          }}
        />
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          type="password"
          style={s.input}
          onKeyDown={(e) => {
            if (e.key === 'Enter') void submit()
          }}
        />

        {authError && <div style={s.error}>{authError.slice(0, 200)}</div>}

        <button disabled={authLoading} onClick={() => void submit()} style={s.primaryBtn}>
          {authLoading ? 'Working...' : mode === 'login' ? 'Login' : 'Create account'}
        </button>
      </div>
    </div>
  )
}

const s: Record<string, CSSProperties> = {
  wrap: {
    width: '100%',
    height: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'radial-gradient(circle at top, #1e1b3a 0%, #0b0f19 70%)',
  },
  card: {
    width: 340,
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
    padding: '28px 26px',
    borderRadius: 14,
    border: '1px solid rgba(255,255,255,0.08)',
    background: 'rgba(15,23,42,0.75)',
    boxShadow: '0 20px 60px rgba(0,0,0,0.45)',
  },
  title: {
    margin: 0,
    fontSize: 18,
    color: '#f1f5f9',
    textAlign: 'center',
  },
  subtitle: {
    margin: '0 0 8px',
    fontSize: 12,
    color: '#94a3b8',
    textAlign: 'center',
  },
  tabs: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 6,
    marginBottom: 4,
  },
  tab: {
    border: '1px solid rgba(255,255,255,0.08)',
    background: 'rgba(255,255,255,0.04)',
    color: '#6b7280',
    borderRadius: 8,
    padding: '8px 10px',
    fontSize: 13,
    cursor: 'pointer',
  },
  tabActive: {
    color: '#e2e8f0',
    borderColor: 'rgba(99,102,241,0.45)',
    background: 'rgba(99,102,241,0.18)',
  },
  input: {
    width: '100%',
    boxSizing: 'border-box',
    border: '1px solid rgba(255,255,255,0.08)',
    background: 'rgba(15,23,42,0.5)',
    color: '#e2e8f0',
    borderRadius: 8,
    padding: '10px 12px',
    fontSize: 13,
    outline: 'none',
  },
  primaryBtn: {
    border: 'none',
    borderRadius: 8,
    padding: '10px 12px',
    background: '#6366f1',
    color: '#fff',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    marginTop: 4,
  },
  error: {
    color: '#fecaca',
    fontSize: 11,
    lineHeight: 1.4,
  },
}
