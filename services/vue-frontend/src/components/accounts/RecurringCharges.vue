<template>
  <div class="rounded-xl border" style="background: var(--surface); border-color: var(--border)">
    <div class="flex items-center justify-between p-4 border-b" style="border-color: var(--border)">
      <div>
        <p class="text-sm font-semibold" style="color: var(--text)">Subscriptions &amp; recurring</p>
        <p class="text-[11px]" style="color: var(--text-muted)">Detected by Plaid from this card's history</p>
      </div>
      <div v-if="data?.available && data.streams.length" class="text-right">
        <p class="text-[10px] uppercase tracking-wide" style="color: var(--text-muted)">Per month</p>
        <p class="text-sm font-bold" style="color: var(--text)">{{ money(data.monthly_total) }}</p>
      </div>
    </div>

    <div v-if="loading" class="p-4 space-y-2 animate-pulse">
      <div v-for="i in 3" :key="i" class="h-8 rounded" style="background: var(--surface-2)"></div>
    </div>
    <p v-else-if="!data?.available" class="p-4 text-xs" style="color: var(--text-muted)">
      Recurring-charge detection isn't available for this account. It needs Plaid's Recurring Transactions
      product and enough transaction history.
    </p>
    <p v-else-if="!data.streams.length" class="p-4 text-xs" style="color: var(--text-muted)">No recurring charges detected yet.</p>
    <div v-else>
      <div
        v-for="s in data.streams"
        :key="s.stream_id"
        class="flex items-center gap-3 px-4 py-2.5 border-b last:border-b-0"
        style="border-color: var(--border)"
      >
        <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background: var(--surface-2)">
          <i class="pi pi-replay text-xs" style="color: var(--mint)"></i>
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-sm truncate" style="color: var(--text)">{{ s.name }}</p>
          <p class="text-[11px]" style="color: var(--text-muted)">
            {{ freqLabel(s.frequency) }}
            <span v-if="s.next_date"> · next {{ fmtDate(s.next_date) }}</span>
            <span v-else-if="s.last_date"> · last {{ fmtDate(s.last_date) }}</span>
            <span v-if="s.status === 'EARLY_DETECTION'" class="ml-1 px-1.5 py-0.5 rounded text-[10px]" style="background: var(--surface-2)">New</span>
          </p>
        </div>
        <p class="text-sm font-semibold" style="color: var(--text)">{{ money(s.last_amount) }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import api from '@/utils/api'

const props = defineProps({ accountId: { type: [String, Number], required: true } })

const loading = ref(true)
const data = ref(null)

const load = async () => {
  loading.value = true
  try {
    const res = await api.get(`/api/accounts/${props.accountId}/credit/recurring`)
    data.value = res.data
  } catch {
    data.value = { available: false, streams: [], monthly_total: 0 }
  } finally {
    loading.value = false
  }
}

const freqLabel = (f) => ({
  WEEKLY: 'Weekly',
  BIWEEKLY: 'Every 2 weeks',
  SEMI_MONTHLY: 'Twice a month',
  MONTHLY: 'Monthly',
  ANNUALLY: 'Yearly',
}[f] || 'Irregular')

const money = (v) =>
  v == null ? '—' : Number(v).toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })
const fmtDate = (d) => new Date(d + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

onMounted(load)
watch(() => props.accountId, load)
defineExpose({ reload: load })
</script>
