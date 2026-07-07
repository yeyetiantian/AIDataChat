/** AI 对话状态管理 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  charts?: Record<string, any>[] | null
  suggestions?: string[]
}

function generateSessionId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const loading = ref(false)
  const sessionId = ref(generateSessionId())

  async function sendMessage(msg: string) {
    if (!msg.trim() || loading.value) return
    loading.value = true
    messages.value.push({ role: 'user', content: msg })
    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, session_id: sessionId.value }),
      })

      if (!resp.ok) {
        const err = await resp.json()
        throw new Error(err.detail || 'AI 分析失败')
      }

      const resp_data = await resp.json()
      // 更新 sessionId（首次请求后端返回的）
      if (resp_data.session_id) {
        sessionId.value = resp_data.session_id
      }
      messages.value.push({
        role: 'assistant',
        content: resp_data.reply || '已生成分析配置',
        charts: resp_data.charts || null,
        suggestions: resp_data.suggestions || [],
      })
    } catch (e: any) {
      messages.value.push({
        role: 'assistant',
        content: `错误: ${e.message || 'AI 分析失败'}`,
      })
    } finally {
      loading.value = false
    }
  }

  function clearMessages() {
    messages.value = []
    sessionId.value = generateSessionId()
  }

  return { messages, loading, sendMessage, clearMessages }
})
