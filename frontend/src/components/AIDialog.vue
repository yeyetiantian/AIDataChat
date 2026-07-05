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
          <div v-if="msg.data && msg.data.length" class="message-chart">
            <VegaLiteRenderer :data="msg.data" :config="msg.pivot_config" :chart-type="msg.chart_type || 'bar'" />
            <div class="chart-actions">
              <el-button size="small" type="primary" @click="saveToBoard(msg)">保存到看板</el-button>
            </div>
          </div>

          <!-- 建议标签 -->
          <div v-if="msg.suggestions && msg.suggestions.length" class="message-suggestions">
            <el-tag
              v-for="s in msg.suggestions" :key="s"
              size="small"
              class="suggest-tag"
              @click="onSuggest(s)"
            >
              {{ s }}
            </el-tag>
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
import VegaLiteRenderer from './VegaLiteRenderer.vue'
import { useChatStore, type ChatMessage } from '@/stores/useChatStore'
import { useChartStore, type SavedChart } from '@/stores/useChartStore'
import type { PivotConfig } from '@/types'

const chatStore = useChatStore()
const chartStore = useChartStore()

const emit = defineEmits<{
  save: [chart: Omit<SavedChart, 'id' | 'created_at' | 'updated_at'>]
}>()

const input = ref('')
const messagesRef = ref<HTMLElement | null>(null)
const showSaveDialog = ref(false)
const saveTitle = ref('')
const saveDesc = ref('')
const saving = ref(false)
const savingMessage = ref<ChatMessage | null>(null)

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

function onSuggest(text: string) {
  if (chatStore.loading) return
  chatStore.sendMessage(text)
}

function saveToBoard(msg: ChatMessage) {
  savingMessage.value = msg
  saveTitle.value = (msg.content || '').substring(0, 30) + '...'
  saveDesc.value = ''
  showSaveDialog.value = true
}

async function confirmSave() {
  if (!saveTitle.value.trim() || !savingMessage.value) return
  saving.value = true
  try {
    const msg = savingMessage.value
    emit('save', {
      title: saveTitle.value,
      description: saveDesc.value,
      pivot_config: (msg.pivot_config || { filters: [], axes: [], legend: [], values: [] }) as PivotConfig,
      chart_type: msg.chart_type || 'bar',
      data: msg.data || null,
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
  background: #ffffff;
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
  max-height: 74vh;
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
  border-color: #f5d0d0 !important;
  color: #d93a3a !important;
  background: #fff5f5 !important;
}
.suggestion-tag:hover {
  background: #d93a3a !important;
  color: #fff !important;
  border-color: #d93a3a !important;
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
  max-width: 90%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
}

.message.user .message-content {
  background: #d93a3a;
  color: #fff;
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

.message-chart {
  width: 420px;
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

.message-suggestions {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.suggest-tag {
  cursor: pointer;
  border-color: #f5d0d0 !important;
  color: #d93a3a !important;
  background: #fff5f5 !important;
  font-size: 12px;
  border-radius: 12px;
  transition: all 0.2s;
}
.suggest-tag:hover {
  background: #d93a3a !important;
  color: #fff !important;
  border-color: #d93a3a !important;
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
