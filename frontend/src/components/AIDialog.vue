<template>
  <div class="ai-dialog">
    <div class="dialog-messages" ref="messagesRef">
      <div v-if="chatStore.messages.length === 0" class="empty-state">
        <el-icon :size="48" color="#c0c4cc"><ChatLineSquare /></el-icon>
        <p>输入分析需求，AI 将自动生成图表</p>
        <div class="suggestions">
          <el-tag
            v-for="s in suggestions" :key="s"
            size="small"
            class="suggestion-tag"
            @click="chatStore.sendMessage(s)"
          >
            {{ s }}
          </el-tag>
        </div>
      </div>

      <div v-for="(msg, i) in chatStore.messages" :key="i" class="message" :class="msg.role">
        <div class="message-content">
          <div class="message-text">{{ msg.content }}</div>

          <!-- 图表显示 -->
          <div v-if="msg.charts && msg.charts.length" class="message-charts">
            <div v-for="(chart, ci) in msg.charts" :key="getChartKey(i, ci)" class="chart-card">
              <div class="card-header">
                <span class="card-title">{{ chart.title }}</span>
                <div class="card-actions">
                  <el-tooltip content="保存图片" placement="top">
                    <el-button text circle class="action-btn action-btn-primary" @click="exportChartPng(`chat_${ci}`, chart.title)">
                      <el-icon :size="16"><Picture /></el-icon>
                    </el-button>
                  </el-tooltip>
                  <el-tooltip content="查看数据" placement="top">
                    <el-button text circle class="action-btn action-btn-primary" @click="openDataDialog(chart)">
                      <el-icon :size="16"><View /></el-icon>
                    </el-button>
                  </el-tooltip>
                  <el-tooltip content="查看配置" placement="top">
                    <el-button text circle class="action-btn action-btn-primary" @click="openConfigDialog(chart)">
                      <el-icon :size="16"><Operation /></el-icon>
                    </el-button>
                  </el-tooltip>
                  <el-tooltip content="查看SQL" placement="top">
                    <el-button text circle class="action-btn action-btn-primary" @click="openSqlDialog(chart)">
                      <el-icon :size="16"><Orange /></el-icon>
                    </el-button>
                  </el-tooltip>
                  <el-tooltip content="全屏" placement="top">
                    <el-button text circle class="action-btn action-btn-primary" @click="toggleChartFullscreen(`chat_${ci}`)">
                      <el-icon :size="16"><FullScreen /></el-icon>
                    </el-button>
                  </el-tooltip>
                  <el-tooltip content="保存到看板" placement="top">
                    <el-button text circle class="action-btn action-btn-primary" @click="openSaveDialog(chart, ci)">
                      <el-icon :size="16"><PieChart /></el-icon>
                    </el-button>
                  </el-tooltip>
                </div>
              </div>
              <div class="card-chart">
                <div v-if="chart.error" class="chart-error">
                  <el-icon :size="24" color="#e6a23c"><WarningFilled /></el-icon>
                  <span>图表生成失败，请尝试重新描述分析需求</span>
                </div>
                <VegaLiteRenderer
                  v-else
                  :ref="(el) => setRendererRef(`chat_${ci}`, el)"
                  :data="chart.data"
                  :config="chart.pivot_config"
                  :chart-type="chart.chart_type"
                  :hide-toolbar="true"
                  :hide-title="true"
                />
              </div>
            </div>
            <div v-if="msg.charts.length > 1" class="batch-board-save-bar">
              <el-button type="primary" size="small" class="batch-board-save-btn" :loading="isBatchSaving(i)" @click="saveMessageChartsToBoard(i, msg.charts)">
                <el-icon><PieChart /></el-icon>
                <span>批量保存到看板</span>
              </el-button>
            </div>
          </div>
          <el-tag type="primary" v-for="sg in msg.suggestions" :key="sg" class="suggestion-tag" @click="onSuggest(sg)">
            {{ sg }}
          </el-tag>
        </div>
      </div>
      <div v-if="chatStore.loading" class="message assistant">
        <div class="message-content">
          <div class="typing-dots">
            <span>.</span><span>.</span><span>.</span>
          </div>
        </div>
      </div>
    </div>

    <div class="dialog-input">
      <el-input
        v-model="input"
        type="textarea"
        :rows="2"
        placeholder="输入分析需求，如：按车型统计各规则的触发次数"
        @keydown.enter.prevent="handleSend"
      />
      <el-button type="primary" :loading="chatStore.loading" @click="handleSend" class="send-btn">
        <el-icon><Promotion /></el-icon>
      </el-button>
    </div>

    <ChartDataDialog
      v-model:visible="showDataDialog"
      :data="selectedChart?.data"
      :title="selectedChart ? `${selectedChart.title || '图表'} - 数据` : '查看数据'"
    />
    <ChartSqlDialog
      v-model:visible="showConfigDialog"
      :content="configContent"
      title="查看配置"
      lang="json"
    />
    <ChartSqlDialog
      v-model:visible="showSqlDialog"
      :content="selectedChart?.sql"
      :title="selectedChart ? `${selectedChart.title || '图表'} - SQL` : '查看SQL'"
      lang="sql"
    />
    <SaveToBoardDialog
      v-model:visible="showSaveDialog"
      :chart="selectedSaveChart"
      :index="selectedSaveIndex"
      @save="handleSaveToBoard"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatLineSquare, FullScreen, Picture, PieChart, Promotion, View, WarningFilled, Operation, Orange } from '@element-plus/icons-vue'
