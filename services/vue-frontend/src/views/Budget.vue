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

    <!-- Account insights -->
    <div v-if="loadingInsights" class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
      <div v-for="i in 2" :key="i" class="rounded-xl border p-4 animate-pulse" style="background: var(--surface); border-color: var(--border)">
        <div class="h-4 rounded w-1/3 mb-4" style="background: var(--surface-2)"></div>
        <div class="h-64 rounded" style="background: var(--surface-2)"></div>
      </div>
    </div>

    <div v-else-if="hasAccountInsights" class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <div class="flex items-center justify-between mb-3">
          <p class="text-sm font-semibold" style="color: var(--text)">Balances by Account</p>
          <p class="text-xs" style="color: var(--text-muted)">Top 8</p>
        </div>
        <div class="h-72">
          <Bar :data="balancesByAccountChartData" :options="barChartOptions" />
        </div>
      </div>

      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <div class="flex items-center justify-between mb-3">
          <p class="text-sm font-semibold" style="color: var(--text)">Balance Mix by Account Type</p>
          <p class="text-xs" style="color: var(--text-muted)">Current</p>
        </div>
        <div class="h-72">
          <Doughnut :data="balanceByTypeChartData" :options="doughnutOptions" />
        </div>
      </div>

      <div class="rounded-xl border p-4 lg:col-span-2" style="background: var(--surface); border-color: var(--border)">
        <div class="flex items-center justify-between mb-3">
          <p class="text-sm font-semibold" style="color: var(--text)">Spending by Account</p>
          <p class="text-xs" style="color: var(--text-muted)">{{ displayMonth }}</p>
        </div>
        <div class="h-72">
          <Bar :data="spendingByAccountChartData" :options="barChartOptions" />
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
import { ref, computed, onMounted } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import api from '@/utils/api'
import { Bar, Doughnut } from 'vue-chartjs'
import {
  Chart as ChartJS,
  ArcElement,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
} from 'chart.js'
import { usePlaidSync } from '@/composables/usePlaidSync'

ChartJS.register(ArcElement, BarElement, CategoryScale, LinearScale, Tooltip, Legend)

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
const accounts = ref([])
const monthlyTransactions = ref([])
const loading = ref(true)
const loadingInsights = ref(true)
const showAdd = ref(false)
const saving = ref(false)
const currentDate = ref(new Date())
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

const monthDateRange = computed(() => {
  const d = currentDate.value
  const year = d.getFullYear()
  const month = d.getMonth() + 1
  const lastDay = new Date(year, month, 0).getDate()
  const mm = String(month).padStart(2, '0')
  return {
    start: `${year}-${mm}-01`,
    end: `${year}-${mm}-${String(lastDay).padStart(2, '0')}`,
  }
})

const fmt = (v) => Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const fmtCat = (c) => c?.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase()) || c
const catIcon = (c) => {
  const m = { FOOD_AND_DRINK: 'pi-shopping-bag', TRANSPORTATION: 'pi-car', SHOPPING: 'pi-shopping-cart',
    ENTERTAINMENT: 'pi-ticket', RENT_AND_UTILITIES: 'pi-home', MEDICAL: 'pi-heart',
    TRAVEL: 'pi-send', GENERAL_MERCHANDISE: 'pi-box', PERSONAL_CARE: 'pi-user' }
  return m[c] || 'pi-wallet'
}

const accountTypeCategory = (acct) => {
  const subtype = (acct.subtype || '').toString().trim().toLowerCase().replace(/[_-]+/g, ' ')
  const type = (acct.type || '').toString().trim().toLowerCase()

  if (
    ['mortgage', 'heloc', 'auto', 'student loan', 'personal loan', 'loan'].includes(subtype) ||
    type === 'loan'
  ) return 'Loan'

  if (subtype.includes('credit') || type === 'credit') return 'Credit'

  if (
    ['checking', 'savings', 'money market', 'cd', 'cash management'].includes(subtype) ||
    type === 'depository'
  ) return 'Deposit'

  if (
    subtype.includes('brokerage') ||
    subtype.includes('retirement') ||
    subtype.includes('ira') ||
    type === 'investment'
  ) return 'Investment'

  return 'Other'
}

const accountLabel = (acct) => {
  const institution = acct.institution_name || 'Unknown Bank'
  return `${institution} · ${acct.name}`
}

