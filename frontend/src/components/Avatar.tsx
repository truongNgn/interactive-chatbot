/**
 * Avatar — Stage 3 (Tier 3 model: Three.js facecap ARKit)
 *
 * Model: /models/avatar.glb (facecap — 52 ARKit blendshapes)
 * Nodes: head (SkinnedMesh w/ morphs), teeth, eyeLeft, eyeRight
 *
 * Responsibilities:
 *  - Load GLB, traverse to find the morph-capable SkinnedMesh
 *  - Register morphTargetInfluences in `avatarMorphRef` for Stage 4
 *  - Idle animations: eye blink, subtle breathing (no clips in this model)
 *  - Read `currentEmotion` from store → drive eyebrow / smile blendshapes
 */

import { useEffect, useRef, Suspense } from 'react'
import { useGLTF } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { useChatStore } from '../store/chatStore'
import type { Emotion } from '../types'
import { tickLipSync, ALL_VISEME_KEYS } from '../hooks/useLipSync'

const AVATAR_PATH = '/models/avatar.glb'

// ---------------------------------------------------------------------------
// Module-level ref — Stage 4 reads this to drive lip-sync morphs
// ---------------------------------------------------------------------------
export const avatarMorphRef: {
  mesh: THREE.SkinnedMesh | null
  dict: Record<string, number>   // morphTargetDictionary
  influences: number[]           // morphTargetInfluences (live array)
} = { mesh: null, dict: {}, influences: [] }

/** Helper: set a single morph target by name (safe — no-op if unknown). */
export function setMorph(name: string, value: number) {
  const idx = avatarMorphRef.dict[name]
  if (idx !== undefined) {
    avatarMorphRef.influences[idx] = Math.max(0, Math.min(1, value))
  }
}

/** Reset a list of morph targets to 0. */
export function resetMorphs(names: string[]) {
  for (const name of names) setMorph(name, 0)
}

// ---------------------------------------------------------------------------
// Emotion → blendshape presets (runs every frame via lerp in Avatar)
// ---------------------------------------------------------------------------
const EMOTION_MORPHS: Record<Emotion, Partial<Record<string, number>>> = {
  joy:      { mouthSmile_L: 0.7, mouthSmile_R: 0.7, cheekSquint_L: 0.4, cheekSquint_R: 0.4 },
  sad:      { mouthFrown_L: 0.6, mouthFrown_R: 0.6, browInnerUp: 0.5 },
  neutral:  {},
  thinking: { browInnerUp: 0.3, browDown_L: 0.2 },
  surprise: { eyeWide_L: 0.8, eyeWide_R: 0.8, jawOpen: 0.3, browOuterUp_L: 0.6, browOuterUp_R: 0.6 },
  anger:    { browDown_L: 0.7, browDown_R: 0.7, noseSneer_L: 0.4, noseSneer_R: 0.4 },
}

const ALL_EMOTION_KEYS = Array.from(
  new Set(Object.values(EMOTION_MORPHS).flatMap(Object.keys)),
)

// ---------------------------------------------------------------------------
// Idle blink timing
// ---------------------------------------------------------------------------
function nextBlinkDelay() {
  return 2000 + Math.random() * 3000 // 2-5 seconds
}

