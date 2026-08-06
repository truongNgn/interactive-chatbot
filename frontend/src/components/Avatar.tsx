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

const SPEAKING_FACE_KEYS = [
  'jawOpen',
  'mouthOpen',
  'mouthPucker',
  'mouthSmile_L',
  'mouthSmile_R',
  'eyeWide_L',
  'eyeWide_R',
  'eyeBlink_L',
  'eyeBlink_R',
  'browInnerUp',
  'browDown_L',
  'browDown_R',
  'cheekSquint_L',
  'cheekSquint_R',
]

// ---------------------------------------------------------------------------
// Bone store — tìm runtime, dùng cho procedural animation
// ---------------------------------------------------------------------------
interface BoneSet {
  hips?:     THREE.Bone
  spine?:    THREE.Bone
  chest?:    THREE.Bone
  head?:     THREE.Bone
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
  const baseRotations  = useRef<Map<string, THREE.Euler>>(new Map())
  const blinkSeed      = useRef(Math.random() * 10)
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
      hips:     findBone(scene, /^hips$/),
      spine:    findBone(scene, /^spine$|torso/),
      chest:    findBone(scene, /^chest$/),
      head:     findBone(scene, /^head$/),
      leftArm:  findBone(scene, /left.*arm|arm.*l(?!\w)|shoulder.*l(?!\w)/),
      rightArm: findBone(scene, /right.*arm|arm.*r(?!\w)|shoulder.*r(?!\w)/),
      leftLeg:  findBone(scene, /left.*(?:up.?leg|thigh)|upleg.*l(?!\w)|thigh.*l(?!\w)/),
      rightLeg: findBone(scene, /right.*(?:up.?leg|thigh)|upleg.*r(?!\w)|thigh.*r(?!\w)/),
    }
    bonesRef.current = bones
    baseRotations.current.clear()
    Object.values(bones).forEach((bone) => {
      if (bone) baseRotations.current.set(bone.uuid, bone.rotation.clone())
    })

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
  // Chỉ chạy nếu GLB có clips; play idle loop làm base animation.
  useEffect(() => {
    if (!hasClips || !actions) return
    const names = Object.keys(actions)

    const idleName =
      names.find((n) => /idle/i.test(n)) ??
      names.find((n) => /stand|rest|wait/i.test(n)) ??
      names[0]

    if (idleName) {
      const action = actions[idleName]
      action?.reset().fadeIn(0.4).play()
      console.info('[Avatar] Playing animation:', idleName)
    }

    return () => {
      if (idleName) actions[idleName]?.fadeOut(0.3)
    }
  }, [hasClips, actions])

  // ── useFrame — procedural + morph lerp ───────────────────────────────────
  useFrame((_, delta) => {
    const t = performance.now() / 1000

    {
      // ── Procedural body overlay ───────────────────────────────────────────
      // GLB donghua_girl_1 currently has an idle clip but no talking clip, so
      // keep this overlay active to make chat responses visibly alive.
      const speed     = isAISpeaking ? 1.0 : 0.45
      const hipsAmp   = isAISpeaking ? 0.045 : (hasClips ? 0.00 : 0.025)
      const spineAmp  = isAISpeaking ? 0.115 : (hasClips ? 0.00 : 0.05)
      const headAmp   = isAISpeaking ? 0.105 : (hasClips ? 0.00 : 0.035)
      const armAmp    = isAISpeaking ? 0.34 : (hasClips ? 0.00 : 0.06)
      const legAmp    = isAISpeaking ? 0.065 : (hasClips ? 0.00 : 0.03)
      const lerpSpeed = delta * (isAISpeaking ? 8 : 5)

      const { hips, spine, chest, head, leftArm, rightArm, leftLeg, rightLeg } = bonesRef.current
      const base = (bone: THREE.Bone, axis: 'x' | 'y' | 'z') =>
        baseRotations.current.get(bone.uuid)?.[axis] ?? 0

      if (hips) {
        hips.rotation.y = THREE.MathUtils.lerp(
          hips.rotation.y,
          base(hips, 'y') + Math.sin(t * speed * 0.65) * hipsAmp,
          lerpSpeed,
        )
      }

      // Spine sway
      if (spine) {
        spine.rotation.y = THREE.MathUtils.lerp(
          spine.rotation.y,
          base(spine, 'y') + Math.sin(t * speed * 0.9) * spineAmp,
          lerpSpeed,
        )
        spine.rotation.z = THREE.MathUtils.lerp(
          spine.rotation.z,
          base(spine, 'z') + Math.sin(t * speed * 0.7) * spineAmp * 0.35,
          lerpSpeed,
        )
      }
      if (chest) {
        chest.rotation.x = THREE.MathUtils.lerp(
          chest.rotation.x,
          base(chest, 'x') + Math.sin(t * speed * 1.35) * spineAmp * 0.22,
          lerpSpeed,
        )
        chest.rotation.z = THREE.MathUtils.lerp(
          chest.rotation.z,
          base(chest, 'z') + Math.sin(t * speed * 0.8 + 0.7) * spineAmp * 0.45,
          lerpSpeed,
        )
      }
      if (head) {
        const nod = Math.sin(t * speed * 2.15) * headAmp * 0.55
        const turn = Math.sin(t * speed * 0.9 + 1.2) * headAmp
        const tilt = Math.sin(t * speed * 1.15 + 2.0) * headAmp * 0.45
        head.rotation.x = THREE.MathUtils.lerp(head.rotation.x, base(head, 'x') + nod, lerpSpeed)
        head.rotation.y = THREE.MathUtils.lerp(head.rotation.y, base(head, 'y') + turn, lerpSpeed)
        head.rotation.z = THREE.MathUtils.lerp(head.rotation.z, base(head, 'z') + tilt, lerpSpeed)
      }

      // Arms swing đối nghịch nhau
      if (leftArm) {
        leftArm.rotation.z = THREE.MathUtils.lerp(
          leftArm.rotation.z,
          base(leftArm, 'z') + Math.sin(t * speed + Math.PI) * armAmp,
          lerpSpeed,
        )
      }
      if (rightArm) {
        rightArm.rotation.z = THREE.MathUtils.lerp(
          rightArm.rotation.z,
          base(rightArm, 'z') + Math.sin(t * speed) * armAmp,
          lerpSpeed,
        )
      }

      // Legs đối nghịch với arms
      if (leftLeg) {
        leftLeg.rotation.x = THREE.MathUtils.lerp(
          leftLeg.rotation.x,
          base(leftLeg, 'x') + Math.sin(t * speed) * legAmp,
          lerpSpeed,
        )
      }
      if (rightLeg) {
        rightLeg.rotation.x = THREE.MathUtils.lerp(
          rightLeg.rotation.x,
          base(rightLeg, 'x') + Math.sin(t * speed + Math.PI) * legAmp,
          lerpSpeed,
        )
      }

      // Fallback group sway nếu không tìm được bones
      const noBones = !spine && !chest && !leftArm && !rightArm
      if (groupRef.current && noBones) {
        const groupAmp = isAISpeaking ? 0.05 : 0.02
        groupRef.current.rotation.y = Math.sin(t * 0.7) * groupAmp
        groupRef.current.position.y = Math.sin(t * 0.9) * 0.008
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

    // --- 3b. Speaking facial fallback for models with a small ARKit subset ---
    // donghua_girl_1 has 20 practical morphs, while Rhubarb maps may reference
    // richer ARKit keys. This layer keeps face, brows, cheeks and blinks alive.
    const speechPulse =
      Math.max(0, Math.sin(t * 11.0)) * 0.55 +
      Math.max(0, Math.sin(t * 7.3 + 1.4)) * 0.30 +
      Math.max(0, Math.sin(t * 17.0 + 0.6)) * 0.15
    const speech = isAISpeaking ? Math.min(1, speechPulse) : 0
    const blinkPhase = (t + blinkSeed.current) % 4.2
    const blink =
      blinkPhase < 0.10
        ? Math.sin((blinkPhase / 0.10) * Math.PI)
        : isAISpeaking && blinkPhase > 2.1 && blinkPhase < 2.17
          ? Math.sin(((blinkPhase - 2.1) / 0.07) * Math.PI) * 0.65
          : 0
    const talkingFace: Record<string, number> = {
      jawOpen: speech * 0.48,
      mouthOpen: speech * 0.38,
      mouthPucker: Math.max(0, Math.sin(t * 5.1 + 0.8)) * speech * 0.22,
      mouthSmile_L: isAISpeaking ? 0.13 + Math.max(0, Math.sin(t * 2.0)) * 0.08 : 0,
      mouthSmile_R: isAISpeaking ? 0.13 + Math.max(0, Math.sin(t * 2.0 + 0.25)) * 0.08 : 0,
      eyeWide_L: isAISpeaking ? 0.08 + Math.max(0, Math.sin(t * 1.6 + 0.5)) * 0.08 : 0,
      eyeWide_R: isAISpeaking ? 0.08 + Math.max(0, Math.sin(t * 1.5 + 0.7)) * 0.08 : 0,
      eyeBlink_L: blink,
      eyeBlink_R: blink,
      browInnerUp: isAISpeaking ? 0.09 + Math.max(0, Math.sin(t * 1.25 + 1.1)) * 0.10 : 0,
      browDown_L: isAISpeaking ? Math.max(0, Math.sin(t * 1.4 + 2.2)) * 0.06 : 0,
      browDown_R: isAISpeaking ? Math.max(0, Math.sin(t * 1.3 + 2.6)) * 0.06 : 0,
      cheekSquint_L: isAISpeaking ? 0.07 + Math.max(0, Math.sin(t * 2.1 + 0.3)) * 0.09 : 0,
      cheekSquint_R: isAISpeaking ? 0.07 + Math.max(0, Math.sin(t * 2.0 + 0.8)) * 0.09 : 0,
    }
    for (const key of SPEAKING_FACE_KEYS) {
      const idx = avatarMorphRef.dict[key]
      if (idx === undefined) continue
      const current = avatarMorphRef.influences[idx] ?? 0
      const target = Math.max(
        talkingFace[key] ?? 0,
        (visemeWeights as Record<string, number>)[key] ?? 0,
        emotionTarget.current[key] ?? 0,
      )
      avatarMorphRef.influences[idx] = THREE.MathUtils.lerp(current, target, delta * 12)
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
  const currentModel = useChatStore((s) => s.currentModel)
  if (!currentModel) {
    return <AvatarFallback />
  }
  return (
    <Suspense fallback={<AvatarFallback />}>
      <GLBAvatar />
    </Suspense>
  )
}