const palette = [
  '#3DDBB8', '#60A5FA', '#F59E0B', '#F87171', '#22D3EE', '#A78BFA', '#34D399', '#FB7185',
]

const accountBalanceRows = computed(() => {
  return accounts.value
    .map(a => ({ label: accountLabel(a), value: Number(a.current_balance || 0) }))
    .filter(a => a.value !== 0)
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .slice(0, 8)
})

const balanceByTypeRows = computed(() => {
  const sums = {}
  for (const acct of accounts.value) {
    const key = accountTypeCategory(acct)
    sums[key] = (sums[key] || 0) + Number(acct.current_balance || 0)
  }
  return Object.entries(sums)
    .map(([label, value]) => ({ label, value }))
    .filter(r => r.value !== 0)
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
})

const monthlySpendRows = computed(() => {
  const sums = {}
  for (const txn of monthlyTransactions.value) {
    if (txn.pending || Number(txn.amount) <= 0) continue
    const key = `${txn.institution_name || 'Unknown Bank'} · ${txn.account_name || 'Account'}`
    sums[key] = (sums[key] || 0) + Number(txn.amount || 0)
  }
  return Object.entries(sums)
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8)
})

const hasAccountInsights = computed(() =>
  accountBalanceRows.value.length > 0 || balanceByTypeRows.value.length > 0 || monthlySpendRows.value.length > 0
)

const balancesByAccountChartData = computed(() => ({
  labels: accountBalanceRows.value.map(r => r.label),
  datasets: [{
    label: 'Balance',
    data: accountBalanceRows.value.map(r => r.value),
    backgroundColor: accountBalanceRows.value.map((_, i) => palette[i % palette.length]),
    borderRadius: 8,
  }],
}))

const balanceByTypeChartData = computed(() => ({
  labels: balanceByTypeRows.value.map(r => r.label),
  datasets: [{
    data: balanceByTypeRows.value.map(r => r.value),
    backgroundColor: balanceByTypeRows.value.map((_, i) => palette[i % palette.length]),
    borderWidth: 0,
  }],
}))

const spendingByAccountChartData = computed(() => ({
  labels: monthlySpendRows.value.map(r => r.label),
  datasets: [{
    label: 'Spent',
    data: monthlySpendRows.value.map(r => r.value),
    backgroundColor: '#fb923c',
    borderRadius: 8,
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

const fetchMonthlyTransactions = async () => {
  const all = []
  const pageSize = 200
  let offset = 0
  let total = 0

  do {
    const params = new URLSearchParams({
      limit: String(pageSize),
      offset: String(offset),
      start_date: monthDateRange.value.start,
      end_date: monthDateRange.value.end,
    })
    const res = await api.get(`/api/transactions?${params}`)
    const txns = res.data?.transactions || []
    total = Number(res.data?.total || 0)
    all.push(...txns)
    offset += pageSize
    if (!txns.length) break
  } while (offset < total && offset < 2000)

  return all
}

const load = async () => {
  loading.value = true
  loadingInsights.value = true
  try {
    const [budgetRes, accountsRes, txns] = await Promise.all([
      api.get(`/api/budgets?month_year=${monthYear.value}`),
      api.get('/api/accounts'),
      fetchMonthlyTransactions(),
    ])
    budgets.value = budgetRes.data
    accounts.value = (accountsRes.data || []).filter(a => Number.isInteger(a.id) && a.item_db_id !== null)
    monthlyTransactions.value = txns
  } finally {
    loading.value = false
    loadingInsights.value = false
  }
}

const prevMonth = () => {
  const d = new Date(currentDate.value)
  d.setMonth(d.getMonth() - 1)
  currentDate.value = d
  load()
}
const nextMonth = () => {
  const d = new Date(currentDate.value)
  d.setMonth(d.getMonth() + 1)
  currentDate.value = d
  load()
}

const addBudget = async () => {
  saving.value = true
  try {
    await api.post('/api/budgets', { ...newBudget.value, month_year: monthYear.value, monthly_limit: Number(newBudget.value.monthly_limit) })
    showAdd.value = false
    newBudget.value = { category: 'FOOD_AND_DRINK', monthly_limit: '' }
    await load()
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
  await load()
})
</script>
