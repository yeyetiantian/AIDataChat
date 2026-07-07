import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { PivotConfig } from '@/types'
import { assignBoardSlot, clearBoardSlotMap, removeBoardSlot, syncBoardSlotMap } from '@/utils/boardSlots'

export const MAX_BOARD_CHARTS = 6

export interface SavedChart {
  id: number
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

export const useChartStore = defineStore('charts', () => {
  const charts = ref<SavedChart[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchCharts() {
    loading.value = true
    error.value = null

    try {
      const resp = await fetch(API_BASE)
      if (!resp.ok) throw new Error('加载看板失败')

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
    preferredSlot?: number,
  ) {
    loading.value = true
    error.value = null

    try {
      const listResp = await fetch(API_BASE)
      if (!listResp.ok) throw new Error('加载看板失败')

      charts.value = await listResp.json()
      syncBoardSlotMap(charts.value, MAX_BOARD_CHARTS)

      if (charts.value.length >= MAX_BOARD_CHARTS) {
        throw new Error(`看板最多只能保存 ${MAX_BOARD_CHARTS} 个`)
      }

      const resp = await fetch(API_BASE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          description,
          pivot_config: pivotConfig,
          chart_type: chartType,
          vega_spec: vegaSpec,
          data,
        }),
      })
      if (!resp.ok) throw new Error('保存失败')

      const createdChart: SavedChart = await resp.json()
      if (typeof preferredSlot === 'number') {
        assignBoardSlot(createdChart.id, preferredSlot, [...charts.value, createdChart], MAX_BOARD_CHARTS)
      }

      await fetchCharts()
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

  async function updateChart(id: number, data: Partial<SavedChart>) {
    loading.value = true
    error.value = null

    try {
      const resp = await fetch(`${API_BASE}/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (!resp.ok) throw new Error('更新失败')

      await fetchCharts()
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  return { charts, loading, error, fetchCharts, saveChart, deleteChart, updateChart }
})