import VegaLiteRenderer from './VegaLiteRenderer.vue'
import ChartDataDialog from './ChartDataDialog.vue'
import ChartSqlDialog from './ChartSqlDialog.vue'
import SaveToBoardDialog from './SaveToBoardDialog.vue'
import { useChatStore } from '@/stores/useChatStore'
import { MAX_BOARD_CHARTS, useChartStore, type SavedChart } from '@/stores/useChartStore'
import type { PivotConfig } from '@/types'

const chatStore = useChatStore()
const chartStore = useChartStore()

const emit = defineEmits<{
  save: [chart: Omit<SavedChart, 'id' | 'created_at' | 'updated_at'>]
  close: []
}>()

type ChartRendererHandle = {
  openDataDialog: () => void
  toggleFullscreen: () => void
  exportPng: (fileName?: string) => Promise<void>
  exportSvg: (fileName?: string) => Promise<void>
}

type ChatChart = {
  title?: string
  error?: string
  pivot_config?: PivotConfig | null
  chart_type?: string
  vega_spec?: Record<string, any> | null
  data?: Record<string, any>[] | null
  sql?: string | null
}

const input = ref('')
const messagesRef = ref<HTMLElement | null>(null)
const rendererRefs = ref<Record<string, ChartRendererHandle | null>>({})
const batchSaving = ref<Record<string, boolean>>({})

// 弹窗状态
const showSaveDialog = ref(false)
const showDataDialog = ref(false)
const showConfigDialog = ref(false)
const showSqlDialog = ref(false)
const selectedChart = ref<ChatChart | null>(null)
const selectedSaveChart = ref<ChatChart | null>(null)
const selectedSaveIndex = ref(0)

const configContent = computed(() => {
  if (!selectedChart.value?.pivot_config) return '-- 无配置'
  return JSON.stringify(selectedChart.value.pivot_config, null, 2)
})

const suggestions = [
  '各车辆触发次数占比',
  '按周统计报警趋势',
  '各任务下规则执行TOP10',
]

function handleSend() {
  const msg = input.value.trim()
  if (!msg || chatStore.loading) return
  input.value = ''
  chatStore.sendMessage(msg)
}

function getMessageKey(messageIndex: number) {
  return `message-${messageIndex}`
}

function getChartKey(messageIndex: number, chartIndex: number) {
  return `${getMessageKey(messageIndex)}-chart-${chartIndex}`
}

function isBatchSaving(messageIndex: number) {
  return !!batchSaving.value[getMessageKey(messageIndex)]
}

