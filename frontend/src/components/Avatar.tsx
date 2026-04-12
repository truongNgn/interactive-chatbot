/**
 * Avatar — Stage 3: Load Ready Player Me .glb model và render với idle animation.
 *
 * Đặt file .glb vào: public/models/avatar.glb
 * Nếu model chưa có, hiển thị placeholder geometry.
 *
 * Stage 4 sẽ bổ sung:
 *   - morphTargetInfluences cho lip-sync (Rhubarb visemes)
 *   - Emotion blendshapes (smile, browRaise, v.v.)
 */

import { useRef, useEffect, Suspense } from 'react'
import { useGLTF, useAnimations } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { useChatStore } from '../store/chatStore'

const AVATAR_PATH = '/models/avatar.glb'

// ---------------------------------------------------------------------------
// Placeholder: simple humanoid shape shown before GLB is available
// ---------------------------------------------------------------------------
function AvatarPlaceholder() {
  const groupRef = useRef<THREE.Group>(null)
  const isAISpeaking = useChatStore((s) => s.isAISpeaking)

  useFrame(({ clock }) => {
    if (!groupRef.current) return
    const t = clock.getElapsedTime()
    // Gentle idle bob
    groupRef.current.position.y = Math.sin(t * 1.2) * 0.03
    // Subtle speaking pulse on head
    if (isAISpeaking) {
      const pulse = 1 + Math.sin(t * 8) * 0.02
      groupRef.current.scale.setScalar(pulse)
    } else {
      groupRef.current.scale.setScalar(1)
    }
  })

  return (
    <group ref={groupRef} position={[0, 0, 0]}>
      {/* Head */}
      <mesh position={[0, 1.6, 0]}>
        <sphereGeometry args={[0.22, 32, 32]} />
        <meshStandardMaterial color="#f0c8a0" roughness={0.6} />
      </mesh>
      {/* Eyes */}
      <mesh position={[-0.07, 1.65, 0.21]}>
        <sphereGeometry args={[0.03, 16, 16]} />
        <meshStandardMaterial color="#2a2a2a" />
      </mesh>
      <mesh position={[0.07, 1.65, 0.21]}>
        <sphereGeometry args={[0.03, 16, 16]} />
        <meshStandardMaterial color="#2a2a2a" />
      </mesh>
      {/* Torso */}
      <mesh position={[0, 1.1, 0]}>
        <capsuleGeometry args={[0.18, 0.5, 8, 16]} />
        <meshStandardMaterial color="#4a90d9" roughness={0.7} />
      </mesh>
    </group>
  )
}

// ---------------------------------------------------------------------------
// Real GLB Avatar (Ready Player Me)
// ---------------------------------------------------------------------------
function GLBAvatar() {
  const group = useRef<THREE.Group>(null)
  const { scene, animations } = useGLTF(AVATAR_PATH)
  const { actions, names } = useAnimations(animations, group)

  // Play idle animation if available
  useEffect(() => {
    const idleName = names.find((n) => /idle/i.test(n)) ?? names[0]
    if (idleName && actions[idleName]) {
      actions[idleName]!.reset().fadeIn(0.5).play()
    }
    return () => {
      if (idleName && actions[idleName]) {
        actions[idleName]!.fadeOut(0.3)
      }
    }
  }, [actions, names])

  // Gentle idle bob when no animation clip
  useFrame(({ clock }) => {
    if (!group.current || names.length > 0) return
    group.current.position.y = Math.sin(clock.getElapsedTime() * 1.2) * 0.03
  })

  return (
    <group ref={group} dispose={null}>
      <primitive object={scene} />
    </group>
  )
}

// ---------------------------------------------------------------------------
// Exported Avatar: tries GLB, falls back to placeholder
// ---------------------------------------------------------------------------
export function Avatar() {
  return (
    <Suspense fallback={<AvatarPlaceholder />}>
      <GLBAvatarWithFallback />
    </Suspense>
  )
}

function GLBAvatarWithFallback() {
  try {
    return <GLBAvatar />
  } catch {
    return <AvatarPlaceholder />
  }
}

// Preload GLB in background
useGLTF.preload(AVATAR_PATH)
