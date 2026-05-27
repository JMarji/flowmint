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
          <p class="text-sm font-semibold" style="color: var(--text)">Debt by Institution</p>
          <p class="text-xs" style="color: var(--text-muted)">Top 8</p>
        </div>
        <div class="h-72">
          <Bar :data="debtInstitutionChartData" :options="barChartOptions" />
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

ChartJS.register(ArcElement, BarElement, CategoryScale, LinearScale, Tooltip, Legend)

const accounts = ref([])
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

const debtInstitutionRows = computed(() => {
  const sums = {}
  for (const acct of debtAccounts.value) {
    const key = acct.institution_name || 'Unknown Bank'
    sums[key] = (sums[key] || 0) + acct.debt_amount
  }
  return Object.entries(sums)
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8)
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

const debtInstitutionChartData = computed(() => ({
  labels: debtInstitutionRows.value.map(r => r.label),
  datasets: [{
    label: 'Debt',
    data: debtInstitutionRows.value.map(r => r.value),
    backgroundColor: '#F87171',
    borderRadius: 8,
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

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get('/api/accounts')
    accounts.value = res.data || []
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
