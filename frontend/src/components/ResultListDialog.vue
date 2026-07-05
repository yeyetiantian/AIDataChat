<template>
  <el-dialog
    v-model="visible"
    width="95%"
    top="4vh"
    destroy-on-close
    class="result-list-dialog"
    @open="onOpen"
  >
    <template #header>
      <div class="dialog-title">
        <el-icon><Document /></el-icon>
        <span>结果列表</span>
      </div>
    </template>

    <div class="search-bar">
      <el-select v-model="query.vin" clearable placeholder="请选择VIN" size="small" style="width:180px">
        <el-option v-for="v in RESULT_VIN_OPTIONS" :key="v" :label="v" :value="v" />
      </el-select>
      <el-select v-model="query.rule" clearable placeholder="规则名称" size="small" style="width:200px">
        <el-option v-for="r in RESULT_RULE_OPTIONS" :key="r" :label="r" :value="r" />
      </el-select>
      <el-date-picker
        v-model="query.startDate"
        type="datetime"
        value-format="YYYY-MM-DD HH:mm:ss"
        placeholder="开始日期"
        size="small"
        style="width:170px"
      />
      <el-date-picker
        v-model="query.endDate"
        type="datetime"
        value-format="YYYY-MM-DD HH:mm:ss"
        placeholder="结束日期"
        size="small"
        style="width:170px"
      />
      <el-button type="primary" size="small" :icon="Search" @click="handleSearch">搜索</el-button>
      <el-button type="success" size="small" :icon="Download" @click="handleExport">结果导出</el-button>
    </div>

    <el-table
      ref="tableRef"
      class="result-table"
      :data="pageData"
      border
      stripe
      size="small"
      max-height="420"
      :header-cell-style="{ backgroundColor: '#f5f7fa' }"
      @selection-change="onSelectionChange"
    >
      <el-table-column type="selection" width="40" align="center" />
      <el-table-column label="序号" width="55" align="center">
        <template #default="{ $index }">{{ (currentPage - 1) * pageSize + $index + 1 }}</template>
      </el-table-column>
      <el-table-column prop="vin" label="VIN" min-width="140" show-overflow-tooltip />
      <el-table-column prop="rule" label="规则名称" min-width="160" show-overflow-tooltip />
      <el-table-column prop="ruleType" label="规则类型" width="80" align="center" />
      <el-table-column prop="preTime" label="前置条件满足时间" min-width="165" show-overflow-tooltip />
      <el-table-column prop="alarmTime" label="报警/前置条件不满足时间" min-width="175" show-overflow-tooltip />
      <el-table-column prop="duration" label="持续时间(s)" width="95" align="center" />
      <el-table-column prop="alarmData" label="告警/统计数据" min-width="180" show-overflow-tooltip />
      <el-table-column prop="freezeFrame" label="冻结帧" min-width="110" show-overflow-tooltip />
      <el-table-column prop="highPrecision" label="高精度数据" width="95" show-overflow-tooltip />
      <el-table-column prop="downsampled" label="降频数据整合" min-width="120" show-overflow-tooltip />
    </el-table>

    <div class="pagination-bar">
      <span class="total-text">共 {{ filteredData.length }} 条</span>
      <el-select v-model="pageSize" size="small" style="width:100px" @change="onPageSizeChange">
        <el-option label="10条/页" :value="10" />
        <el-option label="20条/页" :value="20" />
        <el-option label="50条/页" :value="50" />
      </el-select>
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="filteredData.length"
        layout="prev, pager, next"
        size="small"
        background
      />
      <span class="goto-label">前往</span>
      <el-input-number
        v-model="gotoPage"
        :min="1"
        :max="totalPages"
        size="small"
        controls-position="right"
        style="width:90px"
      />
      <span class="goto-label">页</span>
      <el-button size="small" @click="handleGotoPage">跳转</el-button>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { Document, Search, Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { TableInstance } from 'element-plus'
import {
  RESULT_LIST_DATA,
  RESULT_VIN_OPTIONS,
  RESULT_RULE_OPTIONS,
  type ResultListItem,
} from '@/constants/resultList'

const visible = defineModel<boolean>({ default: false })

const tableRef = ref<TableInstance>()
const filteredData = ref<ResultListItem[]>([...RESULT_LIST_DATA])
const selectedRows = ref<ResultListItem[]>([])
const currentPage = ref(1)
const pageSize = ref(10)
const gotoPage = ref(1)

const query = reactive({
  vin: '',
  rule: '',
  startDate: '',
  endDate: '',
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredData.value.length / pageSize.value)))

const pageData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredData.value.slice(start, start + pageSize.value)
})

function onOpen() {
  resetQuery()
  filteredData.value = [...RESULT_LIST_DATA]
  currentPage.value = 1
  pageSize.value = 10
  gotoPage.value = 1
  selectedRows.value = []
  tableRef.value?.clearSelection()
}

function resetQuery() {
  query.vin = ''
  query.rule = ''
  query.startDate = ''
  query.endDate = ''
}

function handleSearch() {
  filteredData.value = RESULT_LIST_DATA.filter(d => {
    if (query.vin && d.vin !== query.vin) return false
    if (query.rule && d.rule !== query.rule) return false
    if (query.startDate && d.preTime < query.startDate) return false
    if (query.endDate && d.preTime > query.endDate) return false
    return true
  })
  currentPage.value = 1
  gotoPage.value = 1
  selectedRows.value = []
  tableRef.value?.clearSelection()
}

function onSelectionChange(rows: ResultListItem[]) {
  selectedRows.value = rows
}

function onPageSizeChange() {
  currentPage.value = 1
  gotoPage.value = 1
}

function handleGotoPage() {
  if (gotoPage.value >= 1 && gotoPage.value <= totalPages.value) {
    currentPage.value = gotoPage.value
  }
}

function handleExport() {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请至少选择一条记录导出')
    return
  }
  ElMessage.success(`已选择 ${selectedRows.value.length} 条记录，导出功能待接口对接`)
}
</script>

<style scoped>
.dialog-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
}

.search-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.pagination-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.total-text {
  font-size: 12px;
  color: #606266;
}

.goto-label {
  font-size: 12px;
  color: #606266;
}
</style>

<style>
.result-list-dialog .el-dialog__body {
  padding-top: 8px;
}

.result-list-dialog .result-table th.el-table__cell {
  background-color: #f5f7fa !important;
}
</style>
