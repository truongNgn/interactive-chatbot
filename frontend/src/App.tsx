import { useCallback, useEffect } from 'react'
import { ChatInterface } from './components/ChatInterface'
import { Sidebar } from './components/Sidebar'
import { RightSidebar } from './components/RightSidebar'
import { useWebSocket } from './hooks/useWebSocket'
import { useAudioQueue } from './hooks/useAudioQueue'
import { useVAD } from './hooks/useVAD'
import { useChatStore } from './store/chatStore'

export function App() {
  const { stopPlayback } = useAudioQueue()
  const { sendMessage, sendInterrupt, sendSetModel } = useWebSocket(stopPlayback)

  const handleInterrupt = useCallback(() => {
    stopPlayback()
    sendInterrupt()
  }, [stopPlayback, sendInterrupt])

  const isAISpeaking = useCallback(
    () => useChatStore.getState().isAISpeaking,
    [],
  )

  const { startListening, stopListening } = useVAD({
    onVoiceDetected: handleInterrupt,
    isAISpeaking,
  })

  useEffect(() => {
    startListening()
    return () => stopListening()
  }, [startListening, stopListening])

  // New session: update store + reconnect WS với sessionId mới không cần thiết
  // vì useWebSocket luôn đọc activeSessionId từ store khi gửi message.
  const handleNewSession = useCallback(() => {
    useChatStore.getState().createNewSession()
  }, [])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', display: 'flex' }}>
      <Sidebar onNewSession={handleNewSession} sendSetModel={sendSetModel} />
      <div style={{ flex: 1, position: 'relative' }}>
        <ChatInterface sendMessage={sendMessage} sendInterrupt={handleInterrupt} />
      </div>
      <RightSidebar />
    </div>
  )
}
