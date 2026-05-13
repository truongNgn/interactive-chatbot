/**
 * Avatar — full-body character với animation support.
 *
 * Ưu tiên 1: animation clips có sẵn trong GLB (useAnimations).
 *   - Tìm clip theo tên: idle, talking/wave/speak → tự động switch.
 * Ưu tiên 2: procedural bone animation (fallback khi GLB không có clips).
 *   - Traverse skeleton → tìm spine / arm / leg bones → animate bằng sin wave.
 *   - Tốc độ & biên độ thay đổi theo isAISpeaking.
 */

import { useEffect, useRef, Suspense } from 'react'
import { useGLTF, useAnimations } from '@react-three/drei'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { KTX2Loader } from 'three/examples/jsm/loaders/KTX2Loader.js'
import { useChatStore } from '../store/chatStore'
import type { Emotion } from '../types'
import { tickLipSync, ALL_VISEME_KEYS } from '../hooks/useLipSync'
// Note: We use dynamic model path instead of AVATAR_PATH.

// ---------------------------------------------------------------------------
// Module-level morph ref (Stage 4 lip-sync)
// ---------------------------------------------------------------------------
export const avatarMorphRef: {
  mesh: THREE.SkinnedMesh | null
  dict: Record<string, number>
  influences: number[]
} = { mesh: null, dict: {}, influences: [] }

export function setMorph(name: string, value: number) {
  const idx = avatarMorphRef.dict[name]
  if (idx !== undefined) {
    avatarMorphRef.influences[idx] = Math.max(0, Math.min(1, value))
  }
}

export function resetMorphs(names: string[]) {
  for (const name of names) setMorph(name, 0)
}

// ---------------------------------------------------------------------------
// Emotion → blendshape presets
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
// Bone store — tìm runtime, dùng cho procedural animation
// ---------------------------------------------------------------------------
interface BoneSet {
  spine?:    THREE.Bone
  leftArm?:  THREE.Bone
  rightArm?: THREE.Bone
  leftLeg?:  THREE.Bone
  rightLeg?: THREE.Bone
}

/** Tìm bone đầu tiên khớp với regex trong scene. */
function findBone(scene: THREE.Object3D, pattern: RegExp): THREE.Bone | undefined {
  let found: THREE.Bone | undefined
  scene.traverse((obj) => {
    if (found || !(obj instanceof THREE.Bone)) return
    if (pattern.test(obj.name.toLowerCase())) found = obj
  })
  return found
}

