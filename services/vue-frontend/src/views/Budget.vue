<template>
  <div class="p-6 max-w-6xl mx-auto">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold" style="color: var(--text)">Budget</h1>
        <p class="text-sm mt-1" style="color: var(--text-muted)">Spending limits for {{ displayMonth }}</p>
      </div>
      <div class="flex items-center gap-3">
        <button @click="prevMonth" class="p-2 rounded-lg hover:opacity-80" style="background: var(--surface-2); color: var(--text-muted)"><i class="pi pi-chevron-left text-sm"></i></button>
        <span class="text-sm font-medium" style="color: var(--text)">{{ displayMonth }}</span>
        <button @click="nextMonth" class="p-2 rounded-lg hover:opacity-80" style="background: var(--surface-2); color: var(--text-muted)"><i class="pi pi-chevron-right text-sm"></i></button>
        <Button @click="showAdd = true" label="Add Budget" icon="pi pi-plus" class="p-button-primary" size="small" />
      </div>
    </div>

    <!-- Summary strip -->
    <div class="grid grid-cols-3 gap-4 mb-6" v-if="budgets.length">
      <div class="rounded-xl border p-4 text-center" style="background: var(--surface); border-color: var(--border)">
        <p class="text-xs mb-1" style="color: var(--text-muted)">Total Budgeted</p>
        <p class="text-lg font-bold" style="color: var(--text)">${{ fmt(totalBudgeted) }}</p>
      </div>
      <div class="rounded-xl border p-4 text-center" style="background: var(--surface); border-color: var(--border)">
        <p class="text-xs mb-1" style="color: var(--text-muted)">Total Spent</p>
        <p class="text-lg font-bold" :style="totalSpent > totalBudgeted ? 'color:#f87171' : 'color: var(--text)'">${{ fmt(totalSpent) }}</p>
      </div>
      <div class="rounded-xl border p-4 text-center" style="background: var(--surface); border-color: var(--border)">
        <p class="text-xs mb-1" style="color: var(--text-muted)">Remaining</p>
        <p class="text-lg font-bold" :style="totalRemaining < 0 ? 'color:#f87171' : 'color: var(--mint)'">${{ fmt(totalRemaining) }}</p>
      </div>
    </div>

    <!-- Transaction insights -->
    <div class="rounded-xl border p-4 mb-4" style="background: var(--surface); border-color: var(--border)">
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <p class="text-sm font-semibold" style="color: var(--text)">Transaction Insights</p>
          <p class="text-xs mt-1" style="color: var(--text-muted)">Showing {{ selectedAccountLabel }} across {{ historyWindowLabel }}</p>
        </div>
        <div class="min-w-64">
          <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Filter by account</label>
          <select v-model="selectedAccountId" class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--surface-2); border: 1px solid var(--border); color: var(--text)">
            <option value="">All linked accounts</option>
            <option v-for="acct in accountOptions" :key="acct.id" :value="String(acct.id)">
              {{ acct.institution_name }} · {{ acct.name }}
            </option>
          </select>
        </div>
      </div>
    </div>

    <div v-if="loadingInsights" class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
      <div v-for="i in 4" :key="i" class="rounded-xl border p-4 animate-pulse" style="background: var(--surface); border-color: var(--border)">
        <div class="h-4 rounded w-1/3 mb-4" style="background: var(--surface-2)"></div>
        <div class="h-64 rounded" style="background: var(--surface-2)"></div>
      </div>
    </div>

    <div v-else-if="hasHistoryInsights" class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <div class="flex items-center justify-between mb-3">
          <p class="text-sm font-semibold" style="color: var(--text)">Monthly Spending Trend</p>
          <p class="text-xs" style="color: var(--text-muted)">Expenses only</p>
        </div>
        <div class="h-72">
          <Line :data="spendTrendChartData" :options="lineChartOptions" />
        </div>
      </div>

      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <div class="flex items-center justify-between mb-3">
          <p class="text-sm font-semibold" style="color: var(--text)">Monthly Transaction Count</p>
          <p class="text-xs" style="color: var(--text-muted)">Posted only</p>
        </div>
        <div class="h-72">
          <Bar :data="txnCountChartData" :options="countBarOptions" />
        </div>
      </div>

      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <div class="flex items-center justify-between mb-3">
          <p class="text-sm font-semibold" style="color: var(--text)">Top Spending Categories</p>
          <p class="text-xs" style="color: var(--text-muted)">{{ displayMonth }}</p>
        </div>
        <div class="h-72">
          <Bar :data="categorySpendChartData" :options="barChartOptions" />
        </div>
      </div>

      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <div class="flex items-center justify-between mb-3">
          <p class="text-sm font-semibold" style="color: var(--text)">Cash In vs Cash Out</p>
          <p class="text-xs" style="color: var(--text-muted)">{{ displayMonth }}</p>
        </div>
        <div class="h-72">
          <Doughnut :data="cashflowChartData" :options="doughnutOptions" />
        </div>
      </div>
    </div>

    <!-- Empty -->
    <div v-if="!loading && budgets.length === 0" class="rounded-xl border p-12 flex flex-col items-center gap-3 text-center" style="background: var(--surface); border-color: var(--border); border-style: dashed">
      <i class="pi pi-chart-pie text-3xl" style="color: var(--mint)"></i>
      <p class="text-sm font-medium" style="color: var(--text)">No budgets for {{ displayMonth }}</p>
      <Button @click="showAdd = true" label="Add your first budget" class="p-button-primary mt-1" size="small" />
    </div>

    <!-- Budget rows -->
    <div class="space-y-3">
      <div v-for="b in budgets" :key="b.id" class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-2">
            <i :class="`pi ${catIcon(b.category)}`" class="text-sm" style="color: var(--mint)"></i>
            <p class="text-sm font-medium" style="color: var(--text)">{{ fmtCat(b.category) }}</p>
          </div>
          <div class="flex items-center gap-3">
            <span class="text-xs" style="color: var(--text-muted)">${{ fmt(b.spent) }} / ${{ fmt(b.monthly_limit) }}</span>
            <button @click="deleteBudget(b.id)" class="text-xs hover:opacity-80" style="color: var(--text-muted)"><i class="pi pi-trash"></i></button>
          </div>
        </div>
        <!-- Progress bar -->
        <div class="h-2 rounded-full overflow-hidden" style="background: var(--surface-2)">
          <div class="h-full rounded-full transition-all"
            :style="{
              width: Math.min(b.percent, 100) + '%',
              background: b.percent >= 100 ? '#f87171' : b.percent >= 80 ? '#fb923c' : 'var(--mint)'
            }"
          ></div>
        </div>
        <p class="text-xs mt-1.5" :style="b.remaining < 0 ? 'color:#f87171' : 'color: var(--text-muted)'">
          {{ b.remaining >= 0 ? `$${fmt(b.remaining)} left` : `$${fmt(Math.abs(b.remaining))} over budget` }}
        </p>
      </div>
    </div>

    <!-- Add dialog -->
    <Dialog v-model:visible="showAdd" header="Add Budget" modal class="w-full max-w-sm" :style="{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text)' }">
      <div class="space-y-4 py-2">
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Category</label>
          <select v-model="newBudget.category" class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--surface-2); border: 1px solid var(--border); color: var(--text)">
            <option v-for="c in CATEGORIES" :key="c.value" :value="c.value">{{ c.label }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Monthly Limit ($)</label>
          <InputText v-model="newBudget.monthly_limit" type="number" min="1" class="w-full" placeholder="500" />
        </div>
      </div>
      <template #footer>
        <Button @click="showAdd = false" label="Cancel" severity="secondary" text />
        <Button @click="addBudget" label="Add" class="p-button-primary" :loading="saving" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import api from '@/utils/api'
import { Bar, Doughnut, Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  ArcElement,
  BarElement,
  CategoryScale,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  Legend,
} from 'chart.js'
import { usePlaidSync } from '@/composables/usePlaidSync'

ChartJS.register(ArcElement, BarElement, CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend)

const CATEGORIES = [
  { value: 'FOOD_AND_DRINK', label: 'Food & Drink' },
  { value: 'TRANSPORTATION', label: 'Transportation' },
  { value: 'SHOPPING', label: 'Shopping' },
  { value: 'ENTERTAINMENT', label: 'Entertainment' },
  { value: 'RENT_AND_UTILITIES', label: 'Rent & Utilities' },
  { value: 'MEDICAL', label: 'Medical' },
  { value: 'PERSONAL_CARE', label: 'Personal Care' },
  { value: 'TRAVEL', label: 'Travel' },
  { value: 'GENERAL_MERCHANDISE', label: 'General Merchandise' },
]

const budgets = ref([])
const accountOptions = ref([])
const historyTransactions = ref([])
const loading = ref(true)
const loadingInsights = ref(true)
const showAdd = ref(false)
const saving = ref(false)
const currentDate = ref(new Date())
const selectedAccountId = ref('')
const newBudget = ref({ category: 'FOOD_AND_DRINK', monthly_limit: '' })
const { syncIfStale } = usePlaidSync()

const monthYear = computed(() => {
  const d = currentDate.value
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
})
const displayMonth = computed(() => currentDate.value.toLocaleString('default', { month: 'long', year: 'numeric' }))
const totalBudgeted = computed(() => budgets.value.reduce((s, b) => s + b.monthly_limit, 0))
const totalSpent = computed(() => budgets.value.reduce((s, b) => s + b.spent, 0))
const totalRemaining = computed(() => totalBudgeted.value - totalSpent.value)

const monthEndDate = computed(() => {
  const d = currentDate.value
  return new Date(d.getFullYear(), d.getMonth() + 1, 0)
})

const historyStartDate = computed(() => {
  const d = currentDate.value
  return new Date(d.getFullYear(), d.getMonth() - 5, 1)
})

const toIsoDate = (d) => {
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

const historyWindowLabel = computed(() => {
  const start = historyStartDate.value
  const end = monthEndDate.value
  return `${start.toLocaleString('default', { month: 'short', year: 'numeric' })} - ${end.toLocaleString('default', { month: 'short', year: 'numeric' })}`
})

const selectedAccountLabel = computed(() => {
  if (!selectedAccountId.value) return 'all accounts'
  const found = accountOptions.value.find(a => String(a.id) === selectedAccountId.value)
  if (!found) return 'selected account'
  return `${found.institution_name} · ${found.name}`
})

const historyMonthBuckets = computed(() => {
  const buckets = []
  const start = new Date(historyStartDate.value)
  for (let i = 0; i < 6; i += 1) {
    const d = new Date(start.getFullYear(), start.getMonth() + i, 1)
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    const label = d.toLocaleString('default', { month: 'short', year: '2-digit' })
    buckets.push({ key, label })
  }
  return buckets
})

const fmt = (v) => Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const fmtCat = (c) => c?.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase()) || c
const catIcon = (c) => {
  const m = { FOOD_AND_DRINK: 'pi-shopping-bag', TRANSPORTATION: 'pi-car', SHOPPING: 'pi-shopping-cart',
    ENTERTAINMENT: 'pi-ticket', RENT_AND_UTILITIES: 'pi-home', MEDICAL: 'pi-heart',
    TRAVEL: 'pi-send', GENERAL_MERCHANDISE: 'pi-box', PERSONAL_CARE: 'pi-user' }
  return m[c] || 'pi-wallet'
}

const palette = [
  '#3DDBB8', '#60A5FA', '#F59E0B', '#F87171', '#22D3EE', '#A78BFA', '#34D399', '#FB7185',
]

const postedHistoryTransactions = computed(() =>
  historyTransactions.value.filter(t => !t.pending)
)

const currentMonthTransactions = computed(() =>
  postedHistoryTransactions.value.filter(t => (t.date || '').slice(0, 7) === monthYear.value)
)

const spendTrendRows = computed(() => {
  const sums = Object.fromEntries(historyMonthBuckets.value.map(b => [b.key, 0]))
  for (const txn of postedHistoryTransactions.value) {
    if (Number(txn.amount) <= 0) continue
    const key = (txn.date || '').slice(0, 7)
    if (key in sums) sums[key] += Number(txn.amount || 0)
  }
  return historyMonthBuckets.value.map(b => ({ label: b.label, value: sums[b.key] || 0 }))
})

const txnCountRows = computed(() => {
  const counts = Object.fromEntries(historyMonthBuckets.value.map(b => [b.key, 0]))
  for (const txn of postedHistoryTransactions.value) {
    const key = (txn.date || '').slice(0, 7)
    if (key in counts) counts[key] += 1
  }
  return historyMonthBuckets.value.map(b => ({ label: b.label, value: counts[b.key] || 0 }))
})

const currentMonthCategoryRows = computed(() => {
  const sums = {}
  for (const txn of currentMonthTransactions.value) {
    if (Number(txn.amount) <= 0) continue
    const key = txn.category || 'UNCATEGORIZED'
    sums[key] = (sums[key] || 0) + Number(txn.amount || 0)
  }
  return Object.entries(sums)
    .map(([label, value]) => ({ label: fmtCat(label), value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8)
})

const monthInflow = computed(() =>
  currentMonthTransactions.value
    .filter(t => Number(t.amount) < 0)
    .reduce((sum, t) => sum + Math.abs(Number(t.amount || 0)), 0)
)

const monthOutflow = computed(() =>
  currentMonthTransactions.value
    .filter(t => Number(t.amount) > 0)
    .reduce((sum, t) => sum + Number(t.amount || 0), 0)
)

const hasHistoryInsights = computed(() =>
  spendTrendRows.value.some(r => r.value > 0) ||
  txnCountRows.value.some(r => r.value > 0) ||
  currentMonthCategoryRows.value.length > 0 ||
  monthInflow.value > 0 ||
  monthOutflow.value > 0
)

const spendTrendChartData = computed(() => ({
  labels: spendTrendRows.value.map(r => r.label),
  datasets: [{
    label: 'Spent',
    data: spendTrendRows.value.map(r => r.value),
    borderColor: '#fb923c',
    backgroundColor: 'rgba(251,146,60,0.2)',
    tension: 0.3,
    fill: true,
    pointRadius: 3,
  }],
}))

const txnCountChartData = computed(() => ({
  labels: txnCountRows.value.map(r => r.label),
  datasets: [{
    label: 'Transactions',
    data: txnCountRows.value.map(r => r.value),
    backgroundColor: '#60a5fa',
    borderRadius: 8,
  }],
}))

const categorySpendChartData = computed(() => ({
  labels: currentMonthCategoryRows.value.map(r => r.label),
  datasets: [{
    label: 'Spent',
    data: currentMonthCategoryRows.value.map(r => r.value),
    backgroundColor: currentMonthCategoryRows.value.map((_, i) => palette[i % palette.length]),
    borderRadius: 8,
  }],
}))

const cashflowChartData = computed(() => ({
  labels: ['Cash In', 'Cash Out'],
  datasets: [{
    data: [monthInflow.value, monthOutflow.value],
    backgroundColor: ['#3DDBB8', '#F87171'],
    borderWidth: 0,
  }],
}))

const barChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (ctx) => `$${fmt(ctx.parsed.y ?? ctx.parsed.x ?? 0)}`,
      },
    },
  },
  scales: {
    x: {
      ticks: { color: '#94A3B8' },
      grid: { display: false },
    },
    y: {
      ticks: {
        color: '#94A3B8',
        callback: (value) => `$${Number(value).toLocaleString('en-US')}`,
      },
      grid: { color: 'rgba(148,163,184,0.15)' },
    },
  },
}))

const lineChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (ctx) => `$${fmt(ctx.parsed.y ?? 0)}`,
      },
    },
  },
  scales: {
    x: {
      ticks: { color: '#94A3B8' },
      grid: { display: false },
    },
    y: {
      ticks: {
        color: '#94A3B8',
        callback: (value) => `$${Number(value).toLocaleString('en-US')}`,
      },
      grid: { color: 'rgba(148,163,184,0.15)' },
    },
  },
}))

const countBarOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
  },
  scales: {
    x: {
      ticks: { color: '#94A3B8' },
      grid: { display: false },
    },
    y: {
      beginAtZero: true,
      ticks: { color: '#94A3B8', precision: 0 },
      grid: { color: 'rgba(148,163,184,0.15)' },
    },
  },
}))

const doughnutOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom',
      labels: { color: '#94A3B8', boxWidth: 10, boxHeight: 10 },
    },
    tooltip: {
      callbacks: {
        label: (ctx) => `${ctx.label}: $${fmt(ctx.raw || 0)}`,
      },
    },
  },
}))

const fetchHistoryTransactions = async () => {
  const all = []
  const pageSize = 200
  let offset = 0
  let total = 0

  do {
    const params = new URLSearchParams({
      limit: String(pageSize),
      offset: String(offset),
      start_date: toIsoDate(historyStartDate.value),
      end_date: toIsoDate(monthEndDate.value),
    })
    if (selectedAccountId.value) params.set('account_id', selectedAccountId.value)
    const res = await api.get(`/api/transactions?${params}`)
    const txns = res.data?.transactions || []
    total = Number(res.data?.total || 0)
    all.push(...txns)
    offset += pageSize
    if (!txns.length) break
  } while (offset < total && offset < 2000)

  return all
}

