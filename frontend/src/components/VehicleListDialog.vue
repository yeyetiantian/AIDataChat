<template>
  <el-dialog
    v-model="visible"
    width="720px"
    top="8vh"
    destroy-on-close
    class="vehicle-list-dialog"
    @open="onOpen"
  >
    <template #header>
      <span class="dialog-title">车辆列表</span>
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
      class="vehicle-table"
      :data="filteredData"
      :row-key="getRowId"
      border
      stripe
      size="small"
      height="360"
      @select="handleSelect"
      @select-all="handleSelectAll"
    >
      <el-table-column type="selection" width="48" align="center" reserve-selection />
      <el-table-column prop="vinPatacId" label="泛亚编号" min-width="120" show-overflow-tooltip />
      <el-table-column prop="name" label="VIN" min-width="180" show-overflow-tooltip />
      <el-table-column prop="rmuCode" label="RMU模块号" min-width="120" show-overflow-tooltip />
    </el-table>

    <template #footer>
      <el-button size="small" @click="visible = false">取消</el-button>
      <el-button type="primary" size="small" @click="handleConfirm">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'
import type { TableInstance } from 'element-plus'
import {
  getFilterDropdownItemValue,
  type FilterSelectDropdownItem,
} from '@/api/filterSelect'

const props = defineProps<{
  data: FilterSelectDropdownItem[]
  selectedValues: string[]
}>()

const emit = defineEmits<{
  confirm: [values: string[]]
}>()

const visible = defineModel<boolean>({ default: false })

const tableRef = ref<TableInstance>()
const keyword = ref('')
const filteredData = ref<FilterSelectDropdownItem[]>([])
const selectedIdSet = ref(new Set<string>())

function getRowId(row: FilterSelectDropdownItem): string {
  return getFilterDropdownItemValue(row)
}

function onOpen() {
  keyword.value = ''
  filteredData.value = [...props.data]
  selectedIdSet.value = new Set(props.selectedValues.filter(v => v !== '' && v != null).map(String))
  nextTick(syncTableSelection)
}

function applyFilter() {
  const q = keyword.value.trim().toLowerCase()
  if (!q) {
    filteredData.value = [...props.data]
  } else {
    filteredData.value = props.data.filter(row => {
      const fields = [row.vinPatacId, row.name, row.rmuCode]
        .filter(v => v != null && v !== '')
        .map(v => String(v).toLowerCase())
      return fields.some(f => f.includes(q))
    })
  }
  nextTick(syncTableSelection)
}

function syncTableSelection() {
  if (!tableRef.value) return
  tableRef.value.clearSelection()
  filteredData.value.forEach(row => {
    if (selectedIdSet.value.has(getRowId(row))) {
      tableRef.value?.toggleRowSelection(row, true)
    }
  })
}

function handleSelect(selection: FilterSelectDropdownItem[], row: FilterSelectDropdownItem) {
  const id = getRowId(row)
  if (!id) return
  const isSelected = selection.some(r => getRowId(r) === id)
  if (isSelected) selectedIdSet.value.add(id)
  else selectedIdSet.value.delete(id)
}

function handleSelectAll(selection: FilterSelectDropdownItem[]) {
  if (selection.length === 0) {
    filteredData.value.forEach(row => selectedIdSet.value.delete(getRowId(row)))
    return
  }
  selection.forEach(row => selectedIdSet.value.add(getRowId(row)))
}

function handleConfirm() {
  emit('confirm', Array.from(selectedIdSet.value).filter(id => id !== ''))
  visible.value = false
}
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
.vehicle-list-dialog .el-dialog__body {
  padding-top: 8px;
}

.vehicle-list-dialog .vehicle-table th.el-table__cell {
  background-color: #f5f7fa !important;
}
</style>
