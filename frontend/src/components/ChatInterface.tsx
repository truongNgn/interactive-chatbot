/**
 * ChatInterface — Text input, message history, connection status indicator.
 * Mounted over the 3D canvas as a CSS overlay.
 */

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useChatStore } from '../store/chatStore'
import type { Emotion, LlmProvider } from '../types'

interface ChatInterfaceProps {
  sendMessage: (text: string) => void
  sendInterrupt: () => void
  sendSetModel: (provider: LlmProvider) => void
}

// ---------------------------------------------------------------------------
// Emotion badge colors
// ---------------------------------------------------------------------------
const EMOTION_COLORS: Record<Emotion, string> = {
  joy: '#fbbf24',
  sad: '#60a5fa',
  neutral: '#9ca3af',
  thinking: '#a78bfa',
  surprise: '#f472b6',
  anger: '#f87171',
}

const STATUS_COLORS = {
  connecting: '#fbbf24',
  open: '#34d399',
  closed: '#9ca3af',
  error: '#f87171',
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function ChatInterface({ sendMessage, sendInterrupt, sendSetModel }: ChatInterfaceProps) {
  const [inputText, setInputText] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const { messages, wsStatus, isAISpeaking, currentEmotion, llmProvider } = useChatStore()

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  const handleSend = useCallback(() => {
    const text = inputText.trim()
    if (!text || wsStatus !== 'open') return

    // Add user message to history immediately
    useChatStore.getState().addMessage({
      id: crypto.randomUUID(),
      role: 'user',
      text,
    })

    sendMessage(text)
    setInputText('')
  }, [inputText, wsStatus, sendMessage])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend],
  )

  const handleProviderChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      sendSetModel(e.target.value as LlmProvider)
    },
    [sendSetModel],
  )

  return (
    <div style={styles.overlay}>
      {/* Status bar */}
      <div style={styles.statusBar}>
        <span
          style={{
            ...styles.statusDot,
            background: STATUS_COLORS[wsStatus],
          }}
        />
        <span style={styles.statusText}>
          {wsStatus === 'open' ? 'Connected' : wsStatus}
        </span>

        {/* Model switcher */}
        <select
          value={llmProvider}
          onChange={handleProviderChange}
          disabled={wsStatus !== 'open'}
          style={styles.modelSelect}
          title="Switch LLM provider"
        >
          <option value="ollama">Ollama (Llama 3)</option>
          <option value="deepseek">DeepSeek v3</option>
        </select>

        {isAISpeaking && (
          <span
            style={{
              ...styles.emotionBadge,
              background: EMOTION_COLORS[currentEmotion],
            }}
          >
            {currentEmotion}
          </span>
        )}

        {isAISpeaking && (
          <button style={styles.interruptBtn} onClick={sendInterrupt}>
            ✕ Stop
          </button>
        )}
      </div>

      {/* Message history */}
      <div style={styles.messageList}>
        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              ...styles.messageBubble,
              alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
              background:
                msg.role === 'user'
                  ? 'rgba(79,70,229,0.75)'
                  : 'rgba(30,41,59,0.85)',
              borderLeft:
                msg.role === 'assistant' && msg.emotion
                  ? `3px solid ${EMOTION_COLORS[msg.emotion]}`
                  : 'none',
            }}
          >
            {msg.text}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div style={styles.inputRow}>
        <textarea
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            wsStatus === 'open' ? 'Type a message… (Enter to send)' : 'Connecting…'
          }
          disabled={wsStatus !== 'open'}
          rows={2}
          style={styles.textarea}
        />
        <button
          onClick={handleSend}
          disabled={wsStatus !== 'open' || !inputText.trim()}
          style={styles.sendBtn}
        >
          Send
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Inline styles
// ---------------------------------------------------------------------------
const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    display: 'flex',
    flexDirection: 'column',
    maxHeight: '55vh',
    padding: '0 16px 16px',
    gap: 8,
    pointerEvents: 'none',
  },
  statusBar: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    pointerEvents: 'auto',
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    flexShrink: 0,
  },
  statusText: {
    color: '#9ca3af',
    fontSize: 12,
    textTransform: 'capitalize',
  },
  modelSelect: {
    background: 'rgba(15,23,42,0.85)',
    color: '#e2e8f0',
    border: '1px solid rgba(255,255,255,0.15)',
    borderRadius: 6,
    padding: '3px 8px',
    fontSize: 12,
    cursor: 'pointer',
    outline: 'none',
    backdropFilter: 'blur(8px)',
  },
  emotionBadge: {
    fontSize: 11,
    fontWeight: 600,
    color: '#0a0a0f',
    padding: '2px 8px',
    borderRadius: 99,
    textTransform: 'capitalize',
  },
  interruptBtn: {
    marginLeft: 'auto',
    background: 'rgba(239,68,68,0.2)',
    color: '#f87171',
    border: '1px solid rgba(239,68,68,0.4)',
    borderRadius: 6,
    padding: '3px 10px',
    fontSize: 12,
    cursor: 'pointer',
  },
  messageList: {
    flex: 1,
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
    paddingRight: 4,
    pointerEvents: 'auto',
  },
  messageBubble: {
    maxWidth: '72%',
    padding: '8px 12px',
    borderRadius: 12,
    color: '#e2e8f0',
    fontSize: 14,
    lineHeight: 1.5,
    backdropFilter: 'blur(8px)',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  },
  inputRow: {
    display: 'flex',
    gap: 8,
    pointerEvents: 'auto',
  },
  textarea: {
    flex: 1,
    resize: 'none',
    background: 'rgba(15,23,42,0.85)',
    border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: 10,
    color: '#e2e8f0',
    fontSize: 14,
    padding: '10px 14px',
    outline: 'none',
    backdropFilter: 'blur(8px)',
    fontFamily: 'inherit',
  },
  sendBtn: {
    background: 'rgba(79,70,229,0.85)',
    color: '#fff',
    border: 'none',
    borderRadius: 10,
    padding: '0 20px',
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
}
