/**
 * useLipSync — Stage 4: Rhubarb viseme playback
 *
 * Architecture:
 *  - `lipSyncState` is a module-level singleton shared between hooks/components.
 *  - `startLipSync(visemes, ctx)` is called by useAudioQueue when audio playback begins.
 *  - `stopLipSync()` is called when audio ends or is interrupted.
 *  - `tickLipSync()` is called each frame (Avatar useFrame) to get the current
 *    ARKit weight map based on AudioContext elapsed time.
 *
 * Time tracking uses AudioContext.currentTime (high-precision, drift-free),
 * not Date.now(), to stay in sync with the audio playback clock.
 */

import type { VisemeKeyframe } from '../types'
import { VISEME_MAP, ALL_VISEME_KEYS } from '../types/visemeMapping'
import type { RhubarbPhoneme } from '../types/visemeMapping'

// ---------------------------------------------------------------------------
// Module-level shared state (write: useAudioQueue, read: Avatar useFrame)
// ---------------------------------------------------------------------------
export const lipSyncState: {
  visemes: VisemeKeyframe[]
  startTime: number   // AudioContext.currentTime at playback start
  ctx: AudioContext | null
  analyser: AnalyserNode | null  // amplitude fallback when no Rhubarb visemes
  _dataBuffer: Uint8Array | null
} = {
  visemes: [],
  startTime: 0,
  ctx: null,
  analyser: null,
  _dataBuffer: null,
}

/** Called by useAudioQueue immediately after source.start() when Rhubarb visemes exist. */
export function startLipSync(visemes: VisemeKeyframe[], ctx: AudioContext): void {
  lipSyncState.visemes = visemes
  lipSyncState.startTime = ctx.currentTime
  lipSyncState.ctx = ctx
  lipSyncState.analyser = null
  lipSyncState._dataBuffer = null
}

/**
 * Amplitude fallback: called when audio plays but no Rhubarb visemes are available.
 * Connects source → AnalyserNode (tap-only, source still connected to destination).
 * tickLipSync() will read RMS to drive jawOpen.
 */
export function startAmplitudeLipSync(source: AudioBufferSourceNode): void {
  try {
    const ctx = source.context as AudioContext
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 512
    analyser.smoothingTimeConstant = 0.6
    source.connect(analyser)
    // Do NOT connect analyser → destination; source → destination is already wired externally
    lipSyncState.analyser = analyser
    lipSyncState._dataBuffer = new Uint8Array(analyser.frequencyBinCount)
    lipSyncState.visemes = []
    lipSyncState.ctx = null
  } catch {
    // ignore — no fallback
  }
}

/** Called by useAudioQueue when audio ends or is stopped. */
export function stopLipSync(): void {
  lipSyncState.visemes = []
  lipSyncState.ctx = null
  lipSyncState.analyser = null
  lipSyncState._dataBuffer = null
}

/** All ARKit keys used by the viseme map (for reset on stop). */
export { ALL_VISEME_KEYS }

// ---------------------------------------------------------------------------
// Frame tick — called from Avatar useFrame
// ---------------------------------------------------------------------------

/**
 * Returns the ARKit weight map for the current viseme at this moment in time.
 * Returns {} when no lip-sync is active (mouth returns to rest via lerp in Avatar).
 */
export function tickLipSync(): Partial<Record<string, number>> {
  const { visemes, startTime, ctx, analyser, _dataBuffer } = lipSyncState

  // ── Amplitude fallback (no Rhubarb visemes) ────────────────────────────────
  if (analyser && _dataBuffer) {
    analyser.getByteTimeDomainData(_dataBuffer)
    let sum = 0
    for (let i = 0; i < _dataBuffer.length; i++) {
      const v = (_dataBuffer[i] - 128) / 128
      sum += v * v
    }
    const rms = Math.sqrt(sum / _dataBuffer.length)
    const jawOpen = Math.min(1, rms * 5)
    return jawOpen > 0.015 ? { jawOpen } : {}
  }

  // ── Rhubarb viseme mode ────────────────────────────────────────────────────
  if (!ctx || visemes.length === 0) return {}

  const elapsed = ctx.currentTime - startTime
  const cue = _findCurrentCue(elapsed, visemes)
  if (!cue) return {}

  return VISEME_MAP[cue.value as RhubarbPhoneme] ?? {}
}

// ---------------------------------------------------------------------------
// Binary search for current mouth cue at `elapsed` seconds
// ---------------------------------------------------------------------------
function _findCurrentCue(
  elapsed: number,
  visemes: VisemeKeyframe[],
): VisemeKeyframe | null {
  if (elapsed < visemes[0].start) return null
  if (elapsed >= visemes[visemes.length - 1].end) return null

  let lo = 0
  let hi = visemes.length - 1
  while (lo <= hi) {
    const mid = (lo + hi) >>> 1
    if (elapsed < visemes[mid].start) {
      hi = mid - 1
    } else if (elapsed >= visemes[mid].end) {
      lo = mid + 1
    } else {
      return visemes[mid]
    }
  }
  return null
}
