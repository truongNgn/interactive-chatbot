const BACKEND_HOST = import.meta.env.VITE_BACKEND_HOST ?? 'localhost'
const BACKEND_PORT = import.meta.env.VITE_BACKEND_PORT ?? '8001'

export const API_BASE_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`
export const WS_BASE_URL = `ws://${BACKEND_HOST}:${BACKEND_PORT}`
