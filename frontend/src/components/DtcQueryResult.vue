<template>
  <div class="msg-query-result">
    <div class="qr-toolbar">
      <span class="qr-label">DTC 查询结果</span>
      <span class="qr-count">共 {{ queryResult.total }} 条</span>
      <div class="qr-actions">
        <button class="qr-action-btn" title="查看 SQL" @click="viewSql">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
          SQL
        </button>
        <button class="qr-action-btn" title="下载 CSV" @click="downloadCsv">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          下载 CSV
        </button>
      </div>
    </div>
    <div class="qr-table-wrap">
      <table class="qr-table">
        <thead>
          <tr>
            <th v-for="col in queryResult.columns" :key="col">{{ col }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, ri) in pageRows" :key="ri">
            <td v-for="col in queryResult.columns" :key="col">{{ row[col] ?? '' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="queryResult.total > pageSize" class="qr-pagination">
      <button class="qr-page-btn" :disabled="page <= 1" @click="page--">‹</button>
      <span class="qr-page-info">{{ page }} / {{ totalPages }}</span>
      <button class="qr-page-btn" :disabled="page >= totalPages" @click="page++">›</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{
  queryResult: {
    sql: string
    explanation?: string
    columns: string[]
    rows: Record<string, any>[]
    total: number
  }
}>()

const emit = defineEmits<{
  viewSql: [sql: string]
}>()

const pageSize = 10
const page = ref(1)

const totalPages = computed(() => Math.max(1, Math.ceil(props.queryResult.total / pageSize)))

const pageRows = computed(() => {
  const start = (page.value - 1) * pageSize
  return props.queryResult.rows.slice(start, start + pageSize)
})

function viewSql() {
  emit('viewSql', props.queryResult.sql)
}

function downloadCsv() {
  const { columns, rows } = props.queryResult
  if (!rows || rows.length === 0) return
  const bom = '\uFEFF'
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
  link.download = `DTC查询结果_${new Date().toISOString().slice(0, 10)}.csv`
  link.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.msg-query-result {
  margin-top: 10px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  overflow: hidden;
}

.qr-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
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