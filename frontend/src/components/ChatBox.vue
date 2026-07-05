<template>
  <div class="chat-box">
    <div class="chat-header">
      <h3>AI 对话分析</h3>
      <el-button size="small" text @click="clearChat">清空对话</el-button>
    </div>

    <div class="chat-messages" ref="messagesRef">
      <div v-if="messages.length === 0" class="chat-empty">
        <el-icon :size="36" color="#c0c4cc"><ChatLineSquare /></el-icon>
        <p>输入分析需求，AI 将自动生成图表</p>
        <div class="suggestions">
          <el-tag
            v-for="s in suggestions" :key="s"
            size="small"
            class="suggestion-tag"
            @click="sendMessage(s)"
          >
            {{ s }}
          </el-tag>
        </div>
      </div>

      <div v-for="(msg, i) in messages" :key="i" class="message" :class="msg.role">
        <div class="message-content">
          <div class="message-text">{{ msg.content }}</div>
          <div v-if="msg.vega_spec" class="message-chart">
            <VegaLiteRenderer :spec="msg.vega_spec" />
          </div>
        </div>
      </div>

      <div v-if="loading" class="message assistant">
        <div class="message-content">
          <div class="typing-dots">
            <span>.</span><span>.</span><span>.</span>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-input">
      <el-input
        v-model="input"
        type="textarea"
        :rows="2"
        placeholder="输入分析需求，如：按车型统计各规则的触发次数"
        @keydown.enter.prevent="handleSend"
      />
      <el-button type="primary" :loading="loading" @click="handleSend" class="send-btn">
        <el-icon><Promotion /></el-icon>
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { ChatLineSquare, Promotion } from '@element-plus/icons-vue'
import type { ChatMessage } from '@/types'
import VegaLiteRenderer from './VegaLiteRenderer.vue'

const props = defineProps<{
  messages: ChatMessage[]
  loading: boolean
}>()

const emit = defineEmits<{
  send: [message: string]
  clear: []
}>()

const input = ref('')
const messagesRef = ref<HTMLElement | null>(null)

const suggestions = [
  '各车型触发次数分布',
  '按规则统计每日触发次数趋势',
  '各任务下规则执行TOP10',
]

function handleSend() {
  const msg = input.value.trim()
  if (!msg || props.loading) return
  emit('send', msg)
  input.value = ''
}

function sendMessage(msg: string) {
  if (props.loading) return
  emit('send', msg)
}

function clearChat() {
  emit('clear')
}

watch(() => props.messages.length, async () => {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
})
</script>

<style scoped>
.chat-box {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: white;
  border-radius: 8px;
  overflow: hidden;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
}

.chat-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #c0c4cc;
  text-align: center;
  gap: 12px;
}

.chat-empty p {
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

.message-chart {
  margin-top: 8px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
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

.chat-input {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #ebeef5;
  align-items: flex-end;
}

.chat-input .el-textarea {
  flex: 1;
}

.send-btn {
  height: 36px;
}
</style>
