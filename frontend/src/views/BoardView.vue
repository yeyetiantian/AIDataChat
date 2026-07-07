<template>
  <div class="board-view">
    <section class="board-workspace">
      <div class="board-main">
        <div class="board-list-wrap">
          <ChartBoard
            :selected-card-key="selectedBoardKey"
            @toggle-config="handleToggleConfig"
          />
        </div>
      </div>

      <aside class="board-sidebar" :class="{ 'is-open': showConfigPanel }">
        <div class="board-sidebar-inner">
          <div class="board-sidebar-content">
            <ConfigPanel
              ref="configPanelRef"
              v-if="showConfigPanel"
              :api="pivotApi"
              :config-name="selectedBoard?.title || ''"
            />
          </div>
          <div v-if="showConfigPanel" class="board-sidebar-footer">
            <el-button size="small" type="primary" @click="openImportConfigDialog">导入配置</el-button>
            <el-button size="small" type="danger" @click="closeConfigPanel">关闭配置</el-button>
          </div>
        </div>
      </aside>
    </section>

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

    <el-dialog
      v-model="showAiDialog"
      title="AI 对话分析"
      width="700px"
      top="5vh"
      destroy-on-close
    >
      <AIDialog @save="handleSaveToBoard" @close="showAiDialog = false" />
    </el-dialog>

    <el-dialog
      v-model="importDialogVisible"
      title="导入配置"
      width="560px"
      destroy-on-close
    >
      <div v-if="savedReportConfigs.length === 0" class="config-import-empty">
        暂无已保存配置
      </div>
      <div v-else class="config-import-list">
        <button
          v-for="item in savedReportConfigs"
          :key="item.id"
          type="button"
          class="config-import-item"
          :class="{ 'is-active': selectedImportConfigId === item.id }"
          @click="selectedImportConfigId = item.id"
        >
          <div class="config-import-item-main">
            <span class="config-import-name">{{ item.name }}</span>
            <span class="config-import-time">{{ formatSavedConfigTime(item.savedAt) }}</span>
          </div>
          <el-tag v-if="selectedImportConfigId === item.id" size="small" type="primary">已选择</el-tag>
        </button>
      </div>

      <template #footer>
        <el-button
          type="danger"
          plain
          :disabled="savedReportConfigs.length === 0"
          @click="handleClearStoredConfigs"
        >
          清空配置
        </el-button>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!selectedImportConfigId" @click="handleImportConfig">
          导入配置
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MAX_BOARD_CHARTS, useChartStore } from '@/stores/useChartStore'
import type { SavedChart } from '@/stores/useChartStore'
import type { PivotConfig } from '@/types'
import { normalizeApiDate } from '@/api/filterSelect'
import ChartBoard from '@/components/ChartBoard.vue'
import AIDialog from '@/components/AIDialog.vue'
import ConfigPanel from '@/components/ConfigPanel.vue'
import { createMockBoardCharts } from '@/constants/mockBoardCharts'
import { ChatDotRound } from '@element-plus/icons-vue'
import {
  clearStoredReportConfigs,
  clonePivotConfig,
  loadStoredReportConfigs,
  type StoredReportConfig,
} from '@/utils/reportConfigStorage'

const chartStore = useChartStore()

type ConfigPanelHandle = {
  setDefaultValues: (config: PivotConfig) => Promise<void>
  resetConfig: () => Promise<void>
  applyConfigAndQuery: (config: PivotConfig) => Promise<void>
}

type ToggleBoardCard = (SavedChart & { isPlaceholder?: false }) | {
  id: string | number
  pivot_config: any
  chart_type: string
  isPlaceholder?: boolean
}

const showAiDialog = ref(false)
const showConfigPanel = ref(false)
const selectedBoardKey = ref<string | number | null>(null)
const configPanelRef = ref<ConfigPanelHandle | null>(null)
const importDialogVisible = ref(false)
const savedReportConfigs = ref<StoredReportConfig[]>([])
const selectedImportConfigId = ref('')
const selectedBoard = computed(() => chartStore.charts.find(board => board.id === selectedBoardKey.value) || null)

function createEmptyBoardConfig(): PivotConfig {
  return {
    filters: [],
    axes: [],
    legend: [],
    values: [],
    order_by: [],
    limit: 1000,
    having: [],
    grand_total: false,
    subtotals: false,
  }
}

