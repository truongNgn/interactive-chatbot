import { useCallback, useEffect, useRef } from 'react'
import { useChatStore } from '../store/chatStore'
import type { InterruptPayload, LlmProvider, ServerMessage, SetModelPayload, UserMessagePayload } from '../types'

const WS_URL = 'ws://localhost:8000/ws/chat'
const RECONNECT_DELAY_MS = 3000

export function useWebSocket(onClearQueue?: () => void) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isMounted = useRef(true)
  // Dùng ref để callback luôn là bản mới nhất mà không re-trigger useEffect/useCallback
  const onClearQueueRef = useRef(onClearQueue)
  onClearQueueRef.current = onClearQueue

  const { setWsStatus, addMessage, enqueueAudio, clearQueue, setLlmProvider } = useChatStore.getState()

  const connect = useCallback(() => {
    if (!isMounted.current) return

    setWsStatus('connecting')
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      if (!isMounted.current) return
      setWsStatus('open')
    }

    ws.onclose = () => {
      if (!isMounted.current) return
      setWsStatus('closed')
      // Auto-reconnect
      reconnectTimer.current = setTimeout(() => {
        if (isMounted.current) connect()
      }, RECONNECT_DELAY_MS)
    }

    ws.onerror = () => {
      if (!isMounted.current) return
      setWsStatus('error')
    }

    ws.onmessage = (event: MessageEvent<string>) => {
      let msg: ServerMessage
      try {
        msg = JSON.parse(event.data) as ServerMessage
      } catch {
        console.error('[WS] Failed to parse message:', event.data)
        return
      }

      switch (msg.type) {
        case 'audio_chunk':
          // Add to chat history (assistant turn, accumulate text)
          addMessage({
            id: crypto.randomUUID(),
            role: 'assistant',
            text: msg.text,
            emotion: msg.emotion,
          })
          // Feed audio pipeline
          enqueueAudio(msg)
          break

        case 'done':
          // Nothing to do here — audio queue drains itself
          break

        case 'clear_queue':
          clearQueue()
          onClearQueueRef.current?.()
          break

        case 'connected':
        case 'model_changed':
          setLlmProvider(msg.provider)
          break

        case 'error':
          console.error('[WS] Server error:', msg.message)
          addMessage({
            id: crypto.randomUUID(),
            role: 'assistant',
            text: `⚠ ${msg.message}`,
          })
          break
      }
    }
  }, [setWsStatus, addMessage, enqueueAudio, clearQueue, setLlmProvider])

  useEffect(() => {
    isMounted.current = true
    connect()

    return () => {
      isMounted.current = false
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      const ws = wsRef.current
      if (ws && ws.readyState !== WebSocket.CLOSED) ws.close()
    }
  }, [connect])

  const sendMessage = useCallback((text: string) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn('[WS] Not connected, cannot send message')
      return
    }
    const { userId, activeSessionId, ttsEnabled, routerEnabled, currentVoice } = useChatStore.getState()
    const payload: UserMessagePayload = {
      type: 'user_message',
      text,
      user_id: userId,
      session_id: activeSessionId,
      tts_enabled: ttsEnabled,
      router_enabled: routerEnabled,
      voice: currentVoice,
    }
    ws.send(JSON.stringify(payload))
  }, [])

  const sendInterrupt = useCallback(() => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    const payload: InterruptPayload = { type: 'interrupt' }
    ws.send(JSON.stringify(payload))
    clearQueue()
  }, [clearQueue])

  const sendSetModel = useCallback((provider: LlmProvider) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    const payload: SetModelPayload = { type: 'set_model', provider }
    ws.send(JSON.stringify(payload))
  }, [])

  return { sendMessage, sendInterrupt, sendSetModel }
}
