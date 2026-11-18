<template>
  <div class="rounded-xl border p-5" style="background: var(--surface); border-color: var(--border)">
    <div class="flex items-center justify-between mb-1">
      <p class="text-sm font-semibold" style="color: var(--text)">Payoff planner</p>
      <p class="text-[11px]" style="color: var(--text-muted)">
        {{ money(balance) }} at
        <input
          v-model.number="aprInput"
          type="number"
          step="0.01"
          min="0"
          class="apr-input"
          aria-label="APR"
        />% APR<span v-if="apr == null" title="No APR from Plaid; edit to match your card"> (assumed)</span>
      </p>
    </div>
    <p class="text-[11px] mb-4" style="color: var(--text-muted)">Assumes no new charges. Estimates only.</p>

    <div v-if="!(balance > 0)" class="text-xs" style="color: var(--text-muted)">No balance to pay off. 🎉</div>

    <template v-else>
      <!-- Scenario table -->
      <div class="space-y-2 mb-5">
        <div
          v-for="s in scenarios"
          :key="s.key"
          class="grid grid-cols-[1fr_auto_auto] items-center gap-4 rounded-lg px-3 py-2.5"
          style="background: var(--surface-2)"
        >
          <div class="min-w-0">
            <p class="text-xs font-medium" style="color: var(--text)">{{ s.label }}</p>
            <p class="text-[11px]" style="color: var(--text-muted)">{{ s.detail }}</p>
          </div>
          <div class="text-right">
            <p class="text-[10px] uppercase tracking-wide" style="color: var(--text-muted)">Time</p>
            <p class="text-xs font-semibold" style="color: var(--text)">{{ s.result.never ? 'Never' : duration(s.result.months) }}</p>
          </div>
          <div class="text-right w-24">
            <p class="text-[10px] uppercase tracking-wide" style="color: var(--text-muted)">Interest</p>
            <p class="text-xs font-semibold" :style="{ color: s.result.never || s.result.interest > 0 ? '#f87171' : 'var(--mint)' }">
              {{ s.result.never ? '∞' : money(s.result.interest) }}
            </p>
          </div>
        </div>
      </div>

      <!-- Fixed payment slider -->
      <div class="mb-5">
        <div class="flex items-center justify-between mb-1.5">
          <label class="text-xs" style="color: var(--text-muted)" for="pp-fixed">Fixed monthly payment</label>
          <span class="text-sm font-semibold" style="color: var(--mint)">{{ money(fixedPayment) }}</span>
        </div>
        <input id="pp-fixed" v-model.number="fixedPayment" type="range" :min="sliderMin" :max="sliderMax" :step="sliderStep" class="w-full accent-[var(--mint)]" />
        <p v-if="fixedResult.never" class="text-[11px] mt-1" style="color: #fb923c">
          This doesn't cover the {{ money(firstMonthInterest) }} monthly interest — the balance would never shrink.
        </p>
      </div>

      <!-- Target date -->
      <div class="flex items-center gap-2 text-xs flex-wrap" style="color: var(--text-muted)">
        <span>To be debt-free in</span>
        <select v-model.number="targetMonths" class="px-2 py-1 rounded-md text-xs" style="background: var(--surface-2); border: 1px solid var(--border); color: var(--text)">
          <option v-for="m in [3, 6, 12, 18, 24, 36]" :key="m" :value="m">{{ m }} months</option>
        </select>
        <span>pay</span>
        <span class="font-semibold" style="color: var(--text)">{{ money(targetPayment) }}/mo</span>
        <span>({{ money(targetPayment * targetMonths - balance) }} interest)</span>
      </div>

      <!-- Balance curves -->
      <div class="h-44 mt-5">
        <Line :data="chartData" :options="chartOptions" />
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Line } from 'vue-chartjs'
import { Chart as ChartJS, LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Legend, Filler } from 'chart.js'

ChartJS.register(LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Legend, Filler)

const props = defineProps({
  balance: { type: Number, default: 0 },
  apr: { type: Number, default: null },
  minimumPayment: { type: Number, default: null },
  statementBalance: { type: Number, default: null },
})

const MAX_MONTHS = 600
// Without a Plaid APR, fall back to roughly the US average card APR so the planner still works.
const aprInput = ref(props.apr ?? 22)
watch(() => props.apr, (v) => { if (v != null) aprInput.value = v })

const monthlyRate = computed(() => Math.max(0, Number(aprInput.value) || 0) / 100 / 12)
const firstMonthInterest = computed(() => props.balance * monthlyRate.value)

