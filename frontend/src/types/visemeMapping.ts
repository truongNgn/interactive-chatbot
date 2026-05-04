/**
 * Viseme Mapping — Rhubarb phoneme groups → ARKit blendshape weights
 *
 * Facecap model morph targets (ARKit):
 *   jawOpen, jawForward, jawLeft, jawRight,
 *   mouthFunnel, mouthPucker, mouthLeft, mouthRight,
 *   mouthRollUpper, mouthRollLower, mouthShrugUpper, mouthShrugLower,
 *   mouthClose, mouthSmile_L, mouthSmile_R, mouthFrown_L, mouthFrown_R,
 *   mouthDimple_L, mouthDimple_R, mouthUpperUp_L, mouthUpperUp_R,
 *   mouthLowerDown_L, mouthLowerDown_R, mouthPress_L, mouthPress_R,
 *   mouthStretch_L, mouthStretch_R, tongueOut, ...
 *
 * Rhubarb output phoneme groups (Preston Blair):
 *   A  – open vowel  (ah, aa)
 *   B  – closed lips (p, b, m)
 *   C  – open teeth  (th, d, n, t)
 *   D  – narrow open (ee, ih)
 *   E  – wide open   (eh, ae)
 *   F  – lip-teeth   (f, v)
 *   G  – round open  (oh)
 *   H  – round pucker (oo, uw)
 *   X  – silence / rest
 */

export type RhubarbPhoneme = 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H' | 'X'

/** Partial ARKit blendshape weights for one phoneme. Unlisted keys → 0. */
export type ARKitWeights = Partial<Record<string, number>>

export const VISEME_MAP: Record<RhubarbPhoneme, ARKitWeights> = {
  // A — open mouth "ah"
  A: { jawOpen: 0.8, mouthFunnel: 0.2, mouthLowerDown_L: 0.4, mouthLowerDown_R: 0.4 },

  // B — closed "p/b/m"
  B: { mouthClose: 0.9, mouthPress_L: 0.4, mouthPress_R: 0.4, jawOpen: 0.0 },

  // C — open teeth "th/d/n"
  C: { jawOpen: 0.35, mouthLowerDown_L: 0.6, mouthLowerDown_R: 0.6, mouthUpperUp_L: 0.4, mouthUpperUp_R: 0.4 },

  // D — narrow open "ee/ih"
  D: { jawOpen: 0.2, mouthSmile_L: 0.5, mouthSmile_R: 0.5, mouthStretch_L: 0.3, mouthStretch_R: 0.3 },

  // E — wide "eh/ae"
  E: { jawOpen: 0.45, mouthStretch_L: 0.4, mouthStretch_R: 0.4, mouthLowerDown_L: 0.3, mouthLowerDown_R: 0.3 },

  // F — lip-teeth "f/v"
  F: { mouthRollLower: 0.6, mouthLowerDown_L: 0.3, mouthLowerDown_R: 0.3, jawOpen: 0.1 },

  // G — round open "oh"
  G: { jawOpen: 0.55, mouthFunnel: 0.6, mouthRollLower: 0.2 },

  // H — round pucker "oo/uw"
  H: { mouthPucker: 0.7, mouthFunnel: 0.5, jawOpen: 0.2 },

  // X — silence / rest
  X: {},
}

/** All unique ARKit keys touched by this mapping (needed for reset). */
export const ALL_VISEME_KEYS = Array.from(
  new Set(Object.values(VISEME_MAP).flatMap((w) => Object.keys(w))),
)
