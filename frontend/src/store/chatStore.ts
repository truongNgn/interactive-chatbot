import { create } from 'zustand'
import { API_BASE_URL } from '../config/backend'
import type { AudioChunkPayload, AuthUser, ChatMessage, ConversationDetail, ConversationSummary, Emotion, LlmProvider, Project, Session, WarmupStatus, WsStatus } from '../types'

const MAX_SESSIONS = 100 // Increased for better project management
const SESSIONS_KEY = 'chatbot_sessions'
const PROJECTS_KEY = 'chatbot_projects'
const TTS_KEY = 'chatbot_tts_enabled'
const ROUTER_KEY = 'chatbot_router_enabled'
const AUTO_SEND_VOICE_KEY = 'chatbot_auto_send_voice_transcript'
const AUTH_TOKEN_KEY = 'chatbot_auth_token'
const AUTH_USER_KEY = 'chatbot_auth_user'
function generateTitle(text: string): string {
  const words = text.trim().split(/\s+/).slice(0, 8).join(' ')
  return words.length > 0 ? words : 'New Chat'
}

function loadSessions(): Session[] {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY)
    return raw ? (JSON.parse(raw) as Session[]) : []
  } catch {
    return []
  }
}

function saveSessions(sessions: Session[]): void {
  try {
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions))
  } catch {}
}

function loadProjects(): Project[] {
  try {
    const raw = localStorage.getItem(PROJECTS_KEY)
    return raw ? (JSON.parse(raw) as Project[]) : []
  } catch {
    return []
  }
}

function saveProjects(projects: Project[]): void {
  try {
    localStorage.setItem(PROJECTS_KEY, JSON.stringify(projects))
  } catch {}
}

function loadTtsEnabled(): boolean {
  try {
    const raw = localStorage.getItem(TTS_KEY)
    return raw === null ? true : raw === 'true'
  } catch {
    return true
  }
}

function loadRouterEnabled(): boolean {
  try {
    const raw = localStorage.getItem(ROUTER_KEY)
    return raw === null ? true : raw === 'true'
  } catch {
    return true
  }
}

function loadAutoSendVoiceTranscript(): boolean {
  try {
    const raw = localStorage.getItem(AUTO_SEND_VOICE_KEY)
    return raw === null ? true : raw === 'true'
  } catch {
    return true
  }
}

function loadAuthToken(): string {
  try {
    return localStorage.getItem(AUTH_TOKEN_KEY) ?? ''
  } catch {
    return ''
  }
}

function loadAuthUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(AUTH_USER_KEY)
    return raw ? (JSON.parse(raw) as AuthUser) : null
  } catch {
    return null
  }
}

function saveAuth(token: string, user: AuthUser | null): void {
  try {
    if (token) localStorage.setItem(AUTH_TOKEN_KEY, token)
    else localStorage.removeItem(AUTH_TOKEN_KEY)
    if (user) localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user))
    else localStorage.removeItem(AUTH_USER_KEY)
  } catch {}
}

function mapConversation(detail: ConversationDetail): Session {
  return {
    id: detail.conversation.id,
    title: detail.conversation.title || 'New Chat',
    createdAt: detail.conversation.created_at * 1000,
    messages: detail.messages.map((message) => ({
      id: String(message.id),
      role: message.role === 'human' ? 'user' : 'assistant',
      text: message.content,
      emotion: message.emotion ?? undefined,
      turnId: message.turn_id ?? undefined,
    })),
  }
}

interface ChatState {
  // WebSocket
  wsStatus: WsStatus

  // Chat history (active session)
  messages: ChatMessage[]

  // Session & Project management
  sessions: Session[]
  projects: Project[]
  activeSessionId: string

  // Audio pipeline
  audioQueue: AudioChunkPayload[]
  isAISpeaking: boolean

  // Avatar & Voice state
  currentEmotion: Emotion
  currentModel: string
  currentVoice: string

  // LLM provider
  llmProvider: LlmProvider

  // TTS toggle
  ttsEnabled: boolean

  // Router toggle
  routerEnabled: boolean

  // Voice input
  autoSendVoiceTranscript: boolean

  // Backend warmup
  warmupStatus: WarmupStatus | null

  // User identity
  userId: string
  authToken: string
  authUser: AuthUser | null
  authLoading: boolean
  authError: string | null

  // Actions
  setWsStatus: (status: WsStatus) => void
  addMessage: (msg: ChatMessage) => void
  setMessageFeedback: (messageId: string, rating: 'up' | 'down') => void
  enqueueAudio: (chunk: AudioChunkPayload) => void
  dequeueAudio: () => AudioChunkPayload | undefined
  clearQueue: () => void
  setIsAISpeaking: (val: boolean) => void
  setCurrentEmotion: (emotion: Emotion) => void
  setCurrentModel: (model: string) => void
  setCurrentVoice: (voice: string) => void
  setLlmProvider: (provider: LlmProvider) => void
  setTtsEnabled: (val: boolean) => void
  setRouterEnabled: (val: boolean) => void
  setAutoSendVoiceTranscript: (val: boolean) => void
  setWarmupStatus: (status: WarmupStatus | null) => void
  setAuth: (token: string, user: AuthUser) => void
  logout: () => void
  login: (email: string, password: string) => Promise<boolean>
  loginGoogle: (credential: string) => Promise<boolean>
  register: (email: string, password: string, displayName?: string) => Promise<boolean>
  refreshServerConversations: () => Promise<void>

