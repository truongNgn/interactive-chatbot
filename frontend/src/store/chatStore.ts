import { create } from 'zustand'
import type { AudioChunkPayload, ChatMessage, Emotion, WsStatus } from '../types'

interface ChatState {
  // WebSocket
  wsStatus: WsStatus

  // Chat history
  messages: ChatMessage[]

  // Audio pipeline
  audioQueue: AudioChunkPayload[]
  isAISpeaking: boolean

  // Current avatar state
  currentEmotion: Emotion

  // Actions
  setWsStatus: (status: WsStatus) => void
  addMessage: (msg: ChatMessage) => void
  enqueueAudio: (chunk: AudioChunkPayload) => void
  dequeueAudio: () => AudioChunkPayload | undefined
  clearQueue: () => void
  setIsAISpeaking: (val: boolean) => void
  setCurrentEmotion: (emotion: Emotion) => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  wsStatus: 'connecting',
  messages: [],
  audioQueue: [],
  isAISpeaking: false,
  currentEmotion: 'neutral',

  setWsStatus: (status) => set({ wsStatus: status }),

  addMessage: (msg) =>
    set((state) => ({ messages: [...state.messages, msg] })),

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
}))
