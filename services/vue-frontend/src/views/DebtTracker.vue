<template>
  <div class="p-6 max-w-6xl mx-auto">
    <div class="flex items-center justify-between mb-8">
      <div>
        <h1 class="text-2xl font-bold" style="color: var(--text)">Debt Tracker</h1>
        <p class="text-sm mt-1" style="color: var(--text-muted)">Track liabilities across linked credit and loan accounts</p>
      </div>
      <Button
        @click="refreshDebt"
        :loading="syncing"
        icon="pi pi-refresh"
        severity="secondary"
        text
        rounded
        title="Refresh debt data"
      />
    </div>

    <!-- Summary -->
    <div v-if="debtAccounts.length" class="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-6">
      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--mint)">
        <p class="text-xs mb-1" style="color: var(--text-muted)">Total Debt</p>
        <p class="text-xl font-bold" style="color: #f87171">${{ fmt(totalDebt) }}</p>
      </div>
      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <p class="text-xs mb-1" style="color: var(--text-muted)">Debt Accounts</p>
        <p class="text-xl font-bold" style="color: var(--text)">{{ debtAccounts.length }}</p>
      </div>
      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <p class="text-xs mb-1" style="color: var(--text-muted)">Largest Debt</p>
        <p class="text-xl font-bold" style="color: var(--text)">${{ fmt(largestDebtAmount) }}</p>
      </div>
      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <p class="text-xs mb-1" style="color: var(--text-muted)">Debt / Assets</p>
        <p class="text-xl font-bold" style="color: var(--text)">{{ debtToAssetLabel }}</p>
      </div>
    </div>

    <!-- Empty -->
    <div v-if="!loading && debtAccounts.length === 0" class="rounded-xl border p-12 flex flex-col items-center gap-3 text-center" style="background: var(--surface); border-color: var(--border); border-style: dashed">
      <i class="pi pi-wallet text-3xl" style="color: var(--mint)"></i>
      <p class="text-sm font-medium" style="color: var(--text)">No debt accounts detected</p>
      <p class="text-xs" style="color: var(--text-muted)">Link a credit card or loan account in Accounts to track debt here</p>
    </div>

    <!-- Loading -->
    <div v-else-if="loading" class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div v-for="i in 4" :key="i" class="rounded-xl border p-4 animate-pulse" style="background: var(--surface); border-color: var(--border)">
        <div class="h-4 rounded w-1/3 mb-4" style="background: var(--surface-2)"></div>
        <div class="h-64 rounded" style="background: var(--surface-2)"></div>
      </div>
    </div>

    <!-- Charts -->
    <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <div class="flex items-center justify-between mb-3">
          <p class="text-sm font-semibold" style="color: var(--text)">Debt Composition</p>
          <p class="text-xs" style="color: var(--text-muted)">By debt type</p>
        </div>
        <div class="h-72">
          <Doughnut :data="debtTypeChartData" :options="doughnutOptions" />
        </div>
      </div>

      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <div class="flex items-center justify-between mb-3">
          <p class="text-sm font-semibold" style="color: var(--text)">Debt Over Time</p>
          <p class="text-xs" style="color: var(--text-muted)">{{ historyWindowLabel }}</p>
        </div>
        <div class="h-72">
          <Line :data="debtHistoryChartData" :options="lineChartOptions" />
        </div>
      </div>

      <div class="rounded-xl border p-4 lg:col-span-2" style="background: var(--surface); border-color: var(--border)">
        <div class="flex items-center justify-between mb-3">
          <p class="text-sm font-semibold" style="color: var(--text)">Largest Debt Accounts</p>
          <p class="text-xs" style="color: var(--text-muted)">Current balances</p>
        </div>
        <div class="h-80">
          <Bar :data="debtAccountChartData" :options="barChartOptions" />
        </div>
      </div>
    </div>

    <p v-if="error" class="mt-4 text-sm px-3 py-2 rounded-lg" style="color: #f87171; background: rgba(248,113,113,0.1)">
      {{ error }}
    </p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import Button from 'primevue/button'
import api from '@/utils/api'
import { usePlaidSync } from '@/composables/usePlaidSync'
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

ChartJS.register(ArcElement, BarElement, CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend)

const accounts = ref([])
const historyTransactions = ref([])
const loading = ref(true)
const error = ref('')
const { syncing, syncNow, syncIfStale } = usePlaidSync()

const palette = ['#F87171', '#FB923C', '#FBBF24', '#60A5FA', '#34D399', '#A78BFA', '#22D3EE', '#F472B6']

const fmt = (v) => Number(v || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

const debtCategory = (acct) => {
  const subtype = (acct.subtype || '').toString().trim().toLowerCase().replace(/[_-]+/g, ' ')
  const type = (acct.type || '').toString().trim().toLowerCase()

  if (subtype.includes('mortgage') || subtype.includes('heloc')) return 'Mortgage'
  if (subtype.includes('credit') || subtype.includes('card') || type === 'credit') return 'Credit Card'
  if (subtype.includes('student')) return 'Student Loan'
  if (subtype.includes('auto')) return 'Auto Loan'
  if (type === 'loan') return 'Other Loan'
  return 'Other Debt'
}

const isDebtAccount = (acct) => {
  const subtype = (acct.subtype || '').toString().trim().toLowerCase().replace(/[_-]+/g, ' ')
  const type = (acct.type || '').toString().trim().toLowerCase()

  if (type === 'loan' || type === 'credit') return true
  return [
    'mortgage', 'heloc', 'loan', 'credit', 'credit card', 'student loan', 'auto', 'personal loan'
  ].some(term => subtype.includes(term))
}

const normalizedAccounts = computed(() => {
  return accounts.value.map(a => {
    const amount = Math.abs(Number(a.current_balance || 0))
    return {
      ...a,
      debt_amount: isDebtAccount(a) ? amount : 0,
      debt_category: debtCategory(a),
    }
  })
})

const debtAccounts = computed(() => normalizedAccounts.value.filter(a => a.debt_amount > 0))
const totalDebt = computed(() => debtAccounts.value.reduce((s, a) => s + a.debt_amount, 0))
const largestDebtAmount = computed(() => debtAccounts.value.length ? Math.max(...debtAccounts.value.map(a => a.debt_amount)) : 0)

const currentMonthEnd = computed(() => {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth() + 1, 0)
})

