<template>
  <div class="board-view">
    <section class="board-workspace">
      <div class="board-main">
        <div class="board-list-wrap">
          <ChartBoard
            :selected-card-key="selectedBoardKey"
            @edit="loadToAnalysis"
            @toggle-config="handleToggleConfig"
          />
        </div>
      </div>

      <aside class="board-sidebar" :class="{ 'is-open': showConfigPanel }">
        <div class="board-sidebar-inner">
          <div class="board-sidebar-content">
            <ConfigPanel ref="configPanelRef" v-if="showConfigPanel" :api="pivotApi" />
          </div>
          <div v-if="showConfigPanel" class="board-sidebar-footer">
            <el-button size="small" type="danger" @click="closeConfigPanel">关闭配置</el-button>
          </div>
        </div>
      </aside>
    </section>

    <!-- AI 对话按钮 -->
    <el-button
      :type="showAiDialog ? 'success' : 'default'"
      circle
      size="large"
      class="board-ai-button"
      :style="{ right: showConfigPanel ? '392px' : '24px' }"
      @click="showAiDialog = !showAiDialog"
    >
      <el-icon :size="20"><ChatDotRound /></el-icon>
    </el-button>

    <!-- AI 对话弹窗 -->
    <el-dialog
      v-model="showAiDialog"
      title="AI 对话分析"
      width="700px"
      top="5vh"
      destroy-on-close
    >
      <AIDialog @save="handleSaveToBoard" />
    </el-dialog>

    <el-dialog v-model="showCreateDialog" title="新增看板" width="420px">
      <el-form label-position="top">
        <el-form-item label="看板名称">
          <el-input v-model="createTitle" placeholder="请输入看板名称" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="createDesc" type="textarea" :rows="3" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="chartStore.loading" @click="handleCreateBoard">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { MAX_BOARD_CHARTS, useChartStore } from '@/stores/useChartStore'
import type { SavedChart } from '@/stores/useChartStore'
import type { PivotConfig } from '@/types'
import ChartBoard from '@/components/ChartBoard.vue'
import AIDialog from '@/components/AIDialog.vue'
import ConfigPanel from '@/components/ConfigPanel.vue'
import { createMockBoardCharts } from '@/constants/mockBoardCharts'
import { ChatDotRound } from '@element-plus/icons-vue'

const router = useRouter()
const chartStore = useChartStore()

type ConfigPanelHandle = {
  setDefaultValues: (config: any) => void
  resetConfig: () => void
}

type ToggleBoardCard = SavedChart | {
  id: string | number
  pivot_config: any
  chart_type: string
}

const showAiDialog = ref(false)
const showConfigPanel = ref(false)
const showCreateDialog = ref(false)
const createTitle = ref('空白看板')
const createDesc = ref('')
const selectedBoardKey = ref<string | number | null>(null)
const configPanelRef = ref<ConfigPanelHandle | null>(null)
const selectedBoard = computed(() => chartStore.charts.find(board => board.id === selectedBoardKey.value) || null)

function closeConfigPanel() {
  showConfigPanel.value = false
  selectedBoardKey.value = null
}

function loadToAnalysis(chart: SavedChart) {
  void chart
  router.push('/set')
}

