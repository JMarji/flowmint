<template>
  <div class="p-6 max-w-5xl mx-auto">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-6">
      <RouterLink to="/accounts" class="p-2 rounded-lg hover:opacity-80 transition" style="color: var(--text-muted); background: var(--surface-2)">
        <i class="pi pi-arrow-left text-sm"></i>
      </RouterLink>
      <div class="flex-1 min-w-0">
        <h1 class="text-xl font-bold truncate" style="color: var(--text)">{{ settings.product_name || account?.name || 'Credit Card' }}</h1>
        <p class="text-xs" style="color: var(--text-muted)">
          {{ account?.institution_name }}<span v-if="account?.mask"> · ••••{{ account.mask }}</span>
          <span v-if="account?.updated_at"> · Updated {{ relTime(account.updated_at) }}</span>
        </p>
      </div>
      <Button v-if="account" @click="showSettings = true" icon="pi pi-cog" severity="secondary" text rounded title="Card details &amp; rewards" aria-label="Card details and rewards" />
      <Button @click="refresh" :loading="syncing" icon="pi pi-refresh" severity="secondary" text rounded title="Sync" />
    </div>

    <!-- Loading -->
    <div v-if="loading" class="grid md:grid-cols-[380px_1fr] gap-6 animate-pulse">
      <div class="rounded-2xl" style="aspect-ratio: 1.586/1; background: var(--surface-2)"></div>
      <div class="space-y-3">
        <div v-for="i in 4" :key="i" class="h-12 rounded-xl" style="background: var(--surface-2)"></div>
      </div>
    </div>

    <p v-else-if="error" class="text-sm px-3 py-2 rounded-lg" style="color: #f87171; background: rgba(248,113,113,0.1)">{{ error }}</p>

    <template v-else-if="account">
      <!-- Card + key payment info -->
      <div class="grid md:grid-cols-[380px_1fr] gap-6 mb-8">
        <div class="space-y-4">
          <CreditCard
            :name="account.name"
            :institution="account.institution_name"
            :mask="account.mask"
            :product-name="settings.product_name || ''"
            :network="settings.network || ''"
            :balance="account.current_balance"
            :limit="liability.credit_limit"
          />

          <!-- Utilization -->
          <div v-if="utilization != null" class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
            <div class="flex items-center justify-between mb-2">
              <p class="text-xs font-medium" style="color: var(--text-muted)">Credit utilization</p>
              <p class="text-sm font-bold" :style="{ color: utilColor }">{{ utilization.toFixed(1) }}%</p>
            </div>
            <div class="h-2 rounded-full overflow-hidden" style="background: var(--surface-2)">
              <div class="h-full rounded-full transition-all" :style="{ width: Math.min(utilization, 100) + '%', background: utilColor }"></div>
            </div>
            <p class="text-[11px] mt-2" style="color: var(--text-muted)">
              {{ money(availableCredit) }} available of {{ money(liability.credit_limit) }}.
              <span v-if="utilization > 30">Keeping it under 30% helps your credit score.</span>
            </p>
          </div>
        </div>

        <div class="space-y-4">
          <!-- Overdue banner -->
          <div v-if="liability.is_overdue" class="rounded-xl border p-3 flex items-center gap-2 text-sm" style="border-color: #f87171; background: rgba(248,113,113,0.1); color: #f87171">
            <i class="pi pi-exclamation-triangle"></i> This account is past due.
          </div>

          <!-- Next payment -->
          <div v-if="liabilityAvailable" class="rounded-xl border p-5" style="background: var(--surface); border-color: var(--mint)">
            <div class="flex items-start justify-between gap-4">
              <div>
                <p class="text-xs" style="color: var(--text-muted)">Next payment due</p>
                <p class="text-2xl font-bold mt-1" style="color: var(--text)">
                  {{ liability.next_payment_due_date ? fmtDate(liability.next_payment_due_date) : '—' }}
                </p>
                <p v-if="daysUntilDue != null" class="text-xs mt-1" :style="{ color: daysUntilDue <= 5 ? '#fb923c' : 'var(--text-muted)' }">
                  {{ daysUntilDue < 0 ? `${-daysUntilDue} days ago` : daysUntilDue === 0 ? 'Today' : `in ${daysUntilDue} days` }}
                </p>
              </div>
              <div class="text-right">
                <p class="text-xs" style="color: var(--text-muted)">Minimum</p>
                <p class="text-lg font-bold" style="color: var(--mint)">{{ money(liability.minimum_payment_amount) }}</p>
              </div>
            </div>
            <div class="grid grid-cols-2 gap-4 mt-4 pt-4 border-t" style="border-color: var(--border)">
              <div>
                <p class="text-xs" style="color: var(--text-muted)">Statement balance</p>
                <p class="text-sm font-semibold" style="color: var(--text)">{{ money(liability.last_statement_balance) }}</p>
                <p v-if="liability.last_statement_issue_date" class="text-[11px]" style="color: var(--text-muted)">Issued {{ fmtDate(liability.last_statement_issue_date) }}</p>
              </div>
              <div>
                <p class="text-xs" style="color: var(--text-muted)">Last payment</p>
                <p class="text-sm font-semibold" style="color: var(--text)">{{ money(liability.last_payment_amount) }}</p>
                <p v-if="liability.last_payment_date" class="text-[11px]" style="color: var(--text-muted)">{{ fmtDate(liability.last_payment_date) }}</p>
              </div>
            </div>
            <p v-if="payoffHint" class="text-[11px] mt-3" style="color: var(--text-muted)">
              <i class="pi pi-info-circle text-[10px]"></i> {{ payoffHint }}
            </p>
            <div class="flex items-center justify-between mt-3 text-[11px]" style="color: var(--text-muted)">
              <span v-if="billId"><i class="pi pi-calendar text-[10px]"></i> Tracked in Bills ({{ settings.bill_amount_mode === 'minimum' ? 'minimum payment' : 'statement balance' }})</span>
              <span v-else-if="settings.auto_bill === false">Not tracked in Bills</span>
              <span v-else></span>
              <RouterLink v-if="billId" to="/bills" class="hover:underline" style="color: var(--mint)">Open Bills →</RouterLink>
              <button v-else-if="settings.auto_bill === false" class="hover:underline" style="color: var(--mint)" @click="showSettings = true">Turn on</button>
            </div>
          </div>

          <!-- Statement cycle -->
          <div v-if="cycle" class="rounded-xl border p-5" style="background: var(--surface); border-color: var(--border)">
            <div class="flex items-center justify-between mb-2">
              <p class="text-xs font-medium" style="color: var(--text-muted)">
                {{ cycle.source === 'statement' ? 'Current statement cycle' : 'This month' }}
              </p>
              <p class="text-[11px]" style="color: var(--text-muted)">
                {{ fmtShort(cycle.start) }} – {{ fmtShort(cycle.next_close) }}
              </p>
            </div>
            <div class="flex items-end justify-between gap-4">
              <div>
                <p class="text-2xl font-bold" style="color: var(--text)">{{ money(cycle.charges) }}</p>
                <p class="text-[11px]" style="color: var(--text-muted)">
                  {{ cycle.charge_count }} charge{{ cycle.charge_count === 1 ? '' : 's' }}
                  <span v-if="cycle.payments"> · {{ money(cycle.payments) }} paid</span>
                </p>
              </div>
              <div class="text-right">
                <p class="text-sm font-semibold" style="color: var(--text)">{{ cycle.days_left }} day{{ cycle.days_left === 1 ? '' : 's' }}</p>
                <p class="text-[11px]" style="color: var(--text-muted)">{{ cycle.source === 'statement' ? 'until statement closes (est.)' : 'left in month' }}</p>
              </div>
            </div>
            <div class="h-1.5 rounded-full overflow-hidden mt-3" style="background: var(--surface-2)">
              <div class="h-full rounded-full" :style="{ width: cycleProgress + '%', background: 'var(--mint)' }"></div>
            </div>
          </div>

          <!-- APRs -->
          <div v-if="liability.aprs?.length" class="rounded-xl border p-5" style="background: var(--surface); border-color: var(--border)">
            <p class="text-xs font-medium mb-3" style="color: var(--text-muted)">Interest rates</p>
            <div class="space-y-2">
              <div v-for="apr in liability.aprs" :key="apr.apr_type" class="flex items-center justify-between text-sm">
                <span style="color: var(--text)">{{ aprLabel(apr.apr_type) }}</span>
                <span class="flex items-center gap-3">
                  <span v-if="apr.interest_charge_amount" class="text-xs" style="color: #f87171">{{ money(apr.interest_charge_amount) }} interest</span>
                  <span class="font-semibold" style="color: var(--text)">{{ apr.apr_percentage != null ? apr.apr_percentage.toFixed(2) + '%' : '—' }}</span>
                </span>
              </div>
            </div>
          </div>

          <p v-if="!liabilityAvailable" class="text-xs px-3 py-2 rounded-lg" style="color: var(--text-muted); background: var(--surface-2)">
            <i class="pi pi-info-circle text-[10px]"></i>
            Statement, APR, and due-date details aren't available from this institution via Plaid.
          </p>
        </div>
      </div>

      <!-- Rewards + balance history -->
      <div class="grid md:grid-cols-2 gap-6 mb-8">
        <div class="rounded-xl border p-5" style="background: var(--surface); border-color: var(--border)">
          <div class="flex items-center justify-between mb-3">
            <p class="text-sm font-semibold" style="color: var(--text)">Rewards</p>
            <button class="text-[11px] hover:underline" style="color: var(--mint)" @click="showSettings = true">
              {{ rewards?.configured ? 'Edit rates' : 'Set up' }}
            </button>
          </div>
          <div v-if="!rewards?.configured" class="text-xs space-y-2" style="color: var(--text-muted)">
            <p>Add this card's reward rates to estimate what you're earning, and whether it covers the annual fee.</p>
            <Button label="Add rewards" icon="pi pi-star" size="small" severity="secondary" @click="showSettings = true" />
          </div>
          <template v-else>
            <div class="grid grid-cols-3 gap-3 mb-4">
              <div>
                <p class="text-[10px] uppercase tracking-wide" style="color: var(--text-muted)">This cycle</p>
                <p class="text-lg font-bold" style="color: var(--mint)">{{ money(rewards.cycle.value) }}</p>
                <p v-if="rewards.cycle.points != null" class="text-[11px]" style="color: var(--text-muted)">{{ rewards.cycle.points.toLocaleString() }} pts</p>
              </div>
              <div>
                <p class="text-[10px] uppercase tracking-wide" style="color: var(--text-muted)">Last 12 mo</p>
                <p class="text-lg font-bold" style="color: var(--text)">{{ money(rewards.trailing_12m.value) }}</p>
                <p v-if="rewards.trailing_12m.points != null" class="text-[11px]" style="color: var(--text-muted)">{{ rewards.trailing_12m.points.toLocaleString() }} pts</p>
              </div>
              <div>
                <p class="text-[10px] uppercase tracking-wide" style="color: var(--text-muted)">Net of fee</p>
                <p class="text-lg font-bold" :style="{ color: rewards.net_12m < 0 ? '#f87171' : 'var(--text)' }">{{ money(rewards.net_12m) }}</p>
                <p class="text-[11px]" style="color: var(--text-muted)">{{ rewards.annual_fee ? `${money(rewards.annual_fee)} fee${annualFeeWhen}` : 'No annual fee' }}</p>
              </div>
            </div>
            <div v-if="rewards.trailing_12m.by_category.length" class="space-y-1.5">
              <div v-for="c in rewards.trailing_12m.by_category.slice(0, 5)" :key="c.category" class="flex items-center justify-between text-xs">
                <span style="color: var(--text)">{{ categoryLabel(c.category) }}</span>
                <span style="color: var(--text-muted)">{{ money(c.value) }} on {{ money(c.spend) }}</span>
              </div>
            </div>
            <p class="text-[11px] mt-3" style="color: var(--text-muted)">Estimate based on synced transactions; excludes fees, payments, and transfers.</p>
          </template>
        </div>

        <div class="rounded-xl border p-5" style="background: var(--surface); border-color: var(--border)">
          <div class="flex items-center justify-between mb-3">
            <p class="text-sm font-semibold" style="color: var(--text)">Balance history</p>
            <p class="text-[11px]" style="color: var(--text-muted)">Recorded at each sync</p>
          </div>
          <div v-if="balanceHistory.length >= 2" class="h-48">
            <Line :data="historyChart" :options="historyOptions" />
          </div>
          <div v-else class="h-48 flex flex-col items-center justify-center text-center gap-2">
            <i class="pi pi-chart-line text-xl" style="color: var(--text-muted)"></i>
            <p class="text-xs" style="color: var(--text-muted)">History builds up as your accounts sync each day.<br />Check back in a few days.</p>
          </div>
        </div>
      </div>

      <!-- Payoff + recurring -->
      <div class="grid md:grid-cols-2 gap-6 mb-8">
        <PayoffPlanner
          :balance="account.current_balance || 0"
          :apr="purchaseApr"
          :minimum-payment="liability.minimum_payment_amount"
          :statement-balance="liability.last_statement_balance"
        />
        <RecurringCharges :account-id="accountId" />
      </div>

      <!-- Spending -->
      <div class="grid md:grid-cols-2 gap-6 mb-8">
        <div class="rounded-xl border p-5" style="background: var(--surface); border-color: var(--border)">
          <div class="flex items-center justify-between mb-3">
            <p class="text-sm font-semibold" style="color: var(--text)">Monthly activity</p>
            <p class="text-[11px]" style="color: var(--text-muted)">Last 6 months</p>
          </div>
          <div v-if="spending.monthly.length" class="h-56">
            <Bar :data="monthlyChart" :options="chartOptions" />
          </div>
          <p v-else class="text-xs" style="color: var(--text-muted)">No transactions synced yet.</p>
        </div>

        <div class="rounded-xl border p-5" style="background: var(--surface); border-color: var(--border)">
          <div class="flex items-center justify-between mb-3">
            <p class="text-sm font-semibold" style="color: var(--text)">Where it goes</p>
            <p class="text-[11px]" style="color: var(--text-muted)">Last 90 days</p>
          </div>
          <div v-if="spending.top_categories.length" class="space-y-2.5">
            <div v-for="c in spending.top_categories" :key="c.category">
              <div class="flex justify-between text-xs mb-1">
                <span style="color: var(--text)">{{ categoryLabel(c.category) }}</span>
                <span style="color: var(--text-muted)">{{ money(c.total) }}</span>
              </div>
              <div class="h-1.5 rounded-full overflow-hidden" style="background: var(--surface-2)">
                <div class="h-full rounded-full" :style="{ width: (c.total / maxCategory * 100) + '%', background: 'var(--mint)' }"></div>
              </div>
            </div>
          </div>
          <p v-else class="text-xs" style="color: var(--text-muted)">No charges in the last 90 days.</p>

          <div v-if="spending.top_merchants.length" class="mt-5 pt-4 border-t" style="border-color: var(--border)">
            <p class="text-xs font-medium mb-2" style="color: var(--text-muted)">Top merchants</p>
            <div class="space-y-2">
              <div v-for="m in spending.top_merchants" :key="m.name" class="flex items-center gap-2 text-xs">
                <img v-if="m.logo_url" :src="m.logo_url" class="w-5 h-5 rounded" alt="" />
                <div v-else class="w-5 h-5 rounded flex items-center justify-center" style="background: var(--surface-2)">
                  <i class="pi pi-shop text-[9px]" style="color: var(--text-muted)"></i>
                </div>
                <span class="flex-1 truncate" style="color: var(--text)">{{ m.name }}</span>
                <span style="color: var(--text-muted)">{{ m.count }}×</span>
                <span class="w-20 text-right font-medium" style="color: var(--text)">{{ money(m.total) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Recent transactions -->
      <div class="rounded-xl border" style="background: var(--surface); border-color: var(--border)">
        <div class="flex items-center justify-between p-4 border-b" style="border-color: var(--border)">
          <p class="text-sm font-semibold" style="color: var(--text)">Recent transactions</p>
          <RouterLink :to="{ path: '/transactions', query: { account: account.id } }" class="text-xs hover:underline" style="color: var(--mint)">
            View all →
          </RouterLink>
        </div>
        <div v-if="!transactions.length" class="p-4 text-xs" style="color: var(--text-muted)">No transactions yet.</div>
        <div v-for="t in transactions" :key="t.id" class="flex items-center gap-3 px-4 py-3 border-b last:border-b-0" style="border-color: var(--border)">
          <img v-if="t.logo_url" :src="t.logo_url" class="w-8 h-8 rounded-lg" alt="" />
          <div v-else class="w-8 h-8 rounded-lg flex items-center justify-center" style="background: var(--surface-2)">
            <i :class="`pi ${t.amount < 0 ? 'pi-arrow-down-left' : 'pi-shopping-bag'} text-xs`" style="color: var(--text-muted)"></i>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm truncate" style="color: var(--text)">{{ t.merchant_name || t.name }}</p>
            <p class="text-[11px]" style="color: var(--text-muted)">
              {{ fmtDate(t.date) }} · {{ categoryLabel(t.category) }}
              <span v-if="t.pending" class="ml-1 px-1.5 py-0.5 rounded text-[10px]" style="background: var(--surface-2)">Pending</span>
            </p>
          </div>
          <!-- Plaid: positive = charge, negative = payment/credit -->
          <p class="text-sm font-semibold" :style="{ color: t.amount < 0 ? 'var(--mint)' : 'var(--text)' }">
            {{ t.amount < 0 ? '+' : '' }}{{ money(Math.abs(t.amount)) }}
          </p>
        </div>
      </div>
    </template>

    <CardSettingsDialog
      v-if="account"
      v-model:visible="showSettings"
      :account-id="accountId"
      :settings="settings"
      @saved="load"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import Button from 'primevue/button'
import { Bar, Line } from 'vue-chartjs'
import { Chart as ChartJS, BarElement, LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Legend, Filler } from 'chart.js'
import api from '@/utils/api'
import CreditCard from '@/components/accounts/CreditCard.vue'
import PayoffPlanner from '@/components/accounts/PayoffPlanner.vue'
import RecurringCharges from '@/components/accounts/RecurringCharges.vue'
import CardSettingsDialog from '@/components/accounts/CardSettingsDialog.vue'
import { usePlaidSync } from '@/composables/usePlaidSync'

ChartJS.register(BarElement, LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Legend, Filler)

const route = useRoute()
const accountId = route.params.id
const { syncNow } = usePlaidSync()

const loading = ref(true)
const syncing = ref(false)
const error = ref('')
const account = ref(null)
const liability = ref({})
const liabilityAvailable = ref(false)
const utilization = ref(null)
const spending = ref({ monthly: [], top_categories: [], top_merchants: [] })
const transactions = ref([])
const settings = ref({})
const cycle = ref(null)
const rewards = ref(null)
const balanceHistory = ref([])
const billId = ref(null)
const showSettings = ref(false)

const money = (v) =>
  v == null ? '—' : Number(v).toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })

