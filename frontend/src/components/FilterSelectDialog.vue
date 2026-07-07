<template>
  <el-dialog
    v-model="visible"
    width="720px"
    top="8vh"
    destroy-on-close
    class="filter-select-dialog"
    @open="onOpen"
  >
    <template #header>
      <span class="dialog-title">{{ dialogTitle }}</span>
    </template>

    <div class="search-bar">
      <el-input
        v-model="keyword"
        placeholder="请输入名称"
        size="small"
        clearable
        class="search-input"
        @keyup.enter="applyFilter"
        @clear="applyFilter"
      />
      <el-button type="primary" size="small" @click="applyFilter">搜索</el-button>
    </div>

    <el-table
      ref="tableRef"
      class="filter-select-table"
      :data="filteredData"
      :row-key="getRowValue"
      border
      stripe
      size="small"
      height="360"
      @select="handleSelect"
      @select-all="handleSelectAll"
    >
      <el-table-column type="selection" width="48" align="center" reserve-selection />
      <el-table-column
        v-for="col in tableColumns"
        :key="col.field"
        :prop="col.field"
        :label="col.label"
        min-width="120"
        show-overflow-tooltip
      />
    </el-table>

    <template #footer>
      <el-button size="small" @click="handleCancel">取消</el-button>
      <el-button type="primary" size="small" @click="handleConfirm">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'
import type { TableInstance } from 'element-plus'

import type { FilterSelectDialogColumn } from '@/constants/filterSelectDialog'

export interface FilterSelectDialogOpenOptions {
  title?: string
  data: Record<string, unknown>[]
  columns?: FilterSelectDialogColumn[]
  valueKey?: string
  labelKey?: string
  selectedValues?: string[]
}

const visible = ref(false)
const dialogTitle = ref('列表')
const tableData = ref<Record<string, unknown>[]>([])
const tableColumns = ref<FilterSelectDialogColumn[]>([])
const valueKey = ref('value')
const labelKey = ref('label')
const initialSelected = ref<string[]>([])

const tableRef = ref<TableInstance>()
const keyword = ref('')
const filteredData = ref<Record<string, unknown>[]>([])
const selectedIdSet = ref(new Set<string>())

let resolveConfirm: ((values: string[]) => void) | null = null
let rejectConfirm: (() => void) | null = null

function getRowValue(row: Record<string, unknown>): string {
  return String(row[valueKey.value] ?? '')
}

function getSearchFields(row: Record<string, unknown>): string[] {
  return tableColumns.value
    .map(col => row[col.field])
    .filter(v => v != null && v !== '')
    .map(v => String(v).toLowerCase())
}

function onOpen() {
  keyword.value = ''
  filteredData.value = [...tableData.value]
  selectedIdSet.value = new Set(initialSelected.value.filter(v => v !== '' && v != null).map(String))
  nextTick(syncTableSelection)
}

function applyFilter() {
  const q = keyword.value.trim().toLowerCase()
  if (!q) {
    filteredData.value = [...tableData.value]
  } else {
    filteredData.value = tableData.value.filter(row =>
      getSearchFields(row).some(f => f.includes(q)),
    )
  }
  nextTick(syncTableSelection)
}

function syncTableSelection() {
  if (!tableRef.value) return
  tableRef.value.clearSelection()
  filteredData.value.forEach(row => {
    if (selectedIdSet.value.has(getRowValue(row))) {
      tableRef.value?.toggleRowSelection(row, true)
    }
  })
}

function handleSelect(selection: Record<string, unknown>[], row: Record<string, unknown>) {
  const id = getRowValue(row)
  if (!id) return
  const isSelected = selection.some(r => getRowValue(r) === id)
  if (isSelected) selectedIdSet.value.add(id)
  else selectedIdSet.value.delete(id)
}

function handleSelectAll(selection: Record<string, unknown>[]) {
  if (selection.length === 0) {
    filteredData.value.forEach(row => selectedIdSet.value.delete(getRowValue(row)))
    return
  }
  selection.forEach(row => {
    const id = getRowValue(row)
    if (id) selectedIdSet.value.add(id)
  })
}

function handleConfirm() {
  const values = Array.from(selectedIdSet.value).filter(id => id !== '')
  resolveConfirm?.(values)
  resolveConfirm = null
  rejectConfirm = null
  visible.value = false
}

function handleCancel() {
  rejectConfirm?.()
  resolveConfirm = null
  rejectConfirm = null
  visible.value = false
}

function open(options: FilterSelectDialogOpenOptions): Promise<string[]> {
  dialogTitle.value = options.title ?? '列表'
  tableData.value = options.data
  valueKey.value = options.valueKey ?? 'value'
  labelKey.value = options.labelKey ?? 'label'
  tableColumns.value = options.columns ?? [{ field: labelKey.value, label: dialogTitle.value }]
  initialSelected.value = options.selectedValues ?? []
  visible.value = true

  return new Promise((resolve, reject) => {
    resolveConfirm = resolve
    rejectConfirm = reject
  })
}

defineExpose({ open })
</script>

<style scoped>
.dialog-title {
  font-size: 15px;
  font-weight: 600;
}

.search-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.search-input {
  flex: 1;
}
</style>

<style>
.filter-select-dialog .el-dialog__body {
  padding-top: 8px;
}

.filter-select-dialog .filter-select-table th.el-table__cell {
  background-color: #f5f7fa !important;
}
</style>
