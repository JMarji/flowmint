<template>
  <Dialog
    :visible="visible"
    @update:visible="emit('update:visible', $event)"
    header="Card details & rewards"
    modal
    :style="{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text)', width: '520px', maxWidth: '95vw' }"
  >
    <div class="space-y-5 py-1">
      <p class="text-xs" style="color: var(--text-muted)">
        Plaid doesn't share these details, so enter them from your card's terms.
      </p>

      <!-- Card -->
      <section class="grid grid-cols-2 gap-3">
        <div class="col-span-2">
          <label class="field-label">Card name</label>
          <InputText v-model="form.product_name" class="w-full" placeholder="e.g. Sapphire Preferred" />
        </div>
        <div>
          <label class="field-label">Network</label>
          <select v-model="form.network" class="field-select">
            <option :value="null">—</option>
            <option value="visa">Visa</option>
            <option value="mastercard">Mastercard</option>
            <option value="amex">American Express</option>
            <option value="discover">Discover</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div class="grid grid-cols-[1fr_auto] gap-2">
          <div>
            <label class="field-label">Annual fee</label>
            <InputText v-model="annualFee" type="number" min="0" step="1" class="w-full" placeholder="0" />
          </div>
          <div>
            <label class="field-label">Charged in</label>
            <select v-model="form.annual_fee_month" class="field-select">
              <option :value="null">—</option>
              <option v-for="(m, i) in MONTHS" :key="m" :value="i + 1">{{ m }}</option>
            </select>
          </div>
        </div>
      </section>

      <!-- Rewards -->
      <section class="space-y-3 pt-4 border-t" style="border-color: var(--border)">
        <div class="flex items-center justify-between">
          <p class="text-sm font-semibold" style="color: var(--text)">Rewards</p>
          <div class="flex rounded-lg overflow-hidden border text-xs" style="border-color: var(--border)">
            <button
              v-for="t in ['cashback', 'points']"
              :key="t"
              type="button"
              class="px-3 py-1"
              :style="form.reward_type === t ? 'background: var(--mint); color: #080C0B; font-weight: 600' : 'background: var(--surface-2); color: var(--text-muted)'"
              @click="form.reward_type = t"
            >{{ t === 'cashback' ? 'Cash back' : 'Points / miles' }}</button>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="field-label">Base rate ({{ rateUnit }})</label>
            <InputText v-model="baseRate" type="number" min="0" step="0.25" class="w-full" />
          </div>
          <div v-if="form.reward_type === 'points'">
            <label class="field-label">Point value (¢)</label>
            <InputText v-model="pointValue" type="number" min="0" step="0.05" class="w-full" />
          </div>
        </div>

        <div>
          <label class="field-label">Bonus categories</label>
          <div class="space-y-2">
            <div v-for="(row, i) in rateRows" :key="i" class="grid grid-cols-[1fr_90px_auto] gap-2 items-center">
              <select v-model="row.category" class="field-select">
                <option value="" disabled>Choose category</option>
                <option v-for="c in CATEGORY_OPTIONS" :key="c.value" :value="c.value" :disabled="isUsed(c.value, i)">{{ c.label }}</option>
              </select>
              <InputText v-model="row.rate" type="number" min="0" step="0.25" class="w-full" :placeholder="rateUnit" />
              <Button icon="pi pi-times" text rounded severity="secondary" size="small" @click="rateRows.splice(i, 1)" />
            </div>
          </div>
          <Button label="Add category" icon="pi pi-plus" text size="small" class="mt-1" @click="rateRows.push({ category: '', rate: '' })" />
          <p class="text-[11px] mt-1" style="color: var(--text-muted)">
            A specific category (e.g. Groceries) wins over its parent (Food &amp; Drink).
          </p>
        </div>
      </section>

      <!-- Bills -->
      <section class="space-y-3 pt-4 border-t" style="border-color: var(--border)">
        <label class="flex items-center gap-2 text-sm cursor-pointer" style="color: var(--text)">
          <input v-model="form.auto_bill" type="checkbox" class="accent-[var(--mint)]" />
          Add this card's payment to Bills automatically
        </label>
        <div v-if="form.auto_bill" class="flex items-center gap-2 text-xs pl-6" style="color: var(--text-muted)">
          <span>Bill amount:</span>
          <select v-model="form.bill_amount_mode" class="field-select !w-auto">
            <option value="statement">Statement balance</option>
            <option value="minimum">Minimum payment</option>
          </select>
        </div>
      </section>

      <p v-if="error" class="text-xs px-3 py-2 rounded-lg" style="color: #f87171; background: rgba(248,113,113,0.1)">{{ error }}</p>
    </div>

    <template #footer>
      <Button label="Cancel" text severity="secondary" @click="emit('update:visible', false)" />
      <Button label="Save" class="p-button-primary" :loading="saving" @click="save" />
    </template>
  </Dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import api from '@/utils/api'

