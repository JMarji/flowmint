<template>
  <div class="p-6 max-w-4xl mx-auto">
    <div class="flex items-center justify-between mb-8">
      <div>
        <h1 class="text-2xl font-bold" style="color: var(--text)">Bills</h1>
        <p class="text-sm mt-1" style="color: var(--text-muted)">Recurring payments — ${{ fmt(totalMonthly) }}/mo</p>
      </div>
      <Button @click="showAdd = true" label="Add Bill" icon="pi pi-plus" class="p-button-primary" />
    </div>

    <!-- Upcoming banner -->
    <div v-if="upcoming.length" class="rounded-xl border p-4 mb-6 flex items-center gap-3" style="background: var(--surface); border-color: var(--mint)">
      <i class="pi pi-bell text-lg" style="color: var(--mint)"></i>
      <div>
        <p class="text-sm font-medium" style="color: var(--text)">{{ upcoming.length }} bill{{ upcoming.length > 1 ? 's' : '' }} due in the next 7 days</p>
        <p class="text-xs" style="color: var(--text-muted)">{{ upcoming.map(b => b.name).join(', ') }}</p>
      </div>
    </div>

    <!-- Empty -->
    <div v-if="!loading && bills.length === 0" class="rounded-xl border p-12 flex flex-col items-center gap-3 text-center" style="background: var(--surface); border-color: var(--border); border-style: dashed">
      <i class="pi pi-calendar-clock text-3xl" style="color: var(--mint)"></i>
      <p class="text-sm font-medium" style="color: var(--text)">No bills added yet</p>
      <Button @click="showAdd = true" label="Add your first bill" class="p-button-primary mt-1" size="small" />
    </div>

    <div class="space-y-3">
      <div v-for="bill in bills" :key="bill.id" class="rounded-xl border p-4 flex items-center gap-4" :style="`background: var(--surface); border-color: ${isDueSoon(bill) ? 'var(--mint)' : 'var(--border)'}`">
        <!-- Due day badge -->
        <div class="w-12 h-12 rounded-xl flex flex-col items-center justify-center flex-shrink-0" style="background: var(--surface-2)">
          <p class="text-lg font-bold leading-none" style="color: var(--mint)">{{ bill.due_day_of_month }}</p>
          <p class="text-xs" style="color: var(--text-muted)">day</p>
        </div>

        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium" style="color: var(--text)">{{ bill.name }}</p>
          <p class="text-xs" style="color: var(--text-muted)">
            {{ fmtCat(bill.category) || 'Uncategorized' }}
            <span v-if="bill.last_paid_date" class="ml-2">· Paid {{ bill.last_paid_date }}</span>
          </p>
        </div>

        <p class="text-base font-bold flex-shrink-0" style="color: var(--text)">${{ fmt(bill.amount) }}</p>

        <div class="flex gap-1 flex-shrink-0">
          <Button @click="markPaid(bill)" icon="pi pi-check" severity="secondary" text rounded size="small" title="Mark paid" />
          <Button @click="deleteBill(bill.id)" icon="pi pi-trash" severity="secondary" text rounded size="small" title="Delete" />
        </div>
      </div>
    </div>

    <!-- Add dialog -->
    <Dialog v-model:visible="showAdd" header="Add Bill" modal :style="{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text)', width: '360px' }">
      <div class="space-y-4 py-2">
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Name</label>
          <InputText v-model="form.name" class="w-full" placeholder="Netflix, Mortgage, etc." />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Amount ($)</label>
            <InputText v-model="form.amount" type="number" min="0.01" step="0.01" class="w-full" placeholder="0.00" />
          </div>
          <div>
            <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Due day of month</label>
            <InputText v-model="form.due_day_of_month" type="number" min="1" max="31" class="w-full" placeholder="1–31" />
          </div>
        </div>
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Category (optional)</label>
          <select v-model="form.category" class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--surface-2); border: 1px solid var(--border); color: var(--text)">
            <option value="">None</option>
            <option value="RENT_AND_UTILITIES">Rent & Utilities</option>
            <option value="SUBSCRIPTION">Subscription</option>
            <option value="INSURANCE">Insurance</option>
            <option value="LOAN">Loan</option>
            <option value="OTHER">Other</option>
          </select>
        </div>
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Notes (optional)</label>
          <InputText v-model="form.notes" class="w-full" placeholder="Optional notes" />
        </div>
      </div>
      <template #footer>
        <Button @click="showAdd = false" label="Cancel" severity="secondary" text />
        <Button @click="addBill" label="Add Bill" class="p-button-primary" :loading="saving" />
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

const bills = ref([])
const loading = ref(true)
const showAdd = ref(false)
const saving = ref(false)
const form = ref({ name: '', amount: '', due_day_of_month: '', category: '', notes: '' })

const totalMonthly = computed(() => bills.value.filter(b => b.is_active).reduce((s, b) => s + b.amount, 0))
const upcoming = computed(() => {
  const today = new Date()
  return bills.value.filter(b => {
    const d = new Date(today.getFullYear(), today.getMonth(), b.due_day_of_month)
    if (d < today) d.setMonth(d.getMonth() + 1)
    return (d - today) / 86400000 <= 7
  })
})

const fmt = (v) => Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const fmtCat = (c) => c?.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase())
const isDueSoon = (b) => upcoming.value.some(u => u.id === b.id)

const load = async () => {
  loading.value = true
  try { const res = await api.get('/api/bills'); bills.value = res.data }
  finally { loading.value = false }
}

const addBill = async () => {
  saving.value = true
  try {
    await api.post('/api/bills', { ...form.value, amount: Number(form.value.amount), due_day_of_month: Number(form.value.due_day_of_month) })
    showAdd.value = false
    form.value = { name: '', amount: '', due_day_of_month: '', category: '', notes: '' }
    await load()
  } finally { saving.value = false }
}

const markPaid = async (bill) => {
  await api.post(`/api/bills/${bill.id}/mark-paid`, {})
  await load()
}

const deleteBill = async (id) => {
  await api.delete(`/api/bills/${id}`)
  bills.value = bills.value.filter(b => b.id !== id)
}

onMounted(load)
</script>
