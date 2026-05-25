<template>
  <div class="p-6 max-w-6xl mx-auto">
    <header class="mb-8">
      <h1 class="text-2xl font-bold" style="color: var(--text)">Dashboard</h1>
      <p class="text-sm mt-1" style="color: var(--text-muted)">{{ greeting }}, {{ firstName }}</p>
    </header>

    <!-- Summary cards -->
    <div class="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-8">
      <div class="rounded-xl border p-5 flex items-center gap-4 sm:col-span-1" style="background: var(--surface); border-color: var(--mint)">
        <div class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0" style="background: var(--mint)">
          <i class="pi pi-wallet text-lg" style="color: #080C0B"></i>
        </div>
        <div>
          <p class="text-xs" style="color: var(--text-muted)">Net Worth</p>
          <p class="text-xl font-bold mt-0.5" style="color: var(--text)">${{ fmt(netWorth?.net_worth) }}</p>
        </div>
      </div>

      <div class="rounded-xl border p-5 flex items-center gap-4" style="background: var(--surface); border-color: var(--border)">
        <div class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0" style="background: var(--surface-2)">
          <i class="pi pi-building-columns text-lg" style="color: var(--mint)"></i>
        </div>
        <div>
          <p class="text-xs" style="color: var(--text-muted)">Liquid Assets</p>
          <p class="text-xl font-bold mt-0.5" style="color: var(--text)">${{ fmt(netWorth?.liquid_assets) }}</p>
        </div>
      </div>

      <div class="rounded-xl border p-5 flex items-center gap-4" style="background: var(--surface); border-color: var(--border)">
        <div class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0" style="background: var(--surface-2)">
          <i class="pi pi-arrow-up-right text-lg" style="color: #f87171"></i>
        </div>
        <div>
          <p class="text-xs" style="color: var(--text-muted)">Spent This Month</p>
          <p class="text-xl font-bold mt-0.5" style="color: var(--text)">${{ fmt(spentThisMonth) }}</p>
        </div>
      </div>

      <div class="rounded-xl border p-5 flex items-center gap-4" style="background: var(--surface); border-color: var(--border)">
        <div class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0" style="background: var(--surface-2)">
          <i class="pi pi-arrow-down-left text-lg" style="color: var(--mint)"></i>
        </div>
        <div>
          <p class="text-xs" style="color: var(--text-muted)">Income This Month</p>
          <p class="text-xl font-bold mt-0.5" style="color: var(--text)">${{ fmt(incomeThisMonth) }}</p>
        </div>
      </div>
    </div>

    <!-- Recent transactions + upcoming bills -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Recent transactions -->
      <div class="rounded-xl border overflow-hidden" style="background: var(--surface); border-color: var(--border)">
        <div class="flex items-center justify-between px-5 py-4 border-b" style="border-color: var(--border)">
          <p class="font-semibold text-sm" style="color: var(--text)">Recent Transactions</p>
          <RouterLink to="/transactions" class="text-xs font-medium" style="color: var(--mint)">View all</RouterLink>
        </div>

        <div v-if="loadingTxns" class="p-5 space-y-3">
          <div v-for="i in 5" :key="i" class="flex gap-3 animate-pulse">
            <div class="w-8 h-8 rounded-lg flex-shrink-0" style="background: var(--surface-2)"></div>
            <div class="flex-1 space-y-2"><div class="h-3 rounded w-2/3" style="background: var(--surface-2)"></div><div class="h-2 rounded w-1/3" style="background: var(--surface-2)"></div></div>
            <div class="h-3 rounded w-14" style="background: var(--surface-2)"></div>
          </div>
        </div>

        <div v-else-if="recentTxns.length === 0" class="p-8 text-center">
          <i class="pi pi-receipt text-2xl mb-2" style="color: var(--mint)"></i>
          <p class="text-xs" style="color: var(--text-muted)">Link accounts to see transactions</p>
        </div>

        <div v-else>
          <div
            v-for="txn in recentTxns"
            :key="txn.id"
            class="flex items-center gap-3 px-5 py-3 border-b last:border-0"
            style="border-color: var(--border)"
          >
            <div class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 overflow-hidden" style="background: var(--surface-2)">
              <img v-if="txn.logo_url" :src="txn.logo_url" class="w-full h-full object-cover" />
              <i v-else class="pi pi-receipt text-xs" style="color: var(--mint)"></i>
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm truncate" style="color: var(--text)">{{ txn.merchant_name || txn.name }}</p>
              <p class="text-xs" style="color: var(--text-muted)">{{ formatDate(txn.date) }}</p>
            </div>
            <p class="text-sm font-medium flex-shrink-0" :style="txn.amount < 0 ? 'color: var(--mint)' : 'color: var(--text)'">
              {{ txn.amount < 0 ? '+' : '-' }}${{ Math.abs(txn.amount).toFixed(2) }}
            </p>
          </div>
        </div>
      </div>

      <!-- Linked accounts summary -->
      <div class="rounded-xl border overflow-hidden" style="background: var(--surface); border-color: var(--border)">
        <div class="flex items-center justify-between px-5 py-4 border-b" style="border-color: var(--border)">
          <p class="font-semibold text-sm" style="color: var(--text)">Accounts</p>
          <RouterLink to="/accounts" class="text-xs font-medium" style="color: var(--mint)">Manage</RouterLink>
        </div>

        <div v-if="accounts.length === 0" class="p-8 text-center">
          <i class="pi pi-building-columns text-2xl mb-2" style="color: var(--mint)"></i>
          <p class="text-xs" style="color: var(--text-muted)">No accounts linked</p>
          <RouterLink to="/accounts" class="text-xs mt-1 block" style="color: var(--mint)">Link your bank →</RouterLink>
        </div>

        <div v-else>
          <div
            v-for="acct in accounts.slice(0, 6)"
            :key="acct.id"
            class="flex items-center justify-between px-5 py-3 border-b last:border-0"
            style="border-color: var(--border)"
          >
            <div class="flex items-center gap-2">
              <i class="pi pi-building-columns text-sm" style="color: var(--mint)"></i>
              <div>
                <p class="text-sm" style="color: var(--text)">{{ acct.name }}</p>
                <p class="text-xs" style="color: var(--text-muted)">{{ acct.institution_name }}</p>
              </div>
            </div>
            <p class="text-sm font-semibold" style="color: var(--mint)">${{ fmt(acct.current_balance) }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import api from '@/utils/api'
import { useAuth } from '@/composables/useAuth'

const auth = useAuth()
const accounts = ref([])
const recentTxns = ref([])
const netWorth = ref(null)
const loadingTxns = ref(true)

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
})

