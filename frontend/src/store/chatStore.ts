import { create } from 'zustand'
import type { AudioChunkPayload, ChatMessage, Emotion, LlmProvider, Project, Session, WsStatus } from '../types'

const MAX_SESSIONS = 100 // Increased for better project management
const SESSIONS_KEY = 'chatbot_sessions'
const PROJECTS_KEY = 'chatbot_projects'
const TTS_KEY = 'chatbot_tts_enabled'
const ROUTER_KEY = 'chatbot_router_enabled'

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

  // User identity
  userId: string

  // Actions
  setWsStatus: (status: WsStatus) => void
  addMessage: (msg: ChatMessage) => void
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
  currentModel: '/models/fashion_girl_asian_girl.glb',
  currentVoice: 'NT_Voice_full.wav',
  llmProvider: 'ollama',
  ttsEnabled: loadTtsEnabled(),
  routerEnabled: loadRouterEnabled(),
  userId: (() => {
    let id = localStorage.getItem('chat_user_id')
    if (!id) { id = crypto.randomUUID(); localStorage.setItem('chat_user_id', id) }
    return id
  })(),

  setWsStatus: (status) => set({ wsStatus: status }),

  addMessage: (msg) => {
    set((state) => ({ messages: [...state.messages, msg] }))
    // Auto-save after adding message
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
