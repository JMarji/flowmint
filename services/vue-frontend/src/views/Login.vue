<template>
  <div class="min-h-screen flex items-center justify-center px-4" style="background: var(--bg)">
    <!-- Background glow -->
    <div class="absolute top-1/4 left-1/2 -translate-x-1/2 w-96 h-96 rounded-full blur-3xl opacity-10 pointer-events-none" style="background: var(--mint)"></div>

    <div class="w-full max-w-sm relative">
      <!-- Logo -->
      <div class="flex items-center justify-center gap-2 mb-10">
        <div class="w-9 h-9 rounded-xl flex items-center justify-center" style="background: var(--mint)">
          <svg width="20" height="20" viewBox="0 0 16 16" fill="none">
            <path d="M8 2L13 5V11L8 14L3 11V5L8 2Z" fill="#080C0B"/>
            <path d="M8 5L11 6.8V10.2L8 12L5 10.2V6.8L8 5Z" fill="var(--mint)"/>
          </svg>
        </div>
        <span class="text-2xl font-bold tracking-tight" style="color: var(--mint)">flowmint</span>
      </div>

      <!-- Card -->
      <div class="rounded-2xl border p-8" style="background: var(--surface); border-color: var(--border)">
        <h1 class="text-xl font-semibold mb-1" style="color: var(--text)">Welcome back</h1>
        <p class="text-sm mb-6" style="color: var(--text-muted)">Sign in to your account</p>

        <form @submit.prevent="handleLogin" class="space-y-4">
          <div>
            <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted)">Email</label>
            <InputText v-model="email" type="email" placeholder="you@example.com" class="w-full" autocomplete="email" />
          </div>
          <div>
            <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted)">Password</label>
            <Password v-model="password" :feedback="false" toggleMask placeholder="••••••••" class="w-full" inputClass="w-full" autocomplete="current-password" />
          </div>

          <p v-if="errorMsg" class="text-xs px-3 py-2 rounded-lg" style="color: #f87171; background: rgba(248,113,113,0.1)">{{ errorMsg }}</p>

          <Button type="submit" :loading="loading" label="Sign in" class="w-full p-button-primary mt-2" />
        </form>

        <p class="text-center text-sm mt-6" style="color: var(--text-muted)">
          Don't have an account?
          <RouterLink to="/register" class="font-medium" style="color: var(--mint)">Register</RouterLink>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import { useAuth } from '@/composables/useAuth'

const auth = useAuth()
const router = useRouter()
const email = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')

const handleLogin = async () => {
  errorMsg.value = ''
  loading.value = true
  try {
    await auth.login(email.value, password.value)
    router.push({ name: 'dashboard' })
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || 'Invalid credentials'
  } finally {
    loading.value = false
  }
}
</script>
