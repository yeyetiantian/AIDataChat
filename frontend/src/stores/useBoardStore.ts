/** 看板管理 Store — 多看板、多用户体系 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useChartStore } from './useChartStore'

export interface Board {
  id: number
  user_id: number
  name: string
  description: string
  created_at: string
  updated_at: string
}

const API_BASE = '/api/boards'

function getUserId(): number {
  try { return Number(localStorage.getItem('ai_chat_user_id')) || 1 } catch { return 1 }
}

export const useBoardStore = defineStore('boards', () => {
  const boards = ref<Board[]>([])
  const activeBoardId = ref<number | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const activeBoard = computed(() =>
    boards.value.find(b => b.id === activeBoardId.value) || null
  )

  async function fetchBoards() {
    loading.value = true
    error.value = null
    try {
      const resp = await fetch(API_BASE + '?user_id=' + getUserId())
      if (!resp.ok) throw new Error('加载看板列表失败')
      boards.value = await resp.json()

      // 自动选择第一个
      if (boards.value.length > 0 && !activeBoardId.value) {
        activeBoardId.value = boards.value[0].id
      } else if (boards.value.length > 0 && !boards.value.find(b => b.id === activeBoardId.value)) {
        activeBoardId.value = boards.value[0].id
      }
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function switchBoard(boardId: number) {
    if (activeBoardId.value === boardId) return
    activeBoardId.value = boardId
    // 切换看板时自动刷新图表
    const chartStore = useChartStore()
    await chartStore.fetchCharts(boardId)
  }

  async function createBoard(name: string, description = '') {
    loading.value = true
    error.value = null
    try {
      const resp = await fetch(API_BASE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, user_id: getUserId() }),
      })
      if (!resp.ok) throw new Error('创建看板失败')
      const newBoard: Board = await resp.json()
      boards.value.push(newBoard)
      await switchBoard(newBoard.id)
      return newBoard
    } catch (e: any) {
      error.value = e.message
      return null
    } finally {
      loading.value = false
    }
  }

  async function updateBoard(boardId: number, data: { name?: string; description?: string }) {
    error.value = null
    try {
      const resp = await fetch(`${API_BASE}/${boardId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (!resp.ok) throw new Error('更新看板失败')
      const updated: Board = await resp.json()
      const idx = boards.value.findIndex(b => b.id === boardId)
      if (idx >= 0) boards.value[idx] = updated
      return updated
    } catch (e: any) {
      error.value = e.message
      return null
    }
  }

  async function deleteBoard(boardId: number) {
    error.value = null
    try {
      const resp = await fetch(`${API_BASE}/${boardId}`, { method: 'DELETE' })
      if (!resp.ok) throw new Error('删除看板失败')
      boards.value = boards.value.filter(b => b.id !== boardId)

      // 如果删除的是当前看板，切换到第一个
      if (activeBoardId.value === boardId) {
        if (boards.value.length > 0) {
          await switchBoard(boards.value[0].id)
        } else {
          // 没有看板了，创建一个默认的
          await createBoard('默认看板')
        }
      }
      return true
    } catch (e: any) {
      error.value = e.message
      return false
    }
  }

  return {
    boards, activeBoardId, activeBoard, loading, error,
    fetchBoards, switchBoard, createBoard, updateBoard, deleteBoard,
  }
})