  // Session actions
  createNewSession: () => string    // returns new sessionId
  switchSession: (id: string) => void
  saveCurrentSession: () => void
  deleteSession: (id: string) => void
  renameSession: (id: string, title: string) => void
  moveSessionToProject: (sessionId: string, projectId: string | null) => void

  // Project actions
  createProject: (name: string) => void
  deleteProject: (id: string) => void
  renameProject: (id: string, name: string) => void
}

const initialSessions = loadSessions()
const initialProjects = loadProjects()
const initialSessionId = initialSessions.length > 0
  ? initialSessions[0].id
  : crypto.randomUUID()

const initialMessages = initialSessions.length > 0
  ? initialSessions[0].messages
  : []

export const useChatStore = create<ChatState>((set, get) => ({
  wsStatus: 'connecting',
  messages: initialMessages,
  sessions: initialSessions,
  projects: initialProjects,
  activeSessionId: initialSessionId,
  audioQueue: [],
  isAISpeaking: false,
  currentEmotion: 'neutral',
  currentModel: '',
  currentVoice: '',
  llmProvider: 'ollama',
  ttsEnabled: loadTtsEnabled(),
  routerEnabled: loadRouterEnabled(),
  autoSendVoiceTranscript: loadAutoSendVoiceTranscript(),
  warmupStatus: null,
  userId: loadAuthUser()?.id ?? '',
  authToken: loadAuthToken(),
  authUser: loadAuthUser(),
  authLoading: false,
  authError: null,

  setWsStatus: (status) => set({ wsStatus: status }),

  addMessage: (msg) => {
    set((state) => ({ messages: [...state.messages, msg] }))
    // Auto-save after adding message
    get().saveCurrentSession()
  },

  setMessageFeedback: (messageId, rating) => {
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === messageId ? { ...msg, feedbackRating: rating } : msg
      ),
    }))
    get().saveCurrentSession()
  },

  enqueueAudio: (chunk) =>
    set((state) => ({ audioQueue: [...state.audioQueue, chunk] })),

  dequeueAudio: () => {
    const queue = get().audioQueue
    if (queue.length === 0) return undefined
    const [head, ...rest] = queue
    set({ audioQueue: rest })
    return head
  },

  clearQueue: () =>
    set({ audioQueue: [], isAISpeaking: false, currentEmotion: 'neutral' }),

  setIsAISpeaking: (val) => set({ isAISpeaking: val }),

  setCurrentEmotion: (emotion) => set({ currentEmotion: emotion }),

  setCurrentModel: (model) => set({ currentModel: model }),

  setCurrentVoice: (voice) => set({ currentVoice: voice }),

  setLlmProvider: (provider) => set({ llmProvider: provider }),

  setTtsEnabled: (val) => {
    set({ ttsEnabled: val })
    try { localStorage.setItem(TTS_KEY, String(val)) } catch {}
  },

  setRouterEnabled: (val) => {
    set({ routerEnabled: val })
    try { localStorage.setItem(ROUTER_KEY, String(val)) } catch {}
  },

  setAutoSendVoiceTranscript: (val) => {
    set({ autoSendVoiceTranscript: val })
    try { localStorage.setItem(AUTO_SEND_VOICE_KEY, String(val)) } catch {}
  },

  setWarmupStatus: (status) => set({ warmupStatus: status }),

  setAuth: (token, user) => {
    saveAuth(token, user)
    set({ authToken: token, authUser: user, userId: user.id, authError: null })
  },

  logout: () => {
    saveAuth('', null)
    set({
      authToken: '',
      authUser: null,
      userId: '',
      messages: [],
      sessions: [],
      activeSessionId: crypto.randomUUID(),
      authError: null,
    })
    saveSessions([])
  },

  login: async (email, password) => {
    set({ authLoading: true, authError: null })
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (!response.ok) throw new Error(await response.text())
      const payload = await response.json()
      get().setAuth(payload.access_token, payload.user)
      await get().refreshServerConversations()
      return true
    } catch (error) {
      set({ authError: error instanceof Error ? error.message : 'Login failed' })
      return false
    } finally {
      set({ authLoading: false })
    }
  },

  loginGoogle: async (credential) => {
    set({ authLoading: true, authError: null })
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/google`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credential }),
      })
      if (!response.ok) throw new Error(await response.text())
      const payload = await response.json()
      get().setAuth(payload.access_token, payload.user)
      await get().refreshServerConversations()
      return true
    } catch (error) {
      set({ authError: error instanceof Error ? error.message : 'Google login failed' })
      return false
    } finally {
      set({ authLoading: false })
    }
  },

  register: async (email, password, displayName) => {
    set({ authLoading: true, authError: null })
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, display_name: displayName || null }),
      })
      if (!response.ok) throw new Error(await response.text())
      const payload = await response.json()
      get().setAuth(payload.access_token, payload.user)
      await get().refreshServerConversations()
      return true
    } catch (error) {
      set({ authError: error instanceof Error ? error.message : 'Registration failed' })
      return false
    } finally {
      set({ authLoading: false })
    }
  },

  refreshServerConversations: async () => {
    const token = get().authToken
    if (!token) return
    const headers = { Authorization: `Bearer ${token}` }
    const response = await fetch(`${API_BASE_URL}/api/conversations`, { headers })
    if (!response.ok) return
    const payload = (await response.json()) as { conversations: ConversationSummary[] }
    const details = await Promise.all(
      payload.conversations.map(async (conversation) => {
        const detailResponse = await fetch(`${API_BASE_URL}/api/conversations/${conversation.id}`, { headers })
        if (!detailResponse.ok) return null
        return (await detailResponse.json()) as ConversationDetail
      }),
    )
    const serverSessions = details
      .filter((item): item is ConversationDetail => item !== null)
      .map(mapConversation)
      .sort((a, b) => b.createdAt - a.createdAt)
    saveSessions(serverSessions)
    const active = serverSessions[0]
    set({
      sessions: serverSessions,
      activeSessionId: active?.id ?? get().activeSessionId,
      messages: active?.messages ?? get().messages,
    })
  },

  createNewSession: () => {
    const newId = crypto.randomUUID()
    const newSession: Session = {
      id: newId,
      title: 'New Chat',
      createdAt: Date.now(),
      messages: [],
    }
    set((state) => {
      const updated = [newSession, ...state.sessions].slice(0, MAX_SESSIONS)
      saveSessions(updated)
      return { sessions: updated, activeSessionId: newId, messages: [] }
    })
    return newId
  },

  switchSession: (id) => {
    // Save current session first
    get().saveCurrentSession()
    const session = get().sessions.find((s) => s.id === id)
    if (!session) return
    set({ activeSessionId: id, messages: session.messages })
  },

  saveCurrentSession: () => {
    const { activeSessionId, messages, sessions } = get()
    if (messages.length === 0) return

    const title = generateTitle(
      messages.find((m) => m.role === 'user')?.text ?? 'New Chat'
    )

    const updated = sessions.map((s) =>
      s.id === activeSessionId ? { ...s, title, messages } : s
    )

    // If session doesn't exist yet (e.g. very first message), add it
    const exists = sessions.some((s) => s.id === activeSessionId)
    const final = exists
      ? updated
      : [{ id: activeSessionId, title, createdAt: Date.now(), messages }, ...updated].slice(0, MAX_SESSIONS)

    saveSessions(final)
    set({ sessions: final })
  },

  deleteSession: (id) => {
    set((state) => {
      const filtered = state.sessions.filter((s) => s.id !== id)
      saveSessions(filtered)

      // If deleting active session, switch to the most recent remaining one
      if (state.activeSessionId === id) {
        if (filtered.length > 0) {
          return { sessions: filtered, activeSessionId: filtered[0].id, messages: filtered[0].messages }
        }
        // No sessions left — create clean state
        const newId = crypto.randomUUID()
        return { sessions: filtered, activeSessionId: newId, messages: [] }
      }
      return { sessions: filtered }
    })
  },

  renameSession: (id, title) => {
    set((state) => {
      const updated = state.sessions.map((s) =>
        s.id === id ? { ...s, title } : s
      )
      saveSessions(updated)
      return { sessions: updated }
    })
  },

  moveSessionToProject: (sessionId, projectId) => {
    set((state) => {
      const updated = state.sessions.map((s) =>
        s.id === sessionId ? { ...s, projectId: projectId || undefined } : s
      )
      saveSessions(updated)
      return { sessions: updated }
    })
  },

  createProject: (name) => {
    const newProject: Project = {
      id: crypto.randomUUID(),
      name,
      createdAt: Date.now(),
    }
    set((state) => {
      const updated = [newProject, ...state.projects]
      saveProjects(updated)
      return { projects: updated }
    })
  },

  deleteProject: (id) => {
    set((state) => {
      const filteredProjects = state.projects.filter((p) => p.id !== id)
      // Unassign sessions from this project
      const updatedSessions = state.sessions.map((s) =>
        s.projectId === id ? { ...s, projectId: undefined } : s
      )
      saveProjects(filteredProjects)
      saveSessions(updatedSessions)
      return { projects: filteredProjects, sessions: updatedSessions }
    })
  },

  renameProject: (id, name) => {
    set((state) => {
      const updated = state.projects.map((p) =>
        p.id === id ? { ...p, name } : p
      )
      saveProjects(updated)
      return { projects: updated }
    })
  },
}))
