<template>
  <div class="p-6 max-w-5xl mx-auto">
    <header class="mb-6">
      <h1 class="text-2xl font-bold" style="color: var(--text)">Transactions</h1>
      <p class="text-sm mt-1" style="color: var(--text-muted)">{{ total }} transactions</p>
    </header>

    <!-- Filters -->
    <div class="flex gap-3 mb-5 flex-wrap">
      <InputText v-model="search" placeholder="Search..." class="flex-1 min-w-40" @input="debounceSearch" />
      <select v-model="accountFilter" @change="applyFilters" class="px-3 py-2 rounded-lg text-sm" style="background: var(--surface-2); border: 1px solid var(--border); color: var(--text)">
        <option value="">All accounts</option>
        <option v-for="acct in accountOptions" :key="acct.id" :value="String(acct.id)">
          {{ acct.institution_name }} · {{ acct.name }}
        </option>
      </select>
      <select v-model="categoryFilter" @change="applyFilters" class="px-3 py-2 rounded-lg text-sm" style="background: var(--surface-2); border: 1px solid var(--border); color: var(--text)">
        <option value="">All categories</option>
        <option v-for="cat in CATEGORIES" :key="cat.value" :value="cat.value">{{ cat.label }}</option>
      </select>
      <input type="date" v-model="startDate" @change="applyFilters" class="px-3 py-2 rounded-lg text-sm" style="background: var(--surface-2); border: 1px solid var(--border); color: var(--text)" />
      <input type="date" v-model="endDate" @change="applyFilters" class="px-3 py-2 rounded-lg text-sm" style="background: var(--surface-2); border: 1px solid var(--border); color: var(--text)" />
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="space-y-2">
      <div v-for="i in 8" :key="i" class="rounded-xl border p-4 animate-pulse flex gap-4" style="background: var(--surface); border-color: var(--border)">
        <div class="w-10 h-10 rounded-lg flex-shrink-0" style="background: var(--surface-2)"></div>
        <div class="flex-1 space-y-2">
          <div class="h-3 rounded w-1/3" style="background: var(--surface-2)"></div>
          <div class="h-2 rounded w-1/4" style="background: var(--surface-2)"></div>
        </div>
        <div class="h-4 rounded w-16" style="background: var(--surface-2)"></div>
      </div>
    </div>

    <!-- Empty -->
    <div v-else-if="transactions.length === 0" class="rounded-xl border p-12 flex flex-col items-center gap-3 text-center" style="background: var(--surface); border-color: var(--border); border-style: dashed">
      <i class="pi pi-receipt text-3xl" style="color: var(--mint)"></i>
      <p class="text-sm font-medium" style="color: var(--text)">No transactions found</p>
      <p class="text-xs" style="color: var(--text-muted)">Link a bank account on the Accounts page to start syncing</p>
    </div>

    <!-- List -->
    <div v-else class="rounded-xl border overflow-hidden" style="background: var(--surface); border-color: var(--border)">
      <div
        v-for="(txn, i) in transactions"
        :key="txn.id"
        class="flex items-center gap-4 px-5 py-3.5 transition hover:opacity-90"
        :class="i % 2 === 0 ? '' : ''"
        :style="i % 2 !== 0 ? 'background: var(--surface-2)' : ''"
      >
        <!-- Icon / Logo -->
        <div class="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 overflow-hidden" style="background: var(--surface-2)">
          <img v-if="txn.logo_url" :src="txn.logo_url" class="w-full h-full object-cover" :alt="txn.merchant_name" />
          <i v-else :class="`pi ${categoryIcon(txn.category)}`" class="text-sm" style="color: var(--mint)"></i>
        </div>

        <!-- Name + meta -->
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium truncate" style="color: var(--text)">{{ txn.merchant_name || txn.name }}</p>
          <p class="text-xs" style="color: var(--text-muted)">
            {{ txn.account_name }} · {{ formatDate(txn.date) }}
            <span v-if="txn.pending" class="ml-1 px-1.5 py-0.5 rounded text-xs" style="background: var(--surface-2); color: var(--text-muted)">Pending</span>
          </p>
        </div>

        <!-- Category badge -->
        <span class="hidden sm:block text-xs px-2 py-1 rounded-full flex-shrink-0" style="background: var(--surface-2); color: var(--text-muted)">
          {{ formatCategory(txn.category) }}
        </span>

        <!-- Amount -->
        <p class="text-sm font-semibold flex-shrink-0 w-24 text-right" :style="txn.amount < 0 ? 'color: var(--mint)' : 'color: var(--text)'">
          {{ txn.amount < 0 ? '+' : '-' }}${{ Math.abs(txn.amount).toLocaleString('en-US', { minimumFractionDigits: 2 }) }}
        </p>
      </div>
    </div>

    <!-- Vendor aggregate -->
    <VendorAggregation
      v-if="!loading && (transactions.length || vendorSummary.vendors.length)"
      :vendors="vendorSummary.vendors"
      :vendor-count="vendorSummary.vendor_count"
      :total-outflow="vendorSummary.total_outflow"
      scope-label="all filtered transactions"
      class="mt-5"
    />

    <!-- Pagination -->
    <div v-if="total > limit" class="flex justify-center gap-3 mt-5">
      <Button @click="prevPage" :disabled="offset === 0" label="Previous" severity="secondary" size="small" />
      <span class="text-sm self-center" style="color: var(--text-muted)">{{ offset + 1 }}–{{ Math.min(offset + limit, total) }} of {{ total }}</span>
      <Button @click="nextPage" :disabled="offset + limit >= total" label="Next" severity="secondary" size="small" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import api from '@/utils/api'
