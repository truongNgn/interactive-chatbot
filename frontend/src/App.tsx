import { useCallback, useEffect } from 'react'
import { Scene } from './components/Scene'
import { ChatInterface } from './components/ChatInterface'
import { useWebSocket } from './hooks/useWebSocket'
import { useAudioQueue } from './hooks/useAudioQueue'
import { useVAD } from './hooks/useVAD'
import { useChatStore } from './store/chatStore'

export function App() {
  const { sendMessage, sendInterrupt, sendSetModel } = useWebSocket()
  const { stopPlayback } = useAudioQueue()

  const isAISpeaking = useCallback(
    () => useChatStore.getState().isAISpeaking,
    [],
  )

  const handleVoiceDetected = useCallback(() => {
    stopPlayback()
    sendInterrupt()
  }, [stopPlayback, sendInterrupt])

  const { startListening, stopListening } = useVAD({
    onVoiceDetected: handleVoiceDetected,
    isAISpeaking,
  })

  // Bắt đầu lắng nghe mic khi component mount
  useEffect(() => {
    startListening()
    return () => stopListening()
  }, [startListening, stopListening])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* 3D layer — fills the screen */}
      <div style={{ position: 'absolute', inset: 0 }}>
        <Scene />
      </div>

      {/* UI overlay — sits on top of canvas */}
      <ChatInterface sendMessage={sendMessage} sendInterrupt={sendInterrupt} sendSetModel={sendSetModel} />
    </div>
  )
}