const firstName = computed(() => {
  const email = auth.currentUser.value?.email || ''
  return email.split('@')[0]
})

const totalBalance = computed(() => accounts.value.reduce((s, a) => s + (a.current_balance || 0), 0))

const currentMonthBounds = () => {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10)
  const end = now.toISOString().slice(0, 10)
  return { start, end }
}

const spentThisMonth = computed(() =>
  recentTxns.value.filter(t => t.amount > 0).reduce((s, t) => s + t.amount, 0)
)
const incomeThisMonth = computed(() =>
  recentTxns.value.filter(t => t.amount < 0).reduce((s, t) => s + Math.abs(t.amount), 0)
)

const fmt = (val) => val != null ? Number(val).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00'
const formatDate = (d) => new Date(d + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

onMounted(async () => {
  const [acctRes, nwRes] = await Promise.allSettled([api.get('/api/accounts'), api.get('/api/networth')])
  if (acctRes.status === 'fulfilled') accounts.value = acctRes.value.data
  if (nwRes.status === 'fulfilled') netWorth.value = nwRes.value.data

  const { start, end } = currentMonthBounds()
  try {
    const txnRes = await api.get(`/api/transactions?limit=200&start_date=${start}&end_date=${end}`)
    recentTxns.value = txnRes.data.transactions.slice(0, 8)
  } catch (e) {}
  loadingTxns.value = false
})
</script>