import VendorAggregation from '@/components/transactions/VendorAggregation.vue'
import { usePlaidSync } from '@/composables/usePlaidSync'

const CATEGORIES = [
  { value: 'FOOD_AND_DRINK', label: 'Food & Drink' },
  { value: 'TRANSPORTATION', label: 'Transportation' },
  { value: 'UTILITIES', label: 'Utilities' },
  { value: 'SHOPPING', label: 'Shopping' },
  { value: 'ENTERTAINMENT', label: 'Entertainment' },
  { value: 'INCOME', label: 'Income' },
  { value: 'TRANSFER_IN', label: 'Transfer In' },
  { value: 'TRANSFER_OUT', label: 'Transfer Out' },
  { value: 'RENT_AND_UTILITIES', label: 'Rent & Utilities' },
  { value: 'MEDICAL', label: 'Medical' },
]

const transactions = ref([])
const total = ref(0)
const loading = ref(true)
const search = ref('')
const accountFilter = ref('')
const accountOptions = ref([])
const categoryFilter = ref('')
const startDate = ref('')
const endDate = ref('')
const limit = ref(25)
const offset = ref(0)
const vendorSummary = ref({ vendors: [], vendor_count: 0, total_outflow: 0 })
let searchTimer = null
const { syncIfStale } = usePlaidSync()

const load = async () => {
  loading.value = true
  try {
    const listParams = new URLSearchParams({
      limit: limit.value,
      offset: offset.value,
    })
    const summaryParams = new URLSearchParams({ top_n: '50' })

    if (accountFilter.value) {
      listParams.set('account_id', accountFilter.value)
      summaryParams.set('account_id', accountFilter.value)
    }
    if (categoryFilter.value) {
      listParams.set('category', categoryFilter.value)
      summaryParams.set('category', categoryFilter.value)
    }
    if (startDate.value) {
      listParams.set('start_date', startDate.value)
      summaryParams.set('start_date', startDate.value)
    }
    if (endDate.value) {
      listParams.set('end_date', endDate.value)
      summaryParams.set('end_date', endDate.value)
    }
    if (search.value.trim()) {
      summaryParams.set('search', search.value.trim())
    }

    const [listResult, summaryResult] = await Promise.allSettled([
      api.get(`/api/transactions?${listParams}`),
      api.get(`/api/transactions/vendors-summary?${summaryParams}`),
    ])

    if (listResult.status !== 'fulfilled') {
      throw listResult.reason
    }

    const res = listResult.value
    let txns = res.data.transactions
    if (search.value.trim()) {
      const q = search.value.toLowerCase()
      txns = txns.filter(t => (t.name || '').toLowerCase().includes(q) || (t.merchant_name || '').toLowerCase().includes(q))
    }
    transactions.value = txns
    total.value = res.data.total

    if (summaryResult.status === 'fulfilled') {
      vendorSummary.value = {
        vendors: summaryResult.value?.data?.vendors || [],
        vendor_count: Number(summaryResult.value?.data?.vendor_count) || 0,
        total_outflow: Number(summaryResult.value?.data?.total_outflow) || 0,
      }
    } else {
      vendorSummary.value = { vendors: [], vendor_count: 0, total_outflow: 0 }
    }
  } catch (e) {
    transactions.value = []
    vendorSummary.value = { vendors: [], vendor_count: 0, total_outflow: 0 }
  } finally {
    loading.value = false
  }
}

const debounceSearch = () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    offset.value = 0
    load()
  }, 300)
}

const applyFilters = () => {
  offset.value = 0
  load()
}

const loadAccounts = async () => {
  try {
    const res = await api.get('/api/accounts')
    accountOptions.value = (res.data || []).filter(a => Number.isInteger(a.id) && a.item_db_id !== null)
  } catch (e) {
    accountOptions.value = []
  }
}

const prevPage = () => { offset.value = Math.max(0, offset.value - limit.value); load() }
const nextPage = () => { offset.value += limit.value; load() }

const formatDate = (d) => new Date(d + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
const formatCategory = (c) => c ? c.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase()) : '—'
const categoryIcon = (c) => {
  if (!c) return 'pi-receipt'
  const map = {
    FOOD_AND_DRINK: 'pi-shopping-bag', TRANSPORTATION: 'pi-car',
    SHOPPING: 'pi-shopping-cart', ENTERTAINMENT: 'pi-ticket',
    INCOME: 'pi-arrow-down-left', TRANSFER_IN: 'pi-arrow-down-left',
    TRANSFER_OUT: 'pi-arrow-up-right', MEDICAL: 'pi-heart',
    UTILITIES: 'pi-bolt', RENT_AND_UTILITIES: 'pi-home',
  }
  return map[c] || 'pi-receipt'
}

onMounted(async () => {
  try {
    await syncIfStale({ maxAgeMs: 3 * 60_000 })
  } catch (e) {}
  await loadAccounts()
  await load()
})
</script>