const parseDate = (d) => (typeof d === 'string' && d.length === 10 ? new Date(d + 'T00:00:00') : new Date(d))
const fmtShort = (d) => parseDate(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
const fmtDate = (d) => parseDate(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
const relTime = (iso) => {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  if (mins < 1440) return `${Math.round(mins / 60)}h ago`
  return `${Math.round(mins / 1440)}d ago`
}

const titleCase = (s) => s.toLowerCase().split(/[_\s]+/).filter(Boolean).map(w => w[0].toUpperCase() + w.slice(1)).join(' ')
const categoryLabel = (c) => (c ? titleCase(c).replace(' And ', ' & ') : 'Uncategorized')
const aprLabel = (t) => ({
  purchase_apr: 'Purchases',
  cash_apr: 'Cash advance',
  balance_transfer_apr: 'Balance transfer',
  special: 'Promotional',
}[t] || (t ? titleCase(t) : 'APR'))

const availableCredit = computed(() => {
  const lim = liability.value.credit_limit
  const bal = account.value?.current_balance
  return lim != null && bal != null ? lim - bal : null
})

const utilColor = computed(() => {
  const u = utilization.value ?? 0
  if (u >= 70) return '#f87171'
  if (u >= 30) return '#fb923c'
  return 'var(--mint)'
})

const daysUntilDue = computed(() => {
  const d = liability.value.next_payment_due_date
  if (!d) return null
  const today = new Date(); today.setHours(0, 0, 0, 0)
  return Math.round((parseDate(d) - today) / 86400000)
})

// Paying the statement balance in full avoids interest on purchases.
const payoffHint = computed(() => {
  const stmt = liability.value.last_statement_balance
  const min = liability.value.minimum_payment_amount
  const purchaseApr = liability.value.aprs?.find(a => a.apr_type === 'purchase_apr')?.apr_percentage
  if (!stmt || !min || stmt <= min || !purchaseApr) return ''
  const monthlyInterest = (stmt - min) * (purchaseApr / 100 / 12)
  return `Paying only the minimum leaves ${money(stmt - min)} revolving — roughly ${money(monthlyInterest)} in interest next month at ${purchaseApr.toFixed(2)}% APR.`
})

const purchaseApr = computed(() => {
  const aprs = liability.value.aprs || []
  const a = aprs.find(x => x.apr_type === 'purchase_apr') || aprs[0]
  return a?.apr_percentage ?? null
})

const cycleProgress = computed(() => {
  if (!cycle.value) return 0
  const { days_total, days_left } = cycle.value
  return Math.min(100, Math.max(0, ((days_total - days_left) / days_total) * 100))
})

const annualFeeWhen = computed(() => {
  const m = settings.value.annual_fee_month
  return m ? ` in ${new Date(2000, m - 1, 1).toLocaleDateString('en-US', { month: 'short' })}` : ''
})

const historyChart = computed(() => {
  const rows = balanceHistory.value
  const hasLimit = rows.some(r => r.limit)
  return {
    labels: rows.map(r => fmtShort(r.date)),
    datasets: [
      { label: 'Balance', data: rows.map(r => r.balance), borderColor: '#3DDBB8', backgroundColor: 'rgba(61,219,184,0.1)', fill: true, pointRadius: 0, borderWidth: 2, tension: 0.25, yAxisID: 'y' },
      ...(hasLimit ? [{
        label: 'Utilization %',
        data: rows.map(r => (r.limit && r.balance != null ? (r.balance / r.limit) * 100 : null)),
        borderColor: '#fb923c', borderDash: [4, 4], pointRadius: 0, borderWidth: 1.5, tension: 0.25, yAxisID: 'y1', spanGaps: true,
      }] : []),
    ],
  }
})

const historyOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { labels: { color: '#7A9E94', boxWidth: 10, font: { size: 11 } } },
    tooltip: {
      callbacks: {
        label: (ctx) => ctx.dataset.yAxisID === 'y1'
          ? `Utilization: ${ctx.parsed.y.toFixed(1)}%`
          : `Balance: ${money(ctx.parsed.y)}`,
      },
    },
  },
  scales: {
    x: { ticks: { color: '#7A9E94', maxTicksLimit: 6, maxRotation: 0 }, grid: { display: false } },
    y: { ticks: { color: '#7A9E94', callback: (v) => '$' + Number(v).toLocaleString() }, grid: { color: 'rgba(37,61,53,0.6)' } },
    y1: {
      display: historyChart.value.datasets.length > 1,
      position: 'right',
      min: 0,
      ticks: { color: '#fb923c', callback: (v) => v + '%' },
      grid: { display: false },
    },
  },
}))