// ---------------------------------------------------------------------------
// Main GLB Avatar component
// ---------------------------------------------------------------------------
function GLBAvatar() {
  const { scene } = useGLTF(AVATAR_PATH)
  const groupRef = useRef<THREE.Group>(null)

  // Blink state
  const blinkTimer = useRef(nextBlinkDelay())
  const blinkProgress = useRef(0) // 0 = open, 1 = closed, -1 = not blinking

  const currentEmotion = useChatStore((s) => s.currentEmotion)
  const emotionTarget = useRef<Partial<Record<string, number>>>({})

  // --- Find and register the head SkinnedMesh ---
  useEffect(() => {
    let found = false
    scene.traverse((obj) => {
      if (found) return
      const mesh = obj as THREE.SkinnedMesh
      if (
        mesh.isMesh &&
        mesh.morphTargetDictionary &&
        Object.keys(mesh.morphTargetDictionary).length > 10
      ) {
        avatarMorphRef.mesh = mesh
        avatarMorphRef.dict = mesh.morphTargetDictionary
        avatarMorphRef.influences = mesh.morphTargetInfluences as number[]
        found = true
        console.info(
          '[Avatar] Morph mesh found:',
          obj.name || '(unnamed)',
          '— targets:',
          Object.keys(mesh.morphTargetDictionary).length,
        )
      }
    })
    if (!found) {
      console.warn('[Avatar] No morph-capable mesh found in GLB.')
    }

    return () => {
      avatarMorphRef.mesh = null
      avatarMorphRef.dict = {}
      avatarMorphRef.influences = []
    }
  }, [scene])

  // Update emotion target when store changes
  useEffect(() => {
    emotionTarget.current = EMOTION_MORPHS[currentEmotion] ?? {}
  }, [currentEmotion])

  useFrame((_, delta) => {
    if (!avatarMorphRef.mesh) return

    // --- 1. Blink ---
    blinkTimer.current -= delta * 1000
    if (blinkTimer.current <= 0) {
      blinkProgress.current = 1 // start blink
      blinkTimer.current = nextBlinkDelay()
    }
    if (blinkProgress.current > 0) {
      // Close on first half (progress 1→0.5), open on second (0.5→0)
      const closeness = blinkProgress.current > 0.5
        ? (blinkProgress.current - 0.5) * 2
        : blinkProgress.current * 2
      setMorph('eyeBlink_L', closeness)
      setMorph('eyeBlink_R', closeness)
      blinkProgress.current = Math.max(0, blinkProgress.current - delta * 4)
    }

    // --- 2. Emotion morphs (lerp toward target) ---
    for (const key of ALL_EMOTION_KEYS) {
      const target = emotionTarget.current[key] ?? 0
      const idx = avatarMorphRef.dict[key]
      if (idx === undefined) continue
      avatarMorphRef.influences[idx] = THREE.MathUtils.lerp(
        avatarMorphRef.influences[idx],
        target,
        delta * 3,
      )
    }

    // --- 3. Lip-sync viseme morphs (lerp toward current Rhubarb cue weights) ---
    const visemeWeights = tickLipSync()
    for (const key of ALL_VISEME_KEYS) {
      const target = (visemeWeights as Record<string, number>)[key] ?? 0
      const idx = avatarMorphRef.dict[key]
      if (idx === undefined) continue
      avatarMorphRef.influences[idx] = THREE.MathUtils.lerp(
        avatarMorphRef.influences[idx],
        target,
        delta * 14, // faster lerp than emotion (~14 vs 3) for snappy lip-sync
      )
    }

    // --- 4. Subtle head bob ---
    if (groupRef.current) {
      const t = performance.now() / 1000
      groupRef.current.rotation.z = Math.sin(t * 0.6) * 0.008
      groupRef.current.rotation.x = Math.sin(t * 0.4) * 0.005
    }
  })

  return (
    <group ref={groupRef} dispose={null}>
      <primitive object={scene} />
    </group>
  )
}

// ---------------------------------------------------------------------------
// Fallback placeholder (while GLB loads)
// ---------------------------------------------------------------------------
function AvatarFallback() {
  return (
    <mesh position={[0, 0, 0]}>
      <sphereGeometry args={[0.3, 32, 32]} />
      <meshStandardMaterial color="#f0c8a0" roughness={0.6} />
    </mesh>
  )
}

// ---------------------------------------------------------------------------
// Exported component
// ---------------------------------------------------------------------------
export function Avatar() {
  return (
    <Suspense fallback={<AvatarFallback />}>
      <GLBAvatar />
    </Suspense>
  )
}

useGLTF.preload(AVATAR_PATH)
