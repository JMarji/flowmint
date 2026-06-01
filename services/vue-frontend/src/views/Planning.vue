<template>
  <div class="flex h-screen overflow-hidden">

    <!-- Left: plan list -->
    <aside class="w-72 flex flex-col flex-shrink-0 border-r" style="background: var(--surface); border-color: var(--border)">
      <div class="px-4 py-4 border-b" style="border-color: var(--border)">
        <h2 class="text-sm font-semibold mb-3" style="color: var(--text)">Plans</h2>
        <Button @click="showNewPlan = true" label="New Plan" icon="pi pi-plus" class="w-full p-button-primary" size="small" />
      </div>

      <div class="flex-1 overflow-y-auto p-2 space-y-0.5">
        <div
          v-for="plan in plans"
          :key="plan.id"
          @click="selectPlan(plan)"
          :class="[
            'group flex items-center justify-between gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-all',
            selectedPlan?.id === plan.id
              ? 'text-[#080C0B] bg-[#3DDBB8]'
              : 'hover:bg-[#192620]'
          ]"
          :style="selectedPlan?.id === plan.id ? '' : 'color: var(--text-muted)'"
        >
          <div class="flex items-center gap-2 min-w-0">
            <i class="pi pi-compass text-sm flex-shrink-0"></i>
            <span class="text-sm font-medium truncate" :style="selectedPlan?.id === plan.id ? 'color: #080C0B' : 'color: var(--text)'">
              {{ plan.title }}
            </span>
          </div>
          <button
            @click.stop="deletePlan(plan.id)"
            class="opacity-0 group-hover:opacity-60 hover:!opacity-100 flex-shrink-0 transition-opacity p-0.5"
            :style="selectedPlan?.id === plan.id ? 'color: #080C0B' : 'color: var(--text-muted)'"
          >
            <i class="pi pi-trash text-xs"></i>
          </button>
        </div>

        <div v-if="!plans.length && !loadingPlans" class="px-3 py-8 text-center">
          <i class="pi pi-compass text-2xl mb-2 block" style="color: var(--mint)"></i>
          <p class="text-xs" style="color: var(--text-muted)">No plans yet</p>
        </div>
      </div>
    </aside>

    <!-- Right: chat area -->
    <div class="flex-1 flex flex-col min-w-0" style="background: var(--bg)">

      <!-- Empty state -->
      <div v-if="!selectedPlan" class="flex-1 flex items-center justify-center">
        <div class="text-center max-w-sm px-6">
          <div class="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4" style="background: var(--mint-dim)">
            <i class="pi pi-compass text-2xl" style="color: var(--mint)"></i>
          </div>
          <h3 class="font-semibold mb-2" style="color: var(--text)">Financial Planning</h3>
          <p class="text-sm leading-relaxed" style="color: var(--text-muted)">
            Create a plan to explore scenarios — paying off a mortgage, making an investment, starting a project. The AI advisor has access to your actual financial data.
          </p>
          <Button @click="showNewPlan = true" label="Create your first plan" icon="pi pi-plus" class="p-button-primary mt-5" />
        </div>
      </div>

      <template v-else>
        <!-- Chat header -->
        <div class="px-6 py-4 border-b flex items-center gap-3" style="border-color: var(--border)">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style="background: var(--mint-dim)">
            <i class="pi pi-compass text-sm" style="color: var(--mint)"></i>
          </div>
          <div class="min-w-0">
            <h2 class="font-semibold text-sm truncate" style="color: var(--text)">{{ selectedPlan.title }}</h2>
            <p class="text-xs" style="color: var(--text-muted)">AI advisor · your financial data is included as context</p>
          </div>
        </div>

        <!-- Messages -->
        <div ref="messagesEl" class="flex-1 overflow-y-auto px-6 py-6 space-y-5">

          <!-- Starter prompts (shown when no messages yet) -->
          <div v-if="!messages.length && !loadingMessages" class="max-w-xl mx-auto">
            <p class="text-sm text-center mb-5" style="color: var(--text-muted)">Start the conversation — or pick a prompt to kick things off</p>
            <div class="grid gap-2">
              <button
                v-for="prompt in starterPrompts"
                :key="prompt"
                @click="sendMessage(prompt)"
                :disabled="streaming"
                class="text-left text-sm px-4 py-3 rounded-xl border transition-colors hover:border-[color:var(--mint)] hover:text-[color:var(--mint)]"
                style="border-color: var(--border); color: var(--text-muted); background: var(--surface)"
              >
                {{ prompt }}
              </button>
            </div>
          </div>

          <div v-if="loadingMessages" class="flex justify-center py-8">
            <i class="pi pi-spin pi-spinner" style="color: var(--mint)"></i>
          </div>

          <!-- Message bubbles -->
          <div
            v-for="(msg, i) in messages"
            :key="i"
            :class="['flex', msg.role === 'user' ? 'justify-end' : 'justify-start']"
          >
            <!-- Assistant avatar -->
            <div v-if="msg.role === 'assistant'" class="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mr-2 mt-0.5" style="background: var(--mint-dim)">
              <i class="pi pi-star text-xs" style="color: var(--mint)"></i>
            </div>

            <div
              :class="['max-w-2xl px-4 py-3 rounded-2xl text-sm leading-relaxed', msg.role === 'user' ? 'rounded-tr-sm' : 'rounded-tl-sm']"
              :style="msg.role === 'user'
                ? 'background: var(--mint); color: #080C0B; max-width: 70%'
                : 'background: var(--surface); color: var(--text); border: 1px solid var(--border); max-width: 80%'"
            >
              <pre class="whitespace-pre-wrap font-sans text-sm leading-relaxed">{{ msg.content }}<span v-if="msg.streaming" class="inline-block w-0.5 h-4 ml-0.5 align-text-bottom animate-pulse" style="background: currentColor"></span></pre>
            </div>
          </div>
        </div>

        <!-- Input bar -->
        <div class="px-6 py-4 border-t" style="border-color: var(--border)">
          <div class="flex gap-3 items-end">
            <Textarea
              v-model="inputText"
              @keydown.enter.exact.prevent="send"
              placeholder="Describe your scenario or ask a question… (Enter to send, Shift+Enter for new line)"
              :autoResize="true"
              rows="1"
              class="flex-1 text-sm"
              style="resize: none; max-height: 160px"
              :disabled="streaming"
            />
            <Button
              @click="send"
              icon="pi pi-send"
              :disabled="!inputText.trim() || streaming"
              class="p-button-primary flex-shrink-0"
              :loading="streaming"
            />
          </div>
          <p class="text-xs mt-2" style="color: var(--text-muted)">Shift+Enter for new line · responses include your live financial data</p>
        </div>
      </template>
    </div>

    <!-- New plan dialog -->
    <Dialog
      v-model:visible="showNewPlan"
      header="New Plan"
      modal
      :style="{ width: '380px', background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text)' }"
    >
      <div class="py-2">
        <label class="block text-xs mb-2" style="color: var(--text-muted)">What are you planning?</label>
        <InputText
          v-model="newPlanTitle"
          @keydown.enter="createPlan"
          class="w-full"
          placeholder="e.g. Pay off mortgage early, Buy a tractor, Invest in rental property"
          autofocus
        />
        <p class="text-xs mt-2" style="color: var(--text-muted)">Give it a descriptive name — you'll be able to chat through the details with the AI advisor.</p>
      </div>
      <template #footer>
        <Button @click="showNewPlan = false" label="Cancel" severity="secondary" text />
        <Button @click="createPlan" label="Create Plan" class="p-button-primary" :disabled="!newPlanTitle.trim()" :loading="creatingPlan" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import api from '@/utils/api'

