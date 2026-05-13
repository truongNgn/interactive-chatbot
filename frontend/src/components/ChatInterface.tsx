/**
 * ChatInterface — message history + input bar.
 * Status bar và LLM dropdown đã được chuyển sang Sidebar.
 */

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useChatStore } from '../store/chatStore'
import type { Emotion } from '../types'

interface ChatInterfaceProps {
  sendMessage: (text: string) => void
  sendInterrupt: () => void
}

const EMOTION_COLORS: Record<Emotion, string> = {
  joy: '#fbbf24',
  sad: '#60a5fa',
  neutral: '#9ca3af',
  thinking: '#a78bfa',
  surprise: '#f472b6',
  anger: '#f87171',
}

export function ChatInterface({ sendMessage, sendInterrupt }: ChatInterfaceProps) {
  const [inputText, setInputText] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const { messages, wsStatus, isAISpeaking, currentEmotion, ttsEnabled } = useChatStore()

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  const handleSend = useCallback(() => {
    const text = inputText.trim()
    if (!text || wsStatus !== 'open') return
    useChatStore.getState().addMessage({ id: crypto.randomUUID(), role: 'user', text })
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

  const isEmpty = messages.length === 0

  return (
    <div style={s.container}>
      {/* ── Message list / Empty state ─────────────────── */}
      <div style={s.messageList}>
        {isEmpty ? (
          <div style={s.emptyState}>
            <div style={s.emptyIcon}>◈</div>
            <div style={s.emptyTitle}>AI Chatbot</div>
            <div style={s.emptySubtitle}>Xin chào! Tôi có thể giúp gì cho bạn hôm nay?</div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                ...s.messageBubble,
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                background:
                  msg.role === 'user'
                    ? 'rgba(79,70,229,0.72)'
                    : 'rgba(22,30,46,0.82)',
                borderLeft:
                  msg.role === 'assistant' && msg.emotion
                    ? `3px solid ${EMOTION_COLORS[msg.emotion]}`
                    : msg.role === 'assistant'
                      ? '3px solid rgba(255,255,255,0.08)'
                      : 'none',
              }}
            >
              {msg.text}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* ── TTS-off badge ───────────────────────────────── */}
      {!ttsEnabled && (
        <div style={s.ttsBadge}>⚡ Text only — phản hồi nhanh hơn</div>
      )}

      {/* ── Input area ──────────────────────────────────── */}
      <div style={s.inputWrap}>
        <div style={s.inputBox}>
          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={wsStatus === 'open' ? 'Message AI…' : 'Đang kết nối…'}
            disabled={wsStatus !== 'open'}
            rows={2}
            style={s.textarea}
          />
          <div style={s.inputActions}>
            {isAISpeaking && (
              <button onClick={sendInterrupt} style={s.stopBtn} title="Dừng">
                ◼
              </button>
            )}
            <button
              onClick={handleSend}
              disabled={wsStatus !== 'open' || !inputText.trim()}
              style={{
                ...s.sendBtn,
                opacity: wsStatus !== 'open' || !inputText.trim() ? 0.4 : 1,
              }}
              title="Gửi (Enter)"
            >
              ▶
            </button>
          </div>
        </div>

        {/* Emotion badge khi AI đang nói */}
        {isAISpeaking && (
          <div style={{ ...s.emotionBadge, background: EMOTION_COLORS[currentEmotion] }}>
            {currentEmotion}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const s: Record<string, React.CSSProperties> = {
  container: {
    flex: 1,
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    background: 'rgba(0,0,0,0.42)',
    backdropFilter: 'blur(6px)',
    overflow: 'hidden',
  },
  messageList: {
    flex: 1,
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    padding: '20px 20px 8px',
  },
  emptyState: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    margin: 'auto',
    paddingTop: '20vh',
    opacity: 0.55,
  },
  emptyIcon: {
    fontSize: 36,
    color: '#6366f1',
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: 600,
    color: '#e2e8f0',
    fontFamily: "'JetBrains Mono', monospace",
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#6b7280',
    textAlign: 'center',
    maxWidth: 320,
    lineHeight: 1.6,
  },
  messageBubble: {
    maxWidth: '72%',
    padding: '9px 13px',
    borderRadius: 12,
    color: '#e2e8f0',
    fontSize: 14,
    lineHeight: 1.55,
    backdropFilter: 'blur(6px)',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  },
  ttsBadge: {
    alignSelf: 'center',
    fontSize: 11,
    color: '#fbbf24',
    background: 'rgba(251,191,36,0.1)',
    border: '1px solid rgba(251,191,36,0.2)',
    borderRadius: 99,
    padding: '3px 10px',
    marginBottom: 4,
  },
  inputWrap: {
    padding: '0 16px 14px',
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  inputBox: {
    display: 'flex',
    alignItems: 'flex-end',
    gap: 8,
    background: 'rgba(15,23,42,0.75)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 14,
    padding: '8px 10px 8px 14px',
    backdropFilter: 'blur(8px)',
  },
  textarea: {
    flex: 1,
    resize: 'none',
    background: 'transparent',
    border: 'none',
    outline: 'none',
    color: '#e2e8f0',
    fontSize: 14,
    lineHeight: 1.5,
    fontFamily: 'inherit',
    paddingTop: 2,
  },
  inputActions: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    paddingBottom: 2,
  },
  stopBtn: {
    background: 'rgba(239,68,68,0.18)',
    border: '1px solid rgba(239,68,68,0.3)',
    color: '#f87171',
    borderRadius: 8,
    width: 32,
    height: 32,
    fontSize: 11,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtn: {
    background: 'rgba(99,102,241,0.85)',
    border: 'none',
    color: '#fff',
    borderRadius: 8,
    width: 32,
    height: 32,
    fontSize: 13,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'opacity 0.15s',
  },
  emotionBadge: {
    alignSelf: 'flex-end',
    fontSize: 11,
    fontWeight: 600,
    color: '#0a0a0f',
    padding: '2px 8px',
    borderRadius: 99,
    textTransform: 'capitalize',
  },
}
