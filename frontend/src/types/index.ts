// Mirrors backend app/models.py

export type Emotion = 'joy' | 'sad' | 'neutral' | 'thinking' | 'surprise' | 'anger'

// Server → Client
export interface AudioChunkPayload {
  type: 'audio_chunk'
  text: string
  emotion: Emotion
  audio_base64: string
  duration_ms: number
  visemes: VisemeKeyframe[]
}

export interface VisemeKeyframe {
  start: number  // seconds from audio start
  end: number    // seconds from audio start
  value: string  // Rhubarb phoneme: "A" | "B" | "C" | "D" | "E" | "F" | "G" | "H" | "X"
}

export interface DonePayload {
  type: 'done'
}

export interface ErrorPayload {
  type: 'error'
  message: string
}

export interface ClearQueuePayload {
  type: 'clear_queue'
}

export type ServerMessage =
  | AudioChunkPayload
  | DonePayload
  | ErrorPayload
  | ClearQueuePayload
  | ModelChangedPayload
  | ConnectedPayload

// Session management
export interface Session {
  id: string           // UUID
  title: string        // ~8 từ đầu của user message đầu tiên
  createdAt: number    // Date.now() timestamp
  messages: ChatMessage[]
  projectId?: string   // ID của project chứa session này
}

export interface Project {
  id: string
  name: string
  createdAt: number
}

// Client → Server
export interface UserMessagePayload {
  type: 'user_message'
  text: string
  user_id?: string
  session_id?: string
  tts_enabled?: boolean
  router_enabled?: boolean
  voice?: string
}

export interface InterruptPayload {
  type: 'interrupt'
}

// Chat history
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  emotion?: Emotion
}

export type WsStatus = 'connecting' | 'open' | 'closed' | 'error'

export type LlmProvider = 'ollama' | 'deepseek' | 'qwen'

export interface SetModelPayload {
  type: 'set_model'
  provider: LlmProvider
}

export interface ModelChangedPayload {
  type: 'model_changed'
  provider: LlmProvider
}

export interface ConnectedPayload {
  type: 'connected'
  provider: LlmProvider
}
