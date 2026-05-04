/**
 * Scene — R3F Canvas cho facecap head model.
 * Camera được đặt gần, ngang tầm mặt để lấp đầy viewport.
 */

import { Canvas } from '@react-three/fiber'
import { ContactShadows, Environment, OrbitControls } from '@react-three/drei'
import { Avatar } from './Avatar'

export function Scene() {
  return (
    <Canvas
      camera={{ position: [0, 0, 1.4], fov: 38, near: 0.01, far: 20 }}
      shadows
      gl={{ antialias: true, alpha: false }}
      style={{ background: 'linear-gradient(180deg, #0d1117 0%, #161b27 100%)' }}
    >
      {/* Ambient fill */}
      <ambientLight intensity={0.5} />

      {/* Key light — front-left, warm */}
      <directionalLight
        position={[-1.5, 1.5, 2]}
        intensity={1.4}
        castShadow
      />

      {/* Rim light — back-right, cool */}
      <pointLight position={[1.5, 0.5, -1]} intensity={0.8} color="#a0c4ff" />

      {/* Under-light for soft jaw fill */}
      <pointLight position={[0, -1, 1]} intensity={0.3} color="#ffe8c0" />

      {/* HDR reflections */}
      <Environment preset="studio" />

      {/* Avatar (head centered at ~y=0) */}
      <Avatar />

      {/* Subtle ground shadow */}
      <ContactShadows
        position={[0, -0.55, 0]}
        opacity={0.3}
        scale={2}
        blur={1.5}
        far={1}
      />

      {/* Dev orbit — target head center */}
      <OrbitControls
        target={[0, 0, 0]}
        minDistance={0.6}
        maxDistance={3.0}
        minPolarAngle={Math.PI / 4}
        maxPolarAngle={Math.PI / 1.6}
        enablePan={false}
      />
    </Canvas>
  )
}
