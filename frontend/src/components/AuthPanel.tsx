import { useState } from 'react'
import type { CSSProperties } from 'react'
import { useChatStore } from '../store/chatStore'

export function AuthPanel() {
  const {
    authUser,
    authLoading,
    authError,
    login,
    register,
    logout,
    refreshServerConversations,
  } = useChatStore()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')

  if (authUser) {
    return (
      <div style={s.panel}>
        <div style={s.userLine}>
          <span style={s.userDot} />
          <span style={s.userText}>{authUser.display_name || authUser.email || 'Signed in'}</span>
        </div>
        <div style={s.actions}>
          <button onClick={() => void refreshServerConversations()} style={s.secondaryBtn}>
            Sync
          </button>
          <button onClick={logout} style={s.secondaryBtn}>
            Logout
          </button>
        </div>
      </div>
    )
  }

  const submit = async () => {
    if (!email.trim() || !password) return
    const ok = mode === 'login'
      ? await login(email.trim(), password)
      : await register(email.trim(), password, displayName.trim() || undefined)
    if (ok) {
      setPassword('')
      setDisplayName('')
    }
  }

  return (
    <div style={s.panel}>
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
      {authError && <div style={s.error}>{authError.slice(0, 120)}</div>}
      <button disabled={authLoading} onClick={() => void submit()} style={s.primaryBtn}>
        {authLoading ? 'Working...' : mode === 'login' ? 'Login' : 'Create account'}
      </button>
    </div>
  )
}

const s: Record<string, CSSProperties> = {
  panel: {
    padding: '8px 10px',
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  tabs: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 4,
  },
  tab: {
    border: '1px solid rgba(255,255,255,0.08)',
    background: 'rgba(255,255,255,0.04)',
    color: '#6b7280',
    borderRadius: 6,
    padding: '5px 6px',
    fontSize: 11,
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
    color: '#d1d5db',
    borderRadius: 6,
    padding: '6px 8px',
    fontSize: 11,
    outline: 'none',
  },
  primaryBtn: {
    border: 'none',
    borderRadius: 6,
    padding: '6px 8px',
    background: '#6366f1',
    color: '#fff',
    fontSize: 11,
    cursor: 'pointer',
  },
  secondaryBtn: {
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 6,
    padding: '5px 7px',
    background: 'rgba(255,255,255,0.04)',
    color: '#9ca3af',
    fontSize: 11,
    cursor: 'pointer',
  },
  userLine: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    minWidth: 0,
  },
  userDot: {
    width: 7,
    height: 7,
    borderRadius: '50%',
    background: '#34d399',
    flexShrink: 0,
  },
  userText: {
    color: '#d1d5db',
    fontSize: 11,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  actions: {
    display: 'flex',
    gap: 6,
  },
  error: {
    color: '#fecaca',
    fontSize: 10,
    lineHeight: 1.35,
  },
}
