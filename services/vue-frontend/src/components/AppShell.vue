<template>
  <div class="flex h-screen overflow-hidden" style="background: var(--bg)">
    <div
      v-if="isMobile && isMobileSidebarOpen"
      class="fixed inset-0 z-30 lg:hidden"
      style="background: rgba(0,0,0,0.45)"
      @click="closeMobileSidebar"
    ></div>

    <!-- Sidebar -->
    <aside
      :class="[
        'fixed lg:relative inset-y-0 left-0 z-40 lg:z-auto flex flex-col border-r transition-all duration-200 ease-out',
        isMobile
          ? (isMobileSidebarOpen ? 'translate-x-0 w-72' : '-translate-x-full w-72')
          : (isSidebarCollapsed ? 'translate-x-0 w-20' : 'translate-x-0 w-60')
      ]"
      style="background: var(--surface); border-color: var(--border)"
    >
      <!-- Logo -->
      <div
        :class="[
          'flex items-center border-b',
          isSidebarCollapsed && !isMobile ? 'justify-center px-3 py-5' : 'justify-between px-4 py-4'
        ]"
        style="border-color: var(--border)"
      >
        <div :class="['flex items-center', isSidebarCollapsed && !isMobile ? '' : 'gap-2']">
          <div class="w-7 h-7 rounded-lg flex items-center justify-center" style="background: var(--mint)">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M8 2L13 5V11L8 14L3 11V5L8 2Z" fill="#080C0B" stroke="#080C0B" stroke-width="0.5"/>
              <path d="M8 5L11 6.8V10.2L8 12L5 10.2V6.8L8 5Z" fill="var(--mint)" stroke="none"/>
            </svg>
          </div>
          <span v-if="!isSidebarCollapsed || isMobile" class="text-lg font-bold tracking-tight" style="color: var(--mint)">flowmint</span>
        </div>

        <button
          v-if="isMobile"
          @click="closeMobileSidebar"
          class="p-2 rounded hover:opacity-80"
          style="color: var(--text-muted); background: var(--surface-2)"
          aria-label="Close navigation"
        >
          <i class="pi pi-times text-sm"></i>
        </button>

        <button
          v-else
          @click="isSidebarCollapsed = !isSidebarCollapsed"
          class="p-2 rounded hover:opacity-80"
          style="color: var(--text-muted); background: var(--surface-2)"
          :title="isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
          aria-label="Toggle sidebar"
        >
          <i :class="`pi ${isSidebarCollapsed ? 'pi-angle-right' : 'pi-angle-left'} text-sm`"></i>
        </button>
      </div>

      <!-- Nav -->
      <nav :class="['flex-1 py-4 space-y-1 overflow-y-auto', isSidebarCollapsed && !isMobile ? 'px-2' : 'px-3']">
        <NavItem
          v-for="item in navItems"
          :key="item.to"
          :item="item"
          :collapsed="isSidebarCollapsed && !isMobile"
          :onNavigate="handleNavItemClick"
        />
      </nav>

      <!-- Version badges -->
      <div v-if="!isSidebarCollapsed || isMobile" class="px-4 pb-2 pt-3 border-t" style="border-color: var(--border)">
        <div class="space-y-1">
          <div class="flex items-center justify-between">
            <span class="text-xs font-mono" style="color: var(--text-muted)">UI</span>
            <span class="text-xs font-mono px-1.5 py-0.5 rounded" style="background: var(--surface-2); color: var(--text-muted)">{{ uiHash }}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-xs font-mono" style="color: var(--text-muted)">API</span>
            <span class="text-xs font-mono px-1.5 py-0.5 rounded" style="background: var(--surface-2); color: var(--text-muted)">{{ apiHash }}</span>
          </div>
        </div>
      </div>

      <!-- User footer -->
      <div :class="[isSidebarCollapsed && !isMobile ? 'px-2 py-3' : 'px-4 py-4', 'border-t']" style="border-color: var(--border)">
        <div :class="['flex items-center', isSidebarCollapsed && !isMobile ? 'justify-center' : 'gap-3']">
          <div class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold" style="background: var(--mint-dim); color: var(--mint)">
            {{ userInitial }}
          </div>
          <div v-if="!isSidebarCollapsed || isMobile" class="flex-1 min-w-0">
            <p class="text-xs truncate" style="color: var(--text-muted)">{{ userEmail }}</p>
          </div>
          <button @click="handleLogout" class="p-1 rounded hover:opacity-80 transition" title="Logout" style="color: var(--text-muted)">
            <i class="pi pi-sign-out text-sm"></i>
          </button>
        </div>
      </div>
    </aside>

    <!-- Main content -->
    <main class="flex-1 overflow-y-auto min-w-0">
      <div class="lg:hidden sticky top-0 z-20 px-4 py-3 border-b flex items-center justify-between" style="background: var(--surface); border-color: var(--border)">
        <button
          @click="openMobileSidebar"
          class="p-2 rounded hover:opacity-80"
          style="color: var(--text-muted); background: var(--surface-2)"
          aria-label="Open navigation"
        >
          <i class="pi pi-bars text-sm"></i>
        </button>
        <span class="text-sm font-semibold" style="color: var(--text)">flowmint</span>
        <div class="w-8"></div>
      </div>
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { RouterView, useRouter, useRoute } from 'vue-router'
import { useAuth } from '@/composables/useAuth'
import api from '@/utils/api'