const maxCategory = computed(() => Math.max(1, ...spending.value.top_categories.map(c => c.total)))

const monthlyChart = computed(() => {
  const rows = spending.value.monthly
  return {
    labels: rows.map(r => {
      const [y, m] = r.month.split('-')
      return new Date(+y, +m - 1, 1).toLocaleDateString('en-US', { month: 'short' })
    }),
    datasets: [
      { label: 'Charges', data: rows.map(r => r.charges), backgroundColor: '#3DDBB8', borderRadius: 4 },
      { label: 'Payments', data: rows.map(r => r.payments), backgroundColor: '#4a6fa5', borderRadius: 4 },
    ],
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { labels: { color: '#7A9E94', boxWidth: 10, font: { size: 11 } } },
    tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${money(ctx.parsed.y)}` } },
  },
  scales: {
    x: { ticks: { color: '#7A9E94' }, grid: { display: false } },
    y: { ticks: { color: '#7A9E94', callback: (v) => '$' + Number(v).toLocaleString() }, grid: { color: 'rgba(37,61,53,0.6)' } },
  },
}

const load = async () => {
  error.value = ''
  try {
    const [detail, txns] = await Promise.all([
      api.get(`/api/accounts/${accountId}/credit`),
      api.get('/api/transactions', { params: { account_id: accountId, limit: 15 } }),
    ])
    account.value = detail.data.account
    liability.value = detail.data.liability || {}
    liabilityAvailable.value = detail.data.liability_available
    utilization.value = detail.data.utilization
    spending.value = detail.data.spending
    settings.value = detail.data.settings || {}
    cycle.value = detail.data.cycle
    rewards.value = detail.data.rewards
    balanceHistory.value = detail.data.balance_history || []
    billId.value = detail.data.bill_id
    transactions.value = txns.data.transactions
  } catch (e) {
    error.value = e?.response?.status === 404 ? 'Account not found' : 'Failed to load account'
  } finally {
    loading.value = false
  }
}

const refresh = async () => {
  syncing.value = true
  try {
    await syncNow({ force: true })
    await load()
  } catch {
    error.value = 'Sync failed'
  } finally {
    syncing.value = false
  }
}

onMounted(load)
</script>