const loadBudgets = async () => {
  loading.value = true
  try {
    const res = await api.get(`/api/budgets?month_year=${monthYear.value}`)
    budgets.value = res.data
  } finally {
    loading.value = false
  }
}

const loadInsights = async () => {
  loadingInsights.value = true
  try {
    historyTransactions.value = await fetchHistoryTransactions()
  } finally {
    loadingInsights.value = false
  }
}

const loadAccountOptions = async () => {
  try {
    const res = await api.get('/api/accounts')
    accountOptions.value = (res.data || []).filter(a => Number.isInteger(a.id) && a.item_db_id !== null)
  } catch (e) {
    accountOptions.value = []
  }
}

const prevMonth = () => {
  const d = new Date(currentDate.value)
  d.setMonth(d.getMonth() - 1)
  currentDate.value = d
}
const nextMonth = () => {
  const d = new Date(currentDate.value)
  d.setMonth(d.getMonth() + 1)
  currentDate.value = d
}

const addBudget = async () => {
  saving.value = true
  try {
    await api.post('/api/budgets', { ...newBudget.value, month_year: monthYear.value, monthly_limit: Number(newBudget.value.monthly_limit) })
    showAdd.value = false
    newBudget.value = { category: 'FOOD_AND_DRINK', monthly_limit: '' }
    await loadBudgets()
  } finally { saving.value = false }
}

const deleteBudget = async (id) => {
  await api.delete(`/api/budgets/${id}`)
  budgets.value = budgets.value.filter(b => b.id !== id)
}

onMounted(async () => {
  try {
    await syncIfStale({ maxAgeMs: 3 * 60_000 })
  } catch (e) {}
  await loadAccountOptions()
  await Promise.all([loadBudgets(), loadInsights()])
})

watch(monthYear, async () => {
  await Promise.all([loadBudgets(), loadInsights()])
})

watch(selectedAccountId, async () => {
  await loadInsights()
})
</script>
