<template>
  <Dialog
    :visible="visible"
    @update:visible="emit('update:visible', $event)"
    :header="`Cancel ${stream?.name || 'subscription'}`"
    modal
    :style="{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text)', width: '480px', maxWidth: '95vw' }"
  >
    <div v-if="stream" class="space-y-4 py-1">
      <!-- Cost -->
      <div class="rounded-lg p-3 flex items-center justify-between" style="background: var(--surface-2)">
        <div>
          <p class="text-lg font-bold" style="color: var(--text)">{{ money(stream.monthly_equivalent) }}<span class="text-xs font-normal" style="color: var(--text-muted)">/mo</span></p>
          <p class="text-[11px]" style="color: var(--text-muted)">{{ money(stream.monthly_equivalent * 12) }} a year</p>
        </div>
        <div v-if="stream.next_date" class="text-right">
          <p class="text-[11px]" style="color: var(--text-muted)">Next charge</p>
          <p class="text-sm font-semibold" :style="{ color: daysToNext <= 3 ? '#fb923c' : 'var(--text)' }">{{ fmtDate(stream.next_date) }}</p>
          <p v-if="daysToNext != null && daysToNext >= 0" class="text-[10px]" style="color: var(--text-muted)">cancel before then</p>
        </div>
      </div>

      <!-- Billed through an intermediary -->
      <div v-if="info.via" class="text-xs rounded-lg px-3 py-2 flex gap-2" style="background: rgba(96,165,250,0.12); color: #93c5fd">
        <i class="pi pi-info-circle mt-0.5"></i>
        <span>This charge comes through <strong>{{ info.name }}</strong>. Cancel it there — the original app or service can't stop it.</span>
      </div>

      <!-- How to cancel -->
      <div v-if="info.matched" class="space-y-3">
        <a
          v-if="info.url"
          :href="info.url"
          target="_blank"
          rel="noopener noreferrer"
          class="flex items-center justify-center gap-2 w-full rounded-lg py-2.5 text-sm font-semibold transition hover:opacity-90"
          style="background: var(--mint); color: #080C0B"
        >
          Open {{ info.name }} <i class="pi pi-external-link text-xs"></i>
        </a>
        <div>
          <p class="text-xs font-medium mb-1.5" style="color: var(--text-muted)">How to cancel</p>
          <ol class="space-y-1.5">
            <li v-for="(step, i) in info.steps" :key="i" class="flex gap-2 text-sm" style="color: var(--text)">
              <span class="flex-shrink-0 w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center" style="background: var(--surface-2); color: var(--mint)">{{ i + 1 }}</span>
              <span>{{ step }}</span>
            </li>
          </ol>
        </div>
        <p v-if="info.notes" class="text-xs" style="color: var(--text-muted)"><i class="pi pi-lightbulb text-[10px]"></i> {{ info.notes }}</p>
      </div>

      <div v-else class="space-y-2 text-sm" style="color: var(--text)">
        <p class="text-xs" style="color: var(--text-muted)">We don't have cancellation steps for this merchant yet. Usually one of these works:</p>
        <ul class="text-xs space-y-1 list-disc pl-5" style="color: var(--text-muted)">
          <li>Look for "Manage subscription" in a receipt email from them</li>
          <li>Sign in → Account / Billing / Membership settings</li>
          <li>If you signed up in a phone app, cancel in the App Store or Google Play</li>
        </ul>
        <a :href="info.search_url" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 text-xs hover:underline" style="color: var(--mint)">
          Search how to cancel {{ stream.name }} <i class="pi pi-external-link text-[10px]"></i>
        </a>
      </div>

      <p class="text-[11px] pt-3 border-t" style="border-color: var(--border); color: var(--text-muted)">
        Once you mark it cancelled, Flowmint watches your accounts and alerts you if {{ stream.name }} charges you again.
      </p>

      <div class="flex items-center gap-2 text-xs" style="color: var(--text-muted)">
        <label for="cancelled-on">Cancelled on</label>
        <input id="cancelled-on" v-model="cancelledOn" type="date" :max="todayIso" class="px-2 py-1 rounded-md text-xs" style="background: var(--surface-2); border: 1px solid var(--border); color: var(--text); color-scheme: dark" />
      </div>

      <p v-if="error" class="text-xs px-3 py-2 rounded-lg" style="color: #f87171; background: rgba(248,113,113,0.1)">{{ error }}</p>
    </div>

    <template #footer>
      <Button label="Keep it" text severity="secondary" :disabled="saving" @click="decide('kept')" />
      <Button label="I cancelled it" icon="pi pi-check" class="p-button-primary" :loading="saving" @click="decide('cancelled')" />
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import api from '@/utils/api'

const props = defineProps({
  visible: { type: Boolean, default: false },
  accountId: { type: [String, Number], required: true },
  stream: { type: Object, default: null },
})
const emit = defineEmits(['update:visible', 'saved'])

const localIso = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
const todayIso = localIso(new Date())
const cancelledOn = ref(todayIso)
const saving = ref(false)
const error = ref('')

watch(() => props.visible, (v) => {
  if (v) { cancelledOn.value = todayIso; error.value = '' }
})

const info = computed(() => props.stream?.cancel_info || { matched: false, via: false, steps: [] })

const daysToNext = computed(() => {
  if (!props.stream?.next_date) return null
  const today = new Date(); today.setHours(0, 0, 0, 0)
  return Math.round((new Date(props.stream.next_date + 'T00:00:00') - today) / 86400000)
})

const decide = async (status) => {
  saving.value = true
  error.value = ''
  const s = props.stream
  try {
    await api.post('/api/subscriptions', {
      account_db_id: Number(props.accountId),
      stream_id: s.stream_id,
      merchant_name: s.name,
      frequency: s.frequency,
      last_amount: s.last_amount,
      monthly_amount: s.monthly_equivalent,
      next_date: s.next_date,
      status,
      cancelled_on: status === 'cancelled' ? cancelledOn.value : null,
    })
    emit('saved', status)
    emit('update:visible', false)
  } catch (e) {
    error.value = typeof e?.response?.data?.detail === 'string' ? e.response.data.detail : 'Could not save — try again'
  } finally {
    saving.value = false
  }
}

const money = (v) =>
  v == null ? '—' : Number(v).toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })
const fmtDate = (d) => new Date(d + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
</script>
