<template>
  <div class="p-6 max-w-5xl mx-auto">
    <div class="flex items-center justify-between gap-3 mb-6">
      <div>
        <h1 class="text-2xl font-bold" style="color: var(--text)">Subscriptions</h1>
        <p class="text-sm mt-1" style="color: var(--text-muted)">Recurring charges across all your accounts</p>
      </div>
      <Button @click="refresh" :loading="refreshing" icon="pi pi-refresh" severity="secondary" text rounded title="Refresh" />
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-3 animate-pulse">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div v-for="i in 4" :key="i" class="h-20 rounded-xl" style="background: var(--surface-2)"></div>
      </div>
      <div v-for="i in 5" :key="'r' + i" class="h-14 rounded-xl" style="background: var(--surface-2)"></div>
    </div>

    <p v-else-if="error" class="text-sm px-3 py-2 rounded-lg" style="color: #f87171; background: rgba(248,113,113,0.1)">{{ error }}</p>

    <template v-else>
      <!-- Summary -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--mint)">
          <p class="text-xs" style="color: var(--text-muted)">Subscriptions</p>
          <p class="text-xl font-bold mt-0.5" style="color: var(--text)">{{ money(summary.subscriptions_monthly) }}<span class="text-xs font-normal" style="color: var(--text-muted)">/mo</span></p>
          <p class="text-[11px]" style="color: var(--text-muted)">{{ summary.subscription_count }} active · {{ money(summary.subscriptions_monthly * 12) }}/yr</p>
        </div>
        <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
          <p class="text-xs" style="color: var(--text-muted)">Next 7 days</p>
          <p class="text-xl font-bold mt-0.5" style="color: var(--text)">{{ money(nextWeek.total) }}</p>
          <p class="text-[11px]" style="color: var(--text-muted)">{{ nextWeek.count }} charge{{ nextWeek.count === 1 ? '' : 's' }} expected</p>
        </div>
        <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
          <p class="text-xs" style="color: var(--text-muted)">Saved by cancelling</p>
          <p class="text-xl font-bold mt-0.5" style="color: var(--mint)">{{ money(summary.monthly_saved) }}<span class="text-xs font-normal" style="color: var(--text-muted)">/mo</span></p>
          <p class="text-[11px]" style="color: var(--text-muted)">{{ money(summary.saved_to_date) }} so far</p>
        </div>
        <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
          <p class="text-xs" style="color: var(--text-muted)">Other recurring</p>
          <p class="text-xl font-bold mt-0.5" style="color: var(--text)">{{ money(summary.bills_monthly) }}<span class="text-xs font-normal" style="color: var(--text-muted)">/mo</span></p>
          <p class="text-[11px]" style="color: var(--text-muted)">Rent, loans, transfers</p>
        </div>
      </div>

      <!-- Still-charging alerts -->
      <div v-for="c in alerts" :key="'alert-' + c.tracking.id" class="mb-3 rounded-xl border p-4" style="border-color: #f87171; background: rgba(248,113,113,0.08)">
        <div class="flex items-start gap-3">
          <i class="pi pi-exclamation-triangle mt-0.5" style="color: #f87171"></i>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-semibold" style="color: #f87171">{{ c.name }} is still charging you</p>
            <p class="text-xs mt-0.5" style="color: var(--text)">
              {{ money(c.tracking.still_charging.amount) }} on {{ fmtDate(c.tracking.still_charging.date) }}
              <span v-if="c.tracking.still_charging.account_name" style="color: var(--text-muted)">({{ c.tracking.still_charging.account_name }})</span>
              — after you cancelled on {{ fmtDate(c.tracking.cancelled_on) }}.
              Check the merchant confirmed it; if they did, dispute the charge with your card issuer.
            </p>
            <div class="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs">
              <button class="hover:underline" style="color: var(--mint)" @click="openCancel(c)">How to cancel</button>
              <button class="hover:underline" style="color: var(--mint)" :disabled="busy" @click="recancel(c)">I cancelled it again</button>
              <button class="hover:underline" style="color: var(--text-muted)" :disabled="busy" @click="dismiss(c)">Dismiss</button>
            </div>
          </div>
        </div>
      </div>

      <p v-if="data.unavailable_institutions.length" class="mb-4 text-xs px-3 py-2 rounded-lg" style="color: var(--text-muted); background: var(--surface-2)">
        <i class="pi pi-info-circle text-[10px]"></i>
        Recurring charges aren't available from {{ data.unavailable_institutions.join(', ') }}.
        Plaid needs its Recurring Transactions product and some transaction history for these.
      </p>

      <!-- Controls -->
      <div class="flex flex-col sm:flex-row sm:items-center gap-3 mb-3">
        <div class="flex rounded-lg overflow-hidden border text-xs self-start max-w-full overflow-x-auto" style="border-color: var(--border)">
          <button
            v-for="t in tabs"
            :key="t.key"
            type="button"
            class="px-3 py-1.5"
            :style="tab === t.key ? 'background: var(--mint); color: #080C0B; font-weight: 600' : 'background: var(--surface-2); color: var(--text-muted)'"
            @click="tab = t.key"
            style="white-space: nowrap"
          >{{ t.label }} <span class="opacity-70">{{ t.count }}</span></button>
        </div>
        <div class="flex gap-2 sm:ml-auto min-w-0">
          <select v-model="accountFilter" class="field-select min-w-0 flex-1 sm:flex-none sm:max-w-[260px]" aria-label="Filter by account">
            <option value="">All accounts</option>
            <option v-for="a in accountOptions" :key="a.key" :value="a.key">{{ a.label }}</option>
          </select>
          <select v-model="sortBy" class="field-select flex-shrink-0" aria-label="Sort">
            <option value="cost">Highest cost</option>
            <option value="next">Next charge</option>
            <option value="name">Name</option>
          </select>
        </div>
      </div>

      <!-- List -->
      <div class="rounded-xl border" style="background: var(--surface); border-color: var(--border)">
        <p v-if="!data.available && !data.cancelled.length" class="p-6 text-sm text-center" style="color: var(--text-muted)">
          Recurring-charge detection isn't available for any linked account yet.
        </p>
        <p v-else-if="!rows.length" class="p-6 text-sm text-center" style="color: var(--text-muted)">Nothing here.</p>

        <div
          v-for="s in rows"
          :key="(s.account_id || '') + s.stream_id"
          class="flex items-center gap-3 px-4 py-3 border-b last:border-b-0"
          style="border-color: var(--border)"
        >
          <div class="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0" style="background: var(--surface-2)">
            <i :class="`pi ${rowIcon(s)} text-sm`" :style="{ color: rowIconColor(s) }"></i>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm truncate" :class="{ 'line-through decoration-1': tab === 'cancelled' }" :style="{ color: tab === 'cancelled' ? 'var(--text-muted)' : 'var(--text)' }">
              {{ s.name }}
              <span v-if="s.tracking?.status === 'kept'" class="chip" style="background: var(--surface-2); color: var(--text-muted)">Kept</span>
              <span v-if="s.price_increase" class="chip" style="background: rgba(251,146,60,0.16); color: #fb923c" :title="`Was ${money(s.tracking.kept_amount)} when you chose to keep it`">↑ {{ money(s.price_increase) }}</span>
              <span v-if="s.status === 'EARLY_DETECTION'" class="chip" style="background: var(--surface-2); color: var(--text-muted)">New</span>
            </p>
            <p class="text-[11px] truncate" style="color: var(--text-muted)">
              <RouterLink
                v-if="s.account && s.account.type === 'credit'"
                :to="{ name: 'credit-card-detail', params: { id: s.account.db_id } }"
                class="hover:underline"
              >{{ accountLabel(s.account) }}</RouterLink>
              <span v-else>{{ accountLabel(s.account) }}</span>
              <template v-if="tab === 'cancelled'">
                · Cancelled {{ fmtDate(s.tracking.cancelled_on) }}
                <span v-if="s.tracking.still_charging" style="color: #f87171"> · still charging</span>
                <span v-else> · no charges since</span>
              </template>
              <template v-else>
                · {{ freqLabel(s.frequency) }}
                <span v-if="s.next_date"> · next {{ fmtDate(s.next_date) }}</span>
              </template>
            </p>
          </div>
          <div class="text-right">
            <p class="text-sm font-semibold" :style="{ color: tab === 'cancelled' && !s.tracking.still_charging ? 'var(--mint)' : 'var(--text)' }">
              {{ tab === 'cancelled' && !s.tracking.still_charging ? '+' : '' }}{{ money(tab === 'cancelled' ? s.monthly_equivalent : s.last_amount) }}<span v-if="tab === 'cancelled'" class="text-[10px] font-normal">/mo</span>
            </p>
            <p v-if="tab !== 'cancelled' && s.frequency !== 'MONTHLY' && s.monthly_equivalent" class="text-[10px]" style="color: var(--text-muted)">≈ {{ money(s.monthly_equivalent) }}/mo</p>
          </div>
          <button
            v-if="tab === 'subscription'"
            class="text-[11px] px-2 py-1 rounded-md border transition hover:opacity-80"
            style="border-color: var(--border); color: var(--text-muted)"
            :title="`Cancel ${s.name}`"
            @click="openCancel(s)"
          >Cancel</button>
          <button
            v-else-if="tab === 'cancelled'"
            class="text-[11px] hover:underline"
            style="color: var(--text-muted)"
            :disabled="busy"
            title="Mark as not cancelled"
            @click="undo(s)"
          >Undo</button>
        </div>
      </div>
      <p class="text-[11px] mt-2" style="color: var(--text-muted)">
        Detected by Plaid from your transaction history. Amounts are the most recent charge.
      </p>
    </template>

    <CancelSubscriptionDialog v-model:visible="dialogOpen" :stream="selected" @saved="load" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import Button from 'primevue/button'
