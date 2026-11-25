<template>
  <div class="page">
    <header>
      <div><h1>BOM Stock Check</h1><p>Compare PCB components against live distributor inventory.</p></div>
      <div v-if="results.length" class="summary"><span><strong>{{ inStockCount }}</strong> in stock</span><span class="missing"><strong>{{ results.length-inStockCount }}</strong> unavailable</span></div>
    </header>
    <section class="card">
      <div class="row"><div><h2>Import your BOM</h2><p>CSV headers: part number, quantity, reference, description</p></div><button class="link" @click="loadSample">Load sample</button></div>
      <label class="drop" :class="{dragging}" @dragover.prevent="dragging=true" @dragleave="dragging=false" @drop.prevent="onDrop">
        <input type="file" accept=".csv,text/csv" @change="onFile"><i class="pi pi-file-arrow-up"></i><span><strong>Choose a CSV</strong> or drop it here</span><small>Up to 50 line items</small>
      </label>
      <div class="divider"><span>or paste CSV</span></div>
      <textarea v-model="csvText" rows="6" spellcheck="false" placeholder="part_number,quantity,reference,description&#10;STM32F103C8T6,5,U1,Microcontroller"></textarea>
      <div class="controls">
        <fieldset><legend>Distributors</legend><label><input v-model="providers" type="checkbox" value="mouser"> Mouser</label><label><input v-model="providers" type="checkbox" value="digikey"> DigiKey</label></fieldset>
        <button class="search" :disabled="loading||!csvText.trim()||!providers.length" @click="search"><i :class="`pi ${loading?'pi-spin pi-spinner':'pi-search'}`"></i>{{ loading?'Checking stock…':'Check stock' }}</button>
      </div>
      <p v-if="error" class="notice error"><i class="pi pi-exclamation-circle"></i>{{ error }}</p>
    </section>
    <section v-if="results.length" class="results">
      <div class="row heading"><div><h2>Availability</h2><p>{{ results.length }} BOM line items</p></div><span>Checked {{ checkedAt }}</span></div>
      <p v-if="warnings.length" class="notice warning"><i class="pi pi-info-circle"></i>{{ warnings.join(' · ') }}</p>
      <BomResultsList :items="results" />
    </section>
  </div>
</template>

<script setup>
import {computed,ref} from 'vue'
import api from '@/utils/api'
import BomResultsList from '@/components/bom/BomResultsList.vue'
const csvText=ref(''),providers=ref(['mouser','digikey']),results=ref([]),warnings=ref([]),checkedAt=ref(''),loading=ref(false),error=ref(''),dragging=ref(false)
const inStockCount=computed(()=>results.value.filter(x=>x.in_stock).length)
const parseRow=line=>{const out=[];let value='',quoted=false;for(let i=0;i<line.length;i++){const c=line[i];if(c==='"'&&quoted&&line[i+1]==='"'){value+='"';i++}else if(c==='"')quoted=!quoted;else if(c===','&&!quoted){out.push(value.trim());value=''}else value+=c}out.push(value.trim());return out}
const normalize=value=>value.toLowerCase().replace(/[^a-z0-9]/g,'')
const parseBom=text=>{const rows=text.replace(/^\uFEFF/,'').split(/\r?\n/).filter(x=>x.trim()).map(parseRow);if(rows.length<2)throw new Error('Include a header row and at least one BOM item.');const headers=rows[0].map(normalize),find=a=>headers.findIndex(h=>a.includes(h)),pi=find(['partnumber','manufacturerpartnumber','mpn','part','component']),qi=find(['quantity','qty','count']),ri=find(['reference','references','designator','designators','refdes']),di=find(['description','value','comment']);if(pi<0)throw new Error('A part number, MPN, or component column is required.');const items=rows.slice(1).map((r,i)=>({part_number:r[pi]?.trim(),quantity:Number.parseInt(r[qi],10)||1,reference:ri>=0?r[ri]||'':'',description:di>=0?r[di]||'':'',row:i+2})).filter(x=>x.part_number);if(!items.length)throw new Error('No part numbers were found in the CSV.');if(items.length>50)throw new Error('BOMs are limited to 50 line items per search.');const bad=items.find(x=>x.quantity<1||x.quantity>1000000);if(bad)throw new Error(`Quantity on row ${bad.row} must be between 1 and 1,000,000.`);return items.map(({row,...item})=>item)}
const readFile=file=>{if(!file)return;if(file.size>1048576){error.value='CSV files must be smaller than 1 MB.';return}const reader=new FileReader();reader.onload=()=>{csvText.value=String(reader.result||'');error.value=''};reader.onerror=()=>error.value='The CSV could not be read.';reader.readAsText(file)}
const onFile=e=>readFile(e.target.files?.[0]);const onDrop=e=>{dragging.value=false;readFile(e.dataTransfer.files?.[0])}
const loadSample=()=>csvText.value='part_number,quantity,reference,description\nSTM32F103C8T6,5,U1,32-bit microcontroller\nGRM188R71C104KA01D,20,"C1,C2,C3",100nF ceramic capacitor\nSN74LVC1G14DBVR,8,U2-U9,Schmitt-trigger inverter'
const search=async()=>{error.value='';let items;try{items=parseBom(csvText.value)}catch(e){error.value=e.message;return}loading.value=true;try{const {data}=await api.post('/api/bom/search',{items,providers:providers.value});results.value=data.items;warnings.value=Object.entries(data.provider_errors||{}).map(([name,message])=>`${name==='mouser'?'Mouser':'DigiKey'}: ${message}`);checkedAt.value=new Date().toLocaleTimeString([],{hour:'numeric',minute:'2-digit'})}catch(e){error.value=e.response?.data?.detail||'Stock lookup failed. Please try again.'}finally{loading.value=false}}
</script>

