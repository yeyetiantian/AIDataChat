<template>
  <div class="analysis-view">
    <!-- 左侧：字段列表 + 透视表配置（合并为一个组件，完全自包含） -->
    <aside class="sidebar-left">
      <ConfigPanel :api="pivotApi" />
    </aside>

    <!-- 中间：图表区域 -->
    <main class="main-content">
      <div class="chart-area">
        <div class="chart-toolbar">
          <!-- 图表类型切换 -->
          <div class="toolbar-right">
            <el-button v-if="chatResult" size="small" type="primary" text @click="showSaveDialog = true">保存到看板</el-button>
          </div>
        </div>

        <VegaLiteRenderer
          :data="chatResult?.data"
          :config="pivotConfig"
          :chart-type="pivotConfig?.chartType || 'bar'"
          :columns="chatResult?.columns"
          :sql="chatResult?.sql"
          :execution-time-ms="chatResult?.execution_time_ms"
        />
      </div>
    </main>

    <!-- 保存到看板 -->
    <el-dialog v-model="showSaveDialog" title="保存到看板" width="400px">
      <el-form label-position="top">
        <el-form-item label="图表名称">
          <el-input v-model="saveTitle" placeholder="输入图表名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="saveDesc" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSaveDialog = false">取消</el-button>
        <el-button type="primary" :loading="chartStore.loading" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useChartStore } from '@/stores/useChartStore'
import ConfigPanel from '@/components/ConfigPanel.vue'
import VegaLiteRenderer from '@/components/VegaLiteRenderer.vue'
import { PivotResponse } from '@/types'

const chartStore = useChartStore()

const chatResult = ref<any | null>(null)
const pivotConfig = ref<any>(null)

const showSaveDialog = ref(false)
const saveTitle = ref('')
const saveDesc = ref('')
const chartType = ref('bar')

function onChartTypeChange(type: string) {
  pivotConfig.value.chartType = type
}

async function pivotApi(config: any) {
  pivotConfig.value = config
  try {
    const resp = await fetch(`/api/pivot`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    })

    if (!resp.ok) {
      const err = await resp.json()
      throw new Error(err.detail || '查询失败')
    }

    const data: PivotResponse = await resp.json()
    chatResult.value = data
  } catch (e: any) {
    console.error('Pivot 查询失败:', e)
  }
}


async function handleSave() {
  if (!saveTitle.value.trim()) return
  const config = pivotConfig.value || (chatResult.value ? Object.assign({ filters: [], axes: [], legend: [], values: [] }, chatResult.value.config) : {})
  await chartStore.saveChart(saveTitle.value, config, saveDesc.value, chartType.value, chatResult.value?.data)
  showSaveDialog.value = false
  saveTitle.value = ''
  saveDesc.value = ''
}

</script>

<style scoped>
.analysis-view {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.sidebar-left {
  width: 340px;
  min-width: 340px;
  padding: 8px;
  overflow-y: auto;
  background: #f5f7fa;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  overflow-y: auto;
}

.chart-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chart-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.exec-time {
  color: #909399;
  font-size: 12px;
}

.sql-display {
  padding: 12px 16px;
  background: #f8f9fa;
}

.sql-display pre {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  color: #606266;
}

.sidebar-right {
  width: 360px;
  min-width: 360px;
  padding: 12px;
  background: #f5f7fa;
  overflow: hidden;
}

/* ============ 高级配置面板 ============ */
.adv-panel {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}
.adv-grid {
  padding: 12px 16px 4px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.adv-row {
  display: flex;
  align-items: center;
  gap: 36px;
}
.adv-item {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}
.adv-item > label {
  font-size: 13px;
  color: #606266;
  font-weight: 500;
  min-width: 72px;
  white-space: nowrap;
}
.show-as-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0 4px 12px;
  width: 100%;
}
.show-as-name {
  min-width: 150px;
  font-size: 13px;
  color: #303133;
  background: #f4f4f5;
  padding: 2px 8px;
  border-radius: 4px;
}

/* ============ 聚合过滤 / 计算 / 分页 样式 ============ */
.filter-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fafafa;
}
.filter-block-head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  border-bottom: 1px dashed #dcdfe6;
  padding-bottom: 4px;
}
.filter-block-head strong {
  font-size: 13px;
  color: #303133;
}
.filter-block-head .hint {
  font-size: 12px;
  color: #909399;
  margin-right: auto;
}
.filter-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 4px;
}
.filter-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.empty-tip {
  font-size: 12px;
  color: #909399;
  padding: 6px 0;
  font-style: italic;
}
.hint-block {
  flex: 1;
}
.tip-bar .tip {
  font-size: 12px;
  color: #909399;
  padding: 8px 12px;
  background: #ecf5ff;
  border: 1px dashed #a0cfff;
  border-radius: 4px;
}

/* ============ 明细宽表 ============ */
.main-tabs {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
}
.main-tabs :deep(.el-tabs__content) {
  flex: 1;
  min-height: 0;
  padding: 0;
}
.main-tabs :deep(.el-tab-pane) {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.detail-view {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 6px 8px 10px;
  height: 100%;
  min-height: 0;
}
.detail-filter {
  background: #fafbfc;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.detail-filter-row {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  align-items: center;
}
.df-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.df-item--grow { flex: 1 1 400px; min-width: 320px; }
.df-item--actions { gap: 4px; }
.df-item > label {
  font-size: 12px;
  color: #606266;
  font-weight: 500;
  white-space: nowrap;
}
.df-sep { color: #909399; }

.detail-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 6px 8px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}
.detail-signals {
  margin-left: 8px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #606266;
  font-size: 12px;
}
.detail-signals .chip {
  background: #f4f4f5;
  border: none;
  color: #303133;
  font-weight: normal;
}
.detail-signals .more {
  font-size: 12px;
  color: #909399;
}
.detail-table-wrap {
  flex: 1 1 auto;
  min-height: 0;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  overflow: hidden;
}
.detail-table-wrap :deep(.el-table .sig-val) {
  font-variant-numeric: tabular-nums;
  font-size: 12px;
}
.detail-table-wrap :deep(.el-table .sig-val.num) {
  color: #1f6feb;
}
.detail-pager {
  padding: 6px 4px 0;
  display: flex;
  justify-content: flex-end;
}
.detail-sql { margin-top: 2px; }
.sql-pre {
  background: #1f2937;
  color: #e5e7eb;
  padding: 12px;
  font-size: 12px;
  border-radius: 4px;
  overflow: auto;
  max-height: 320px;
  line-height: 1.55;
}
</style>
