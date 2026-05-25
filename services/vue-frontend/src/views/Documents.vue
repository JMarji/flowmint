<template>
  <div class="p-6 max-w-4xl mx-auto">
    <div class="flex items-center justify-between mb-8">
      <div>
        <h1 class="text-2xl font-bold" style="color: var(--text)">Documents</h1>
        <p class="text-sm mt-1" style="color: var(--text-muted)">Insurance docs, leases, and property files</p>
      </div>
      <label class="cursor-pointer">
        <input type="file" class="hidden" @change="uploadFile" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.txt" />
        <span class="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold cursor-pointer" style="background: var(--mint); color: #080C0B">
          <i class="pi pi-upload"></i> Upload
        </span>
      </label>
    </div>

    <!-- Upload progress -->
    <div v-if="uploadProgress > 0 && uploadProgress < 100" class="mb-4">
      <div class="flex justify-between text-xs mb-1" style="color: var(--text-muted)">
        <span>Uploading {{ uploadingName }}…</span>
        <span>{{ uploadProgress }}%</span>
      </div>
      <div class="h-1.5 rounded-full overflow-hidden" style="background: var(--surface-2)">
        <div class="h-full rounded-full transition-all" :style="`width: ${uploadProgress}%; background: var(--mint)`"></div>
      </div>
    </div>

    <!-- Filters -->
    <div class="flex gap-3 mb-6 flex-wrap">
      <button @click="propFilter = null; load()" class="px-3 py-1.5 rounded-lg text-xs font-medium transition" :style="propFilter === null ? 'background: var(--mint); color: #080C0B' : 'background: var(--surface-2); color: var(--text-muted)'">All</button>
      <button @click="propFilter = 'general'; load()" class="px-3 py-1.5 rounded-lg text-xs font-medium transition" :style="propFilter === 'general' ? 'background: var(--mint); color: #080C0B' : 'background: var(--surface-2); color: var(--text-muted)'">General</button>
      <button v-for="p in properties" :key="p.id" @click="propFilter = p.id; load()" class="px-3 py-1.5 rounded-lg text-xs font-medium transition" :style="propFilter === p.id ? 'background: var(--mint); color: #080C0B' : 'background: var(--surface-2); color: var(--text-muted)'">
        {{ p.address.split(' ').slice(0,2).join(' ') }}
      </button>
    </div>

    <!-- Empty -->
    <div v-if="!loading && docs.length === 0" class="rounded-xl border p-12 flex flex-col items-center gap-3 text-center" style="background: var(--surface); border-color: var(--border); border-style: dashed">
      <i class="pi pi-cloud-upload text-3xl" style="color: var(--mint)"></i>
      <p class="text-sm font-medium" style="color: var(--text)">No documents uploaded</p>
      <p class="text-xs" style="color: var(--text-muted)">Upload insurance policies, leases, deeds, or any property file</p>
    </div>

    <!-- Doc grid -->
    <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <div v-for="doc in docs" :key="doc.id" class="flex items-center gap-3 p-4 rounded-xl border group" style="background: var(--surface); border-color: var(--border)">
        <div class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0" style="background: var(--surface-2)">
          <i :class="`pi ${docIcon(doc.content_type)} text-lg`" style="color: var(--mint)"></i>
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium truncate" style="color: var(--text)">{{ doc.name }}</p>
          <p class="text-xs" style="color: var(--text-muted)">
            {{ fmtBytes(doc.size_bytes) }} · {{ doc.uploaded_at.slice(0,10) }}
            <span v-if="doc.property_address" class="ml-1">· {{ doc.property_address.split(' ').slice(0,3).join(' ') }}</span>
          </p>
        </div>
        <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition">
          <button @click="downloadDoc(doc)" title="Download" style="color: var(--mint)" class="p-1.5 rounded hover:opacity-80"><i class="pi pi-download text-sm"></i></button>
          <button @click="deleteDoc(doc.id)" style="color: var(--text-muted)" class="p-1.5 rounded hover:opacity-80"><i class="pi pi-trash text-sm"></i></button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/utils/api'

const docs = ref([])
const properties = ref([])
const loading = ref(true)
const propFilter = ref(null)
const uploadProgress = ref(0)
const uploadingName = ref('')

const fmtBytes = (b) => b > 1048576 ? `${(b/1048576).toFixed(1)} MB` : `${(b/1024).toFixed(0)} KB`
const docIcon = (ct) => {
  if (!ct) return 'pi-file'
  if (ct.includes('pdf')) return 'pi-file-pdf'
  if (ct.includes('image')) return 'pi-image'
  if (ct.includes('word') || ct.includes('document')) return 'pi-file-word'
  return 'pi-file'
}

const load = async () => {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (propFilter.value && propFilter.value !== 'general') params.set('property_id', propFilter.value)
    const res = await api.get(`/api/documents${params.toString() ? '?' + params : ''}`)
    let all = res.data
    if (propFilter.value === 'general') all = all.filter(d => !d.property_id)
    docs.value = all
  } finally { loading.value = false }
}

const uploadFile = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  uploadingName.value = file.name
  uploadProgress.value = 10

  const propId = propFilter.value && propFilter.value !== 'general' ? Number(propFilter.value) : null
  const { data } = await api.post('/api/documents/upload-url', {
    name: file.name, content_type: file.type || 'application/octet-stream',
    size_bytes: file.size, property_id: propId
  })
  uploadProgress.value = 35

  await fetch(data.upload_url, { method: 'PUT', body: file, headers: { 'Content-Type': file.type || 'application/octet-stream' } })
  uploadProgress.value = 75

  await api.post('/api/documents', {
    name: file.name, s3_key: data.s3_key,
    content_type: file.type || 'application/octet-stream',
    size_bytes: file.size, property_id: propId
  })
  uploadProgress.value = 100
  setTimeout(() => { uploadProgress.value = 0; uploadingName.value = '' }, 1200)
  await load()
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
  const [, propRes] = await Promise.allSettled([load(), api.get('/api/properties')])
  if (propRes.status === 'fulfilled') properties.value = propRes.value.data
})
</script>