const props = defineProps({
  visible: { type: Boolean, default: false },
  accountId: { type: [String, Number], required: true },
  settings: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:visible', 'saved'])

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// Plaid personal_finance_category values (primary, plus common detailed ones issuers use for bonuses).
const CATEGORY_OPTIONS = [
  { value: 'FOOD_AND_DRINK', label: 'Food & Drink (all)' },
  { value: 'FOOD_AND_DRINK_RESTAURANT', label: 'Dining / Restaurants' },
  { value: 'FOOD_AND_DRINK_GROCERIES', label: 'Groceries' },
  { value: 'FOOD_AND_DRINK_COFFEE', label: 'Coffee' },
  { value: 'TRAVEL', label: 'Travel (all)' },
  { value: 'TRAVEL_FLIGHTS', label: 'Flights' },
  { value: 'TRAVEL_LODGING', label: 'Hotels / Lodging' },
  { value: 'TRANSPORTATION', label: 'Transportation (all)' },
  { value: 'TRANSPORTATION_GAS', label: 'Gas' },
  { value: 'TRANSPORTATION_TAXIS_AND_RIDE_SHARES', label: 'Rideshare' },
  { value: 'ENTERTAINMENT', label: 'Entertainment' },
  { value: 'ENTERTAINMENT_TV_AND_MOVIES', label: 'Streaming / TV & Movies' },
  { value: 'GENERAL_MERCHANDISE', label: 'Shopping (all)' },
  { value: 'GENERAL_MERCHANDISE_ONLINE_MARKETPLACES', label: 'Online marketplaces' },
  { value: 'GENERAL_MERCHANDISE_SUPERSTORES', label: 'Superstores' },
  { value: 'RENT_AND_UTILITIES', label: 'Rent & Utilities' },
  { value: 'HOME_IMPROVEMENT', label: 'Home improvement' },
  { value: 'MEDICAL', label: 'Medical' },
  { value: 'MEDICAL_PHARMACIES_AND_SUPPLEMENTS', label: 'Pharmacies' },
  { value: 'PERSONAL_CARE', label: 'Personal care' },
  { value: 'GENERAL_SERVICES', label: 'Services' },
]

const form = reactive({})
const annualFee = ref('')
const baseRate = ref('')
const pointValue = ref('')
const rateRows = ref([])
const saving = ref(false)
const error = ref('')

const rateUnit = computed(() => (form.reward_type === 'points' ? 'pts per $' : '%'))
const isUsed = (val, idx) => rateRows.value.some((r, i) => i !== idx && r.category === val)

const reset = () => {
  const s = props.settings || {}
  Object.assign(form, {
    network: s.network ?? null,
    product_name: s.product_name ?? '',
    annual_fee_month: s.annual_fee_month ?? null,
    reward_type: s.reward_type || 'cashback',
    auto_bill: s.auto_bill ?? true,
    bill_amount_mode: s.bill_amount_mode || 'statement',
  })
  annualFee.value = s.annual_fee ?? ''
  baseRate.value = s.base_reward_rate ?? ''
  pointValue.value = s.point_value_cents ?? 1
  rateRows.value = Object.entries(s.category_rates || {}).map(([category, rate]) => ({ category, rate }))
  error.value = ''
}
watch(() => props.visible, (v) => { if (v) reset() }, { immediate: true })

const num = (v, fallback = null) => (v === '' || v == null || isNaN(Number(v)) ? fallback : Number(v))

const save = async () => {
  saving.value = true
  error.value = ''
  const category_rates = {}
  for (const r of rateRows.value) {
    const rate = num(r.rate)
    if (r.category && rate != null) category_rates[r.category] = rate
  }
  try {
    const res = await api.put(`/api/accounts/${props.accountId}/credit/settings`, {
      network: form.network,
      product_name: (form.product_name || '').trim() || null,
      annual_fee: num(annualFee.value),
      annual_fee_month: form.annual_fee_month,
      reward_type: form.reward_type,
      point_value_cents: num(pointValue.value, 1),
      base_reward_rate: num(baseRate.value, 0),
      category_rates,
      auto_bill: form.auto_bill,
      bill_amount_mode: form.bill_amount_mode,
    })
    emit('saved', res.data)
    emit('update:visible', false)
  } catch (e) {
    error.value = e?.response?.data?.detail?.[0]?.msg || 'Failed to save card details'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.field-label {
  display: block;
  font-size: 11px;
  margin-bottom: 4px;
  color: var(--text-muted);
}
.field-select {
  width: 100%;
  padding: 0.5rem 0.6rem;
  border-radius: 8px;
  font-size: 13px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  color: var(--text);
}
</style>
