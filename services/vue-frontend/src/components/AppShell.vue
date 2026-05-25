<template>
  <div class="flex h-screen overflow-hidden" style="background: var(--bg)">
    <!-- Sidebar -->
    <aside class="w-60 flex flex-col flex-shrink-0 border-r" style="background: var(--surface); border-color: var(--border)">
      <!-- Logo -->
      <div class="flex items-center gap-2 px-6 py-5 border-b" style="border-color: var(--border)">
        <div class="w-7 h-7 rounded-lg flex items-center justify-center" style="background: var(--mint)">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 2L13 5V11L8 14L3 11V5L8 2Z" fill="#080C0B" stroke="#080C0B" stroke-width="0.5"/>
            <path d="M8 5L11 6.8V10.2L8 12L5 10.2V6.8L8 5Z" fill="var(--mint)" stroke="none"/>
          </svg>
        </div>
        <span class="text-lg font-bold tracking-tight" style="color: var(--mint)">flowmint</span>
      </div>

      <!-- Nav -->
      <nav class="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <NavItem v-for="item in navItems" :key="item.to" :item="item" />
      </nav>

      <!-- User footer -->
      <div class="px-4 py-4 border-t" style="border-color: var(--border)">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold" style="background: var(--mint-dim); color: var(--mint)">
            {{ userInitial }}
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-xs truncate" style="color: var(--text-muted)">{{ userEmail }}</p>
          </div>
          <button @click="handleLogout" class="p-1 rounded hover:opacity-80 transition" title="Logout" style="color: var(--text-muted)">
            <i class="pi pi-sign-out text-sm"></i>
          </button>
        </div>
      </div>
    </aside>

    <!-- Main content -->
    <main class="flex-1 overflow-y-auto">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { RouterView, useRouter } from 'vue-router'
import { useAuth } from '@/composables/useAuth'

const auth = useAuth()
const router = useRouter()

const userEmail = computed(() => auth.currentUser.value?.email || '')
const userInitial = computed(() => userEmail.value ? userEmail.value[0].toUpperCase() : 'U')

const handleLogout = async () => {
  await auth.logout()
  router.push({ name: 'login' })
}

const navItems = [
  { label: 'Dashboard',     to: '/dashboard',    icon: 'pi-home' },
  { label: 'Accounts',      to: '/accounts',     icon: 'pi-building-columns' },
  { label: 'Transactions',  to: '/transactions', icon: 'pi-receipt' },
  { label: 'Budget',        to: '/budget',       icon: 'pi-chart-pie' },
  { label: 'Bills',         to: '/bills',        icon: 'pi-calendar-clock' },
  { label: 'Properties',    to: '/properties',   icon: 'pi-building' },
  { label: 'Documents',     to: '/documents',    icon: 'pi-file' },
]
</script>

<script>
import { defineComponent, h } from 'vue'
import { RouterLink, useLink } from 'vue-router'

const NavItem = defineComponent({
  props: { item: Object },
  setup(props) {
    const { isActive } = useLink({ to: props.item.to })
    return () => h(
      RouterLink,
      {
        to: props.item.to,
        class: [
          'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150',
          isActive.value
            ? 'text-[#080C0B] bg-[#3DDBB8]'
            : 'text-[#7A9E94] hover:text-[#E4F2EE] hover:bg-[#192620]'
        ]
      },
      () => [
        h('i', { class: `pi ${props.item.icon} text-base` }),
        h('span', props.item.label)
      ]
    )
  }
})

export { NavItem }
</script>
