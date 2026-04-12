/**
 * useAudioQueue — Stage 3: Web Audio API sequential playback
 *
 * Drains the audioQueue from chatStore one chunk at a time.
 * For each chunk:
 *   1. Decode base64 → ArrayBuffer
 *   2. AudioContext.decodeAudioData → AudioBuffer
 *   3. Play via AudioBufferSourceNode
 *   4. On end → dequeue next
 *
 * Exposes `audioContextRef` so Stage 4 (lip-sync) can read currentTime.
 */

import { useCallback, useEffect, useRef } from 'react'
import { useChatStore } from '../store/chatStore'

function base64ToArrayBuffer(b64: string): ArrayBuffer {
  const binary = atob(b64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i)
  }
  return bytes.buffer
}

export function useAudioQueue() {
  const audioCtxRef = useRef<AudioContext | null>(null)
  const isPlayingRef = useRef(false)
  const sourceRef = useRef<AudioBufferSourceNode | null>(null)

  const { dequeueAudio, setIsAISpeaking, setCurrentEmotion } =
    useChatStore.getState()

  // Lazy-init AudioContext on first interaction (browser autoplay policy)
  const getAudioContext = useCallback((): AudioContext => {
    if (!audioCtxRef.current) {
      audioCtxRef.current = new AudioContext()
    }
    // Resume if suspended (Chrome requires user gesture)
    if (audioCtxRef.current.state === 'suspended') {
      audioCtxRef.current.resume()
    }
    return audioCtxRef.current
  }, [])

  const playNext = useCallback(async () => {
    if (isPlayingRef.current) return

    const chunk = dequeueAudio()
    if (!chunk) {
      setIsAISpeaking(false)
      return
    }

    // Text-only mode: no audio bytes, skip playback but update emotion
    if (!chunk.audio_base64) {
      setCurrentEmotion(chunk.emotion)
      // Small delay to allow UI to react to emotion change
      setTimeout(playNext, 100)
      return
    }

    isPlayingRef.current = true
    setIsAISpeaking(true)
    setCurrentEmotion(chunk.emotion)

    try {
      const ctx = getAudioContext()
      const arrayBuffer = base64ToArrayBuffer(chunk.audio_base64)
      const audioBuffer = await ctx.decodeAudioData(arrayBuffer)

      const source = ctx.createBufferSource()
      source.buffer = audioBuffer
      source.connect(ctx.destination)
      sourceRef.current = source

      source.onended = () => {
        isPlayingRef.current = false
        sourceRef.current = null
        // Immediately dequeue and play next sentence
        playNext()
      }

      source.start(0)
    } catch (err) {
      console.error('[AudioQueue] Playback error:', err)
      isPlayingRef.current = false
      playNext() // skip broken chunk, play next
    }
  }, [dequeueAudio, getAudioContext, setCurrentEmotion, setIsAISpeaking])

  const stopPlayback = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.onended = null
      try { sourceRef.current.stop() } catch { /* already stopped */ }
      sourceRef.current = null
    }
    isPlayingRef.current = false
    setIsAISpeaking(false)
  }, [setIsAISpeaking])

  // Watch audioQueue length — kick off playback when new chunks arrive
  const audioQueue = useChatStore((s) => s.audioQueue)

  useEffect(() => {
    if (audioQueue.length > 0 && !isPlayingRef.current) {
      playNext()
    }
  }, [audioQueue.length, playNext])

  // Stop + clear when queue is externally cleared (interrupt)
  useEffect(() => {
    if (audioQueue.length === 0 && isPlayingRef.current) {
      stopPlayback()
    }
  }, [audioQueue.length, stopPlayback])

  useEffect(() => {
    return () => {
      stopPlayback()
      audioCtxRef.current?.close()
    }
  }, [stopPlayback])

  return {
    audioContextRef: audioCtxRef,
    stopPlayback,
  }
}