import api from '@/utils/api'
import CancelSubscriptionDialog from '@/components/accounts/CancelSubscriptionDialog.vue'
import { projectDates, toIsoDate } from '@/utils/recurrence'
import { usePlaidSync } from '@/composables/usePlaidSync'

const { syncNow, syncIfStale } = usePlaidSync()

const loading = ref(true)
const refreshing = ref(false)
const busy = ref(false)
const error = ref('')
const data = ref({ available: false, unavailable_institutions: [], streams: [], cancelled: [], summary: {} })
const tab = ref('subscription')
const accountFilter = ref('')
const sortBy = ref('cost')
const dialogOpen = ref(false)
const selected = ref(null)

const summary = computed(() => data.value.summary || {})
const alerts = computed(() => data.value.cancelled.filter(c => c.tracking.still_charging && !c.tracking.alert_dismissed))

const tabs = computed(() => [
  { key: 'subscription', label: 'Subscriptions', count: data.value.streams.filter(s => s.kind === 'subscription').length },
  { key: 'bill', label: 'Bills & transfers', count: data.value.streams.filter(s => s.kind === 'bill').length },
  { key: 'cancelled', label: 'Cancelled', count: data.value.cancelled.length },
])

const accountLabel = (a) => (a ? `${a.name}${a.mask ? ' ••' + a.mask : ''}` : 'Unknown account')

