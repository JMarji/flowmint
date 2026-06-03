<template>
  <div class="p-6 max-w-7xl mx-auto">
    <header class="mb-6 flex items-center justify-between gap-3 flex-wrap">
      <div>
        <h1 class="text-2xl font-bold" style="color: var(--text)">Transactions</h1>
        <p class="text-sm mt-1" style="color: var(--text-muted)">{{ total }} transactions</p>
      </div>
      <div v-if="selectedVendor" class="text-xs px-2.5 py-1.5 rounded-full" style="background: color-mix(in oklab, var(--mint) 16%, transparent); color: var(--text)">
        Vendor filter: {{ selectedVendor }}
      </div>
    </header>

    <div class="flex gap-3 mb-5 flex-wrap">
      <InputText v-model="search" placeholder="Search transaction or merchant..." class="flex-1 min-w-52" @input="debounceSearch" />
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

    <div class="grid grid-cols-1 xl:grid-cols-12 gap-5 items-start">
      <section class="xl:col-span-8">
        <div v-if="loading" class="space-y-2">
          <div v-for="i in 8" :key="i" class="rounded-xl border p-4 animate-pulse" style="background: var(--surface); border-color: var(--border)">
            <div class="h-4 rounded w-2/5" style="background: var(--surface-2)"></div>
            <div class="h-3 rounded w-1/4 mt-2" style="background: var(--surface-2)"></div>
            <div class="grid grid-cols-2 gap-2 mt-3">
              <div class="h-2 rounded" style="background: var(--surface-2)"></div>
              <div class="h-2 rounded" style="background: var(--surface-2)"></div>
              <div class="h-2 rounded" style="background: var(--surface-2)"></div>
              <div class="h-2 rounded" style="background: var(--surface-2)"></div>
            </div>
          </div>
        </div>

        <div v-else-if="transactions.length === 0" class="rounded-xl border p-12 flex flex-col items-center gap-3 text-center" style="background: var(--surface); border-color: var(--border); border-style: dashed">
          <i class="pi pi-receipt text-3xl" style="color: var(--mint)"></i>
          <p class="text-sm font-medium" style="color: var(--text)">No transactions found</p>
          <p class="text-xs" style="color: var(--text-muted)">Try a different vendor, date range, category, account, or search text.</p>
        </div>

        <div v-else class="space-y-3">
          <article
            v-for="txn in transactions"
            :key="txn.id"
            class="rounded-xl border p-4"
            style="background: var(--surface); border-color: var(--border)"
          >
            <div class="flex items-start gap-3">
              <div class="w-10 h-10 rounded-lg overflow-hidden flex items-center justify-center flex-shrink-0" style="background: var(--surface-2)">
                <img v-if="txn.logo_url" :src="txn.logo_url" class="w-full h-full object-cover" :alt="txn.merchant_name || txn.name" />
                <i v-else :class="`pi ${categoryIcon(txn.category)}`" class="text-sm" style="color: var(--mint)"></i>
              </div>

              <div class="min-w-0 flex-1">
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <p class="text-base font-semibold break-words" style="color: var(--text)">{{ txn.merchant_name || txn.name || 'Unknown Vendor' }}</p>
                    <p class="text-xs mt-0.5" style="color: var(--text-muted)">
                      {{ txn.institution_name || 'Unknown Institution' }} · {{ txn.account_name || 'Unknown Account' }}
                    </p>
                  </div>
                  <p class="text-base font-semibold text-right flex-shrink-0" :style="Number(txn.amount) < 0 ? 'color: var(--mint)' : 'color: var(--text)'">
                    {{ Number(txn.amount) < 0 ? '+' : '-' }}${{ Math.abs(Number(txn.amount) || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}
                  </p>
                </div>

                <div class="mt-2 flex flex-wrap gap-2">
                  <span class="text-xs px-2 py-1 rounded-full" style="background: var(--surface-2); color: var(--text-muted)">Date: {{ formatDate(txn.date) }}</span>
                  <span class="text-xs px-2 py-1 rounded-full" style="background: var(--surface-2); color: var(--text-muted)">Category: {{ formatCategory(txn.category) }}</span>
                  <span class="text-xs px-2 py-1 rounded-full" style="background: var(--surface-2); color: var(--text-muted)">Pending: {{ txn.pending ? 'Yes' : 'No' }}</span>
                </div>

                <dl class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-x-4 gap-y-2 mt-3 text-xs">
                  <div>
                    <dt style="color: var(--text-muted)">Internal ID</dt>
                    <dd style="color: var(--text)">{{ displayValue(txn.id) }}</dd>
                  </div>
                  <div>
                    <dt style="color: var(--text-muted)">Transaction ID</dt>
                    <dd class="break-all" style="color: var(--text)">{{ displayValue(txn.txn_id) }}</dd>
                  </div>
                  <div>
                    <dt style="color: var(--text-muted)">Name</dt>
                    <dd style="color: var(--text)">{{ displayValue(txn.name) }}</dd>
                  </div>
                  <div>
                    <dt style="color: var(--text-muted)">Merchant</dt>
                    <dd style="color: var(--text)">{{ displayValue(txn.merchant_name) }}</dd>
                  </div>
                  <div>
                    <dt style="color: var(--text-muted)">Account Name</dt>
                    <dd style="color: var(--text)">{{ displayValue(txn.account_name) }}</dd>
                  </div>
                  <div>
                    <dt style="color: var(--text-muted)">Institution</dt>
                    <dd style="color: var(--text)">{{ displayValue(txn.institution_name) }}</dd>
                  </div>
                  <div>
                    <dt style="color: var(--text-muted)">Date</dt>
                    <dd style="color: var(--text)">{{ displayValue(txn.date) }}</dd>
                  </div>
                  <div>
                    <dt style="color: var(--text-muted)">Category</dt>
                    <dd style="color: var(--text)">{{ displayValue(txn.category) }}</dd>
                  </div>
                  <div>
                    <dt style="color: var(--text-muted)">Category Primary</dt>
                    <dd style="color: var(--text)">{{ displayValue(txn.category_primary) }}</dd>
                  </div>
                  <div>
                    <dt style="color: var(--text-muted)">Category Detailed</dt>
                    <dd style="color: var(--text)">{{ displayValue(txn.category_detailed) }}</dd>
                  </div>
                  <div>
                    <dt style="color: var(--text-muted)">Category Override</dt>
                    <dd style="color: var(--text)">{{ displayValue(txn.category_override) }}</dd>
                  </div>
                  <div>
                    <dt style="color: var(--text-muted)">Pending</dt>
                    <dd style="color: var(--text)">{{ txn.pending ? 'true' : 'false' }}</dd>
                  </div>
                  <div>
                    <dt style="color: var(--text-muted)">Logo URL</dt>
                    <dd class="break-all" style="color: var(--text)">{{ displayValue(txn.logo_url) }}</dd>
                  </div>
                  <div>
                    <dt style="color: var(--text-muted)">Synced At</dt>
                    <dd style="color: var(--text)">{{ formatDateTime(txn.synced_at) }}</dd>
                  </div>
                </dl>
              </div>
            </div>
          </article>
        </div>

        <div v-if="!loading && total > limit" class="flex justify-center gap-3 mt-5">
          <Button @click="prevPage" :disabled="offset === 0" label="Previous" severity="secondary" size="small" />
          <span class="text-sm self-center" style="color: var(--text-muted)">{{ offset + 1 }}–{{ Math.min(offset + limit, total) }} of {{ total }}</span>
          <Button @click="nextPage" :disabled="offset + limit >= total" label="Next" severity="secondary" size="small" />
        </div>
      </section>

      <aside class="xl:col-span-4">
        <VendorAggregation
          :vendors="vendorSummary.vendors"
          :vendor-count="vendorSummary.vendor_count"
          :total-outflow="vendorSummary.total_outflow"
          :selected-vendor="selectedVendor"
          :loading="summaryLoading"
          scope-label="all filtered transactions"
          @select-vendor="selectVendor"
        />
      </aside>
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
  { value: 'MORTGAGE_PAYMENT', label: 'Mortgage Payment' },
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
const selectedVendor = ref('')
const limit = ref(25)
const offset = ref(0)
const vendorSummary = ref({ vendors: [], vendor_count: 0, total_outflow: 0 })
const summaryLoading = ref(false)
let searchTimer = null
const { syncIfStale } = usePlaidSync()

const load = async () => {
  loading.value = true
  summaryLoading.value = true
  try {
    const listParams = new URLSearchParams({
      limit: limit.value,
      offset: offset.value,
    })
    const summaryParams = new URLSearchParams()

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
      listParams.set('search', search.value.trim())
      summaryParams.set('search', search.value.trim())
    }
    if (selectedVendor.value) {
      listParams.set('vendor', selectedVendor.value)
    }

    const [listResult, summaryResult] = await Promise.allSettled([
      api.get(`/api/transactions?${listParams}`),
      api.get(`/api/transactions/vendors-summary?${summaryParams}`),
    ])

    if (listResult.status !== 'fulfilled') {
      throw listResult.reason
    }

    const res = listResult.value
    transactions.value = res.data.transactions || []
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
    total.value = 0
    vendorSummary.value = { vendors: [], vendor_count: 0, total_outflow: 0 }
  } finally {
    loading.value = false
    summaryLoading.value = false
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

const selectVendor = (vendorName) => {
  if (selectedVendor.value === vendorName) {
    selectedVendor.value = ''
  } else {
    selectedVendor.value = vendorName || ''
  }
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
const formatDateTime = (d) => {
  if (!d) return '—'
  const parsed = new Date(d)
  return Number.isNaN(parsed.getTime()) ? String(d) : parsed.toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })
}
const formatCategory = (c) => c ? c.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase()) : '—'
const displayValue = (value) => (value === null || value === undefined || value === '' ? '—' : String(value))
const categoryIcon = (c) => {
  if (!c) return 'pi-receipt'
  const map = {
    MORTGAGE_PAYMENT: 'pi-home',
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
