<template>
  <div class="p-6 max-w-5xl mx-auto">
    <div class="flex items-center justify-between mb-8">
      <div>
        <h1 class="text-2xl font-bold" style="color: var(--text)">Properties</h1>
        <p class="text-sm mt-1" style="color: var(--text-muted)">Real estate portfolio · ${{ fmt(totalEquity) }} total equity</p>
      </div>
      <div class="flex items-center gap-2">
        <input ref="jsonImportInput" type="file" accept=".json,application/json" class="hidden" @change="importPropertyJson" :disabled="importingJson" />
        <Button @click="openJsonImporter" :label="importingJson ? 'Importing…' : 'Import JSON'" icon="pi pi-file-import" severity="secondary" outlined :loading="importingJson" :disabled="importingJson" />
        <Button @click="showAdd = true" label="Add Property" icon="pi pi-plus" class="p-button-primary" />
      </div>
    </div>

    <!-- Portfolio summary -->
    <div v-if="properties.length" class="grid grid-cols-3 gap-4 mb-8">
      <div class="rounded-xl border p-4 text-center" style="background: var(--surface); border-color: var(--border)">
        <p class="text-xs mb-1" style="color: var(--text-muted)">Total Value</p>
        <p class="text-lg font-bold" style="color: var(--text)">${{ fmt(totalValue) }}</p>
      </div>
      <div class="rounded-xl border p-4 text-center" style="background: var(--surface); border-color: var(--mint)">
        <p class="text-xs mb-1" style="color: var(--text-muted)">Total Equity</p>
        <p class="text-lg font-bold" style="color: var(--mint)">${{ fmt(totalEquity) }}</p>
      </div>
      <div class="rounded-xl border p-4 text-center" style="background: var(--surface); border-color: var(--border)">
        <p class="text-xs mb-1" style="color: var(--text-muted)">Total Mortgage</p>
        <p class="text-lg font-bold" style="color: var(--text)">${{ fmt(totalMortgage) }}</p>
      </div>
    </div>

    <!-- Empty -->
    <div v-if="!loading && properties.length === 0" class="rounded-xl border p-12 flex flex-col items-center gap-3 text-center" style="background: var(--surface); border-color: var(--border); border-style: dashed">
      <i class="pi pi-building text-3xl" style="color: var(--mint)"></i>
      <p class="text-sm font-medium" style="color: var(--text)">No properties added</p>
      <p class="text-xs" style="color: var(--text-muted)">Add your real estate investments to track equity and cash flow</p>
      <div class="flex items-center gap-2 mt-1">
        <Button @click="showAdd = true" label="Add first property" class="p-button-primary" size="small" />
        <Button @click="openJsonImporter" label="Import JSON" icon="pi pi-file-import" severity="secondary" outlined size="small" :loading="importingJson" :disabled="importingJson" />
      </div>
    </div>

    <!-- Property grid -->
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <RouterLink v-for="p in properties" :key="p.id" :to="`/properties/${p.id}`"
        class="block rounded-xl border p-5 hover:border-[color:var(--mint)] transition-colors cursor-pointer"
        style="background: var(--surface); border-color: var(--border)">
        <div class="flex items-start justify-between mb-3">
          <div class="flex items-center gap-2">
            <i class="pi pi-building" style="color: var(--mint)"></i>
            <p class="font-semibold text-sm" style="color: var(--text)">{{ p.address }}</p>
          </div>
          <button @click.prevent="deleteProperty(p.id)" class="p-1 hover:opacity-80" style="color: var(--text-muted)">
            <i class="pi pi-trash text-xs"></i>
          </button>
        </div>
        <p class="text-xs mb-4" style="color: var(--text-muted)">{{ [p.city, p.state].filter(Boolean).join(', ') }}</p>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <p class="text-xs" style="color: var(--text-muted)">Current Value</p>
            <p class="font-bold text-sm mt-0.5" style="color: var(--text)">${{ fmt(p.current_value) }}</p>
          </div>
          <div>
            <p class="text-xs" style="color: var(--text-muted)">Equity</p>
            <p class="font-bold text-sm mt-0.5" style="color: var(--mint)">${{ fmt(p.equity) }}</p>
          </div>
          <div>
            <p class="text-xs" style="color: var(--text-muted)">Mortgage Balance</p>
            <p class="text-sm mt-0.5" style="color: var(--text)">${{ fmt(p.mortgage_balance) }}</p>
          </div>
          <div>
            <p class="text-xs" style="color: var(--text-muted)">Monthly Payment</p>
            <p class="text-sm mt-0.5" style="color: var(--text)">${{ fmt(p.mortgage_payment) }}</p>
          </div>
        </div>
      </RouterLink>
    </div>

    <!-- Add dialog -->
    <Dialog v-model:visible="showAdd" header="Add Property" modal :style="{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text)', width: '420px' }">
      <div class="space-y-3 py-2">
        <div>
          <div class="flex items-center justify-between mb-1.5">
            <label class="block text-xs" style="color: var(--text-muted)">Street Address *</label>
            <button
              @click="autofillFromAddress"
              :disabled="autofilling || !form.address"
              class="text-[11px] px-2 py-1 rounded hover:opacity-80 disabled:opacity-40"
              style="background: var(--surface-2); color: var(--text-muted)"
            >
              {{ autofilling ? 'Fetching…' : 'Auto-fill from address' }}
            </button>
          </div>
          <InputText v-model="form.address" class="w-full" placeholder="123 Main St" />
          <p v-if="autofillNote" class="text-[11px] mt-1" style="color: var(--text-muted)">{{ autofillNote }}</p>
        </div>
        <div class="grid grid-cols-4 gap-2">
          <div class="col-span-2">
            <label class="block text-xs mb-1.5" style="color: var(--text-muted)">City</label>
            <InputText v-model="form.city" class="w-full" placeholder="City" />
          </div>
          <div>
            <label class="block text-xs mb-1.5" style="color: var(--text-muted)">State</label>
            <InputText v-model="form.state" class="w-full" placeholder="TX" maxlength="2" />
          </div>
          <div>
            <label class="block text-xs mb-1.5" style="color: var(--text-muted)">ZIP</label>
            <InputText v-model="form.zip" class="w-full" placeholder="78701" maxlength="10" />
          </div>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <div>
            <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Purchase Price</label>
            <InputText v-model="form.purchase_price" type="number" class="w-full" placeholder="0" />
          </div>
          <div>
            <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Current Value</label>
            <InputText v-model="form.current_value" type="number" class="w-full" placeholder="0" />
          </div>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <div>
            <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Mortgage Balance</label>
            <InputText v-model="form.mortgage_balance" type="number" class="w-full" placeholder="0" />
          </div>
          <div>
            <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Monthly Payment</label>
            <InputText v-model="form.mortgage_payment" type="number" class="w-full" placeholder="0" />
          </div>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <div>
            <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Rate (%)</label>
            <InputText v-model="form.mortgage_rate" type="number" step="0.001" class="w-full" placeholder="6.5" />
          </div>
          <div>
            <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Purchase Date</label>
            <InputText v-model="form.purchase_date" type="date" class="w-full" />
          </div>
        </div>
      </div>
      <template #footer>
        <Button @click="showAdd = false" label="Cancel" severity="secondary" text />
        <Button @click="addProperty" label="Add Property" class="p-button-primary" :loading="saving" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import api from '@/utils/api'

