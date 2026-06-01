<template>
  <section class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
    <header class="flex items-center justify-between gap-3 mb-3">
      <div>
        <h2 class="text-base font-semibold" style="color: var(--text)">Vendor Summary</h2>
        <p class="text-xs" style="color: var(--text-muted)">
          {{ vendorRows.length }} vendors from {{ scopeLabel }} ({{ vendorCount }} total)
        </p>
      </div>
      <div class="text-right">
        <p class="text-xs" style="color: var(--text-muted)">Total spend</p>
        <p class="text-sm font-semibold" style="color: var(--text)">${{ formatCurrency(totalOutflow) }}</p>
      </div>
    </header>

    <div class="mb-3 flex items-center justify-between gap-2">
      <p class="text-xs" style="color: var(--text-muted)">
        Click a vendor to filter transactions.
      </p>
      <button
        type="button"
        class="text-xs px-2 py-1 rounded border transition"
        style="border-color: var(--border); color: var(--text)"
        :style="!selectedVendor ? 'background: color-mix(in oklab, var(--mint) 16%, transparent)' : ''"
        @click="selectVendor('')"
      >
        All vendors
      </button>
    </div>

    <div v-if="loading" class="space-y-2">
      <div
        v-for="i in 4"
        :key="i"
        class="rounded-lg border px-3 py-2 animate-pulse"
        style="border-color: var(--border); background: var(--surface-2)"
      >
        <div class="h-3 rounded w-1/3" style="background: var(--surface)"></div>
        <div class="h-2 rounded w-1/4 mt-2" style="background: var(--surface)"></div>
      </div>
    </div>

    <div v-else-if="vendorRows.length === 0" class="rounded-lg border border-dashed p-4 text-xs" style="border-color: var(--border); color: var(--text-muted)">
      No vendor data available for the selected filters.
    </div>

    <div v-else class="space-y-2 max-h-[70vh] overflow-y-auto pr-1">
      <button
        v-for="vendor in vendorRows"
        :key="vendor.name"
        type="button"
        class="w-full rounded-lg border px-3 py-2 text-left transition"
        style="border-color: var(--border); background: var(--surface-2)"
        :style="selectedVendor === vendor.name ? 'border-color: var(--mint); box-shadow: inset 0 0 0 1px color-mix(in oklab, var(--mint) 55%, transparent)' : ''"
        @click="selectVendor(vendor.name)"
      >
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-lg overflow-hidden flex items-center justify-center flex-shrink-0" style="background: var(--surface)">
            <img v-if="vendor.logo" :src="vendor.logo" :alt="vendor.name" class="w-full h-full object-cover" />
            <i v-else class="pi pi-shop text-xs" style="color: var(--mint)"></i>
          </div>

          <div class="min-w-0 flex-1">
            <p class="text-sm font-medium truncate" style="color: var(--text)">{{ vendor.name }}</p>
            <p class="text-xs" style="color: var(--text-muted)">
              {{ vendor.count }} transaction{{ vendor.count === 1 ? '' : 's' }}
            </p>
          </div>

          <div class="text-right">
            <p class="text-sm font-semibold" style="color: var(--text)">${{ formatCurrency(vendor.outflow) }}</p>
            <p class="text-xs" style="color: var(--text-muted)">
              {{ totalOutflow > 0 ? ((vendor.outflow / totalOutflow) * 100).toFixed(1) : '0.0' }}% of spend
            </p>
          </div>
        </div>

        <div class="w-full h-1.5 rounded-full mt-2 overflow-hidden" style="background: var(--surface)">
          <div
            class="h-full rounded-full"
            style="background: var(--mint)"
            :style="{ width: `${totalOutflow > 0 ? Math.max((vendor.outflow / totalOutflow) * 100, 2) : 0}%` }"
          ></div>
        </div>
      </button>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  vendors: {
    type: Array,
    default: () => [],
  },
  vendorCount: {
    type: Number,
    default: 0,
  },
  totalOutflow: {
    type: Number,
    default: 0,
  },
  scopeLabel: {
    type: String,
    default: 'all filtered transactions',
  },
  loading: {
    type: Boolean,
    default: false,
  },
  selectedVendor: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['select-vendor'])

const normalizedVendors = computed(() =>
  props.vendors.map((vendor) => ({
    name: vendor.name || 'Unknown Vendor',
    count: Number(vendor.count) || 0,
    outflow: Number(vendor.outflow) || 0,
    logo: vendor.logo || vendor.logo_url || null,
  }))
)

const vendorRows = computed(() => normalizedVendors.value)
const vendorCount = computed(() => props.vendorCount || normalizedVendors.value.length)
const totalOutflow = computed(() => Number(props.totalOutflow) || 0)

const selectVendor = (vendorName) => {
  emit('select-vendor', vendorName)
}

const formatCurrency = (value) =>
  Number(value || 0).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
</script>
