import { ref } from 'vue'
import api from '@/utils/api'

const STORAGE_KEY = 'plaid:lastSyncedAt'

const readStoredTimestamp = () => {
  if (typeof window === 'undefined') return 0
  const raw = window.localStorage.getItem(STORAGE_KEY)
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : 0
}

const lastSyncedAt = ref(readStoredTimestamp())
const syncing = ref(false)
const error = ref('')

const writeStoredTimestamp = (timestamp) => {
  lastSyncedAt.value = timestamp
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(STORAGE_KEY, String(timestamp))
  }
}

export function usePlaidSync() {
  const syncNow = async ({ force = false, minIntervalMs = 20_000 } = {}) => {
    const ageMs = Date.now() - (lastSyncedAt.value || 0)

    if (!force && ageMs >= 0 && ageMs < minIntervalMs) {
      return { skipped: true, reason: 'recently-synced' }
    }
    if (syncing.value) {
      return { skipped: true, reason: 'sync-in-flight' }
    }

    syncing.value = true
    error.value = ''
    try {
      const res = await api.post('/api/plaid/sync')
      writeStoredTimestamp(Date.now())
      return { skipped: false, data: res.data }
    } catch (e) {
      error.value = e?.response?.data?.detail || e?.message || 'Failed to sync Plaid data'
      throw e
    } finally {
      syncing.value = false
    }
  }

  const syncIfStale = async ({ maxAgeMs = 5 * 60_000 } = {}) => {
    const ageMs = Date.now() - (lastSyncedAt.value || 0)
    if (ageMs >= 0 && ageMs < maxAgeMs) {
      return { skipped: true, reason: 'data-fresh' }
    }
    return syncNow({ force: false })
  }

  return {
    syncing,
    error,
    lastSyncedAt,
    syncNow,
    syncIfStale,
  }
}
