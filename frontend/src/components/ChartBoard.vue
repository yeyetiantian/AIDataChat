<template>
  <div class="chart-board">
    <div class="board-header">
      <h3>📋 我的看板</h3>
    </div>

    <div v-if="store.loading" class="board-loading">
      <el-skeleton :rows="3" animated />
    </div>

    <div v-else-if="store.charts.length === 0" class="board-empty">
      <el-empty description="还没有保存的图表，在分析页面点击「保存到看板」">
        <el-button type="primary" size="small" @click="router.push('/')">去分析</el-button>
      </el-empty>
    </div>

    <div v-else class="chart-grid">
      <div v-for="chart in store.charts" :key="chart.id" class="chart-card">
        <div class="card-header">
          <span class="card-title">{{ chart.title }}</span>
          <el-dropdown trigger="click">
            <el-button size="small" text :icon="MoreFilled" />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="$emit('edit', chart)">编辑</el-dropdown-item>
                <el-dropdown-item @click="handleDelete(chart.id)">删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <div class="card-desc" v-if="chart.description">{{ chart.description }}</div>
        <div class="card-chart">
          <VegaLiteRenderer :data="chart.data" :config="chart.pivot_config" :chart-type="chart.chart_type" />
        </div>
        <div class="card-footer">
          <el-tag size="small" type="info">{{ chart.chart_type }}</el-tag>
          <span class="card-time">{{ formatTime(chart.updated_at) }}</span>
        </div>
      </div>
    </div>

    <!-- 删除确认 -->
    <el-dialog v-model="showDelete" title="确认删除" width="400px">
      <p>确定要删除这个图表吗？</p>
      <template #footer>
        <el-button @click="showDelete = false">取消</el-button>
        <el-button type="danger" @click="confirmDelete">删除</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { MoreFilled, Warning } from '@element-plus/icons-vue'
import { useChartStore, type SavedChart } from '@/stores/useChartStore'
import VegaLiteRenderer from './VegaLiteRenderer.vue'

interface ChartWithSpec extends SavedChart {
  data?: Record<string, any>[] | null
  chart_error?: string
  chart_loading?: boolean
}

const store = useChartStore()
const router = useRouter()

defineEmits<{
  edit: [chart: SavedChart]
}>()

const showDelete = ref(false)
const deleteId = ref<number | null>(null)
const chartsWithSpec = ref<ChartWithSpec[]>([])

function handleDelete(id: number) {
  deleteId.value = id
  showDelete.value = true
}

async function confirmDelete() {
  if (deleteId.value != null) {
    await store.deleteChart(deleteId.value)
    chartsWithSpec.value = chartsWithSpec.value.filter(c => c.id !== deleteId.value)
  }
  showDelete.value = false
  deleteId.value = null
}

function formatTime(ts: string) {
  if (!ts) return ''
  return ts.substring(0, 16).replace('T', ' ')
}

/**
 * 用已保存的 pivot_config 调用 /api/pivot 动态获取数据
 */

onMounted(async () => {
  await store.fetchCharts()
})
</script>

<style scoped>
.chart-board {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
  padding: 16px;
  overflow-y: auto;
}

.board-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.board-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.board-loading {
  padding: 24px;
}

.board-empty {
  margin-top: 80px;
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}

.chart-card {
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: box-shadow 0.2s;
}

.chart-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #f2f3f5;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.card-desc {
  padding: 8px 16px;
  font-size: 12px;
  color: #909399;
}

.card-chart {
  padding: 12px;
  min-height: 200px;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  border-top: 1px solid #f2f3f5;
  font-size: 12px;
  color: #909399;
}
</style>
