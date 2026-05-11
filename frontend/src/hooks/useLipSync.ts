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
} = {
  visemes: [],
  startTime: 0,
  ctx: null,
}

/** Called by useAudioQueue immediately after source.start(). */
export function startLipSync(visemes: VisemeKeyframe[], ctx: AudioContext): void {
  lipSyncState.visemes = visemes
  lipSyncState.startTime = ctx.currentTime
  lipSyncState.ctx = ctx
}

/** Called by useAudioQueue when audio ends or is stopped. */
export function stopLipSync(): void {
  lipSyncState.visemes = []
  lipSyncState.ctx = null
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
  const { visemes, startTime, ctx } = lipSyncState
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
