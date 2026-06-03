<template>
  <div class="p-6 max-w-6xl mx-auto">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
      <div>
        <h1 class="text-2xl font-bold" style="color: var(--text)">Bills</h1>
        <p class="text-sm mt-1" style="color: var(--text-muted)">
          Monthly calendar with recurring withdrawals - ${{ fmt(totalMonthly) }}/mo
        </p>
      </div>
      <div class="flex gap-2">
        <Button @click="openPlotDialog(selectedDateIso)" label="Plot Day" icon="pi pi-calendar-plus" severity="secondary" />
        <Button @click="showAdd = true" label="Add Bill" icon="pi pi-plus" class="p-button-primary" />
      </div>
    </div>

    <div v-if="upcoming.length" class="rounded-xl border p-4 mb-5 flex items-center gap-3" style="background: var(--surface); border-color: var(--mint)">
      <i class="pi pi-bell text-lg" style="color: var(--mint)"></i>
      <div>
        <p class="text-sm font-medium" style="color: var(--text)">{{ upcoming.length }} bill{{ upcoming.length > 1 ? 's' : '' }} due in the next 7 days</p>
        <p class="text-xs" style="color: var(--text-muted)">{{ upcoming.map(b => b.name).join(', ') }}</p>
      </div>
    </div>

    <div class="grid lg:grid-cols-12 gap-4">
      <section class="lg:col-span-9 rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <div class="flex items-center justify-between mb-3">
          <Button icon="pi pi-chevron-left" severity="secondary" text rounded @click="prevMonth" />
          <p class="text-sm font-semibold" style="color: var(--text)">{{ monthLabel }}</p>
          <Button icon="pi pi-chevron-right" severity="secondary" text rounded @click="nextMonth" />
        </div>

        <div class="grid grid-cols-7 gap-1 mb-1">
          <p v-for="wd in WEEK_DAYS" :key="wd" class="text-[11px] text-center py-1" style="color: var(--text-muted)">{{ wd }}</p>
        </div>

        <div class="grid grid-cols-7 gap-1">
          <button
            v-for="cell in calendarCells"
            :key="cell.iso"
            @click="selectedDateIso = cell.iso"
            class="min-h-[108px] rounded-lg border p-2 text-left transition"
            :style="cellStyle(cell)"
          >
            <div class="flex items-center justify-between mb-1">
              <p class="text-xs font-medium" :style="cellDayStyle(cell)">{{ cell.day }}</p>
              <i v-if="cell.isToday" class="pi pi-circle-fill text-[8px]" style="color: var(--mint)"></i>
            </div>
            <div class="space-y-1">
              <div
                v-for="event in cell.events.slice(0, 3)"
                :key="event.id"
                class="text-[10px] px-1.5 py-1 rounded truncate"
                :style="event.type === 'bill' ? 'background: rgba(61,219,184,0.16); color: var(--mint)' : 'background: rgba(96,165,250,0.16); color: #60a5fa'"
                :title="`${event.name} · $${fmt(event.amount)}`"
              >
                {{ event.name }} · ${{ fmt(event.amount) }}
              </div>
              <p v-if="cell.events.length > 3" class="text-[10px]" style="color: var(--text-muted)">+{{ cell.events.length - 3 }} more</p>
            </div>
          </button>
        </div>

        <div v-if="!loading && bills.length === 0" class="rounded-xl border p-8 mt-4 flex flex-col items-center gap-2 text-center" style="background: var(--surface-2); border-color: var(--border); border-style: dashed">
          <i class="pi pi-calendar-clock text-2xl" style="color: var(--mint)"></i>
          <p class="text-sm" style="color: var(--text)">No recurring bills yet</p>
          <Button @click="showAdd = true" label="Add your first bill" class="p-button-primary" size="small" />
        </div>
      </section>

      <aside class="lg:col-span-3 rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <p class="text-xs mb-1" style="color: var(--text-muted)">Selected Day</p>
        <p class="text-sm font-semibold mb-3" style="color: var(--text)">{{ selectedDateLabel }}</p>

        <div v-if="selectedEvents.length === 0" class="rounded-lg border p-3 text-xs" style="border-color: var(--border); color: var(--text-muted)">
          No scheduled bill activity.
        </div>

        <div v-else class="space-y-2">
          <div v-for="event in selectedEvents" :key="event.id" class="rounded-lg border p-2.5" style="border-color: var(--border); background: var(--surface-2)">
            <p class="text-xs font-medium" style="color: var(--text)">{{ event.name }}</p>
            <p class="text-[11px]" style="color: var(--text-muted)">${{ fmt(event.amount) }} · {{ event.type === 'bill' ? 'Recurring bill' : 'Plotted day' }}</p>
            <div class="flex gap-1 mt-2">
              <Button
                v-if="event.type === 'bill'"
                @click="markPaid(event.bill)"
                icon="pi pi-check"
                text
                rounded
                severity="secondary"
                size="small"
                title="Mark paid"
              />
              <Button
                v-if="event.type === 'bill'"
                @click="openPlotDialog(selectedDateIso, event.bill)"
                icon="pi pi-calendar-plus"
                text
                rounded
                severity="secondary"
                size="small"
                title="Plot transaction day"
              />
              <Button
                v-if="event.type === 'plot'"
                @click="removePlotEvent(event.id)"
                icon="pi pi-trash"
                text
                rounded
                severity="secondary"
                size="small"
                title="Remove plotted day"
              />
            </div>
          </div>
        </div>

        <Button @click="openPlotDialog(selectedDateIso)" label="Plot On This Day" icon="pi pi-calendar-plus" class="w-full mt-3" severity="secondary" />

        <div class="border-t mt-4 pt-3" style="border-color: var(--border)">
          <p class="text-xs mb-2" style="color: var(--text-muted)">Recurring Bills</p>
          <div v-if="loading" class="text-xs" style="color: var(--text-muted)">Loading...</div>
          <div v-else class="space-y-1.5 max-h-56 overflow-y-auto pr-1">
            <div v-for="bill in bills" :key="bill.id" class="rounded-md px-2 py-1.5 flex items-center justify-between" style="background: var(--surface-2)">
              <div class="min-w-0">
                <p class="text-xs truncate" style="color: var(--text)">{{ bill.name }}</p>
                <p class="text-[10px]" style="color: var(--text-muted)">Day {{ bill.due_day_of_month }}</p>
              </div>
              <Button @click="deleteBill(bill.id)" icon="pi pi-trash" text rounded severity="secondary" size="small" />
            </div>
          </div>
        </div>
      </aside>
    </div>

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
            <InputText v-model="form.due_day_of_month" type="number" min="1" max="31" class="w-full" placeholder="1-31" />
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

    <Dialog v-model:visible="showPlot" header="Plot Transaction Day" modal :style="{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text)', width: '380px' }">
      <div class="space-y-3 py-2">
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Date</label>
          <InputText v-model="plotForm.date" type="date" class="w-full" />
        </div>
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Use Existing Bill (optional)</label>
          <select v-model="plotForm.bill_id" @change="applyBillToPlotForm" class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--surface-2); border: 1px solid var(--border); color: var(--text)">
            <option value="">None</option>
            <option v-for="bill in bills" :key="bill.id" :value="String(bill.id)">{{ bill.name }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Name</label>
          <InputText v-model="plotForm.name" class="w-full" placeholder="Mortgage, Electric, etc." />
        </div>
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Amount ($)</label>
          <InputText v-model="plotForm.amount" type="number" min="0" step="0.01" class="w-full" placeholder="0.00" />
        </div>
      </div>
      <template #footer>
        <Button @click="showPlot = false" label="Cancel" severity="secondary" text />
        <Button @click="addPlotEvent" label="Plot" class="p-button-primary" :loading="savingPlot" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import api from '@/utils/api'

const WEEK_DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const PLOT_STORAGE_KEY = 'flowmint-bill-plots-v1'

const bills = ref([])
const loading = ref(true)
const showAdd = ref(false)
const saving = ref(false)
const form = ref({ name: '', amount: '', due_day_of_month: '', category: '', notes: '' })
const viewMonth = ref(new Date(new Date().getFullYear(), new Date().getMonth(), 1))
const selectedDateIso = ref(toIsoDate(new Date()))
const showPlot = ref(false)
const savingPlot = ref(false)
const plottedEvents = ref([])
const plotForm = ref({ date: toIsoDate(new Date()), bill_id: '', name: '', amount: '' })

const totalMonthly = computed(() => bills.value.filter(b => b.is_active).reduce((s, b) => s + b.amount, 0))
const upcoming = computed(() => {
  const today = new Date()
  return bills.value.filter(b => {
    const d = new Date(today.getFullYear(), today.getMonth(), b.due_day_of_month)
    if (d < today) d.setMonth(d.getMonth() + 1)
    return (d - today) / 86400000 <= 7
  })
})

const monthLabel = computed(() => viewMonth.value.toLocaleString('en-US', { month: 'long', year: 'numeric' }))

const recurringEvents = computed(() => {
  const year = viewMonth.value.getFullYear()
  const month = viewMonth.value.getMonth()
  const lastDay = new Date(year, month + 1, 0).getDate()
  return bills.value
    .filter(b => b.is_active)
    .map((bill) => {
      const day = Math.min(Math.max(Number(bill.due_day_of_month) || 1, 1), lastDay)
      const date = new Date(year, month, day)
      return {
        id: `bill-${bill.id}-${toIsoDate(date)}`,
        type: 'bill',
        date: toIsoDate(date),
        name: bill.name,
        amount: Number(bill.amount) || 0,
        bill,
      }
    })
})

const plottedEventsForMonth = computed(() => {
  const year = viewMonth.value.getFullYear()
  const month = viewMonth.value.getMonth()
  return plottedEvents.value.filter((e) => {
    const d = new Date(`${e.date}T00:00:00`)
    return d.getFullYear() === year && d.getMonth() === month
  })
})

const eventsByDate = computed(() => {
  const map = {}
  for (const event of [...recurringEvents.value, ...plottedEventsForMonth.value]) {
    if (!map[event.date]) map[event.date] = []
    map[event.date].push(event)
  }
  for (const key of Object.keys(map)) {
    map[key].sort((a, b) => (a.type === b.type ? b.amount - a.amount : (a.type === 'bill' ? -1 : 1)))
  }
  return map
})

const calendarCells = computed(() => {
  const year = viewMonth.value.getFullYear()
  const month = viewMonth.value.getMonth()
  const firstOfMonth = new Date(year, month, 1)
  const startWeekday = firstOfMonth.getDay()
  const startDate = new Date(year, month, 1 - startWeekday)
  const todayIso = toIsoDate(new Date())

  return Array.from({ length: 42 }, (_, i) => {
    const d = new Date(startDate)
    d.setDate(startDate.getDate() + i)
    const iso = toIsoDate(d)
    return {
      iso,
      day: d.getDate(),
      inMonth: d.getMonth() === month,
      isToday: iso === todayIso,
      events: eventsByDate.value[iso] || [],
    }
  })
})

const selectedEvents = computed(() => eventsByDate.value[selectedDateIso.value] || [])
const selectedDateLabel = computed(() => new Date(`${selectedDateIso.value}T00:00:00`).toLocaleDateString('en-US', {
  weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
}))

const fmt = (v) => Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

function toIsoDate(d) {
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const cellStyle = (cell) => {
  const isSelected = cell.iso === selectedDateIso.value
  if (!cell.inMonth) {
    return `background: var(--surface-2); border-color: ${isSelected ? 'var(--mint)' : 'var(--surface-2)'}; opacity: 0.62`
  }
  return `background: var(--surface); border-color: ${isSelected ? 'var(--mint)' : 'var(--border)'}`
}

const cellDayStyle = (cell) => {
  if (!cell.inMonth) return 'color: var(--text-muted)'
  return cell.iso === selectedDateIso.value ? 'color: var(--mint)' : 'color: var(--text)'
}

const prevMonth = () => {
  viewMonth.value = new Date(viewMonth.value.getFullYear(), viewMonth.value.getMonth() - 1, 1)
}

const nextMonth = () => {
  viewMonth.value = new Date(viewMonth.value.getFullYear(), viewMonth.value.getMonth() + 1, 1)
}

const loadPlottedEvents = () => {
  try {
    const raw = window.localStorage.getItem(PLOT_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    plottedEvents.value = Array.isArray(parsed) ? parsed : []
  } catch {
    plottedEvents.value = []
  }
}

const persistPlottedEvents = () => {
  window.localStorage.setItem(PLOT_STORAGE_KEY, JSON.stringify(plottedEvents.value))
}

const openPlotDialog = (dateIso, bill = null) => {
  plotForm.value = {
    date: dateIso || toIsoDate(new Date()),
    bill_id: bill ? String(bill.id) : '',
    name: bill?.name || '',
    amount: bill ? String(bill.amount) : '',
  }
  showPlot.value = true
}

const applyBillToPlotForm = () => {
  const selected = bills.value.find(b => String(b.id) === String(plotForm.value.bill_id || ''))
  if (!selected) return
  plotForm.value.name = selected.name
  plotForm.value.amount = String(selected.amount)
}

const addPlotEvent = async () => {
  const name = plotForm.value.name.trim()
  const amount = Number(plotForm.value.amount)
  const date = plotForm.value.date
  if (!name || !date || !Number.isFinite(amount) || amount < 0) return

  savingPlot.value = true
  try {
    plottedEvents.value.unshift({
      id: `plot-${Date.now()}`,
      type: 'plot',
      date,
      name,
      amount,
    })
    persistPlottedEvents()
    showPlot.value = false
  } finally {
    savingPlot.value = false
  }
}

const removePlotEvent = (id) => {
  plottedEvents.value = plottedEvents.value.filter(e => e.id !== id)
  persistPlottedEvents()
}

const load = async () => {
  loading.value = true
  try {
    const res = await api.get('/api/bills')
    bills.value = res.data
  } finally {
    loading.value = false
  }
}

const addBill = async () => {
  if (!form.value.name || !form.value.amount || !form.value.due_day_of_month) return
  saving.value = true
  try {
    await api.post('/api/bills', {
      ...form.value,
      amount: Number(form.value.amount),
      due_day_of_month: Number(form.value.due_day_of_month),
    })
    showAdd.value = false
    form.value = { name: '', amount: '', due_day_of_month: '', category: '', notes: '' }
    await load()
  } finally {
    saving.value = false
  }
}

const markPaid = async (bill) => {
  await api.post(`/api/bills/${bill.id}/mark-paid`, {})
  await load()
}

const deleteBill = async (id) => {
  await api.delete(`/api/bills/${id}`)
  bills.value = bills.value.filter(b => b.id !== id)
}

watch(viewMonth, () => {
  const month = viewMonth.value.getMonth()
  const year = viewMonth.value.getFullYear()
  const selected = new Date(`${selectedDateIso.value}T00:00:00`)
  if (selected.getMonth() !== month || selected.getFullYear() !== year) {
    selectedDateIso.value = toIsoDate(new Date(year, month, 1))
  }
})

onMounted(async () => {
  loadPlottedEvents()
  await load()
})
</script>
