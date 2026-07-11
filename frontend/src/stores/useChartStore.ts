import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { PivotConfig } from '@/types'
import { assignBoardSlot, clearBoardSlotMap, removeBoardSlot, syncBoardSlotMap } from '@/utils/boardSlots'

export const MAX_BOARD_CHARTS = 6

export interface SavedChart {
  id: number
  board_id?: number
  title: string
  description: string
  pivot_config: PivotConfig
  chart_type: string
  vega_spec?: Record<string, any> | null
  data?: Record<string, any>[] | null
  created_at: string
  updated_at: string
}

const API_BASE = '/api/charts'

function getUserId(): number {
  try { return Number(localStorage.getItem('ai_chat_user_id')) || 1 } catch { return 1 }
}

export const useChartStore = defineStore('charts', () => {
  const charts = ref<SavedChart[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchCharts(boardId: number) {
    loading.value = true
    error.value = null

    try {
      const resp = await fetch(`${API_BASE}?board_id=${boardId}`)
      if (!resp.ok) throw new Error('加载看板图表失败')

      charts.value = await resp.json()

      syncBoardSlotMap(charts.value, MAX_BOARD_CHARTS)
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function saveChart(
    title: string,
    pivotConfig: PivotConfig,
    description = '',
    chartType = 'bar',
    vegaSpec?: Record<string, any> | null,
    data?: Record<string, any>[] | null,
    boardId?: number,
    preferredSlot?: number,
  ) {
    loading.value = true
    error.value = null

    try {
      if (!boardId) throw new Error('请先选择一个看板')

      // 检查当前看板图表数量
      const listResp = await fetch(`${API_BASE}?board_id=${boardId}`)
      if (!listResp.ok) throw new Error('加载看板失败')
      const existingCharts: SavedChart[] = await listResp.json()

      if (existingCharts.length >= MAX_BOARD_CHARTS) {
        throw new Error(`每个看板最多只能保存 ${MAX_BOARD_CHARTS} 个图表`)
      }

      const resp = await fetch(API_BASE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          description,
          pivot_config: pivotConfig,
          chart_type: chartType,
          data,
          board_id: boardId,
          user_id: getUserId(),
        }),
      })
      if (!resp.ok) throw new Error('保存失败')

      const createdChart: SavedChart = await resp.json()
      if (typeof preferredSlot === 'number') {
        assignBoardSlot(createdChart.id, preferredSlot, [...existingCharts, createdChart], MAX_BOARD_CHARTS)
      }

      await fetchCharts(boardId)
      return charts.value.find(chart => chart.id === createdChart.id) || createdChart
    } catch (e: any) {
      error.value = e.message
      return null
    } finally {
      loading.value = false
    }
  }

  async function deleteChart(id: number) {
    error.value = null

    try {
      const resp = await fetch(`${API_BASE}/${id}`, { method: 'DELETE' })
      if (!resp.ok) throw new Error('删除失败')

      charts.value = charts.value.filter(chart => chart.id !== id)
      removeBoardSlot(id)

      if (charts.value.length === 0) {
        clearBoardSlotMap()
      } else {
        syncBoardSlotMap(charts.value, MAX_BOARD_CHARTS)
      }

      return true
    } catch (e: any) {
      error.value = e.message
      return false
    }
  }

  async function updateChart(id: number, data: Partial<SavedChart>, boardId?: number) {
    loading.value = true
    error.value = null

    try {
      const resp = await fetch(`${API_BASE}/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (!resp.ok) throw new Error('更新失败')

      if (boardId) await fetchCharts(boardId)
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  return { charts, loading, error, fetchCharts, saveChart, deleteChart, updateChart }
})
