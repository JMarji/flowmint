import axios from 'axios'
import router from '@/router'

const BASE_URL = import.meta.env.VITE_API_BASE || ''

let resolvedBase = BASE_URL
if (!resolvedBase && typeof window !== 'undefined') {
  const devPorts = new Set(['5173', '4173'])
  if (devPorts.has(window.location.port) || window.location.hostname === 'localhost') {
    resolvedBase = `${window.location.protocol}//${window.location.hostname}:8000`
  }
}

const api = axios.create({ baseURL: resolvedBase, withCredentials: true })

let subscribers = []
function onRefreshed(token) { subscribers.forEach(cb => cb(token)); subscribers = [] }
function addSubscriber(cb) { subscribers.push(cb) }

api.interceptors.request.use(async (config) => {
  try {
    const mod = await import('@/composables/useAuth')
    const { accessToken } = mod.useAuth()
    const token = (accessToken && accessToken.value) || window.localStorage?.getItem('access_token')
    if (token) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${token}`
    }
  } catch (e) {}
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const { response, config } = error || {}
    if (!response || response.status !== 401) return Promise.reject(error)

    const original = config
    if (original?.url?.includes('/auth/token')) return Promise.reject(error)
    if (original?.url?.includes('/auth/refresh')) {
      const mod = await import('@/composables/useAuth')
      await mod.useAuth().logout()
      return Promise.reject(error)
    }

    const mod = await import('@/composables/useAuth')
    const auth = mod.useAuth()

    if (auth.isRefreshing.value) {
      return new Promise((resolve) => {
        addSubscriber((token) => {
          original.headers.Authorization = `Bearer ${token}`
          resolve(api(original))
        })
      })
    }

    try {
      const token = await auth.refresh()
      if (!token) {
        await auth.logout()
        router.push({ name: 'login' })
        return Promise.reject(error)
      }
      onRefreshed(token)
      original.headers = original.headers || {}
      original.headers.Authorization = `Bearer ${token}`
      return api(original)
    } catch (e) {
      await auth.logout()
      router.push({ name: 'login' })
      return Promise.reject(e)
    }
  }
)

export default api
