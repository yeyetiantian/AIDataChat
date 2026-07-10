<template>
  <div class="chart-board">
    <div v-if="initialLoading" class="board-loading">
      <el-skeleton :rows="3" animated />
    </div>

    <div v-else class="chart-grid">
      <div
        v-for="chart in visibleCharts"
        :key="getCardKey(chart)"
        class="chart-card"
        :class="{
          'is-selected': selectedCardKey === getCardKey(chart),
          'is-draft': chart.isDraft,
          'is-placeholder': chart.isPlaceholder,
        }"
        @dblclick="emit('toggle-config', chart)"
      >
        <div class="card-header">
          <div class="card-title-wrap">
            <span class="card-title">{{ chart.title || '空白看板' }}</span>
            <span v-if="selectedCardKey === getCardKey(chart)" class="selected-chip">已选中</span>
          </div>
          <div class="card-actions">
            <el-tooltip v-if="hasRenderableChart(chart)" content="保存图片" placement="top">
              <el-button text circle class="action-btn action-btn-primary" @click="exportChartPng(chart.id, chart.title)">
                <el-icon :size="16"><Picture /></el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip v-if="hasRenderableChart(chart)" content="全屏" placement="top">
              <el-button text circle class="action-btn action-btn-primary" @click="toggleChartFullscreen(chart.id)">
                <el-icon :size="16"><FullScreen /></el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip v-if="!chart.isPlaceholder" content="删除" placement="top">
              <el-button
                text
                circle
                class="action-btn action-btn-danger"
                @click="handleRemove(chart)"
              >
                <el-icon :size="16"><Delete /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>
        <div v-if="chart.description" class="card-desc">{{ chart.description }}</div>
        <div class="card-chart">
          <div v-if="!hasRenderableChart(chart)" class="draft-placeholder">
            <el-icon :size="34" class="draft-placeholder-icon"><Grid /></el-icon>
            <strong>空白看板</strong>
            <span>双击卡片打开右侧透视表配置</span>
          </div>
          <VegaLiteRenderer
            v-else
            :ref="(el) => setRendererRef(chart.id, el)"
            :spec="chart.vega_spec"
            :data="chart.data"
            :config="chart.pivot_config"
            :chart-type="chart.chart_type"
            :hide-toolbar="true"
            :hide-title="true"
          />
        </div>
        <div class="card-footer">
          <el-tag size="small" :type="chart.isPlaceholder || chart.isDraft ? 'warning' : 'info'">
            {{ chart.isPlaceholder ? '空白' : chart.isDraft ? '草稿' : getChartTypeLabel(chart.chart_type) }}
          </el-tag>
          <span class="card-time">{{ chart.updated_at ? formatTime(chart.updated_at) : '待配置' }}</span>
        </div>
      </div>
    </div>

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
import { Delete, FullScreen, Grid, Picture } from '@element-plus/icons-vue'
import { MAX_BOARD_CHARTS, useChartStore, type SavedChart } from '@/stores/useChartStore'
import { buildBoardSlots } from '@/utils/boardSlots'
import VegaLiteRenderer from './VegaLiteRenderer.vue'

const store = useChartStore()

type DraftChart = {
  id: string
  title: string
  description: string
  pivot_config: Record<string, any> | null
  chart_type: string
  vega_spec?: Record<string, any> | null
  data?: Record<string, any>[] | null
  created_at: string
  updated_at: string
  slotIndex?: number
  isDraft: true
  isPlaceholder?: false
}

type PlaceholderChart = {
  id: string
  title: string
  description: string
  pivot_config: null
  chart_type: 'bar'
  vega_spec?: null
  data: null
  created_at: ''
  updated_at: ''
  slotIndex: number
  isPlaceholder: true
  isDraft?: false
}

type DraftBoardCard = DraftChart & { slotIndex: number }
type SavedBoardCard = SavedChart & { slotIndex: number, isDraft?: false, isPlaceholder?: false }
type BoardCard = SavedBoardCard | DraftBoardCard | PlaceholderChart

type ChartRendererHandle = {
  openDataDialog: () => void
  toggleFullscreen: () => void
  exportPng: (fileName?: string) => Promise<void>
  exportSvg: (fileName?: string) => Promise<void>
}

const props = withDefaults(defineProps<{
  draftCharts?: DraftChart[]
  selectedCardKey?: string | number | null
}>(), {
  draftCharts: () => [],
  selectedCardKey: null,
})

const emit = defineEmits<{
  'toggle-config': [chart: BoardCard]
  'remove-draft': [draftId: string]
}>()

const initialLoading = ref(true)
const showDelete = ref(false)
const deleteId = ref<number | null>(null)
const chartTypeLabels: Record<string, string> = {
  bar: '柱状图',
  line: '折线图',
  area: '面积图',
  point: '散点图',
  pie: '饼图',
  radar: '雷达图',
}

