<template>
  <div class="p-6 max-w-4xl mx-auto">
    <div class="flex items-center justify-between mb-8">
      <div>
        <h1 class="text-2xl font-bold" style="color: var(--text)">Accounts</h1>
        <p class="text-sm mt-1" style="color: var(--text-muted)">Linked bank accounts and balances</p>
      </div>
      <div class="flex gap-2">
        <Button @click="syncAccounts" :loading="syncing" icon="pi pi-refresh" severity="secondary" text rounded title="Sync all" />
        <Button @click="openPlaidLink" :loading="isLinking" label="Link Account" icon="pi pi-plus" class="p-button-primary" />
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-3">
      <div v-for="i in 3" :key="i" class="rounded-xl border p-4 animate-pulse" style="background: var(--surface); border-color: var(--border)">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg" style="background: var(--surface-2)"></div>
          <div class="flex-1 space-y-2">
            <div class="h-3 rounded w-1/3" style="background: var(--surface-2)"></div>
            <div class="h-2 rounded w-1/4" style="background: var(--surface-2)"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="accounts.length === 0" class="rounded-xl border p-12 flex flex-col items-center gap-3 text-center" style="background: var(--surface); border-color: var(--border); border-style: dashed">
      <i class="pi pi-building-columns text-3xl" style="color: var(--mint)"></i>
      <p class="text-sm font-medium" style="color: var(--text)">No accounts linked yet</p>
      <p class="text-xs" style="color: var(--text-muted)">Click "Link Account" to connect your bank through Plaid</p>
      <Button @click="openPlaidLink" label="Link your first account" class="p-button-primary mt-2" />
    </div>

    <!-- Grouped by institution -->
    <div v-else class="space-y-6">
      <div v-for="(group, inst) in grouped" :key="inst">
        <p class="text-xs font-semibold uppercase tracking-wider mb-2" style="color: var(--text-muted)">{{ inst }}</p>
        <div class="space-y-2">
          <div
            v-for="acct in group"
            :key="acct.id"
            class="rounded-xl border p-4 flex items-center justify-between"
            style="background: var(--surface); border-color: var(--border)"
          >
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-lg flex items-center justify-center" style="background: var(--surface-2)">
                <i :class="`pi ${accountIcon(acct.type)}`" style="color: var(--mint)"></i>
              </div>
              <div>
                <p class="text-sm font-medium" style="color: var(--text)">{{ acct.name }}</p>
                <div class="flex items-center gap-2 mt-0.5">
                  <span
                    class="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full"
                    :style="accountBadgeStyle(acct)"
                  >
                    {{ accountTypeLabel(acct) }}
                  </span>
                  <p class="text-xs" style="color: var(--text-muted)">••••{{ acct.mask }}</p>
                </div>
              </div>
            </div>
            <div class="text-right">
              <p class="text-lg font-bold" style="color: var(--mint)">${{ fmt(acct.current_balance) }}</p>
              <p v-if="acct.available_balance !== null" class="text-xs" style="color: var(--text-muted)">
                ${{ fmt(acct.available_balance) }} available
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Total row -->
      <div class="rounded-xl border p-4 flex justify-between items-center" style="background: var(--surface-2); border-color: var(--mint)">
        <p class="font-semibold" style="color: var(--text)">Total Balance</p>
        <p class="text-xl font-bold" style="color: var(--mint)">${{ fmt(totalBalance) }}</p>
      </div>
    </div>

    <!-- Error -->
    <p v-if="error" class="mt-4 text-sm px-3 py-2 rounded-lg" style="color: #f87171; background: rgba(248,113,113,0.1)">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import Button from 'primevue/button'
import api from '@/utils/api'
import { usePlaid } from '@/composables/usePlaid'
import { usePlaidSync } from '@/composables/usePlaidSync'

const accounts = ref([])
const loading = ref(true)
const syncing = ref(false)
const error = ref('')
const { isLinking, openLink } = usePlaid()
const { syncNow, syncIfStale } = usePlaidSync()