function setRendererRef(id: string, instance: any) {
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

function openDataDialog(chart: ChatChart) {
  selectedChart.value = chart
  showDataDialog.value = true
}

function openConfigDialog(chart: ChatChart) {
  selectedChart.value = chart
  showConfigDialog.value = true
}

function openSqlDialog(chart: ChatChart) {
  selectedChart.value = chart
  showSqlDialog.value = true
}

function openSaveDialog(chart: ChatChart, index: number) {
  selectedSaveChart.value = chart
  selectedSaveIndex.value = index
  showSaveDialog.value = true
}

function handleSaveToBoard(payload: {
  title: string
  description: string
  pivot_config: PivotConfig
  chart_type: string
  vega_spec: any
  data: any
}) {
  emit('save', payload)
  showSaveDialog.value = false
}

function exportChartPng(id: string, title: string) {
  void rendererRefs.value[id]?.exportPng(`${title || 'chart'}.png`)
}

function toggleChartFullscreen(id: string) {
  rendererRefs.value[id]?.toggleFullscreen()
}

async function saveMessageChartsToBoard(messageIndex: number, charts: ChatChart[]) {
  const messageKey = getMessageKey(messageIndex)
  if (batchSaving.value[messageKey]) return

  const savableCharts = charts.filter(chart => !chart?.error && chart?.pivot_config)

  if (!savableCharts.length) {
    ElMessage.warning('当前没有可保存到看板的图表')
    return
  }

  batchSaving.value[messageKey] = true

  try {
    await chartStore.fetchCharts()

    if (chartStore.error) {
      ElMessage.warning(chartStore.error || '加载看板失败')
      return
    }

    const remainingSlots = Math.max(MAX_BOARD_CHARTS - chartStore.charts.length, 0)
    if (savableCharts.length > remainingSlots) {
      ElMessage.warning(`看板剩余 ${remainingSlots} 个位置，无法批量保存 ${savableCharts.length} 个图表`)
      return
    }

    let savedCount = 0

    for (const [index, chart] of savableCharts.entries()) {
      const saved = await chartStore.saveChart(
        (chart.title || `图表 ${index + 1}`).trim() || `图表 ${index + 1}`,
        (chart.pivot_config || { filters: [], axes: [], legend: [], values: [] }) as PivotConfig,
        '',
        chart.chart_type || 'bar',
        chart.vega_spec || null,
        chart.data || null,
      )

      if (!saved) {
        const message = chartStore.error || '保存失败'
        if (savedCount > 0) {
          ElMessage.warning(`已保存 ${savedCount} 个图表，剩余保存失败：${message}`)
          return
        }

        ElMessage.warning(message)
        return
      }

      savedCount += 1
    }

    ElMessage.success(`已批量保存 ${savedCount} 个图表到看板`)
    emit('close')
  } finally {
    batchSaving.value[messageKey] = false
  }
}

function onSuggest(text: string) {
  if (chatStore.loading) return
  chatStore.sendMessage(text)
}

// 滚动到底部
watch(() => chatStore.messages.length, async () => {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
})
</script>

<style scoped>
.ai-dialog {
  display: flex;
  flex-direction: column;
  width: 100%;
 height: 80vh;
  min-width: 0;
  min-height: 0;
  background: white;
  overflow: hidden;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
}

.dialog-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.dialog-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #c0c4cc;
  text-align: center;
  gap: 12px;
}

.empty-state p {
  font-size: 14px;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  max-width: 300px;
}

.suggestion-tag {
  cursor: pointer;
}

.message {
  margin-bottom: 16px;
  display: flex;
  width: 100%;
}

.message.user {
  justify-content: flex-end;
}

.message.assistant {
  justify-content: flex-start;
}

.message-content {
  max-width: 100%;
  min-width: 0;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
}

.message.user .message-content {
  max-width: min(85%, 640px);
  background: #409eff;
  color: white;
  border-radius: 12px 4px 12px 12px;
}

.message.assistant .message-content {
  width: 100%;
  max-width: 100%;
  background: #f0f2f5;
  color: #303133;
  border-radius: 4px 12px 12px 12px;
}

.message-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.message-charts {
  width: 100%;
}

.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  padding: 8px 12px 0;
}

.chart-card {
  width: 100%;
  max-width: 100%;
  background: white;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  margin: 10px 0;
  box-sizing: border-box;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 12px;
  padding: 8px 12px;
}

.card-title {
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


.message-chart {
  margin-top: 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
}

.chart-actions {
  padding: 8px;
  text-align: right;
  border-top: 1px solid #ebeef5;
}

.typing-dots {
  display: flex;
  gap: 2px;
  padding: 4px 0;
}

.typing-dots span {
  animation: blink 1.4s infinite;
  font-size: 24px;
  line-height: 1;
}

.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes blink {
  0%, 80%, 100% { opacity: 0; }
  40% { opacity: 1; }
}

.dialog-input {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #ebeef5;
  align-items: flex-end;
  flex-shrink: 0;
}

.dialog-input .el-textarea {
  flex: 1;
}

.send-btn {
  height: 36px;
}

.card-chart {
  min-height: 0;
  width: 100%;
  overflow: hidden;
}

.chart-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px 16px;
  color: #909399;
  font-size: 13px;
  background: #fafafa;
  border-radius: 8px;
}

.batch-board-save-bar {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
  margin-bottom: 18px;
}

.batch-board-save-btn {
  gap: 6px;
  background: #2f6bcb;
  border-color: #2f6bcb;
  color: #ffffff;
  box-shadow: 0 6px 14px rgba(47, 107, 203, 0.18);
}

.batch-board-save-btn:hover,
.batch-board-save-btn:focus {
  background: #2559b3;
  border-color: #2559b3;
  color: #ffffff;
}

@media (max-width: 767px) {
  .dialog-messages {
    padding: 12px;
  }

  .message-content {
    max-width: 100%;
  }

  .message.user .message-content,
  .message.assistant .message-content {
    width: 100%;
    max-width: 100%;
  }

  .dialog-input {
    padding: 10px 12px;
  }
}
</style>
