<template>
  <div class="msg-query-result">
    <!-- 单表模式（兼容旧格式） -->
    <template v-if="isLegacy">
      <div class="qr-toolbar">
        <span class="qr-label">DTC 查询结果</span>
        <span class="qr-count">共 {{ legacyData.total }} 条</span>
        <div class="qr-actions">
          <button class="qr-action-btn" title="查看 SQL" @click="viewSql(legacyData.sql)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            SQL
          </button>
          <button class="qr-action-btn" title="下载 CSV" @click="downloadCsv(legacyData)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            下载 CSV
          </button>
        </div>
      </div>
      <div class="qr-table-wrap">
        <table class="qr-table">
          <thead><tr><th v-for="col in legacyData.columns" :key="col">{{ col }}</th></tr></thead>
          <tbody>
            <tr v-for="(row, ri) in pageRows(legacyData)" :key="ri">
              <td v-for="col in legacyData.columns" :key="col">{{ row[col] ?? '' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="legacyData.total > pageSize" class="qr-pagination">
        <button class="qr-page-btn" :disabled="legacyPage <= 1" @click="legacyPage--">‹</button>
        <span class="qr-page-info">{{ legacyPage }} / {{ legacyPages }}</span>
        <button class="qr-page-btn" :disabled="legacyPage >= legacyPages" @click="legacyPage++">›</button>
      </div>
    </template>

    <!-- 双表模式（info + trigger） -->
    <template v-else>
      <div class="qr-toolbar">
        <div class="qr-tabs">
          <button
            v-for="tab in tableTabs"
            :key="tab.label"
            class="qr-tab"
            :class="{ active: activeTab === tab.label }"
            @click="activeTab = tab.label"
          >
            {{ tab.label }}
            <span class="qr-tab-count">{{ tab.total }}</span>
          </button>
        </div>
        <div class="qr-actions">
          <button class="qr-action-btn" title="查看 SQL" @click="viewSql()">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            SQL
          </button>
          <button class="qr-action-btn" title="下载 CSV" @click="downloadCsv()">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            CSV
          </button>
          <button class="qr-action-btn" title="下载多 Sheet Excel" @click="downloadExcel">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Excel
          </button>
        </div>
      </div>
      <template v-for="tab in tableTabs" :key="tab.label">
        <div v-if="activeTab === tab.label">
          <div class="qr-table-wrap">
            <table class="qr-table">
              <thead><tr><th v-for="col in tab.columns" :key="col">{{ col }}</th></tr></thead>
              <tbody>
                <tr v-for="(row, ri) in pageRows(tab)" :key="ri">
                  <td v-for="col in tab.columns" :key="col">{{ row[col] ?? '' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="tab.total > pageSize" class="qr-pagination">
            <button class="qr-page-btn" :disabled="(tabPages[tab.label] || 1) <= 1" @click="tabPages[tab.label] = (tabPages[tab.label] || 1) - 1">‹</button>
            <span class="qr-page-info">{{ tabPages[tab.label] || 1 }} / {{ Math.max(1, Math.ceil(tab.total / pageSize)) }}</span>
            <button class="qr-page-btn" :disabled="(tabPages[tab.label] || 1) >= Math.max(1, Math.ceil(tab.total / pageSize))" @click="tabPages[tab.label] = (tabPages[tab.label] || 1) + 1">›</button>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive } from 'vue'

interface TableData {
  label: string
  sql: string
  columns: string[]
  rows: Record<string, any>[]
  total: number
}

const props = defineProps<{
  queryResult: any
}>()

const emit = defineEmits<{
  viewSql: [sql: string]
}>()

const pageSize = 10
const legacyPage = ref(1)

/** 判断是否为旧版单表格式（直接有 columns/rows） */
const isLegacy = computed(() => {
  return props.queryResult && 'columns' in props.queryResult && Array.isArray(props.queryResult.columns)
})

/** 兼容旧格式 */
const legacyData = computed((): TableData => {
  const qr = props.queryResult || {}
  return {
    label: 'dtc_info',
    sql: qr.sql || '',
    columns: qr.columns || [],
    rows: qr.rows || [],
    total: qr.total || 0,
  }
})

const legacyPages = computed(() => Math.max(1, Math.ceil(legacyData.value.total / pageSize)))

/** 双表 Tab 列表 */
const tableTabs = computed((): TableData[] => {
  const qr = props.queryResult || {}
  const tabs: TableData[] = []
  if (qr.info) {
    tabs.push({
      label: 'dtc_info',
      sql: qr.info.sql || '',
      columns: qr.info.columns || [],
      rows: qr.info.rows || [],
      total: qr.info.total || 0,
    })
  }
  if (qr.trigger) {
    tabs.push({
      label: 'dtc_trigger',
      sql: qr.trigger.sql || '',
      columns: qr.trigger.columns || [],
      rows: qr.trigger.rows || [],
      total: qr.trigger.total || 0,
    })
  }
  return tabs
})

/** 当前选中的 Tab（默认第一个） */
const activeTab = ref(
  !isLegacy.value && tableTabs.value.length > 0 ? tableTabs.value[0].label : ''
)

/** 每个 Tab 各自的页码 */
const tabPages = reactive<Record<string, number>>({})
if (!isLegacy.value) {
  tableTabs.value.forEach(t => { tabPages[t.label] = 1 })
}

function pageRows(tab: TableData) {
  const page = tabPages[tab.label] || 1
  const start = (page - 1) * pageSize
  return (tab.rows || []).slice(start, start + pageSize)
}

function viewSql(sql?: string) {
  let viewSql = sql
  if (!viewSql) {
    viewSql = tableTabs.value.find(x => x.label === activeTab.value)?.sql || ''
  }
  emit('viewSql', viewSql)
}

function downloadCsv(tab?: TableData) {
  let viewTab: TableData | undefined = tab
  if (!tab) {
    viewTab = tableTabs.value.find(x => x.label === activeTab.value)
  }
  if (!viewTab) return
  const { columns, rows } = viewTab
  if (!rows || rows.length === 0) return
  const bom = '﻿'
  const headers = columns.join(',')
  const csvRows = rows.map(row =>
    columns.map(col => {
      let val = String(row[col] ?? '')
      if (val.includes(',') || val.includes('"') || val.includes('\n')) {
        val = '"' + val.replace(/"/g, '""') + '"'
      }
      return val
    }).join(',')
  )
  const csv = bom + [headers, ...csvRows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `DTC_${viewTab.label}_${new Date().toISOString().slice(0, 10)}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

async function downloadExcel() {
  const qr = props.queryResult || {}
  const sheets: { name: string; columns: string[]; rows: Record<string, any>[] }[] = []
  if (qr.info) {
    sheets.push({ name: 'dtc_info', columns: qr.info.columns || [], rows: qr.info.rows || [] })
  }
  if (qr.trigger) {
    sheets.push({ name: 'dtc_trigger', columns: qr.trigger.columns || [], rows: qr.trigger.rows || [] })
  }
  if (sheets.length === 0) return

  try {
    const resp = await fetch('/api/dtc/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sheets }),
    })
    if (!resp.ok) throw new Error('导出失败')
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `DTC查询结果_${new Date().toISOString().slice(0, 10)}.xlsx`
    link.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    console.error('Excel 导出失败:', e)
    alert('Excel 导出失败，请检查服务端是否安装 openpyxl')
  }
}
</script>

<style scoped>
.msg-query-result {
  margin-top: 10px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  overflow: hidden;
}

/* Tabs */
.qr-tabs {
  display: flex;
  border-bottom: 1px solid #e5e7eb;
  background: #f3f4f6;
}
.qr-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 12px;
  border: none;
  background: transparent;
  color: #6b7280;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all .15s;
  border-bottom: 2px solid transparent;
}
.qr-tab:hover {
  color: #374151;
  background: #e5e7eb;
}
.qr-tab.active {
  color: #2563eb;
  background: #fff;
  border-bottom-color: #2563eb;
  font-weight: 600;
}
.qr-tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: #dbeafe;
  color: #2563eb;
  font-size: 10px;
  font-weight: 600;
}
.qr-tab.active .qr-tab-count {
  background: #2563eb;
  color: #fff;
}

.qr-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
}
.qr-label {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}
.qr-count {
  font-size: 12px;
  color: #6b7280;
}
.qr-actions {
  margin-left: auto;
  display: flex;
  gap: 6px;
}
.qr-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  color: #374151;
  font-size: 12px;
  cursor: pointer;
  transition: all .15s;
}
.qr-action-btn:hover {
  background: #3b82f6;
  color: #fff;
  border-color: #3b82f6;
}
.qr-table-wrap {
  overflow-x: auto;
  max-height: 360px;
  overflow-y: auto;
}
.qr-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  white-space: nowrap;
}
.qr-table th {
  padding: 6px 10px;
  background: #f3f4f6;
  color: #374151;
  font-weight: 600;
  text-align: left;
  border-bottom: 1px solid #e5e7eb;
  position: sticky;
  top: 0;
  z-index: 1;
}
.qr-table td {
  padding: 5px 10px;
  border-bottom: 1px solid #f3f4f6;
  color: #1f2937;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.qr-table tbody tr:hover {
  background: #f9fafb;
}
.qr-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid #f3f4f6;
  background: #fafafa;
}
.qr-page-btn {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  background: #fff;
  color: #374151;
  font-size: 14px;
  cursor: pointer;
  transition: all .15s;
}
.qr-page-btn:hover:not(:disabled) {
  background: #3b82f6;
  color: #fff;
  border-color: #3b82f6;
}
.qr-page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.qr-page-info {
  font-size: 12px;
  color: #6b7280;
  min-width: 60px;
  text-align: center;
}
</style>