const auth = useAuth()
const router = useRouter()
const route = useRoute()

const isSidebarCollapsed = ref(false)
const isMobileSidebarOpen = ref(false)
const windowWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1200)
const isMobile = computed(() => windowWidth.value < 1024)

const userEmail = computed(() => auth.currentUser.value?.email || '')
const userInitial = computed(() => userEmail.value ? userEmail.value[0].toUpperCase() : 'U')

const handleLogout = async () => {
  await auth.logout()
  router.push({ name: 'login' })
}

const shortHash = (h) => (h && h !== 'dev') ? h.slice(0, 7) : (h || '—')
const uiHash = shortHash(import.meta.env.VITE_COMMIT_HASH)
const apiCommit = ref('…')
const apiHash = computed(() => shortHash(apiCommit.value))

const updateViewportState = () => {
  windowWidth.value = window.innerWidth
  if (!isMobile.value) {
    isMobileSidebarOpen.value = false
  }
}

const openMobileSidebar = () => {
  if (!isMobile.value) return
  isMobileSidebarOpen.value = true
}

const closeMobileSidebar = () => {
  isMobileSidebarOpen.value = false
}

const handleNavItemClick = () => {
  if (isMobile.value) {
    isMobileSidebarOpen.value = false
  }
}

onMounted(async () => {
  window.addEventListener('resize', updateViewportState)
  updateViewportState()

  try {
    const res = await api.get('/api/version')
    apiCommit.value = res.data.commit
  } catch {
    apiCommit.value = '—'
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateViewportState)
})

watch(() => route.fullPath, () => {
  if (isMobile.value) {
    isMobileSidebarOpen.value = false
  }
})

const navItems = [
  { label: 'Dashboard',     to: '/dashboard',    icon: 'pi-home' },
  { label: 'Accounts',      to: '/accounts',     icon: 'pi-building-columns' },
  { label: 'Debt Tracker',  to: '/debt',         icon: 'pi-percentage' },
  { label: 'Transactions',  to: '/transactions', icon: 'pi-receipt' },
  { label: 'Budget',        to: '/budget',       icon: 'pi-chart-pie' },
  { label: 'Bills',         to: '/bills',        icon: 'pi-calendar-clock' },
  { label: 'Properties',    to: '/properties',   icon: 'pi-building' },
  { label: 'Documents',     to: '/documents',    icon: 'pi-file' },
  { label: 'Planning',      to: '/planning',     icon: 'pi-compass' },
]
</script>

<script>
import { defineComponent, h } from 'vue'
import { RouterLink, useLink } from 'vue-router'

const NavItem = defineComponent({
  props: {
    item: Object,
    collapsed: Boolean,
    onNavigate: Function,
  },
  setup(props) {
    const { isActive } = useLink({ to: props.item.to })
    return () => h(
      RouterLink,
      {
        to: props.item.to,
        title: props.collapsed ? props.item.label : undefined,
        onClick: () => props.onNavigate && props.onNavigate(),
        class: [
          'flex items-center px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150',
          props.collapsed ? 'justify-center' : 'gap-3',
          isActive.value
            ? 'text-[#080C0B] bg-[#3DDBB8]'
            : 'text-[#7A9E94] hover:text-[#E4F2EE] hover:bg-[#192620]'
        ]
      },
      () => [
        h('i', { class: `pi ${props.item.icon} text-base` }),
        !props.collapsed ? h('span', props.item.label) : null
      ]
    )
  }
})

export { NavItem }
</script>
