/**
 * Scene — R3F Canvas cho full-body character.
 * Camera lùi ra để thấy toàn thân, target ngang hông.
 */

import { Canvas } from '@react-three/fiber'
import { ContactShadows, Environment, OrbitControls } from '@react-three/drei'
import { Avatar } from './Avatar'

export function Scene() {
  return (
    <Canvas
      camera={{ position: [0, 1, 3.5], fov: 50, near: 0.01, far: 50 }}
      shadows
      gl={{ antialias: true, alpha: false }}
      style={{ background: 'linear-gradient(180deg, #0d1117 0%, #161b27 100%)' }}
    >
      {/* Ambient fill */}
      <ambientLight intensity={0.6} />

      {/* Key light — front-left, warm */}
      <directionalLight
        position={[-2, 4, 3]}
        intensity={1.6}
        castShadow
        shadow-mapSize={[1024, 1024]}
      />

      {/* Rim light — back-right, cool */}
      <pointLight position={[2, 2, -2]} intensity={1.0} color="#a0c4ff" />

      {/* Fill light — front-right, soft warm */}
      <pointLight position={[2, 1, 2]} intensity={0.5} color="#ffe8c0" />

      {/* HDR reflections */}
      <Environment preset="studio" />

      {/* Avatar */}
      <Avatar />

      {/* Ground shadow */}
      <ContactShadows
        position={[0, -0.01, 0]}
        opacity={0.4}
        scale={4}
        blur={2}
        far={3}
      />

      {/* Orbit controls — xoay tự do 360° theo cả trục ngang lẫn dọc */}
      <OrbitControls
        target={[0, 1, 0]}
        minDistance={1.5}
        maxDistance={6}
        minPolarAngle={0}
        maxPolarAngle={Math.PI}
        enablePan={false}
      />
    </Canvas>
  )
}
