<template>
  <div class="results-list" aria-live="polite">
    <article v-for="(item, index) in items" :key="`${item.part_number}-${index}`" class="result-row" :class="{ 'no-stock': !item.in_stock }">
      <div class="status-icon" :class="item.in_stock ? 'available' : 'unavailable'">
        <i :class="`pi ${item.in_stock ? 'pi-check' : 'pi-times'}`"></i>
      </div>
      <div class="part-info">
        <div class="part-heading"><strong>{{ item.part_number }}</strong><span v-if="item.reference" class="reference">{{ item.reference }}</span></div>
        <p v-if="item.description">{{ item.description }}</p>
        <div v-if="item.offers.length" class="offers">
          <a v-for="offer in item.offers" :key="`${offer.distributor}-${offer.part_number}`" :href="safeUrl(offer.url)" target="_blank" rel="noopener noreferrer" class="offer" :class="{ disabled: !offer.url }" @click="!offer.url && $event.preventDefault()">
            <span>{{ offer.distributor }}</span><strong>{{ fmt(offer.stock) }}</strong><i v-if="offer.url" class="pi pi-external-link"></i>
          </a>
        </div>
        <span v-else class="no-match">No distributor match found</span>
      </div>
      <div class="quantity-block"><span>Available</span><strong :class="{ shortage: item.stock < item.quantity }">{{ fmt(item.stock) }}</strong><small>of {{ fmt(item.quantity) }} needed</small></div>
    </article>
  </div>
</template>

<script setup>
defineProps({ items: { type: Array, required: true } })
const fmt = value => Number(value || 0).toLocaleString()
const safeUrl = value => /^https?:\/\//i.test(value || '') ? value : '#'
</script>

<style scoped>
.results-list{display:flex;flex-direction:column;gap:.75rem}.result-row{display:grid;grid-template-columns:2.5rem minmax(0,1fr) auto;gap:1rem;align-items:center;padding:1rem 1.125rem;border:1px solid var(--border);border-radius:.875rem;background:var(--surface)}.result-row.no-stock{border-color:rgba(248,113,113,.65);background:rgba(127,29,29,.16)}.status-icon{width:2.5rem;height:2.5rem;border-radius:.7rem;display:grid;place-items:center}.available{color:var(--mint);background:var(--mint-dim)}.unavailable{color:#f87171;background:rgba(248,113,113,.13)}.part-info{min-width:0}.part-heading{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;color:var(--text)}.part-heading strong{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;overflow-wrap:anywhere}.reference{padding:.15rem .45rem;border-radius:.35rem;background:var(--surface-2);color:var(--text-muted);font-size:.7rem}.part-info p{margin:.25rem 0 0;color:var(--text-muted);font-size:.78rem}.offers{display:flex;gap:.45rem;margin-top:.6rem;flex-wrap:wrap}.offer{display:inline-flex;gap:.4rem;align-items:center;padding:.28rem .5rem;border:1px solid var(--border);border-radius:.4rem;color:var(--text-muted);font-size:.72rem;text-decoration:none}.offer strong{color:var(--text)}.offer i{font-size:.62rem}.offer:not(.disabled):hover{border-color:var(--mint);color:var(--mint)}.no-match{display:inline-block;margin-top:.55rem;color:#fca5a5;font-size:.75rem}.quantity-block{min-width:7.5rem;text-align:right;display:flex;flex-direction:column}.quantity-block span,.quantity-block small{color:var(--text-muted);font-size:.7rem}.quantity-block strong{color:var(--mint);font-size:1.25rem;line-height:1.2}.quantity-block strong.shortage{color:#f87171}@media(max-width:640px){.result-row{grid-template-columns:2.5rem minmax(0,1fr)}.quantity-block{grid-column:2;text-align:left;flex-direction:row;gap:.35rem;align-items:baseline}}
</style>