const grouped = computed(() => {
  const g = {}
  for (const a of accounts.value) {
    const key = a.institution_name || 'Unknown Bank'
    if (!g[key]) g[key] = []
    g[key].push(a)
  }
  return g
})

const totalBalance = computed(() =>
  accounts.value.reduce((sum, a) => sum + (a.current_balance || 0), 0)
)

const fmt = (val) => val != null ? Number(val).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'

const accountIcon = (type) => {
  if (type === 'credit') return 'pi-credit-card'
  if (type === 'loan') return 'pi-percentage'
  if (type === 'investment') return 'pi-chart-line'
  return 'pi-building-columns'
}

const accountTypeLabel = (acct) => {
  const raw = (acct.subtype || acct.type || '').toString().trim().toLowerCase()
  const normalized = raw.replace(/[_-]+/g, ' ')

  const labels = {
    checking: 'Checking',
    savings: 'Savings',
    mortgage: 'Mortgage',
    heloc: 'HELOC',
    auto: 'Auto Loan',
    'student loan': 'Student Loan',
    'personal loan': 'Personal Loan',
    credit: 'Credit',
    'credit card': 'Credit Card',
    brokerage: 'Brokerage',
    investment: 'Investment',
  }

  if (labels[normalized]) return labels[normalized]
  if (!normalized) return 'Account'
  return normalized
    .split(' ')
    .filter(Boolean)
    .map(s => s[0].toUpperCase() + s.slice(1))
    .join(' ')
}

const accountTypeCategory = (acct) => {
  const subtype = (acct.subtype || '').toString().trim().toLowerCase().replace(/[_-]+/g, ' ')
  const type = (acct.type || '').toString().trim().toLowerCase()

  if (
    ['mortgage', 'heloc', 'auto', 'student loan', 'personal loan', 'loan'].includes(subtype) ||
    type === 'loan'
  ) return 'loan'

  if (subtype.includes('credit') || type === 'credit') return 'credit'

  if (
    ['checking', 'savings', 'money market', 'cd', 'cash management'].includes(subtype) ||
    type === 'depository'
  ) return 'deposit'

  if (
    subtype.includes('brokerage') ||
    subtype.includes('retirement') ||
    subtype.includes('ira') ||
    type === 'investment'
  ) return 'investment'

  return 'other'
}

const accountBadgeStyle = (acct) => {
  const category = accountTypeCategory(acct)
  if (category === 'loan') return 'background: rgba(251,146,60,0.16); color: #fb923c'
  if (category === 'credit') return 'background: rgba(248,113,113,0.16); color: #f87171'
  if (category === 'deposit') return 'background: rgba(61,219,184,0.14); color: var(--mint)'
  if (category === 'investment') return 'background: rgba(96,165,250,0.16); color: #60a5fa'
  return 'background: var(--surface-2); color: var(--text-muted)'
}

const fetchAccounts = async () => {
  try {
    const res = await api.get('/api/accounts')
    accounts.value = res.data
  } catch (e) {
    error.value = 'Failed to load accounts'
  } finally {
    loading.value = false
  }
}

const syncAccounts = async () => {
  syncing.value = true
  error.value = ''
  try {
    await syncNow({ force: true })
    await fetchAccounts()
  } catch (e) {
    error.value = 'Sync failed'
  } finally {
    syncing.value = false
  }
}

const maybeAutoSync = async (maxAgeMs = 2 * 60_000) => {
  try {
    const result = await syncIfStale({ maxAgeMs })
    return !result.skipped
  } catch {
    return false
  }
}

const handleVisibilityChange = async () => {
  if (document.visibilityState !== 'visible') return
  const synced = await maybeAutoSync(60_000)
  if (synced) await fetchAccounts()
}

const openPlaidLink = () => {
  openLink(async () => {
    loading.value = true
    await syncNow({ force: true })
    await fetchAccounts()
  })
}

onMounted(async () => {
  loading.value = true
  await maybeAutoSync()
  await fetchAccounts()
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>