function closeConfigPanel() {
  showConfigPanel.value = false
  selectedBoardKey.value = null
}

function openImportConfigDialog() {
  savedReportConfigs.value = loadStoredReportConfigs()
  selectedImportConfigId.value = savedReportConfigs.value[0]?.id ?? ''
  importDialogVisible.value = true
}

function formatSavedConfigTime(value: string) {
  const time = new Date(value)
  if (Number.isNaN(time.getTime())) return value
  return time.toLocaleString('zh-CN', { hour12: false })
}

async function handleImportConfig() {
  const selectedConfig = savedReportConfigs.value.find(item => item.id === selectedImportConfigId.value)
  if (!selectedConfig) {
    ElMessage.warning('请选择一条配置')
    return
  }

  if (!configPanelRef.value) {
    ElMessage.warning('配置面板未就绪')
    return
  }

  const importedConfig = clonePivotConfig(selectedConfig.config)
  await configPanelRef.value.applyConfigAndQuery(importedConfig)

  if (selectedBoard.value) {
    await chartStore.updateChart(selectedBoard.value.id, {
      title: selectedConfig.name,
    })
  }

  importDialogVisible.value = false
  ElMessage.success(`已导入配置：${selectedConfig.name}`)
}

async function handleClearStoredConfigs() {
  if (savedReportConfigs.value.length === 0) {
    ElMessage.info('暂无可清空的配置')
    return
  }

  try {
    await ElMessageBox.confirm(
      '确定要清空当前所有已保存的配置吗？清空后不可恢复。',
      '确认清空配置',
      {
        confirmButtonText: '确认清空',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  try {
    clearStoredReportConfigs()
    savedReportConfigs.value = []
    selectedImportConfigId.value = ''
    ElMessage.success('已清空当前所有缓存配置')
  } catch (error: any) {
    ElMessage.error(error?.message || '清空配置失败')
  }
}

function toFilterValueArray(value: unknown) {
  if (Array.isArray(value)) return value
  if (value == null || value === '') return []
  if (typeof value === 'string' && value.includes(',')) {
    return value
      .split(',')
      .map(item => item.trim())
      .filter(item => item !== '')
  }
  return [value]
}

function toQueryFilterValue(filter: { filter_type?: string; op: string; value: unknown }) {
  const values = toFilterValueArray(filter.value)
  if (filter.filter_type === 'date' && filter.op === 'between' && values.length >= 2) {
    return values.map((v, i) => {
      const dateStr = normalizeApiDate(String(v))
      if (!dateStr) return v
      return i === 0 ? `${dateStr} 00:00:00` : `${dateStr} 23:59:59`
    })
  }
  return values
}

function toBoardPivotRequest(config: PivotConfig) {
  return {
    filters: (config.filters ?? []).map((filter, index) => ({
      field: filter.field,
      op: filter.op,
      value: toQueryFilterValue(filter),
      select_ts: filter.select_ts ?? '',
      select_order: filter.select_order ?? index + 1,
      filter_type: filter.filter_type ?? '',
    })),
    axes: (config.axes ?? []).map(axis => ({
      field: axis.field,
      alias: axis.alias,
      ...(axis.aggregation ? { aggregation: axis.aggregation } : {}),
    })),
    legend: (config.legend ?? []).map(item => ({
      field: item.field,
      alias: item.alias,
    })),
    values: (config.values ?? []).map(item => ({
      id: item.id,
      field: item.field,
      aggregation: item.aggregation,
      alias: item.alias,
      ...(item.show_as ? { show_as: item.show_as } : {}),
    })),
    limit: config.limit ?? 1000,
    having: config.having ?? [],
    chart_type: config.chart_type ?? 'bar',
    grand_total: config.grand_total ?? false,
    subtotals: config.subtotals ?? false,
  }
}

async function pivotApi(config: any) {
  if (!selectedBoard.value) {
    ElMessage.warning('请先选择左侧看板，再执行查询')
    return
  }

  try {
    const requestConfig = toBoardPivotRequest(config as PivotConfig)
    const resp = await fetch('http://127.0.0.1:8080/api2/pivot/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestConfig),
    })

    if (!resp.ok) {
      const err = await resp.json()
      throw new Error(err.detail || '查询失败')
    }

    const result = await resp.json()
    await chartStore.updateChart(selectedBoard.value.id, {
      pivot_config: config,
      chart_type: config?.chart_type || 'bar',
      vega_spec: null,
      data: result.data || [],
    })
  } catch (e: any) {
    ElMessage.error(e.message || '查询失败')
  }
}

async function handleSaveToBoard(chart: Omit<SavedChart, 'id' | 'created_at' | 'updated_at'>) {
  const saved = await chartStore.saveChart(
    chart.title,
    chart.pivot_config as PivotConfig,
    chart.description || '',
    chart.chart_type,
    chart.vega_spec || null,
    chart.data,
  )
  if (!saved) {
    ElMessage.warning(chartStore.error || `看板最多只能保存 ${MAX_BOARD_CHARTS} 个`)
    return
  }
  showAiDialog.value = false
}

async function createEmptyBoard() {
  const created = await chartStore.saveChart(
    '空白看板',
    createEmptyBoardConfig(),
    '',
    'bar',
    null,
    null,
  )

  if (!created) {
    ElMessage.warning(chartStore.error || '创建看板失败')
    return
  }

  selectedBoardKey.value = created.id
  showConfigPanel.value = true
  await syncConfigPanel(created)
}

async function syncConfigPanel(chart: SavedChart | null) {
  if (!showConfigPanel.value) return
  await nextTick()

  if (!configPanelRef.value) return

  if (!chart) {
    await configPanelRef.value.resetConfig()
    return
  }

  if (chart.pivot_config) {
    await configPanelRef.value.setDefaultValues(chart.pivot_config)
    return
  }

  await configPanelRef.value.resetConfig()
}

async function handleToggleConfig(chart: ToggleBoardCard) {
  if (chartStore.loading) return

  if (chart.isPlaceholder) {
    await createEmptyBoard()
    return
  }

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

async function clearAllCharts() {
  const chartsToDelete = [...chartStore.charts]

  closeConfigPanel()

  for (const chart of chartsToDelete) {
    const deleted = await chartStore.deleteChart(chart.id)
    if (!deleted) {
      ElMessage.error(chartStore.error || `删除看板“${chart.title || chart.id}”失败`)
      return false
    }
  }

  await chartStore.fetchCharts()
  return true
}

async function handleClearBoardRequest() {
  await chartStore.fetchCharts()

  if (chartStore.charts.length === 0) {
    ElMessage.info('当前没有可清空的看板')
    return
  }

  try {
    await ElMessageBox.confirm(
      '确定要清空当前所有看板吗？清空后不可恢复。',
      '确认清空看板',
      {
        confirmButtonText: '确认清空',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  const cleared = await clearAllCharts()
  if (!cleared) return

  ElMessage.success('已清空当前所有看板')
}

async function handleMockDataRequest() {
  await chartStore.fetchCharts()

  if (chartStore.charts.length > 0) {
    try {
      await ElMessageBox.confirm(
        '生成模拟数据会先删除当前所有看板和报表数据，是否继续？',
        '确认清空现有报表',
        {
          confirmButtonText: '确认删除并生成',
          cancelButtonText: '取消',
          type: 'warning',
        },
      )
    } catch {
      return
    }

    const cleared = await clearAllCharts()
    if (!cleared) return
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
      null,
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
  window.addEventListener('board:mock-data', handleMockDataRequest)
  window.addEventListener('board:clear-all', handleClearBoardRequest)
})

onBeforeUnmount(() => {
  window.removeEventListener('board:mock-data', handleMockDataRequest)
  window.removeEventListener('board:clear-all', handleClearBoardRequest)
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
  gap: 8px;
  padding: 0 0 4px;
  border-top: 1px solid #e4e7ed;
  padding-top: 10px;
}

.board-ai-button {
  position: fixed;
  bottom: 24px;
  z-index: 1000;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transition: right 0.24s ease;
}

.config-import-empty {
  padding: 28px 0;
  text-align: center;
  color: #909399;
  font-size: 14px;
}

.config-import-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 360px;
  overflow-y: auto;
}

.config-import-item {
  appearance: none;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid #dcdfe6;
  border-radius: 10px;
  background: #fff;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}

.config-import-item:hover {
  border-color: #409eff;
}

.config-import-item.is-active {
  border-color: #409eff;
  background: #ecf5ff;
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.16);
}

.config-import-item-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.config-import-name {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.config-import-time {
  font-size: 12px;
  color: #909399;
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
