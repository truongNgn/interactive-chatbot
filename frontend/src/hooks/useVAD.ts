import { useCallback, useRef, useState } from 'react'

const RMS_THRESHOLD = 0.015   // ~-36dBFS — bắt giọng nói, bỏ qua tiếng ồn nền nhẹ
const INTERRUPT_COOLDOWN_MS = 300  // tránh trigger liên tục

interface UseVADOptions {
  onVoiceDetected: () => void
  isAISpeaking: () => boolean
}

interface UseVADReturn {
  startListening: () => Promise<void>
  stopListening: () => void
  pauseVAD: () => void
  resumeVAD: () => void
  getStream: () => MediaStream | null
  isListening: boolean
}

export function useVAD({ onVoiceDetected, isAISpeaking }: UseVADOptions): UseVADReturn {
  const [isListening, setIsListening] = useState(false)

  const audioCtxRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const lastInterruptRef = useRef<number>(0)
  const dataArrayRef = useRef<Float32Array | null>(null)
  const isListeningRef = useRef(false)
  const onVoiceDetectedRef = useRef(onVoiceDetected)
  const isAISpeakingRef = useRef(isAISpeaking)

  onVoiceDetectedRef.current = onVoiceDetected
  isAISpeakingRef.current = isAISpeaking

  const pauseVAD = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  const resumeVAD = useCallback(() => {
    if (intervalRef.current || !analyserRef.current || !dataArrayRef.current) return

    intervalRef.current = setInterval(() => {
      if (!analyserRef.current || !dataArrayRef.current) return

      analyserRef.current.getFloatTimeDomainData(dataArrayRef.current as Float32Array<ArrayBuffer>)

      // Tính RMS (Root Mean Square) của frame hiện tại
      let sumSq = 0
      for (const sample of dataArrayRef.current) {
        sumSq += sample * sample
      }
      const rms = Math.sqrt(sumSq / dataArrayRef.current.length)

      const now = Date.now()
      if (
        rms > RMS_THRESHOLD &&
        isAISpeakingRef.current() &&
        now - lastInterruptRef.current > INTERRUPT_COOLDOWN_MS
      ) {
        lastInterruptRef.current = now
        onVoiceDetectedRef.current()
      }
    }, 100)
  }, [])

  const stopListening = useCallback(() => {
    pauseVAD()
    sourceRef.current?.disconnect()
    streamRef.current?.getTracks().forEach(t => t.stop())
    audioCtxRef.current?.close()

    audioCtxRef.current = null
    analyserRef.current = null
    sourceRef.current = null
    streamRef.current = null
    dataArrayRef.current = null
    isListeningRef.current = false
    setIsListening(false)
  }, [pauseVAD])

  const startListening = useCallback(async () => {
    if (isListeningRef.current) return

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
      streamRef.current = stream

      const ctx = new AudioContext()
      audioCtxRef.current = ctx

      const analyser = ctx.createAnalyser()
      analyser.fftSize = 512
      analyserRef.current = analyser

      const source = ctx.createMediaStreamSource(stream)
      source.connect(analyser)
      sourceRef.current = source

      dataArrayRef.current = new Float32Array(analyser.fftSize) as Float32Array<ArrayBuffer>

      isListeningRef.current = true
      setIsListening(true)
      resumeVAD()
    } catch (err) {
      console.warn('VAD: microphone access denied or unavailable', err)
    }
  }, [resumeVAD])

  const getStream = useCallback(() => streamRef.current, [])

  return { startListening, stopListening, pauseVAD, resumeVAD, getStream, isListening }
}
