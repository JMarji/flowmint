import { createApp } from 'vue'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import { definePreset } from '@primevue/themes'
import ToastService from 'primevue/toastservice'
import 'primeicons/primeicons.css'

import App from './App.vue'
import router from './router'
import './style.css'

const MintPreset = definePreset(Aura, {
  semantic: {
    primary: {
      50:  '#f0fdf9',
      100: '#ccfbef',
      200: '#99f6df',
      300: '#6EEBD0',
      400: '#3DDBB8',
      500: '#27B898',
      600: '#1e9a80',
      700: '#1a7d68',
      800: '#175f4f',
      900: '#124d40',
      950: '#0a2d25',
    }
  }
})

const app = createApp(App)

app.use(PrimeVue, {
  theme: {
    preset: MintPreset,
    options: {
      darkModeSelector: 'html',
      cssLayer: false
    }
  }
})
app.use(ToastService)
app.use(router)

// Bootstrap auth on startup — attempt a silent token refresh
import { useAuth } from '@/composables/useAuth'
const auth = useAuth()
auth.refresh().catch(() => {})

app.mount('#app')
