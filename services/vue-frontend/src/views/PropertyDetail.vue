<template>
  <div class="p-6 max-w-5xl mx-auto">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-6">
      <RouterLink to="/properties" class="p-2 rounded-lg hover:opacity-80 transition" style="color: var(--text-muted); background: var(--surface-2)">
        <i class="pi pi-arrow-left text-sm"></i>
      </RouterLink>
      <div>
        <h1 class="text-xl font-bold" style="color: var(--text)">{{ property?.address || '…' }}</h1>
        <p class="text-xs" style="color: var(--text-muted)">{{ [property?.city, property?.state].filter(Boolean).join(', ') }}</p>
      </div>
    </div>

    <!-- Stats -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8" v-if="property">
      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--mint)">
        <p class="text-xs mb-1" style="color: var(--text-muted)">Current Value</p>
        <p class="text-lg font-bold" style="color: var(--mint)">${{ fmt(property.current_value) }}</p>
      </div>
      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <p class="text-xs mb-1" style="color: var(--text-muted)">Equity</p>
        <p class="text-lg font-bold" style="color: var(--text)">${{ fmt(property.equity) }}</p>
      </div>
      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <p class="text-xs mb-1" style="color: var(--text-muted)">Mortgage Balance</p>
        <p class="text-lg font-bold" style="color: var(--text)">${{ fmt(property.mortgage_balance) }}</p>
      </div>
      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <p class="text-xs mb-1" style="color: var(--text-muted)">Monthly Payment</p>
        <p class="text-lg font-bold" style="color: var(--text)">${{ fmt(property.mortgage_payment) }}</p>
      </div>
    </div>

    <!-- Tabs -->
    <div class="flex gap-2 mb-5">
      <button v-for="t in ['transactions','documents']" :key="t" @click="tab = t"
        class="px-4 py-2 rounded-lg text-sm font-medium transition capitalize"
        :style="tab === t ? 'background: var(--mint); color: #080C0B' : 'background: var(--surface-2); color: var(--text-muted)'">
        {{ t }}
      </button>
    </div>

    <!-- Transactions tab -->
    <div v-if="tab === 'transactions'">
      <div class="flex justify-between items-center mb-4">
        <div class="flex gap-2">
          <button v-for="f in ['all','income','expense']" :key="f" @click="txnFilter = f; loadTxns()"
            class="px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition"
            :style="txnFilter === f ? 'background: var(--mint); color: #080C0B' : 'background: var(--surface-2); color: var(--text-muted)'">
            {{ f }}
          </button>
        </div>
        <Button @click="showAddTxn = true" label="Add" icon="pi pi-plus" class="p-button-primary" size="small" />
      </div>

      <!-- Summary -->
      <div v-if="txnSummary" class="grid grid-cols-3 gap-3 mb-4">
        <div class="rounded-lg p-3 text-center" style="background: var(--surface-2)">
          <p class="text-xs" style="color: var(--text-muted)">Income</p>
          <p class="font-bold text-sm mt-0.5" style="color: var(--mint)">${{ fmt(txnSummary.income) }}</p>
        </div>
        <div class="rounded-lg p-3 text-center" style="background: var(--surface-2)">
          <p class="text-xs" style="color: var(--text-muted)">Expenses</p>
          <p class="font-bold text-sm mt-0.5" style="color: #f87171">${{ fmt(txnSummary.expenses) }}</p>
        </div>
        <div class="rounded-lg p-3 text-center" style="background: var(--surface-2)">
          <p class="text-xs" style="color: var(--text-muted)">Net</p>
          <p class="font-bold text-sm mt-0.5" :style="txnSummary.net >= 0 ? 'color: var(--mint)' : 'color: #f87171'">${{ fmt(txnSummary.net) }}</p>
        </div>
      </div>

      <div v-if="transactions.length === 0" class="rounded-xl border p-8 text-center" style="background: var(--surface); border-color: var(--border); border-style: dashed">
        <p class="text-sm" style="color: var(--text-muted)">No transactions yet</p>
      </div>
      <div v-else class="rounded-xl border overflow-hidden" style="background: var(--surface); border-color: var(--border)">
        <div v-for="(txn, i) in transactions" :key="txn.id"
          class="flex items-center gap-4 px-4 py-3 border-b last:border-0"
          :style="i % 2 !== 0 ? 'background: var(--surface-2); border-color: var(--border)' : 'border-color: var(--border)'">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
            :style="txn.type === 'income' ? 'background: rgba(61,219,184,0.15)' : 'background: rgba(248,113,113,0.15)'">
            <i :class="`pi ${txn.type === 'income' ? 'pi-arrow-down-left' : 'pi-arrow-up-right'} text-sm`"
              :style="txn.type === 'income' ? 'color: var(--mint)' : 'color: #f87171'"></i>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm" style="color: var(--text)">{{ txn.description || txn.category || txn.type }}</p>
            <p class="text-xs" style="color: var(--text-muted)">{{ txn.date }}</p>
          </div>
          <p class="font-semibold text-sm" :style="txn.type === 'income' ? 'color: var(--mint)' : 'color: #f87171'">
            {{ txn.type === 'income' ? '+' : '-' }}${{ fmt(txn.amount) }}
          </p>
          <button @click="deleteTxn(txn.id)" style="color: var(--text-muted)" class="hover:opacity-80">
            <i class="pi pi-trash text-xs"></i>
          </button>
        </div>
      </div>
    </div>

    <!-- Documents tab -->
    <div v-if="tab === 'documents'">
      <div class="flex justify-between items-center mb-4">
        <p class="text-sm" style="color: var(--text-muted)">{{ docs.length }} document{{ docs.length !== 1 ? 's' : '' }}</p>
        <label class="cursor-pointer">
          <input type="file" class="hidden" @change="uploadFile" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" />
          <span class="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium cursor-pointer" style="background: var(--mint); color: #080C0B">
            <i class="pi pi-upload"></i> Upload
          </span>
        </label>
      </div>
      <div v-if="uploadProgress > 0 && uploadProgress < 100" class="mb-4 h-1.5 rounded-full overflow-hidden" style="background: var(--surface-2)">
        <div class="h-full rounded-full transition-all" :style="`width: ${uploadProgress}%; background: var(--mint)`"></div>
      </div>
      <div v-if="docs.length === 0" class="rounded-xl border p-8 text-center" style="background: var(--surface); border-color: var(--border); border-style: dashed">
        <i class="pi pi-file text-2xl mb-2" style="color: var(--mint)"></i>
        <p class="text-sm" style="color: var(--text-muted)">No documents uploaded</p>
      </div>
      <div v-else class="space-y-2">
        <div v-for="doc in docs" :key="doc.id" class="flex items-center gap-3 p-3 rounded-lg" style="background: var(--surface); border: 1px solid var(--border)">
          <i class="pi pi-file-pdf text-lg" style="color: var(--mint)"></i>
          <div class="flex-1 min-w-0">
            <p class="text-sm truncate" style="color: var(--text)">{{ doc.name }}</p>
            <p class="text-xs" style="color: var(--text-muted)">{{ fmtBytes(doc.size_bytes) }} · {{ doc.uploaded_at.slice(0,10) }}</p>
          </div>
          <button @click="downloadDoc(doc)" title="Download" style="color: var(--mint)" class="hover:opacity-80"><i class="pi pi-download"></i></button>
          <button @click="deleteDoc(doc.id)" style="color: var(--text-muted)" class="hover:opacity-80"><i class="pi pi-trash text-xs"></i></button>
        </div>
      </div>
    </div>

    <!-- Add transaction dialog -->
    <Dialog v-model:visible="showAddTxn" header="Add Transaction" modal :style="{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text)', width: '360px' }">
      <div class="space-y-3 py-2">
        <div class="flex gap-2">
          <button v-for="t in ['income','expense']" :key="t" @click="txnForm.type = t"
            class="flex-1 py-2 rounded-lg text-sm font-medium capitalize transition"
            :style="txnForm.type === t ? 'background: var(--mint); color: #080C0B' : 'background: var(--surface-2); color: var(--text-muted)'">
            {{ t }}
          </button>
        </div>
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Amount ($)</label>
          <InputText v-model="txnForm.amount" type="number" step="0.01" min="0.01" class="w-full" placeholder="0.00" />
        </div>
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Date</label>
          <InputText v-model="txnForm.date" type="date" class="w-full" />
        </div>
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Description</label>
          <InputText v-model="txnForm.description" class="w-full" placeholder="Rent payment, repair, etc." />
        </div>
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Category</label>
          <select v-model="txnForm.category" class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--surface-2); border: 1px solid var(--border); color: var(--text)">
            <option value="">None</option>
            <option value="rent">Rent</option>
            <option value="mortgage">Mortgage Payment</option>
            <option value="maintenance">Maintenance</option>
            <option value="insurance">Insurance</option>
            <option value="taxes">Property Taxes</option>
            <option value="utilities">Utilities</option>
            <option value="other">Other</option>
          </select>
        </div>
      </div>
      <template #footer>
        <Button @click="showAddTxn = false" label="Cancel" severity="secondary" text />
        <Button @click="addTxn" label="Add" class="p-button-primary" :loading="savingTxn" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import api from '@/utils/api'

