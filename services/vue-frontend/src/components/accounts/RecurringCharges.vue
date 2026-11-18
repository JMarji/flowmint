<template>
  <div class="rounded-xl border" style="background: var(--surface); border-color: var(--border)">
    <div class="flex items-center justify-between p-4 border-b" style="border-color: var(--border)">
      <div>
        <p class="text-sm font-semibold" style="color: var(--text)">Subscriptions &amp; recurring</p>
        <p class="text-[11px]" style="color: var(--text-muted)">Detected by Plaid from this card's history</p>
      </div>
      <div v-if="data?.streams?.length" class="text-right">
        <p class="text-[10px] uppercase tracking-wide" style="color: var(--text-muted)">Per month</p>
        <p class="text-sm font-bold" style="color: var(--text)">{{ money(data.monthly_total) }}</p>
      </div>
    </div>

    <div v-if="loading" class="p-4 space-y-2 animate-pulse">
      <div v-for="i in 3" :key="i" class="h-8 rounded" style="background: var(--surface-2)"></div>
    </div>

    <template v-else>
      <!-- Still-charging alerts first: they need action -->
      <div v-for="c in alerts" :key="'alert-' + c.stream_id" class="m-3 rounded-lg border p-3" style="border-color: #f87171; background: rgba(248,113,113,0.08)">
        <div class="flex items-start gap-2">
          <i class="pi pi-exclamation-triangle mt-0.5 text-sm" style="color: #f87171"></i>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-semibold" style="color: #f87171">{{ c.name }} is still charging you</p>
            <p class="text-xs mt-0.5" style="color: var(--text)">
              {{ money(c.tracking.still_charging.amount) }} on {{ fmtDate(c.tracking.still_charging.date) }}
              <span v-if="c.tracking.still_charging.account_name" style="color: var(--text-muted)">({{ c.tracking.still_charging.account_name }})</span>
              — after you cancelled on {{ fmtDate(c.tracking.cancelled_on) }}.
            </p>
            <p class="text-[11px] mt-1" style="color: var(--text-muted)">
              Check the merchant confirmed the cancellation. If they did, you can dispute this charge with your card issuer.
            </p>
            <div class="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-xs">
              <button class="hover:underline" style="color: var(--mint)" @click="openCancel(c)">How to cancel</button>
              <button class="hover:underline" style="color: var(--mint)" :disabled="busy" @click="recancel(c)">I cancelled it again</button>
              <button class="hover:underline" style="color: var(--text-muted)" :disabled="busy" @click="dismiss(c)">Dismiss</button>
            </div>
          </div>
        </div>
      </div>

      <p v-if="!data?.available" class="p-4 text-xs" style="color: var(--text-muted)">
        Recurring-charge detection isn't available for this account. It needs Plaid's Recurring Transactions
        product and enough transaction history.
      </p>
      <p v-else-if="!data.streams.length && !data.cancelled.length" class="p-4 text-xs" style="color: var(--text-muted)">No recurring charges detected yet.</p>

      <!-- Active -->
      <div
        v-for="s in data?.streams || []"
        :key="s.stream_id"
        class="flex items-center gap-3 px-4 py-2.5 border-b last:border-b-0"
        style="border-color: var(--border)"
      >
        <div class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style="background: var(--surface-2)">
          <i class="pi pi-replay text-xs" style="color: var(--mint)"></i>
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-sm truncate" style="color: var(--text)">
            {{ s.name }}
            <span v-if="s.tracking?.status === 'kept'" class="chip" style="background: var(--surface-2); color: var(--text-muted)">Kept</span>
            <span v-if="s.price_increase" class="chip" style="background: rgba(251,146,60,0.16); color: #fb923c" :title="`Was ${money(s.tracking.kept_amount)} when you chose to keep it`">
              ↑ {{ money(s.price_increase) }}
            </span>
          </p>
          <p class="text-[11px]" style="color: var(--text-muted)">
            {{ freqLabel(s.frequency) }}
            <span v-if="s.next_date"> · next {{ fmtDate(s.next_date) }}</span>
            <span v-else-if="s.last_date"> · last {{ fmtDate(s.last_date) }}</span>
            <span v-if="s.status === 'EARLY_DETECTION'" class="chip" style="background: var(--surface-2)">New</span>
          </p>
        </div>
        <p class="text-sm font-semibold" style="color: var(--text)">{{ money(s.last_amount) }}</p>
        <button
          class="text-[11px] px-2 py-1 rounded-md border transition hover:opacity-80"
          style="border-color: var(--border); color: var(--text-muted)"
          :title="`Cancel ${s.name}`"
          @click="openCancel(s)"
        >Cancel</button>
      </div>

      <!-- Cancelled -->
      <div v-if="data?.cancelled?.length" class="border-t" style="border-color: var(--border)">
        <button class="w-full flex items-center justify-between px-4 py-2.5 text-xs" style="color: var(--text-muted)" @click="showCancelled = !showCancelled">
          <span>
            <i :class="`pi ${showCancelled ? 'pi-chevron-down' : 'pi-chevron-right'} text-[10px] mr-1`"></i>
            Cancelled ({{ data.cancelled.length }})
          </span>
          <span v-if="data.monthly_saved" style="color: var(--mint)">Saving {{ money(data.monthly_saved) }}/mo</span>
        </button>
        <div v-if="showCancelled">
          <div
            v-for="c in data.cancelled"
            :key="'c-' + c.stream_id"
            class="flex items-center gap-3 px-4 py-2 border-t"
            style="border-color: var(--border)"
          >
            <div class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style="background: var(--surface-2)">
              <i :class="`pi ${c.tracking.still_charging ? 'pi-exclamation-triangle' : 'pi-ban'} text-xs`" :style="{ color: c.tracking.still_charging ? '#f87171' : 'var(--text-muted)' }"></i>
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm truncate line-through decoration-1" style="color: var(--text-muted)">{{ c.name }}</p>
              <p class="text-[11px]" style="color: var(--text-muted)">
                Cancelled {{ fmtDate(c.tracking.cancelled_on) }}
                <span v-if="c.tracking.still_charging" style="color: #f87171"> · still charging</span>
                <span v-else> · no charges since</span>
              </p>
            </div>
            <p class="text-xs" :style="{ color: c.tracking.still_charging ? 'var(--text-muted)' : 'var(--mint)' }">
              {{ c.tracking.still_charging ? '' : '+' }}{{ money(c.monthly_equivalent) }}/mo
            </p>
            <button class="text-[11px] hover:underline" style="color: var(--text-muted)" :disabled="busy" title="Mark as not cancelled" @click="undo(c)">Undo</button>
          </div>
        </div>
      </div>
    </template>

    <p v-if="error" class="mx-4 mb-3 text-xs px-3 py-2 rounded-lg" style="color: #f87171; background: rgba(248,113,113,0.1)">{{ error }}</p>

    <CancelSubscriptionDialog
      v-model:visible="dialogOpen"
      :account-id="accountId"
      :stream="selected"
      @saved="load"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import api from '@/utils/api'
