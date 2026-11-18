<template>
  <div
    class="credit-card relative overflow-hidden select-none"
    :class="{ 'credit-card--compact': compact }"
    :style="{ background: gradient }"
    role="img"
    :aria-label="`${institution || 'Credit'} card ending in ${mask || '••••'}`"
  >
    <!-- decorative sheen -->
    <div class="sheen"></div>
    <div class="ring ring-1"></div>
    <div class="ring ring-2"></div>

    <div class="relative h-full flex flex-col justify-between">
      <!-- Top row -->
      <div class="flex items-start justify-between">
        <div class="min-w-0">
          <p class="issuer truncate">{{ institution || 'Credit Card' }}</p>
          <p v-if="!compact" class="product truncate">{{ name }}</p>
        </div>
        <i class="pi pi-wifi contactless"></i>
      </div>

      <!-- Chip -->
      <div class="chip" aria-hidden="true">
        <span></span><span></span><span></span>
      </div>

      <!-- Number -->
      <p class="number">
        <span>••••</span><span>••••</span><span>••••</span><span>{{ mask || '••••' }}</span>
      </p>

      <!-- Bottom row -->
      <div class="flex items-end justify-between gap-3">
        <div class="min-w-0">
          <p class="label">Balance</p>
          <p class="value">{{ money(balance) }}</p>
        </div>
        <div v-if="limit" class="text-right">
          <p class="label">Limit</p>
          <p class="value">{{ money(limit) }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, default: '' },
  institution: { type: String, default: '' },
  mask: { type: String, default: '' },
  balance: { type: Number, default: null },
  limit: { type: Number, default: null },
  compact: { type: Boolean, default: false },
})

// Stable per-institution palette so each issuer's card looks consistent.
const PALETTES = [
  ['#0f2027', '#203a43', '#2c5364'],
  ['#1f1c2c', '#3a2f5c', '#928dab'],
  ['#0b3d2e', '#14684f', '#3DDBB8'],
  ['#2b1a12', '#6b3a1f', '#c98a4b'],
  ['#141e30', '#243b55', '#4a6fa5'],
  ['#2c0b1e', '#5e1739', '#b04a7a'],
  ['#1a1a1a', '#2e2e2e', '#5a5a5a'],
]

const gradient = computed(() => {
  const key = (props.institution || props.name || '').toLowerCase()
  let h = 0
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0
  const [a, b, c] = PALETTES[h % PALETTES.length]
  return `linear-gradient(135deg, ${a} 0%, ${b} 55%, ${c} 100%)`
})

const money = (v) =>
  v == null
    ? '—'
    : Number(v).toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })
</script>

<style scoped>
.credit-card {
  width: 100%;
  max-width: 380px;
  aspect-ratio: 1.586 / 1; /* ISO/IEC 7810 ID-1 */
  border-radius: 18px;
  padding: 22px 24px;
  color: #f5f7f6;
  box-shadow: 0 18px 40px -12px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.12);
}
.credit-card--compact {
  max-width: 260px;
  padding: 14px 16px;
  border-radius: 12px;
}
.sheen {
  position: absolute;
  inset: 0;
  background: linear-gradient(115deg, rgba(255,255,255,0.14) 0%, rgba(255,255,255,0) 40%);
  pointer-events: none;
}
.ring {
  position: absolute;
  border-radius: 9999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  pointer-events: none;
}
.ring-1 { width: 260px; height: 260px; right: -90px; top: -110px; }
.ring-2 { width: 200px; height: 200px; right: -40px; bottom: -130px; }

.issuer { font-size: 13px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; }
.product { font-size: 11px; opacity: 0.75; margin-top: 2px; }
.contactless { transform: rotate(90deg); opacity: 0.8; font-size: 18px; }

.chip {
  width: 42px;
  height: 32px;
  border-radius: 6px;
  background: linear-gradient(135deg, #e8d18b, #b8963e);
  display: grid;
  grid-template-rows: repeat(3, 1fr);
  gap: 2px;
  padding: 5px 4px;
  box-shadow: inset 0 0 0 1px rgba(0,0,0,0.15);
}
.chip span { border-top: 1px solid rgba(0, 0, 0, 0.25); }

.number {
  display: flex;
  gap: 14px;
  font-family: 'SFMono-Regular', ui-monospace, Menlo, Consolas, monospace;
  font-size: 17px;
  letter-spacing: 0.12em;
  text-shadow: 0 1px 1px rgba(0,0,0,0.4);
}
.label { font-size: 9px; text-transform: uppercase; letter-spacing: 0.12em; opacity: 0.65; }
.value { font-size: 15px; font-weight: 600; }

.credit-card--compact .chip { width: 30px; height: 22px; padding: 3px; }
.credit-card--compact .number { font-size: 12px; gap: 8px; }
.credit-card--compact .issuer { font-size: 11px; }
.credit-card--compact .value { font-size: 12px; }
.credit-card--compact .contactless { font-size: 14px; }
.credit-card--compact .ring { display: none; }
</style>
