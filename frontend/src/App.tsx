import { Scene } from './components/Scene'
import { ChatInterface } from './components/ChatInterface'

export function App() {
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* 3D layer — fills the screen */}
      <div style={{ position: 'absolute', inset: 0 }}>
        <Scene />
      </div>

      {/* UI overlay — sits on top of canvas */}
      <ChatInterface />
    </div>
  )
}
