import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/Login.vue'),
      meta: { public: true }
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/Register.vue'),
      meta: { public: true }
    },
    {
      path: '/',
      component: () => import('@/components/AppShell.vue'),
      meta: { requiresAuth: true },
      children: [
        { path: '', redirect: '/dashboard' },
        { path: 'dashboard', name: 'dashboard', component: () => import('@/views/Dashboard.vue') },
        { path: 'accounts', name: 'accounts', component: () => import('@/views/Accounts.vue') },
        { path: 'transactions', name: 'transactions', component: () => import('@/views/Transactions.vue') },
        { path: 'budget', name: 'budget', component: () => import('@/views/Budget.vue') },
        { path: 'bills', name: 'bills', component: () => import('@/views/Bills.vue') },
        { path: 'properties', name: 'properties', component: () => import('@/views/Properties.vue') },
        { path: 'properties/:id', name: 'property-detail', component: () => import('@/views/PropertyDetail.vue') },
        { path: 'documents', name: 'documents', component: () => import('@/views/Documents.vue') },
        { path: 'planning', name: 'planning', component: () => import('@/views/Planning.vue') }
      ]
    },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' }
  ]
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true
  const stored = window.localStorage.getItem('access_token')
  if (!stored) {
    try {
      const mod = await import('@/composables/useAuth')
      const token = await mod.useAuth().refresh()
      if (!token) return { name: 'login' }
    } catch {
      return { name: 'login' }
    }
  }
  return true
})

export default router