const boardCards = computed<BoardCard[]>(() => {
  const draftQueue = [...props.draftCharts]

  return buildBoardSlots(store.charts, MAX_BOARD_CHARTS).map((savedChart, slotIndex) => {
    if (savedChart) {
      return {
        ...savedChart,
        slotIndex,
      }
    }

    const draftChart = draftQueue.shift()
    if (draftChart) {
      return {
        ...draftChart,
        slotIndex,
      }
    }

    return {
      id: `placeholder-${slotIndex + 1}`,
      title: '空白看板',
      description: '',
      pivot_config: null,
      chart_type: 'bar',
      data: null,
      created_at: '',
      updated_at: '',
      slotIndex,
      isPlaceholder: true,
    }
  })
})

const visibleCharts = computed(() => boardCards.value)
const rendererRefs = ref<Record<string | number, ChartRendererHandle | null>>({})

function getCardKey(chart: BoardCard) {
  return chart.id
}

function hasRenderableChart(chart: BoardCard) {
  return !!(chart.vega_spec || (chart.data?.length && chart.pivot_config))
}

function handleDelete(id: number) {
  deleteId.value = id
  showDelete.value = true
}

function handleRemove(chart: BoardCard) {
  if (chart.isDraft) {
    emit('remove-draft', chart.id)
    return
  }

  if (!chart.isPlaceholder) {
    handleDelete(Number(chart.id))
  }
}

function setRendererRef(id: string | number, instance: unknown) {
  if (
    instance &&
    typeof (instance as ChartRendererHandle).openDataDialog === 'function' &&
    typeof (instance as ChartRendererHandle).toggleFullscreen === 'function' &&
    typeof (instance as ChartRendererHandle).exportPng === 'function' &&
    typeof (instance as ChartRendererHandle).exportSvg === 'function'
  ) {
    rendererRefs.value[id] = instance as ChartRendererHandle
    return
  }

  rendererRefs.value[id] = null
}

function toggleChartFullscreen(id: string | number) {
  rendererRefs.value[id]?.toggleFullscreen()
}

function exportChartPng(id: string | number, title: string) {
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

function getChartTypeLabel(chartType: string) {
  return chartTypeLabels[chartType] || chartType || '未知图表'
}

onMounted(async () => {
  try {
    await store.fetchCharts()
  } finally {
    initialLoading.value = false
  }
})
</script>

<style scoped>
.chart-board {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
  padding: 14px;
  overflow: hidden;
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

.chart-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  grid-template-rows: repeat(2, minmax(0, 1fr));
  gap: 14px;
  align-items: stretch;
}

.chart-card {
  position: relative;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: box-shadow 0.2s, transform 0.2s, border-color 0.2s;
  min-width: 0;
  border: 1px solid transparent;
}

.chart-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.chart-card.is-selected {
  border-color: #60a5fa;
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.14), 0 18px 34px rgba(64, 158, 255, 0.22);
  transform: translateY(-2px);
}

.chart-card.is-selected::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 12px;
  pointer-events: none;
  box-shadow: inset 0 0 0 1px rgba(96, 165, 250, 0.55);
}

.chart-card.is-placeholder {
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}

.card-header {
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid #f2f3f5;
  gap: 12px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-title-wrap {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.selected-chip {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 8px;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
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
  flex-shrink: 0;
  padding: 6px 14px;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.card-chart {
  flex: 1;
  min-height: 0;
  display: flex;
  padding: 8px 10px;
  overflow: hidden;
}

.card-chart :deep(.vega-renderer) {
  width: 100%;
  height: 100%;
  min-height: 0;
  flex: 1;
  border-radius: 6px;
}

.card-chart :deep(.vega-container) {
  height: 100%;
  min-height: 0;
}

.draft-placeholder {
  width: 100%;
  height: 100%;
  min-height: 0;
  border: 1px dashed #d9e3f0;
  border-radius: 8px;
  background: linear-gradient(180deg, #f8fbff 0%, #f3f7fc 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  text-align: center;
  color: #8a94a6;
  padding: 20px;
}

.draft-placeholder strong {
  font-size: 15px;
  color: #606266;
}

.draft-placeholder span {
  font-size: 12px;
}

.draft-placeholder-icon {
  color: #93c5fd;
}

.card-footer {
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 7px 14px;
  border-top: 1px solid #f2f3f5;
  font-size: 12px;
  color: #909399;
}

.card-time {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 1200px) {
  .chart-board {
    overflow-y: auto;
  }

  .chart-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    grid-template-rows: none;
  }

  .chart-card {
    min-height: 360px;
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
