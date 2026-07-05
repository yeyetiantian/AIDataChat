<template>
  <div class="vega-renderer" ref="chartContainer">
    <div v-if="!canRender" class="empty-state">
      <el-icon :size="48" color="#c0c4cc"><Histogram /></el-icon>
      <p>拖拽字段并点击查询生成图表</p>
    </div>

    <template v-else>
      <!-- 工具栏 -->
      <div v-if="!props.hideToolbar" class="chart-toolbar">
        <span v-if="props.executionTimeMs != null" class="exec-time">
          耗时 {{ props.executionTimeMs }}ms
        </span>
        <div class="toolbar-actions">
          <el-button size="small" text @click="showDataDialog = true">查看数据</el-button>
          <el-button v-if="props.sql" size="small" text @click="showSqlDialog = true">查看 SQL</el-button>
          <el-button size="small" text @click="toggleFullscreen">全屏</el-button>
        </div>
      </div>

      <!-- 图表容器 -->
      <div ref="vegaContainer" class="vega-container"></div>
    </template>

    <!-- SQL 弹窗 -->
    <el-dialog v-model="showSqlDialog" title="SQL" width="70%" top="5vh" destroy-on-close>
      <pre class="sql-pre">{{ props.sql || '' }}</pre>
    </el-dialog>

    <!-- 数据弹窗 -->
    <el-dialog v-model="showDataDialog" title="查询数据" width="80%" top="5vh" destroy-on-close>
      <el-table
        v-if="props.data"
        :data="props.data"
        border stripe size="small" max-height="600" style="width: 100%"
      >
        <el-table-column
          v-for="col in displayColumns" :key="col"
          :prop="col" :label="col" min-width="100"
        />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, nextTick } from 'vue'
import { Histogram } from '@element-plus/icons-vue'
import embed from 'vega-embed'

const props = defineProps<{
  data?: Record<string, any>[] | null
  config?: Record<string, any> | null
  chartType?: string
  loading?: boolean
  columns?: string[]
  sql?: string | null
  executionTimeMs?: number
  hideToolbar?: boolean
}>()

const chartContainer = ref<HTMLElement | null>(null)
const vegaContainer = ref<HTMLElement | null>(null)
const showDataDialog = ref(false)
const showSqlDialog = ref(false)
const embedResult = ref<any>(null)

// 数据弹窗的列名：优先用 props.columns，否则从 data 首行取 key
const displayColumns = computed(() => {
  if (props.columns && props.columns.length) return props.columns
  if (props.data && props.data.length) return Object.keys(props.data[0])
  return []
})

/**
 * 根据 data / config / chartType 构建 Vega-Lite spec
 */
function buildVegaSpec(): Record<string, any> | null {
  const data = props.data
  const config = props.config
  if (!data || !data.length || !config) return null

  const axes = config.axes || []
  const values = config.values || []
  const legend = config.legend || []
  const chartType = props.chartType || 'bar'

  const xField = axes[0]?.alias || ''
  const xTitle = axes[0]?.alias || xField
  const yField = values[0]?.field || ''
  const yTitle = values[0]?.alias || yField

  const encoding: any = {}
  if (chartType === 'pie') {
    if (xField) encoding.color = { field: xField, type: 'nominal', title: xTitle }
    if (yField) encoding.theta = { field: yField, type: 'quantitative', title: yTitle }
  } else {
    if (xField) encoding.x = { field: xField, type: 'nominal', title: xTitle }
    if (yField) encoding.y = { field: yField, type: 'quantitative', title: yTitle }
    if (legend.length) {
      const lf = legend[0].field
      encoding.color = { field: lf, type: 'nominal', title: legend[0].alias || lf }
    }
    if (chartType === 'line' && axes[0]?.group) {
      encoding.x.type = 'temporal'
    }
  }

  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
    title: '数据分析',
    width: 'container',
    height: 'container',
    data: { values: data },
    mark: { type: chartType === 'pie' ? 'arc' : chartType, tooltip: true, point: chartType === 'line' },
    encoding,
  }
}

const canRender = computed(() => {
  return props.data && props.data.length > 0 && props.config
})

function toggleFullscreen() {
  const el = chartContainer.value
  if (!el) return
  if (document.fullscreenElement) {
    document.exitFullscreen()
  } else {
    el.requestFullscreen()
  }
}

function openDataDialog() {
  showDataDialog.value = true
}

function openSqlDialog() {
  if (props.sql) {
    showSqlDialog.value = true
  }
}

async function renderChart() {
  const spec = buildVegaSpec()
  if (!spec || !vegaContainer.value) return

  try {
    vegaContainer.value.innerHTML = ''
    embedResult.value = null

    const plainSpec = JSON.parse(JSON.stringify(spec))

    console.log('Vega-Lite spec:', plainSpec)

    embedResult.value = await embed(vegaContainer.value, plainSpec, {
      actions: props.hideToolbar
        ? false
        : {
            export: { svg: true, png: true },
            source: false,
            compiled: false,
            editor: false,
          },
      tooltip: true,
    })
  } catch (e) {
    console.error('Vega-Lite 渲染失败:', e)
  }
}

function normalizeFileName(fileName: string) {
  return (fileName || 'chart').replace(/[\\/:*?"<>|]/g, '-').trim() || 'chart'
}

function downloadUrl(url: string, fileName: string) {
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

async function exportPng(fileName = 'chart.png') {
  const view = embedResult.value?.view
  if (!view) return
  const url = await view.toImageURL('png')
  downloadUrl(url, normalizeFileName(fileName))
}

async function exportSvg(fileName = 'chart.svg') {
  const view = embedResult.value?.view
  if (!view) return
  const svg = await view.toSVG()
  const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  downloadUrl(url, normalizeFileName(fileName))
  URL.revokeObjectURL(url)
}

watch(
  () => props.data ? JSON.stringify(props.data) + '|' + JSON.stringify(props.config) + '|' + (props.chartType || '') : null,
  async () => {
    await nextTick()
    await renderChart()
  },
  { immediate: true }
)

defineExpose({
  openDataDialog,
  openSqlDialog,
  toggleFullscreen,
  exportPng,
  exportSvg,
})

</script>

<style scoped>
.vega-renderer {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: white;
  border-radius: 8px;
  padding: 0;
  min-height: 400px;
  overflow: hidden;
}

.empty-state {
  text-align: center;
  color: #c0c4cc;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
}

.empty-state p {
  font-size: 14px;
}

.chart-toolbar {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  flex-shrink: 0;
}

.toolbar-actions {
  display: flex;
  gap: 4px;
  align-items: center;
}

.exec-time {
  color: #909399;
  font-size: 12px;
}

.vega-container {
  flex: 1;
  width: 100%;
  overflow: hidden;
  height: 300px;
}

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
