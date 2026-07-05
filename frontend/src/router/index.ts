import { createRouter, createWebHistory } from 'vue-router'
import AnalysisView from '@/views/AnalysisView.vue'
import BoardView from '@/views/BoardView.vue'

const routes = [
  { path: '/', redirect: '/board' },
  { path: '/set/:id?', name: 'analysis', component: AnalysisView, meta: { title: '数据分析' } },
  { path: '/board', name: 'board', component: BoardView, meta: { title: '看板' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