import CancelSubscriptionDialog from '@/components/accounts/CancelSubscriptionDialog.vue'

const props = defineProps({ accountId: { type: [String, Number], required: true } })
const emit = defineEmits(['changed'])

const loading = ref(true)
const busy = ref(false)
const error = ref('')
const data = ref(null)
const showCancelled = ref(false)
const dialogOpen = ref(false)
const selected = ref(null)

const alerts = computed(() =>
  (data.value?.cancelled || []).filter(c => c.tracking.still_charging && !c.tracking.alert_dismissed)
)

const load = async () => {
  error.value = ''
  try {
    const res = await api.get(`/api/accounts/${props.accountId}/credit/recurring`)
    data.value = res.data
    emit('changed', res.data)
  } catch {
    data.value = { available: false, streams: [], cancelled: [], monthly_total: 0, monthly_saved: 0 }
  } finally {
    loading.value = false
  }
}

const openCancel = (stream) => {
  selected.value = stream
  dialogOpen.value = true
}

const act = async (fn) => {
  busy.value = true
  error.value = ''
  try {
    await fn()
    await load()
  } catch {
    error.value = 'Could not update — try again'
  } finally {
    busy.value = false
  }
}

const recancel = (c) => act(() => api.patch(`/api/subscriptions/${c.tracking.id}`, { status: 'cancelled' }))
const dismiss = (c) => act(() => api.patch(`/api/subscriptions/${c.tracking.id}`, { alert_dismissed: true }))
const undo = (c) => act(() => api.delete(`/api/subscriptions/${c.tracking.id}`))

const freqLabel = (f) => ({
  WEEKLY: 'Weekly',
  BIWEEKLY: 'Every 2 weeks',
  SEMI_MONTHLY: 'Twice a month',
  MONTHLY: 'Monthly',
  ANNUALLY: 'Yearly',
}[f] || 'Irregular')

const money = (v) =>
  v == null ? '—' : Number(v).toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })
const fmtDate = (d) => (d ? new Date(d + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '—')

onMounted(load)
watch(() => props.accountId, load)
defineExpose({ reload: load })
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
</style>
