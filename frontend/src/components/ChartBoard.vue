<template>
  <div class="chart-board">
    <div class="board-header">
      <h3>📋 我的看板</h3>
      <span class="board-tip">最多 6 个看板，每行 3 个</span>
    </div>

    <div v-if="store.loading" class="board-loading">
      <el-skeleton :rows="3" animated />
    </div>

    <div v-else-if="store.charts.length === 0" class="board-empty">
      <el-empty description="还没有保存的图表，在分析页面点击「保存到看板」">
        <el-button type="primary" size="small" @click="router.push('/set')">去分析</el-button>
      </el-empty>
    </div>

    <div v-else class="chart-grid">
      <div v-for="chart in visibleCharts" :key="chart.id" class="chart-card">
        <div class="card-header">
          <span class="card-title">{{ chart.title }}</span>
          <div class="card-actions">
            <el-tooltip content="保存图片" placement="top">
              <el-button text circle class="action-btn action-btn-primary" @click="exportChartPng(chart.id, chart.title)">
                <el-icon :size="16"><Picture /></el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="查看数据" placement="top">
              <el-button text circle class="action-btn action-btn-primary" @click="openChartData(chart.id)">
                <el-icon :size="16"><View /></el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="全屏" placement="top">
              <el-button text circle class="action-btn action-btn-primary" @click="toggleChartFullscreen(chart.id)">
                <el-icon :size="16"><FullScreen /></el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="编辑" placement="top">
              <el-button text circle class="action-btn action-btn-primary" @click="$emit('edit', chart)">
                <el-icon :size="16"><Edit /></el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="删除" placement="top">
              <el-button text circle class="action-btn action-btn-danger" @click="handleDelete(chart.id)">
                <el-icon :size="16"><Delete /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>
        <div class="card-desc" v-if="chart.description">{{ chart.description }}</div>
        <div class="card-chart">
          <VegaLiteRenderer
            :ref="(el) => setRendererRef(chart.id, el)"
            :data="chart.data"
            :config="chart.pivot_config"
            :chart-type="chart.chart_type"
            :hide-toolbar="true"
          />
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
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Delete, Edit, FullScreen, Picture, View } from '@element-plus/icons-vue'
import { MAX_BOARD_CHARTS, useChartStore, type SavedChart } from '@/stores/useChartStore'
import VegaLiteRenderer from './VegaLiteRenderer.vue'

const store = useChartStore()
const router = useRouter()

type ChartRendererHandle = {
  openDataDialog: () => void
  toggleFullscreen: () => void
  exportPng: (fileName?: string) => Promise<void>
  exportSvg: (fileName?: string) => Promise<void>
}

defineEmits<{
  edit: [chart: SavedChart]
}>()

const showDelete = ref(false)
const deleteId = ref<number | null>(null)
const visibleCharts = computed(() => store.charts.slice(0, MAX_BOARD_CHARTS))
const rendererRefs = ref<Record<number, ChartRendererHandle | null>>({})

function handleDelete(id: number) {
  deleteId.value = id
  showDelete.value = true
}

function setRendererRef(id: number, instance: any) {
  if (
    instance &&
    typeof instance.openDataDialog === 'function' &&
    typeof instance.toggleFullscreen === 'function' &&
    typeof instance.exportPng === 'function' &&
    typeof instance.exportSvg === 'function'
  ) {
    rendererRefs.value[id] = instance as ChartRendererHandle
    return
  }
  rendererRefs.value[id] = null
}

function openChartData(id: number) {
  rendererRefs.value[id]?.openDataDialog()
}

function toggleChartFullscreen(id: number) {
  rendererRefs.value[id]?.toggleFullscreen()
}

function exportChartPng(id: number, title: string) {
  void rendererRefs.value[id]?.exportPng(`${title || 'chart'}.png`)
}

async function confirmDelete() {
  if (deleteId.value != null) {
    await store.deleteChart(deleteId.value)
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
  gap: 12px;
  flex-wrap: wrap;
}

.board-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.board-tip {
  font-size: 13px;
  color: #909399;
}

.board-loading {
  padding: 24px;
}

.board-empty {
  margin-top: 80px;
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  align-items: stretch;
}

.chart-card {
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: box-shadow 0.2s;
  min-width: 0;
}

.chart-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 12px 16px;
  border-bottom: 1px solid #f2f3f5;
  gap: 12px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  line-height: 1.5;
  flex: 1;
  min-width: 0;
  word-break: break-word;
}

.card-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  flex-shrink: 0;
}

.card-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.action-btn {
  width: 24px;
  height: 24px;
  border-radius: 999px;
}

.action-btn-primary {
  color: #409eff;
}

.action-btn-primary:hover {
  background: #ecf5ff;
  color: #409eff;
}

.action-btn-danger {
  color: #f56c6c;
}

.action-btn-danger:hover {
  background: #fef0f0;
  color: #f56c6c;
}

.card-desc {
  padding: 8px 16px;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}

.card-chart {
  padding: 12px;
  height: 240px;
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

@media (max-width: 1200px) {
  .chart-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .chart-board {
    padding: 12px;
  }

  .chart-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