const plans = ref([])
const selectedPlan = ref(null)
const messages = ref([])
const inputText = ref('')
const streaming = ref(false)
const loadingPlans = ref(false)
const loadingMessages = ref(false)
const showNewPlan = ref(false)
const newPlanTitle = ref('')
const creatingPlan = ref(false)
const messagesEl = ref(null)

const starterPrompts = [
  'What happens if I pay an extra $500/month toward my mortgage?',
  'How long would it take to pay off my mortgage completely if I doubled my payment?',
  'What would my finances look like if I bought another property?',
  'How would investing $20,000 affect my net worth over 10 years?',
  'What cash flow would I need to make a new business investment worthwhile?',
]

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesEl.value) {
      messagesEl.value.scrollTop = messagesEl.value.scrollHeight
    }
  })
}

const loadPlans = async () => {
  loadingPlans.value = true
  try {
    const res = await api.get('/api/plans')
    plans.value = res.data
  } finally {
    loadingPlans.value = false
  }
}

const selectPlan = async (plan) => {
  if (selectedPlan.value?.id === plan.id) return
  selectedPlan.value = plan
  messages.value = []
  loadingMessages.value = true
  try {
    const res = await api.get(`/api/plans/${plan.id}/messages`)
    messages.value = res.data
    scrollToBottom()
  } finally {
    loadingMessages.value = false
  }
}

const createPlan = async () => {
  if (!newPlanTitle.value.trim() || creatingPlan.value) return
  creatingPlan.value = true
  try {
    const res = await api.post('/api/plans', { title: newPlanTitle.value.trim() })
    plans.value.unshift(res.data)
    newPlanTitle.value = ''
    showNewPlan.value = false
    await selectPlan(res.data)
  } finally {
    creatingPlan.value = false
  }
}

const deletePlan = async (id) => {
  if (!confirm('Delete this plan and all its conversation history?')) return
  await api.delete(`/api/plans/${id}`)
  plans.value = plans.value.filter(p => p.id !== id)
  if (selectedPlan.value?.id === id) {
    selectedPlan.value = null
    messages.value = []
  }
}

const send = () => {
  const text = inputText.value.trim()
  if (!text || streaming.value || !selectedPlan.value) return
  inputText.value = ''
  sendMessage(text)
}

const sendMessage = async (text) => {
  if (streaming.value) return
  messages.value.push({ role: 'user', content: text })
  scrollToBottom()

  const assistantIdx = messages.value.length
  messages.value.push({ role: 'assistant', content: '', streaming: true })
  streaming.value = true

  try {
    const baseUrl = api.defaults.baseURL || ''
    const token = window.localStorage.getItem('access_token')

    const response = await fetch(`${baseUrl}/api/plans/${selectedPlan.value.id}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ content: text }),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() // keep incomplete last line

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const payload = line.slice(6).trim()
        if (payload === '[DONE]') break
        try {
          const { text: token, error } = JSON.parse(payload)
          if (error) {
            messages.value[assistantIdx].content = `Error: ${error}`
          } else if (token) {
            messages.value[assistantIdx].content += token
            scrollToBottom()
          }
        } catch {}
      }
    }
  } catch (e) {
    messages.value[assistantIdx].content = 'Something went wrong. Please try again.'
  } finally {
    if (messages.value[assistantIdx]) {
      messages.value[assistantIdx].streaming = false
    }
    streaming.value = false
    scrollToBottom()
  }
}

onMounted(loadPlans)
</script>