const route = useRoute()
const propertyId = route.params.id

const property = ref(null)
const transactions = ref([])
const txnSummary = ref(null)
const docs = ref([])
const tab = ref('transactions')
const txnFilter = ref('all')
const showAddTxn = ref(false)
const savingTxn = ref(false)
const uploadProgress = ref(0)
const txnForm = ref({ type: 'income', amount: '', date: new Date().toISOString().slice(0,10), description: '', category: '' })

const fmt = (v) => v != null ? Number(v).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) : '—'
const fmtBytes = (b) => b > 1048576 ? `${(b/1048576).toFixed(1)} MB` : `${(b/1024).toFixed(0)} KB`

const loadProperty = async () => {
  const res = await api.get(`/api/properties/${propertyId}`)
  property.value = res.data
}

const loadTxns = async () => {
  const params = txnFilter.value !== 'all' ? `?txn_type=${txnFilter.value}` : ''
  const res = await api.get(`/api/properties/${propertyId}/transactions${params}`)
  transactions.value = res.data.transactions
  txnSummary.value = { income: res.data.income, expenses: res.data.expenses, net: res.data.net }
}

const loadDocs = async () => {
  const res = await api.get(`/api/documents?property_id=${propertyId}`)
  docs.value = res.data
}

const addTxn = async () => {
  savingTxn.value = true
  try {
    await api.post(`/api/properties/${propertyId}/transactions`, { ...txnForm.value, amount: Number(txnForm.value.amount) })
    showAddTxn.value = false
    txnForm.value = { type: 'income', amount: '', date: new Date().toISOString().slice(0,10), description: '', category: '' }
    await loadTxns()
  } finally { savingTxn.value = false }
}

