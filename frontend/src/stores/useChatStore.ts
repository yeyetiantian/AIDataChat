/** AI 对话状态管理 — 后端持久化 + 用户体系 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'


export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  charts?: Record<string, any>[] | null
  suggestions?: string[]
  ask_questions?: any[]
  pending_step?: string | null
}

export interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  mode: 'chart' | 'rule'
  createdAt: string
  updatedAt: string
}


// ====== 本地存储辅助 ======


function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

function formatTitle(content: string): string {
  return content.length > 30 ? content.slice(0, 30) + '...' : content
}

// ====== Store ======

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<ChatSession[]>([])
  const activeSessionId = ref<string>('')
  const loading = ref(false)
  const mode = ref<'chart' | 'rule'>('chart')
  const userConfig = ref('{\n  "name": "用户",\n  "preferences": {}\n}')
  const user = ref<{id:number;username:string;role:string} | null>(null)
  const userList = ref<{id:number;username:string;role:string}[]>([])
  let _initialized = false

  const activeSession = computed(() => sessions.value.find(s => s.id === activeSessionId.value) || null)
  const messages = computed<ChatMessage[]>({
    get: () => activeSession.value?.messages || [],
    set: (val) => {
      const s = sessions.value.find(s => s.id === activeSessionId.value)
      if (s) { s.messages = val }
    },
  })

  // ====== 初始化 ======

  async function init() {
    if (_initialized) return
    _initialized = true
    // 自动选择用户：优先使用缓存，不存在则用第一个
    const uid = localStorage.getItem('ai_chat_user_id')
    try {
      const resp = await fetch('/api/auth/users')
      if (resp.ok) {
        const list = await resp.json()
        userList.value = list
        const cached = uid ? list.find((x: any) => x.id === Number(uid)) : null
        const target = cached || list[0]
        if (target) {
          user.value = target
          localStorage.setItem('ai_chat_user_id', String(target.id))
        }
      }
    } catch { /* ignore */ }
    await fetchSessions()
    if (sessions.value.length === 0) {
      await createSession()
    } else if (!activeSessionId.value) {
      switchSession(sessions.value[0].id)
    }
  }

  // ====== API 调用 ======

  async function fetchSessions() {
    try {
      const resp = await fetch(`/api/chat/sessions?user_id=${user.value?.id || 1}`)
      if (resp.ok) {
        const data = await resp.json()
        sessions.value = data.map((s: any) => ({
          id: s.id,
          title: s.title,
          messages: [],
          mode: s.mode || 'chart',
          createdAt: s.created_at || '',
          updatedAt: s.updated_at || '',
        }))
      }
    } catch { /* ignore */ }
  }

  async function createSession(title = '新对话') {
    // 当前已有空会话，直接复用不复用不创建
    const newSession = sessions.value.find(s => s.messages.length === 0)
    if (newSession) {
      activeSessionId.value = newSession.id
      return
    }
    if (activeSession.value && activeSession.value.messages.length === 0) {
      return
    }
    try {
      const resp = await fetch('/api/chat/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: user.value?.id || 1, title, mode: mode.value }),
      })
      if (resp.ok) {
        const s = await resp.json()
        const newSession: ChatSession = {
          id: s.id,
          title: s.title,
          messages: [],
          mode: s.mode || 'chart',
          createdAt: s.created_at || '',
          updatedAt: s.updated_at || '',
        }
        sessions.value.unshift(newSession)
        activeSessionId.value = s.id
      }
    } catch { /* ignore */ }
  }

  async function fetchMessages(sessionId: string) {
    try {
      const resp = await fetch(`/api/chat/sessions/${sessionId}/messages`)
      if (resp.ok) {
        const data = await resp.json()
        const session = sessions.value.find(s => s.id === sessionId)
        if (session) {
          session.messages = data.map((m: any) => ({
            role: m.role,
            content: m.content,
            charts: m.charts || null,
            suggestions: m.suggestions || [],
          }))
        }
      }
    } catch { /* ignore */ }
  }

  async function deleteSessionFromBackend(sessionId: string) {
    try {
      await fetch(`/api/chat/sessions/${sessionId}`, { method: 'DELETE' })
    } catch { /* ignore */ }
  }

  // ====== 操作 ======

  function setMode(m: 'chart' | 'rule') {
    mode.value = m
  }

  async function newSession() {
    await createSession()
  }

  async function switchSession(id: string) {
    activeSessionId.value = id
    const session = sessions.value.find(s => s.id === id)
    if (session && session.messages.length === 0) {
      await fetchMessages(id)
    }
  }

  async function deleteSession(id: string) {
    await deleteSessionFromBackend(id)
    sessions.value = sessions.value.filter(s => s.id !== id)
    if (activeSessionId.value === id) {
      if (sessions.value.length > 0) {
        await switchSession(sessions.value[0].id)
      } else {
        await createSession()
      }
    }
  }

  async function sendMessage(msg: string) {
    if (!msg.trim() || loading.value) return
    loading.value = true

    // 当前没有活跃会话才创建新会话
    if (!activeSession.value) {
      await createSession()
    }

    const session = activeSession.value!
    session.messages.push({ role: 'user', content: msg })
    if (session.messages.filter(m => m.role === 'user').length === 1) {
      session.title = formatTitle(msg)
    }

    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: msg,
          session_id: session.id,
          user_id: user.value?.id,
        }),
      })
      if (!resp.ok) throw new Error('AI 分析失败')
      const data = await resp.json()
      let reply = data.reply || '已生成分析配置'
      const charts = data.charts || []

      session.messages.push({
        role: 'assistant',
        content: reply,
        charts: charts || null,
        suggestions: data.suggestions || [],
        ask_questions: data.ask_questions || [],
        pending_step: data.pending_step || null,
      })
    } catch (e: any) {
      session.messages.push({
        role: 'assistant',
        content: `错误: ${e.message || 'AI 分析失败'}`,
        ask_questions: [],
        pending_step: null,
      })
    } finally {
      loading.value = false
    }
  }

  function updateUserConfig(config: string) {
    userConfig.value = config
    try { localStorage.setItem('ai_chat_user_config', config) } catch {}
  }

  async function clearAllSessions() {
    for (const s of sessions.value) {
      await deleteSessionFromBackend(s.id)
    }
    sessions.value = []
    await createSession()
  }

  async function login(username: string, uid: number) {
    user.value = { id: uid, username, role: 'user' }
    try {
      localStorage.setItem('ai_chat_user_id', String(uid))
    } catch {}
    await fetchSessions()
    if (sessions.value.length === 0) {
      await createSession()
    } else {
      await switchSession(sessions.value[0].id)
    }
  }

  // 同步恢复本地缓存用户（不自动 init）

  return {
    sessions, activeSessionId, loading, mode, userConfig, user, userList,
    activeSession, messages,
    sendMessage, newSession, switchSession, deleteSession, setMode,
    updateUserConfig, clearAllSessions, init, fetchSessions, login,
  }
})
