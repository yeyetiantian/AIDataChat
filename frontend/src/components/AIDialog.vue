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
            <div v-for="(chart, ci) in msg.charts" :key="chart.id" class="chart-card">
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
                  <el-tooltip content="保存到看板" placement="top">
                    <el-button text circle class="action-btn action-btn-primary" @click="saveChartToBoard(chart, ci)">
                      <el-icon :size="16"><PieChart /></el-icon>
                    </el-button>
                  </el-tooltip>
                </div>
              </div>
              <div class="card-chart">
                <VegaLiteRenderer
                  :data="chart.data"
                  :config="chart.pivot_config"
                  :chart-type="chart.chart_type"
                  :hide-toolbar="true"
                  style="min-height: auto;"
                />
              </div>
            </div>
          </div>
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

    <!-- 保存确认弹窗 -->
    <el-dialog v-model="showSaveDialog" title="保存到看板" width="400px">
      <el-form label-position="top">
        <el-form-item label="图表名称">
          <el-input v-model="saveTitle" placeholder="输入图表名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="saveDesc" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSaveDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="confirmSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { ChatLineSquare, Promotion } from '@element-plus/icons-vue'
import { Edit, FullScreen, Picture, View, PieChart } from '@element-plus/icons-vue'
import VegaLiteRenderer from './VegaLiteRenderer.vue'
import { useChatStore } from '@/stores/useChatStore'
import { useChartStore, type SavedChart } from '@/stores/useChartStore'
import type { PivotConfig } from '@/types'

const chatStore = useChatStore()
const chartStore = useChartStore()

const emit = defineEmits<{
  save: [chart: Omit<SavedChart, 'id' | 'created_at' | 'updated_at'>]
}>()

type ChartRendererHandle = {
  openDataDialog: () => void
  toggleFullscreen: () => void
  exportPng: (fileName?: string) => Promise<void>
  exportSvg: (fileName?: string) => Promise<void>
}

const input = ref('')
const messagesRef = ref<HTMLElement | null>(null)
const showSaveDialog = ref(false)
const saveTitle = ref('')
const saveDesc = ref('')
const saving = ref(false)
const savingMessage = ref<any>(null)
  const rendererRefs = ref<Record<number, ChartRendererHandle | null>>({})

const suggestions = [
  '各车型触发次数分布',
  '按规则统计每日触发次数趋势',
  '各任务下规则执行TOP10',
]

function handleSend() {
  const msg = input.value.trim()
  if (!msg || chatStore.loading) return
  input.value = ''
  chatStore.sendMessage(msg)
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

function exportChartPng(id: number, title: string) {
  void rendererRefs.value[id]?.exportPng(`${title || 'chart'}.png`)
}

function toggleChartFullscreen(id: number) {
  rendererRefs.value[id]?.toggleFullscreen()
}

function onSuggest(text: string) {
  if (chatStore.loading) return
  chatStore.sendMessage(text)
}

function saveChartToBoard(chart: any, index: number) {
  savingMessage.value = chart
  saveTitle.value = chart.title || `图表 ${index + 1}`
  saveDesc.value = ''
  showSaveDialog.value = true
}

async function confirmSave() {
  if (!saveTitle.value.trim() || !savingMessage.value) return
  saving.value = true
  try {
    const chart = savingMessage.value
    emit('save', {
      title: saveTitle.value,
      description: saveDesc.value,
      pivot_config: (chart.pivot_config || { filters: [], axes: [], legend: [], values: [] }) as PivotConfig,
      chart_type: chart.chart_type || 'bar',
      data: chart.data || null,
    })
    showSaveDialog.value = false
    savingMessage.value = null
  } finally {
    saving.value = false
  }
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
  height: 80vh;
  background: white;
  border-radius: 8px;
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
}

.message.user {
  justify-content: flex-end;
}

.message.assistant {
  justify-content: flex-start;
}

.message-content {
  max-width: 85%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
}

.message.user .message-content {
  background: #409eff;
  color: white;
  border-radius: 12px 4px 12px 12px;
}

.message.assistant .message-content {
  background: #f0f2f5;
  color: #303133;
  border-radius: 4px 12px 12px 12px;
}

.message-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  padding: 8px 12px 0;
}

.chart-card {
  width: 500px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 12px;
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
}

.dialog-input .el-textarea {
  flex: 1;
}

.send-btn {
  height: 36px;
}
</style>