const deleteTxn = async (id) => {
  await api.delete(`/api/properties/${propertyId}/transactions/${id}`)
  transactions.value = transactions.value.filter(t => t.id !== id)
}

const uploadFile = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  uploadProgress.value = 10

  const { data } = await api.post('/api/documents/upload-url', {
    name: file.name, content_type: file.type,
    size_bytes: file.size, property_id: Number(propertyId)
  })
  uploadProgress.value = 30

  await fetch(data.upload_url, { method: 'PUT', body: file, headers: { 'Content-Type': file.type } })
  uploadProgress.value = 80

  await api.post('/api/documents', {
    name: file.name, s3_key: data.s3_key, content_type: file.type,
    size_bytes: file.size, property_id: Number(propertyId)
  })
  uploadProgress.value = 100
  setTimeout(() => { uploadProgress.value = 0 }, 1000)
  await loadDocs()
  e.target.value = ''
}

const downloadDoc = async (doc) => {
  const { data } = await api.get(`/api/documents/${doc.id}/download-url`)
  window.open(data.download_url, '_blank')
}

const deleteDoc = async (id) => {
  await api.delete(`/api/documents/${id}`)
  docs.value = docs.value.filter(d => d.id !== id)
}

onMounted(async () => {
  await Promise.all([loadProperty(), loadTxns(), loadDocs()])
})
</script>