<style scoped>
.page{max-width:64rem;margin:0 auto;padding:2rem 1.5rem 4rem}header,.row,.controls{display:flex;justify-content:space-between;align-items:center;gap:1rem}h1{margin:0;color:var(--text);font-size:1.6rem}h2{margin:0;color:var(--text);font-size:1rem}p{margin:.3rem 0 0;color:var(--text-muted);font-size:.8rem}.summary{display:flex;gap:.5rem}.summary span{padding:.45rem .7rem;border-radius:.5rem;color:var(--mint);background:var(--mint-dim);font-size:.75rem}.summary .missing{color:#f87171;background:rgba(248,113,113,.12)}.card{margin-top:1.5rem;padding:1.25rem;border:1px solid var(--border);border-radius:1rem;background:var(--surface)}.link{color:var(--mint);background:transparent;border:0;cursor:pointer}.drop{display:flex;flex-direction:column;align-items:center;gap:.35rem;margin-top:1rem;padding:1.35rem;border:1px dashed var(--border);border-radius:.75rem;color:var(--text-muted);cursor:pointer}.drop:hover,.drop.dragging{border-color:var(--mint);background:var(--mint-dim)}.drop input{display:none}.drop i,.drop strong{color:var(--mint)}.drop small{font-size:.68rem}.divider{display:flex;align-items:center;gap:.75rem;margin:.9rem 0;color:var(--text-muted);font-size:.68rem}.divider:before,.divider:after{content:'';height:1px;flex:1;background:var(--border)}textarea{width:100%;resize:vertical;padding:.75rem;border:1px solid var(--border);border-radius:.6rem;outline:none;background:var(--surface-2);color:var(--text);font:.75rem/1.5 ui-monospace,monospace}textarea:focus{border-color:var(--mint);box-shadow:0 0 0 2px var(--mint-dim)}.controls{margin-top:1rem}fieldset{display:flex;gap:1rem;border:0;padding:0;margin:0}legend{margin-bottom:.35rem;color:var(--text-muted);font-size:.68rem}fieldset label{color:var(--text);font-size:.78rem}input[type=checkbox]{accent-color:var(--mint)}.search{display:inline-flex;align-items:center;gap:.5rem;padding:.7rem 1rem;border:0;border-radius:.6rem;background:var(--mint);color:#080c0b;font-weight:700;cursor:pointer}.search:disabled{opacity:.45;cursor:not-allowed}.notice{display:flex;align-items:center;gap:.5rem;margin:.8rem 0 0;padding:.65rem .75rem;border-radius:.5rem}.error{color:#fca5a5;background:rgba(127,29,29,.22)}.warning{margin:0 0 .75rem;color:#fcd34d;background:rgba(120,53,15,.22)}.results{margin-top:1.75rem}.heading{margin-bottom:.8rem}.heading>span{color:var(--text-muted);font-size:.7rem}@media(max-width:640px){header,.controls{align-items:stretch;flex-direction:column}.summary{align-self:flex-start}.search{justify-content:center}}
</style>
