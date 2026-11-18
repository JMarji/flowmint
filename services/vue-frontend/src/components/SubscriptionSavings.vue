<template>
  <div v-if="summary && (summary.cancelled_count || alerts.length)" class="rounded-xl border p-5" style="background: var(--surface); border-color: var(--border)">
    <div class="flex flex-wrap items-center gap-x-8 gap-y-3">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0" style="background: var(--mint-dim)">
          <i class="pi pi-money-bill text-lg" style="color: var(--mint)"></i>
        </div>
        <div>
          <p class="text-xs" style="color: var(--text-muted)">Saved from cancelled subscriptions</p>
          <p class="text-xl font-bold" style="color: var(--mint)">
            {{ money(summary.monthly_saved) }}<span class="text-xs font-normal" style="color: var(--text-muted)">/mo</span>
          </p>
        </div>
      </div>
      <div>
        <p class="text-xs" style="color: var(--text-muted)">Per year</p>
        <p class="text-sm font-semibold" style="color: var(--text)">{{ money(summary.annual_saved) }}</p>
      </div>
      <div>
        <p class="text-xs" style="color: var(--text-muted)">Saved so far</p>
        <p class="text-sm font-semibold" style="color: var(--text)">{{ money(summary.saved_to_date) }}</p>
      </div>
      <p class="text-[11px] ml-auto" style="color: var(--text-muted)">{{ summary.cancelled_count }} cancelled</p>
    </div>

    <div v-if="alerts.length" class="mt-4 space-y-2">
      <RouterLink
        v-for="a in alerts"
        :key="a.id"
        :to="{ name: 'credit-card-detail', params: { id: a.account_db_id } }"
        class="flex items-center gap-2 rounded-lg px-3 py-2 text-xs hover:opacity-90"
        style="background: rgba(248,113,113,0.1); color: #f87171"
      >
        <i class="pi pi-exclamation-triangle"></i>
        <span class="flex-1">
          <strong>{{ a.merchant_name }}</strong> charged {{ money(a.still_charging.amount) }} on {{ fmtDate(a.still_charging.date) }}
          after you cancelled it.
        </span>
        <span>Review →</span>
      </RouterLink>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import api from '@/utils/api'

const summary = ref(null)
const subs = ref([])

const alerts = computed(() => {
  const ids = new Set(summary.value?.alert_ids || [])
  return subs.value.filter(s => ids.has(s.id))
})

const money = (v) =>
  Number(v || 0).toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })
const fmtDate = (d) => new Date(d + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

onMounted(async () => {
  try {
    const res = await api.get('/api/subscriptions')
    summary.value = res.data.summary
    subs.value = res.data.subscriptions
  } catch {
    summary.value = null
  }
})
</script>