const historyStartDate = computed(() => {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth() - 5, 1)
})

const toIsoDate = (d) => {
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

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

const historyWindowLabel = computed(() => {
  const start = historyStartDate.value
  const end = currentMonthEnd.value
  return `${start.toLocaleString('default', { month: 'short', year: 'numeric' })} - ${end.toLocaleString('default', { month: 'short', year: 'numeric' })}`
})

const totalAssets = computed(() => {
  return accounts.value
    .filter(a => {
      const type = (a.type || '').toString().trim().toLowerCase()
      return ['depository', 'investment'].includes(type)
    })
    .reduce((s, a) => s + Math.max(Number(a.current_balance || 0), 0), 0)
})

const debtToAssetRatio = computed(() => {
  if (totalAssets.value <= 0) return '—'
  return ((totalDebt.value / totalAssets.value) * 100).toFixed(1)
})

const debtToAssetLabel = computed(() => debtToAssetRatio.value === '—' ? '—' : `${debtToAssetRatio.value}%`)

const debtAccountKeys = computed(() => {
  const keys = new Set()
  for (const acct of debtAccounts.value) {
    keys.add(`${acct.institution_name || 'Unknown Bank'}|${acct.name || 'Account'}`)
  }
  return keys
})

const debtNetByMonth = computed(() => {
  const sums = Object.fromEntries(historyMonthBuckets.value.map(b => [b.key, 0]))
  for (const txn of historyTransactions.value) {
    if (txn.pending) continue
    const key = `${txn.institution_name || 'Unknown Bank'}|${txn.account_name || 'Account'}`
    if (!debtAccountKeys.value.has(key)) continue
    const monthKey = (txn.date || '').slice(0, 7)
    if (!(monthKey in sums)) continue
    sums[monthKey] += Number(txn.amount || 0)
  }
  return sums
})

const debtHistoryRows = computed(() => {
  let rolling = Number(totalDebt.value || 0)
  const reversed = []

  for (let i = historyMonthBuckets.value.length - 1; i >= 0; i -= 1) {
    const bucket = historyMonthBuckets.value[i]
    reversed.push({ label: bucket.label, value: Math.max(rolling, 0) })
    rolling -= Number(debtNetByMonth.value[bucket.key] || 0)
  }

  return reversed.reverse()
})

const debtTypeRows = computed(() => {
  const sums = {}
  for (const acct of debtAccounts.value) {
    const key = acct.debt_category
    sums[key] = (sums[key] || 0) + acct.debt_amount
  }
  return Object.entries(sums)
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value)
})

const debtAccountRows = computed(() => {
  return debtAccounts.value
    .map(a => ({
      label: `${a.institution_name || 'Unknown'} · ${a.name || 'Account'}`,
      value: a.debt_amount,
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10)
})

const debtTypeChartData = computed(() => ({
  labels: debtTypeRows.value.map(r => r.label),
  datasets: [{
    data: debtTypeRows.value.map(r => r.value),
    backgroundColor: debtTypeRows.value.map((_, i) => palette[i % palette.length]),
    borderWidth: 0,
  }],
}))

const debtHistoryChartData = computed(() => ({
  labels: debtHistoryRows.value.map(r => r.label),
  datasets: [{
    label: 'Estimated Debt',
    data: debtHistoryRows.value.map(r => r.value),
    borderColor: '#F87171',
    backgroundColor: 'rgba(248,113,113,0.2)',
    tension: 0.3,
    fill: true,
    pointRadius: 3,
  }],
}))

const debtAccountChartData = computed(() => ({
  labels: debtAccountRows.value.map(r => r.label),
  datasets: [{
    label: 'Debt',
    data: debtAccountRows.value.map(r => r.value),
    backgroundColor: debtAccountRows.value.map((_, i) => palette[i % palette.length]),
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
      end_date: toIsoDate(currentMonthEnd.value),
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
  error.value = ''
  try {
    const [accountsRes, txns] = await Promise.all([
      api.get('/api/accounts'),
      fetchHistoryTransactions(),
    ])
    accounts.value = accountsRes.data || []
    historyTransactions.value = txns
  } catch (e) {
    error.value = 'Failed to load debt accounts'
  } finally {
    loading.value = false
  }
}

const refreshDebt = async () => {
  error.value = ''
  try {
    await syncNow({ force: true })
    await load()
  } catch (e) {
    error.value = 'Debt refresh failed'
  }
}

onMounted(async () => {
  try {
    await syncIfStale({ maxAgeMs: 3 * 60_000 })
  } catch (e) {}
  await load()
})
</script>
