/** AI 对话状态管理 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  data?: Record<string, any>[] | null
  chart_type?: string
  pivot_config?: Record<string, any> | null
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const loading = ref(false)

  async function sendMessage(msg: string) {
    if (!msg.trim() || loading.value) return
    loading.value = true
    messages.value.push({ role: 'user', content: msg })
    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg }),
      })

      if (!resp.ok) {
        const err = await resp.json()
        throw new Error(err.detail || 'AI 分析失败')
      }

      const resp_data = await resp.json()
      messages.value.push({
        role: 'assistant',
        content: data.reply || '已生成分析配置',
        data: data.data || null,
        chart_type: data.chart_type || 'bar',
        pivot_config: data.pivot_config || null,
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
  }

  return { messages, loading, sendMessage, clearMessages }
})