// ---------------------------------------------------------------------------
// GLBAvatar — component chính
// ---------------------------------------------------------------------------
function GLBAvatar() {
  const gl = useThree((s) => s.gl)
  const currentModel = useChatStore((s) => s.currentModel)
  const { scene, animations } = useGLTF(currentModel, true, true, (loader) => {
    const ktx2 = new KTX2Loader()
    ktx2.setTranscoderPath('https://cdn.jsdelivr.net/npm/three/examples/jsm/libs/basis/')
    ktx2.detectSupport(gl)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    loader.setKTX2Loader(ktx2 as any)
  })

  const groupRef       = useRef<THREE.Group>(null)
  const bonesRef       = useRef<BoneSet>({})
  const emotionTarget  = useRef<Partial<Record<string, number>>>({})
  const hasClips       = animations.length > 0

  const currentEmotion = useChatStore((s) => s.currentEmotion)
  const isAISpeaking   = useChatStore((s) => s.isAISpeaking)

  // ── Animation clips (useAnimations) ───────────────────────────────────────
  const { actions } = useAnimations(animations, groupRef)

  // Log animations & bones một lần khi mount
  useEffect(() => {
    if (animations.length > 0) {
      console.info('[Avatar] Animation clips:', animations.map((a) => a.name))
    } else {
      console.info('[Avatar] No embedded animations → using procedural bones.')
    }

    // Tìm bones cho procedural animation
    const bones: BoneSet = {
      spine:    findBone(scene, /spine|chest|torso|hips/),
      leftArm:  findBone(scene, /left.*arm|arm.*l(?!\w)|shoulder.*l(?!\w)/),
      rightArm: findBone(scene, /right.*arm|arm.*r(?!\w)|shoulder.*r(?!\w)/),
      leftLeg:  findBone(scene, /left.*(?:up.?leg|thigh)|upleg.*l(?!\w)|thigh.*l(?!\w)/),
      rightLeg: findBone(scene, /right.*(?:up.?leg|thigh)|upleg.*r(?!\w)|thigh.*r(?!\w)/),
    }
    bonesRef.current = bones

    const found = Object.entries(bones)
      .filter(([, b]) => b)
      .map(([k, b]) => `${k}="${b!.name}"`)
    console.info('[Avatar] Bones found:', found.length ? found.join(', ') : 'none (procedural group sway only)')
  }, [scene, animations])

  // ── Morph setup ───────────────────────────────────────────────────────────
  useEffect(() => {
    let found = false
    scene.traverse((obj) => {
      if (found) return
      const mesh = obj as THREE.SkinnedMesh
      if (mesh.isMesh && mesh.morphTargetDictionary && Object.keys(mesh.morphTargetDictionary).length > 0) {
        avatarMorphRef.mesh       = mesh
        avatarMorphRef.dict       = mesh.morphTargetDictionary
        avatarMorphRef.influences = mesh.morphTargetInfluences as number[]
        found = true
        console.info('[Avatar] Morph mesh:', obj.name, '| targets:', Object.keys(mesh.morphTargetDictionary).length)
      }
    })
    return () => {
      avatarMorphRef.mesh       = null
      avatarMorphRef.dict       = {}
      avatarMorphRef.influences = []
    }
  }, [scene])

  useEffect(() => {
    emotionTarget.current = EMOTION_MORPHS[currentEmotion] ?? {}
  }, [currentEmotion])

  // ── Play animation clips ───────────────────────────────────────────────────
  // Chỉ chạy nếu GLB có clips; tự động switch idle ↔ talking
  useEffect(() => {
    if (!hasClips || !actions) return
    const names = Object.keys(actions)

    const idleName =
      names.find((n) => /idle/i.test(n)) ??
      names.find((n) => /stand|rest|wait/i.test(n)) ??
      names[0]

    const talkName =
      names.find((n) => /talk|speak/i.test(n)) ??
      names.find((n) => /wave|gesture|greet/i.test(n))

    const activeClip   = isAISpeaking && talkName ? talkName : idleName
    const inactiveClip = activeClip === idleName ? talkName : idleName

    if (activeClip) {
      actions[activeClip]?.reset().fadeIn(0.4).play()
    }
    if (inactiveClip) {
      actions[inactiveClip]?.fadeOut(0.4)
    }

    return () => {
      if (activeClip) actions[activeClip]?.fadeOut(0.3)
    }
  }, [isAISpeaking, hasClips, actions])

  // ── useFrame — procedural + morph lerp ───────────────────────────────────
  useFrame((_, delta) => {
    const t = performance.now() / 1000

    if (!hasClips) {
      // ── Procedural animation (fallback khi không có clips) ──
      const speed     = isAISpeaking ? 1.0 : 0.45
      const armAmp    = isAISpeaking ? 0.18 : 0.06
      const legAmp    = isAISpeaking ? 0.10 : 0.03
      const lerpSpeed = delta * 6

      const { spine, leftArm, rightArm, leftLeg, rightLeg } = bonesRef.current

      // Spine sway
      if (spine) {
        spine.rotation.y = THREE.MathUtils.lerp(
          spine.rotation.y,
          Math.sin(t * speed * 0.6) * 0.06,
          lerpSpeed,
        )
        spine.rotation.z = THREE.MathUtils.lerp(
          spine.rotation.z,
          Math.sin(t * speed * 0.4) * 0.02,
          lerpSpeed,
        )
      }

      // Arms swing đối nghịch nhau
      if (leftArm) {
        leftArm.rotation.z = THREE.MathUtils.lerp(
          leftArm.rotation.z,
          Math.sin(t * speed + Math.PI) * armAmp,
          lerpSpeed,
        )
      }
      if (rightArm) {
        rightArm.rotation.z = THREE.MathUtils.lerp(
          rightArm.rotation.z,
          Math.sin(t * speed) * armAmp,
          lerpSpeed,
        )
      }

      // Legs đối nghịch với arms
      if (leftLeg) {
        leftLeg.rotation.x = THREE.MathUtils.lerp(
          leftLeg.rotation.x,
          Math.sin(t * speed) * legAmp,
          lerpSpeed,
        )
      }
      if (rightLeg) {
        rightLeg.rotation.x = THREE.MathUtils.lerp(
          rightLeg.rotation.x,
          Math.sin(t * speed + Math.PI) * legAmp,
          lerpSpeed,
        )
      }

      // Fallback group sway nếu không tìm được bones
      const noBones = !spine && !leftArm && !rightArm
      if (groupRef.current && noBones) {
        groupRef.current.rotation.y = Math.sin(t * 0.4) * 0.03
        groupRef.current.position.y = Math.sin(t * 0.6) * 0.005
      }
    }

    // ── Emotion morphs (lerp) ──
    if (!avatarMorphRef.mesh) return
    for (const key of ALL_EMOTION_KEYS) {
      const target = emotionTarget.current[key] ?? 0
      const idx    = avatarMorphRef.dict[key]
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
// Fallback placeholder
// ---------------------------------------------------------------------------
function AvatarFallback() {
  return (
    <mesh position={[0, 1, 0]}>
      <capsuleGeometry args={[0.3, 1.2, 4, 8]} />
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