async function pivotApi(config: any) {
  if (!selectedBoard.value) {
    ElMessage.warning('请先选择左侧看板，再执行查询')
    return
  }

  try {
    const resp = await fetch('/api/pivot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    })

    if (!resp.ok) {
      const err = await resp.json()
      throw new Error(err.detail || '查询失败')
    }

    const result = await resp.json()
    await chartStore.updateChart(selectedBoard.value.id, {
      pivot_config: config,
      chart_type: config?.chart_type || 'bar',
      data: result.data || [],
    })
  } catch (e: any) {
    ElMessage.error(e.message || '查询失败')
  }
}

async function handleSaveToBoard(chart: Omit<SavedChart, 'id' | 'created_at' | 'updated_at'>) {
  const saved = await chartStore.saveChart(chart.title, chart.pivot_config as PivotConfig, chart.description || '', chart.chart_type, chart.data)
  if (!saved) {
    ElMessage.warning(chartStore.error || `看板最多只能保存 ${MAX_BOARD_CHARTS} 个`)
    return
  }
  showAiDialog.value = false
}

function openCreateDialog() {
  if (chartStore.charts.length >= MAX_BOARD_CHARTS) {
    ElMessage.warning(`看板最多只能保存 ${MAX_BOARD_CHARTS} 个`)
    return
  }
  createTitle.value = '空白看板'
  createDesc.value = ''
  showCreateDialog.value = true
}

async function handleCreateBoard() {
  if (!createTitle.value.trim()) {
    ElMessage.warning('请填写看板名称')
    return
  }

  const emptyConfig: PivotConfig = {
    filters: [],
    axes: [],
    legend: [],
    values: [],
    order_by: [],
    limit: 10000,
    having: [],
    grand_total: false,
    subtotals: false,
  }

  const created = await chartStore.saveChart(
    createTitle.value.trim(),
    emptyConfig,
    createDesc.value.trim(),
    'bar',
    null,
  )

  if (!created) {
    ElMessage.warning(chartStore.error || '创建看板失败')
    return
  }

  selectedBoardKey.value = created.id
  showCreateDialog.value = false
  showConfigPanel.value = true
  await syncConfigPanel(created)
}

async function syncConfigPanel(chart: SavedChart | null) {
  if (!showConfigPanel.value) return
  await nextTick()

  if (!configPanelRef.value) return

  if (!chart) {
    configPanelRef.value.resetConfig()
    return
  }

  if (chart.pivot_config) {
    configPanelRef.value.setDefaultValues(chart.pivot_config)
    return
  }

  configPanelRef.value.resetConfig()
}

async function handleToggleConfig(chart: ToggleBoardCard) {
  if (typeof chart.id !== 'number') return
  const nextKey = chart.id
  const isSameCard = selectedBoardKey.value === nextKey

  if (isSameCard && showConfigPanel.value) {
    closeConfigPanel()
    return
  }

  selectedBoardKey.value = nextKey
  showConfigPanel.value = true
  await syncConfigPanel(chart as SavedChart)
}

watch(showConfigPanel, async (visible) => {
  if (!visible) return
  const current = chartStore.charts.find(chart => chart.id === selectedBoardKey.value) || null
  await syncConfigPanel(current)
})

function handleCreateRequest() {
  openCreateDialog()
}

async function handleMockDataRequest() {
  await chartStore.fetchCharts()

  if (chartStore.charts.length > 0) {
    ElMessage.warning('请先清空现有看板，再生成 6 种模拟图表数据')
    return
  }

  const mockCharts = createMockBoardCharts()
  let createdCount = 0
  let firstCreatedId: number | null = null

  for (const mockChart of mockCharts) {
    const created = await chartStore.saveChart(
      mockChart.title,
      mockChart.pivotConfig,
      mockChart.description,
      mockChart.chartType,
      mockChart.data,
    )

    if (!created) {
      ElMessage.warning(chartStore.error || '模拟数据生成失败')
      break
    }

    createdCount += 1
    if (firstCreatedId == null) {
      firstCreatedId = created.id
    }
  }

  if (createdCount === mockCharts.length) {
    selectedBoardKey.value = firstCreatedId
    showConfigPanel.value = false
    ElMessage.success('已生成 6 种模拟图表数据')
    return
  }

  if (createdCount > 0) {
    ElMessage.warning(`已生成 ${createdCount} 张模拟图表，剩余图表未完成`)
  }
}

onMounted(() => {
  window.addEventListener('board:create', handleCreateRequest)
  window.addEventListener('board:mock-data', handleMockDataRequest)
})

onBeforeUnmount(() => {
  window.removeEventListener('board:create', handleCreateRequest)
  window.removeEventListener('board:mock-data', handleMockDataRequest)
})
</script>

<style scoped>
.board-view {
  flex: 1;
  overflow: hidden;
  padding: 0;
  position: relative;
}

.board-workspace {
  height: 100%;
  display: flex;
  position: relative;
  overflow: hidden;
}

.board-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.24s ease;
}

.board-list-wrap {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.board-sidebar {
  width: 0;
  flex-shrink: 0;
  overflow: hidden;
  background: #f5f7fa;
  border-left: 1px solid transparent;
  transition: width 0.24s ease, border-color 0.24s ease;
}

.board-sidebar.is-open {
  width: 368px;
  border-left-color: #e4e7ed;
}

.board-sidebar-inner {
  width: 368px;
  height: 100%;
  padding: 10px 10px 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.board-sidebar-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.board-sidebar-footer {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  padding: 0 0 4px;
  border-top: 1px solid #e4e7ed;
  padding-top: 10px;
}

.board-ai-button {
  position: fixed;
  bottom: 24px;
  z-index: 1000;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  transition: right 0.24s ease;
}

@media (max-width: 1100px) {
}

@media (max-width: 960px) {
  .board-sidebar {
    position: absolute;
    top: 0;
    right: 0;
    height: 100%;
    z-index: 15;
    box-shadow: -12px 0 24px rgba(15, 23, 42, 0.08);
  }

  .board-sidebar.is-open {
    width: min(368px, calc(100vw - 48px));
  }

  .board-sidebar-inner {
    width: min(368px, calc(100vw - 48px));
  }

  .board-ai-button {
    right: 24px !important;
  }
}
</style>
