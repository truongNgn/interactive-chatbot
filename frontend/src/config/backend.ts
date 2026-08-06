let rawHost = import.meta.env.VITE_BACKEND_HOST || 'localhost'
rawHost = rawHost.replace(/^https?:\/\//i, '').replace(/\/+$/, '')

const BACKEND_HOST = rawHost
const BACKEND_PORT = import.meta.env.VITE_BACKEND_PORT || '8001'

const isLocalhost = BACKEND_HOST === 'localhost' || BACKEND_HOST === '127.0.0.1'

export const API_BASE_URL = isLocalhost
  ? `http://${BACKEND_HOST}:${BACKEND_PORT}`
  : `https://${BACKEND_HOST}`

export const WS_BASE_URL = isLocalhost
  ? `ws://${BACKEND_HOST}:${BACKEND_PORT}`
  : `wss://${BACKEND_HOST}`