const properties = ref([])
const loading = ref(true)
const showAdd = ref(false)
const saving = ref(false)
const importingJson = ref(false)
const autofilling = ref(false)
const autofillNote = ref('')
const jsonImportInput = ref(null)
const form = ref({ address: '', city: '', state: '', zip: '', purchase_price: '', current_value: '', mortgage_balance: '', mortgage_payment: '', mortgage_rate: '', purchase_date: '' })

const totalValue = computed(() => properties.value.reduce((s, p) => s + (p.current_value || 0), 0))
const totalMortgage = computed(() => properties.value.reduce((s, p) => s + (p.mortgage_balance || 0), 0))
const totalEquity = computed(() => totalValue.value - totalMortgage.value)
const fmt = (v) => v != null ? Number(v).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) : '—'

const load = async () => {
  loading.value = true
  try { const res = await api.get('/api/properties'); properties.value = res.data }
  finally { loading.value = false }
}

const numOrNull = (v) => v !== '' && v != null ? Number(v) : null

const autofillFromAddress = async () => {
  if (!form.value.address) return
  autofilling.value = true
  autofillNote.value = ''
  try {
    const res = await api.post('/api/properties/enrich-address', {
      address: form.value.address,
      city: form.value.city || null,
      state: form.value.state || null,
      zip: form.value.zip || null,
    })

    const std = res.data?.standardized || {}
    if (std.city && !form.value.city) form.value.city = std.city
    if (std.state && !form.value.state) form.value.state = std.state
    if (std.zip && !form.value.zip) form.value.zip = std.zip

    if ((form.value.current_value === '' || form.value.current_value == null) && res.data?.suggested_current_value != null) {
      form.value.current_value = Math.round(Number(res.data.suggested_current_value))
    }

    if (res.data?.suggested_current_value != null) {
      autofillNote.value = `Filled from online estimate: $${Number(res.data.suggested_current_value).toLocaleString('en-US', { maximumFractionDigits: 0 })}`
    } else {
      autofillNote.value = 'Address standardized. No value estimate found for this location.'
    }
  } catch (err) {
    autofillNote.value = err.response?.data?.detail || 'Could not fetch online address details'
  } finally {
    autofilling.value = false
  }
}

const addProperty = async () => {
  if (!form.value.address) return
  saving.value = true
  try {
    await api.post('/api/properties', {
      ...form.value,
      purchase_price: numOrNull(form.value.purchase_price),
      current_value: numOrNull(form.value.current_value),
      mortgage_balance: numOrNull(form.value.mortgage_balance),
      mortgage_payment: numOrNull(form.value.mortgage_payment),
      mortgage_rate: numOrNull(form.value.mortgage_rate),
      purchase_date: form.value.purchase_date || null,
    })
    showAdd.value = false
    autofillNote.value = ''
    form.value = { address: '', city: '', state: '', zip: '', purchase_price: '', current_value: '', mortgage_balance: '', mortgage_payment: '', mortgage_rate: '', purchase_date: '' }
    await load()
  } finally { saving.value = false }
}

const openJsonImporter = () => {
  jsonImportInput.value?.click()
}

const importPropertyJson = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  e.target.value = ''
  importingJson.value = true

  try {
    const formData = new FormData()
    formData.append('file', file)
    await api.post('/api/properties/import-json', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    await load()
  } catch (err) {
    alert(err.response?.data?.detail || 'JSON import failed')
  } finally {
    importingJson.value = false
  }
}

const deleteProperty = async (id) => {
  if (!confirm('Delete this property and all its data?')) return
  await api.delete(`/api/properties/${id}`)
  properties.value = properties.value.filter(p => p.id !== id)
}

onMounted(load)
</script>