const accountOptions = computed(() => {
  const seen = new Map()
  for (const s of [...data.value.streams, ...data.value.cancelled]) {
    if (s.account_id && !seen.has(s.account_id)) {
      seen.set(s.account_id, { key: s.account_id, label: `${s.account?.institution_name ? s.account.institution_name + ' · ' : ''}${accountLabel(s.account)}` })
    }
  }
  return [...seen.values()].sort((a, b) => a.label.localeCompare(b.label))
})

const rows = computed(() => {
  let list = tab.value === 'cancelled' ? data.value.cancelled : data.value.streams.filter(s => s.kind === tab.value)
  if (accountFilter.value) list = list.filter(s => s.account_id === accountFilter.value)
  const sorted = [...list]
  if (sortBy.value === 'name') sorted.sort((a, b) => a.name.localeCompare(b.name))
  else if (sortBy.value === 'next') sorted.sort((a, b) => (a.next_date || '9999').localeCompare(b.next_date || '9999'))
  else sorted.sort((a, b) => (b.monthly_equivalent || 0) - (a.monthly_equivalent || 0))
  return sorted
})

const nextWeek = computed(() => {
  const start = new Date()
  const end = new Date(); end.setDate(end.getDate() + 7)
  let count = 0
  let total = 0
  for (const s of data.value.streams) {
    if (s.kind !== 'subscription') continue
    const n = projectDates(s, toIsoDate(start), toIsoDate(end)).length
    count += n
    total += n * (s.last_amount || 0)
  }
  return { count, total }
})

const load = async () => {
  try {
    const res = await api.get('/api/subscriptions/recurring')
    data.value = res.data
    error.value = ''
  } catch {
    error.value = 'Failed to load subscriptions'
  } finally {
    loading.value = false
  }
}

const refresh = async () => {
  refreshing.value = true
  try {
    await syncNow({ force: true })
  } catch {}
  await load()
  refreshing.value = false
}

const openCancel = (s) => { selected.value = s; dialogOpen.value = true }

const act = async (fn) => {
  busy.value = true
  try { await fn(); await load() } catch { error.value = 'Could not update — try again' } finally { busy.value = false }
}
const recancel = (c) => act(() => api.patch(`/api/subscriptions/${c.tracking.id}`, { status: 'cancelled' }))
const dismiss = (c) => act(() => api.patch(`/api/subscriptions/${c.tracking.id}`, { alert_dismissed: true }))
const undo = (c) => act(() => api.delete(`/api/subscriptions/${c.tracking.id}`))

const rowIcon = (s) => {
  if (tab.value === 'cancelled') return s.tracking.still_charging ? 'pi-exclamation-triangle' : 'pi-ban'
  return s.kind === 'bill' ? 'pi-calendar' : 'pi-replay'
}
const rowIconColor = (s) => {
  if (tab.value === 'cancelled') return s.tracking.still_charging ? '#f87171' : 'var(--text-muted)'
  return s.kind === 'bill' ? '#60a5fa' : 'var(--mint)'
}

const freqLabel = (f) => ({
  WEEKLY: 'Weekly', BIWEEKLY: 'Every 2 weeks', SEMI_MONTHLY: 'Twice a month', MONTHLY: 'Monthly', ANNUALLY: 'Yearly',
}[f] || 'Irregular')
const money = (v) => Number(v || 0).toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })
const fmtDate = (d) => (d ? new Date(d + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '—')

onMounted(async () => {
  try { await syncIfStale({ maxAgeMs: 5 * 60_000 }) } catch {}
  await load()
})
</script>

<style scoped>
.chip {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  vertical-align: middle;
}
.field-select {
  padding: 0.4rem 0.6rem;
  border-radius: 8px;
  font-size: 12px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  color: var(--text);
  max-width: 100%;
}
</style>
