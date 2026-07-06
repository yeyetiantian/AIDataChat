import { createRouter, createWebHashHistory } from 'vue-router'
import AnalysisView from '@/views/AnalysisView.vue'
import BoardView from '@/views/BoardView.vue'

const routes = [
  { path: '/', redirect: '/board' },
  { path: '/set/:id?', name: 'analysis', component: AnalysisView, meta: { title: '数据分析' } },
  { path: '/board', name: 'board', component: BoardView, meta: { title: '看板' } },
  { path: '/:pathMatch(.*)*', redirect: '/board' },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
