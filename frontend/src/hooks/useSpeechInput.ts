import { useCallback, useMemo, useRef, useState } from 'react'
import { API_BASE_URL } from '../config/backend'

type SpeechState = 'idle' | 'listening' | 'recording' | 'processing' | 'uploading' | 'error'

interface UseSpeechInputOptions {
  onTranscript: (text: string) => void
  pauseVAD: () => void
  resumeVAD: () => void
  getStream: () => MediaStream | null
  maxRecordingSeconds: number
}

interface SpeechInputResult {
  supported: boolean
  state: SpeechState
  mode: 'backend' | 'browser'
  permissionDenied: boolean
  errorMessage: string | null
  micLevel: number
  remainingSeconds: number
  startRecording: () => void
  stopRecording: () => void
}

export function useSpeechInput({
  onTranscript,
  pauseVAD,
  resumeVAD,
  getStream,
  maxRecordingSeconds,
}: UseSpeechInputOptions): SpeechInputResult {
  const [state, setState] = useState<SpeechState>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [permissionDenied, setPermissionDenied] = useState(false)
  const [remainingSeconds, setRemainingSeconds] = useState(maxRecordingSeconds)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<BlobPart[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const supported = typeof MediaRecorder !== 'undefined'

  const cleanupTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const uploadAudio = useCallback(async (blob: Blob) => {
    setState('uploading')
    try {
      const form = new FormData()
      form.append('audio', blob, 'speech.webm')
      form.append('mime_type', blob.type || 'audio/webm')
      const response = await fetch(`${API_BASE_URL}/api/stt`, {
        method: 'POST',
        body: form,
      })
      if (!response.ok) throw new Error(`STT failed: ${response.status}`)
      const payload = (await response.json()) as { text?: string }
      if (payload.text?.trim()) onTranscript(payload.text)
      setState('idle')
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Voice input failed')
      setState('error')
    } finally {
      resumeVAD()
    }
  }, [onTranscript, resumeVAD])

  const stopRecording = useCallback(() => {
    cleanupTimer()
    const recorder = recorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop()
    }
  }, [cleanupTimer])

  const startRecording = useCallback(async () => {
    if (!supported) return
    setErrorMessage(null)
    setPermissionDenied(false)
    try {
      pauseVAD()
      const stream = getStream() ?? await navigator.mediaDevices.getUserMedia({ audio: true })
      chunksRef.current = []
      const recorder = new MediaRecorder(stream)
      recorderRef.current = recorder
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data)
      }
      recorder.onstop = () => {
        cleanupTimer()
        setState('processing')
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        void uploadAudio(blob)
      }
      setRemainingSeconds(maxRecordingSeconds)
      timerRef.current = setInterval(() => {
        setRemainingSeconds((current) => {
          if (current <= 1) {
            stopRecording()
            return 0
          }
          return current - 1
        })
      }, 1000)
      recorder.start()
      setState('recording')
    } catch (error) {
      resumeVAD()
      setPermissionDenied(true)
      setErrorMessage(error instanceof Error ? error.message : 'Microphone access failed')
      setState('error')
    }
  }, [cleanupTimer, getStream, maxRecordingSeconds, pauseVAD, resumeVAD, stopRecording, supported, uploadAudio])

  return useMemo(() => ({
    supported,
    state,
    mode: 'backend',
    permissionDenied,
    errorMessage,
    micLevel: state === 'recording' ? 0.5 : 0,
    remainingSeconds,
    startRecording,
    stopRecording,
  }), [
    errorMessage,
    permissionDenied,
    remainingSeconds,
    startRecording,
    state,
    stopRecording,
    supported,
  ])
}
