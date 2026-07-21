<template>
  <ModelDialog ref="modelRef" title="查看数据" width="70%" top="5vh">
    <div class="data-toolbar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索数据..."
        clearable
        size="small"
        style="width: 240px"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <span class="data-count">共 {{ filteredData.length }} 条</span>
      <el-button v-if="data && data.length" size="small" @click="handleExport">
        <el-icon><Download /></el-icon> 导出 CSV
      </el-button>
    </div>
    <div class="data-table-wrap">
      <el-table
        :data="filteredData"
        border
        stripe
        max-height="65vh"
        size="small"
        style="width: 100%"
      >
        <el-table-column
          v-for="col in columns"
          :key="col"
          :prop="col"
          :label="col"
          min-width="140"
          show-overflow-tooltip
        />
      </el-table>
      <div v-if="!columns.length && data?.length === 0" class="data-empty">
        <el-icon :size="32" color="#c0c4cc"><FolderOpened /></el-icon>
        <p>暂无数据</p>
      </div>
    </div>
  </ModelDialog>
</template>

<script setup lang="ts">
import ModelDialog from './ModelDialog.vue'
import { computed, ref } from 'vue'
import { Search, FolderOpened, Download } from '@element-plus/icons-vue'

const modelRef = ref<InstanceType<typeof ModelDialog> | null>(null)
const data = ref<any[]>([])

const searchQuery = ref('')

const columns = computed(() => {
  if (!data.value || data.value.length === 0) return []
  return Object.keys(data.value[0])
})

const filteredData = computed(() => {
  if (!data.value || data.value.length === 0) return []
  if (!searchQuery.value.trim()) return data.value    
  const q = searchQuery.value.trim().toLowerCase()
  return data.value.filter(row =>
    Object.values(row).some(val =>
      String(val ?? '').toLowerCase().includes(q)
    )
  )
})

const open = (ch: any[]) => {
  data.value = ch
  modelRef.value?.open()
}

defineExpose({
  open
})

function handleExport() {
  if (!data.value || data.value.length === 0) return
  // UTF-8 BOM for Excel 中文兼容
  const bom = '﻿'
  // 表头
  const headers = columns.value.join(',')
  // 行数据，处理含逗号/引号/换行的值
  const rows = filteredData.value.map(row =>
    columns.value.map(col => {
      let val = String(row[col] ?? '')
      if (val.includes(',') || val.includes('"') || val.includes('\n')) {
        val = '"' + val.replace(/"/g, '""') + '"'
      }
      return val
    }).join(',')
  )
  const csv = bom + [headers, ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `数据导出_${new Date().toISOString().slice(0, 10)}.csv`
  link.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.data-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  position: absolute;
  top: 11px;
  right: 45px;
}

.data-count {
  font-size: 13px;
  color: #909399;
}

.data-table-wrap {
  position: relative;
}

.data-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 0;
  color: #c0c4cc;
  gap: 8px;
}

.data-empty p {
  font-size: 14px;
  margin: 0;
}
</style>
