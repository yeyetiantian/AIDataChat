import { createRouter, createWebHashHistory } from 'vue-router'
import BoardView from '@/views/BoardView.vue'
import MonitorView from '@/views/MonitorView.vue'

const routes = [
  { path: '/', redirect: '/board' },
  { path: '/board', name: 'board', component: BoardView, meta: { title: '看板' } },
  { path: '/monitor', name: 'monitor', component: MonitorView, meta: { title: '监控' } },
  { path: '/:pathMatch(.*)*', redirect: '/board' },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
