/**
 * Scene — R3F Canvas với PBR lighting, Environment, ContactShadows.
 * Camera được đặt ngang tầm mặt avatar để tạo cảm giác đối thoại tự nhiên.
 */

import { Canvas } from '@react-three/fiber'
import { ContactShadows, Environment, OrbitControls } from '@react-three/drei'
import { Avatar } from './Avatar'

export function Scene() {
  return (
    <Canvas
      camera={{ position: [0, 1.4, 2.2], fov: 42, near: 0.1, far: 50 }}
      shadows
      gl={{ antialias: true, alpha: false }}
      style={{ background: 'linear-gradient(180deg, #0d1117 0%, #161b27 100%)' }}
    >
      {/* Ambient light — fill shadows */}
      <ambientLight intensity={0.4} />

      {/* Key light — soft front-left */}
      <directionalLight
        position={[-2, 3, 3]}
        intensity={1.2}
        castShadow
        shadow-mapSize={[1024, 1024]}
        shadow-camera-near={0.5}
        shadow-camera-far={20}
      />

      {/* Rim light — subtle back-right glow */}
      <pointLight position={[2, 2, -2]} intensity={0.6} color="#a0c4ff" />

      {/* HDR environment for PBR reflections */}
      <Environment preset="city" />

      {/* Avatar */}
      <Avatar />

      {/* Ground shadow */}
      <ContactShadows
        position={[0, 0, 0]}
        opacity={0.45}
        scale={4}
        blur={2}
        far={2}
      />

      {/* Dev-only orbit controls — remove or gate behind isDev in production */}
      <OrbitControls
        target={[0, 1.3, 0]}
        minDistance={1.0}
        maxDistance={4.0}
        minPolarAngle={Math.PI / 6}
        maxPolarAngle={Math.PI / 1.8}
        enablePan={false}
      />
    </Canvas>
  )
}
