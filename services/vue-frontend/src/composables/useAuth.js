import { ref, readonly } from 'vue'
import axios from 'axios'

const accessToken = ref(null)
const currentUser = ref(null)
const isRefreshing = ref(false)
let refreshPromise = null
let refreshAxios = null

function getRefreshAxios(baseURL) {
  if (!refreshAxios) refreshAxios = axios.create({ baseURL, withCredentials: true })
  return refreshAxios
}

export function useAuth() {
  const setToken = (token) => {
    accessToken.value = token
    try {
      if (typeof window !== 'undefined') {
        token ? window.localStorage.setItem('access_token', token)
               : window.localStorage.removeItem('access_token')
      }
    } catch (e) {}
  }

  const login = async (email, password) => {
    const { default: api } = await import('@/utils/api')
    const res = await api.post('/auth/token', { email, password })
    setToken(res.data.access_token)
    const me = await api.get('/auth/me')
    currentUser.value = me.data
    return currentUser.value
  }

  const register = async (email, password) => {
    const { default: api } = await import('@/utils/api')
    const res = await api.post('/auth/register', { email, password })
    return res.data
  }

  const refresh = async () => {
    if (refreshPromise) return refreshPromise
    let baseURL = ''
    if (typeof window !== 'undefined') {
      const devPorts = new Set(['5173', '4173'])
      if (devPorts.has(window.location.port) || window.location.hostname === 'localhost') {
        baseURL = `${window.location.protocol}//${window.location.hostname}:8000`
      }
    }
    isRefreshing.value = true
    refreshPromise = (async () => {
      try {
        const res = await getRefreshAxios(baseURL).post('/auth/refresh')
        const token = res.data?.access_token || null
        if (token) setToken(token)
        return token
      } finally {
        isRefreshing.value = false
        refreshPromise = null
      }
    })()
    return refreshPromise
  }

  const logout = async () => {
    try {
      const { default: api } = await import('@/utils/api')
      await api.post('/auth/logout')
    } catch (e) {}
    setToken(null)
    currentUser.value = null
    refreshPromise = null
  }

  const me = async () => {
    const { default: api } = await import('@/utils/api')
    const res = await api.get('/auth/me')
    currentUser.value = res.data
    return currentUser.value
  }

  return {
    accessToken: readonly(accessToken),
    currentUser: readonly(currentUser),
    isRefreshing,
    login,
    register,
    logout,
    refresh,
    me,
    _setToken: setToken
  }
}