/** Simulate month-by-month. paymentFn(balance, interest) → payment for that month. */
function simulate(paymentFn) {
  let bal = props.balance
  let interest = 0
  const path = [bal]
  for (let m = 1; m <= MAX_MONTHS; m++) {
    const i = bal * monthlyRate.value
    const pay = Math.min(paymentFn(bal, i), bal + i)
    if (pay <= i + 0.005) return { never: true, months: Infinity, interest: Infinity, path }
    bal = bal + i - pay
    interest += i
    path.push(Math.max(bal, 0))
    if (bal <= 0.005) return { never: false, months: m, interest, path }
  }
  return { never: true, months: Infinity, interest: Infinity, path }
}

// Common issuer formula: 1% of balance + that month's interest, with a $25 floor.
const minimumFn = (bal, i) => Math.max(25, bal * 0.01 + i)

const defaultFixed = () => {
  const base = Math.max((props.minimumPayment || 25) * 3, props.balance / 12)
  return Math.ceil(base / 10) * 10
}
const fixedPayment = ref(defaultFixed())
watch(() => [props.balance, props.minimumPayment], () => { fixedPayment.value = defaultFixed() })

const sliderMin = computed(() => Math.max(10, Math.floor((props.minimumPayment || 25) / 5) * 5))
const sliderMax = computed(() => Math.max(sliderMin.value + 50, Math.ceil(props.balance / 50) * 50))
const sliderStep = computed(() => (sliderMax.value > 2000 ? 25 : 5))

const minimumResult = computed(() => simulate(minimumFn))
const fixedResult = computed(() => simulate(() => fixedPayment.value))

const scenarios = computed(() => {
  const list = [
    { key: 'min', label: 'Minimum payments only', detail: 'Starts ~' + money(minimumFn(props.balance, firstMonthInterest.value)) + '/mo, shrinking with the balance', result: minimumResult.value },
    { key: 'fixed', label: `${money(fixedPayment.value)} every month`, detail: 'Adjust with the slider below', result: fixedResult.value },
  ]
  if (props.statementBalance != null) {
    list.push({
      key: 'full',
      label: 'Pay statement in full',
      detail: `${money(props.statementBalance)} by the due date avoids purchase interest`,
      result: { never: false, months: props.balance > props.statementBalance ? 2 : 1, interest: 0 },
    })
  }
  return list
})

const targetMonths = ref(12)
const targetPayment = computed(() => {
  const r = monthlyRate.value
  const n = targetMonths.value
  if (r === 0) return props.balance / n
  return (props.balance * r) / (1 - Math.pow(1 + r, -n))
})

const chartData = computed(() => {
  const a = minimumResult.value.path
  const b = fixedResult.value.path
  const len = Math.min(Math.max(a.length, b.length), 121) // cap the x-axis at 10 years
  const labels = Array.from({ length: len }, (_, i) => (i % 12 === 0 ? `Y${i / 12}` : ''))
  const pad = (p) => Array.from({ length: len }, (_, i) => (i < p.length ? p[i] : 0))
  return {
    labels,
    datasets: [
      { label: 'Minimum', data: pad(a), borderColor: '#f87171', backgroundColor: 'transparent', pointRadius: 0, borderWidth: 2, tension: 0.2 },
      { label: 'Fixed', data: pad(b), borderColor: '#3DDBB8', backgroundColor: 'rgba(61,219,184,0.08)', fill: true, pointRadius: 0, borderWidth: 2, tension: 0.2 },
    ],
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { labels: { color: '#7A9E94', boxWidth: 10, font: { size: 11 } } },
    tooltip: {
      callbacks: {
        title: (items) => `Month ${items[0].dataIndex}`,
        label: (ctx) => `${ctx.dataset.label}: ${money(ctx.parsed.y)}`,
      },
    },
  },
  scales: {
    x: { ticks: { color: '#7A9E94', autoSkip: false, maxRotation: 0 }, grid: { display: false } },
    y: { ticks: { color: '#7A9E94', callback: (v) => '$' + Number(v).toLocaleString() }, grid: { color: 'rgba(37,61,53,0.6)' } },
  },
}

function money(v) {
  return v == null || !isFinite(v)
    ? '—'
    : Number(v).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
}
function duration(months) {
  if (months < 12) return `${months} mo`
  const y = Math.floor(months / 12)
  const m = months % 12
  return m ? `${y}y ${m}m` : `${y}y`
}
</script>

<style scoped>
.apr-input {
  width: 56px;
  padding: 1px 4px;
  border-radius: 4px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  color: var(--text);
  font-size: 11px;
  text-align: right;
}
</style>
