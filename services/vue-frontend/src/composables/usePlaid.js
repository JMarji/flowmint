import { ref } from 'vue'
import api from '@/utils/api'

export function usePlaid() {
  const isLinking = ref(false)
  const error = ref(null)

  const openLink = async (onSuccess) => {
    error.value = null
    isLinking.value = true
    try {
      const res = await api.get('/api/plaid/link-token')
      const linkToken = res.data.link_token
      if (!linkToken) throw new Error('No link token received')

      const handler = window.Plaid.create({
        token: linkToken,
        onSuccess: async (publicToken, metadata) => {
          try {
            await api.post('/api/plaid/exchange', { public_token: publicToken })
            if (onSuccess) await onSuccess(metadata)
          } catch (e) {
            error.value = e?.response?.data?.detail || e?.message || 'Failed to link bank account'
          } finally {
            isLinking.value = false
          }
        },
        onExit: (err) => {
          if (err) error.value = err.display_message || 'Bank linking cancelled'
          isLinking.value = false
        },
        onLoad: () => {},
        onEvent: () => {}
      })
      handler.open()
    } catch (e) {
      error.value = e.message || 'Failed to open bank link'
      isLinking.value = false
    }
  }

  return { isLinking, error, openLink }
}
