<template>
  <div class="vega-renderer" :class="{ 'is-fullscreen': isFullscreen }" ref="chartContainer">
    <div v-if="!data" class="empty-state">
      <el-icon :size="48" color="#c0c4cc"><Histogram /></el-icon>
      <p>拖拽字段并点击查询生成图表</p>
    </div>

    <div v-else-if="data.length === 0" class="empty-state">
      <el-icon :size="48" color="#c0c4cc"><Histogram /></el-icon>
      <p>暂无数据</p>
    </div>

    <template v-else-if="canRender">
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
import { computed, ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { Histogram } from '@element-plus/icons-vue'
import embed from 'vega-embed'

const props = defineProps<{
  spec?: Record<string, any> | null
  data?: Record<string, any>[] | null
  config?: Record<string, any> | null
  chartType?: string
  loading?: boolean
  columns?: string[]
  sql?: string | null
  executionTimeMs?: number
  hideToolbar?: boolean
  height?: number | string
}>()

const chartContainer = ref<HTMLElement | null>(null)
const vegaContainer = ref<HTMLElement | null>(null)
const showDataDialog = ref(false)
const showSqlDialog = ref(false)
const embedResult = ref<any>(null)
const isFullscreen = ref(false)
let renderTimer: ReturnType<typeof setTimeout> | null = null
let resizeObserver: ResizeObserver | null = null

// 数据弹窗的列名：优先用 props.columns，否则从 data 首行取 key
const displayColumns = computed(() => {
  if (props.columns && props.columns.length) return props.columns
  if (props.data && props.data.length) return Object.keys(props.data[0])
  return []
})

function buildRadarSpec(
  data: Record<string, any>[],
  axisField: string,
  axisTitle: string,
  values: Array<Record<string, any>>,
) {
  const dimensions = data
    .map(row => String(row[axisField] ?? ''))
    .filter(Boolean)

  if (!dimensions.length || values.length < 2) return null

  const maxValue = Math.max(
    ...data.flatMap(row => values.map(value => Number(row[value.field] ?? 0))),
    1,
  )

  const angleStep = (Math.PI * 2) / dimensions.length
  const ringLevels = [0.25, 0.5, 0.75, 1]

  const polygonData = values.flatMap((value) => {
    const metric = value.alias || value.field
    const points = data.map((row, index) => {
      const angle = angleStep * index - Math.PI / 2
      const rawValue = Number(row[value.field] ?? 0)
      const ratio = maxValue === 0 ? 0 : rawValue / maxValue
      return {
        指标: metric,
        维度: String(row[axisField] ?? ''),
        原始值: rawValue,
        排序: index,
        x: Number((Math.cos(angle) * ratio).toFixed(6)),
        y: Number((Math.sin(angle) * ratio).toFixed(6)),
      }
    })

    return points.length ? [...points, { ...points[0], 排序: points.length }] : points
  })

  const ringData = ringLevels.flatMap(level =>
    dimensions.flatMap((dimension, index) => {
      const angle = angleStep * index - Math.PI / 2
      const point = {
        圈层: `${Math.round(level * 100)}%`,
        排序: index,
        x: Number((Math.cos(angle) * level).toFixed(6)),
        y: Number((Math.sin(angle) * level).toFixed(6)),
      }
      return index === dimensions.length - 1
        ? [point, { ...point, 排序: dimensions.length, x: 0, y: -level }]
        : [point]
    }),
  )

  const axisData = dimensions.map((dimension, index) => {
    const angle = angleStep * index - Math.PI / 2
    const x = Number((Math.cos(angle) * 1.05).toFixed(6))
    const y = Number((Math.sin(angle) * 1.05).toFixed(6))
    return {
      维度: dimension,
      x1: 0,
      y1: 0,
      x2: x,
      y2: y,
      labelX: Number((Math.cos(angle) * 1.18).toFixed(6)),
      labelY: Number((Math.sin(angle) * 1.18).toFixed(6)),
    }
  })

  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
    title: '数据分析',
    width: 'container',
    height: 'container',
    background: '#ffffff',
    padding: 24,
    autosize: { type: 'fit', contains: 'padding' },
    layer: [
      {
        data: { values: ringData },
        mark: { type: 'line', color: '#e5e7eb', strokeWidth: 1 },
        encoding: {
          x: { field: 'x', type: 'quantitative', axis: null, scale: { domain: [-1.25, 1.25] } },
          y: { field: 'y', type: 'quantitative', axis: null, scale: { domain: [-1.25, 1.25] } },
          detail: { field: '圈层', type: 'nominal' },
          order: { field: '排序', type: 'ordinal' },
        },
      },
      {
        data: { values: axisData },
        mark: { type: 'rule', color: '#d1d5db', strokeWidth: 1 },
        encoding: {
          x: { field: 'x1', type: 'quantitative', axis: null, scale: { domain: [-1.25, 1.25] } },
          y: { field: 'y1', type: 'quantitative', axis: null, scale: { domain: [-1.25, 1.25] } },
          x2: { field: 'x2' },
          y2: { field: 'y2' },
        },
      },
      {
        data: { values: polygonData },
        mark: { type: 'line', interpolate: 'linear-closed', strokeWidth: 2.2, opacity: 0.9 },
        encoding: {
          x: { field: 'x', type: 'quantitative', axis: null, scale: { domain: [-1.25, 1.25] } },
          y: { field: 'y', type: 'quantitative', axis: null, scale: { domain: [-1.25, 1.25] } },
          color: { field: '指标', type: 'nominal', title: '指标' },
          detail: { field: '指标', type: 'nominal' },
          order: { field: '排序', type: 'ordinal' },
          tooltip: [
            { field: '指标', type: 'nominal' },
            { field: '维度', type: 'nominal', title: axisTitle },
            { field: '原始值', type: 'quantitative', title: '数值' },
          ],
        },
      },
      {
        data: { values: polygonData },
        transform: [{ filter: `datum.排序 < ${dimensions.length}` }],
        mark: { type: 'point', filled: true, size: 70 },
        encoding: {
          x: { field: 'x', type: 'quantitative', axis: null, scale: { domain: [-1.25, 1.25] } },
          y: { field: 'y', type: 'quantitative', axis: null, scale: { domain: [-1.25, 1.25] } },
          color: { field: '指标', type: 'nominal', legend: null },
          tooltip: [
            { field: '指标', type: 'nominal' },
            { field: '维度', type: 'nominal', title: axisTitle },
            { field: '原始值', type: 'quantitative', title: '数值' },
          ],
        },
      },
      {
        data: { values: axisData },
        mark: { type: 'text', fontSize: 12, fill: '#4b5563', align: 'center', baseline: 'middle' },
        encoding: {
          x: { field: 'labelX', type: 'quantitative', axis: null, scale: { domain: [-1.25, 1.25] } },
          y: { field: 'labelY', type: 'quantitative', axis: null, scale: { domain: [-1.25, 1.25] } },
          text: { field: '维度', type: 'nominal' },
        },
      },
    ],
    config: {
      view: { stroke: null },
    },
  }
}

/**
 * 根据 data / config / chartType 构建 Vega-Lite spec
 */
function buildVegaSpec(): Record<string, any> | null {
  const data = props.data
  const config = props.config
  if (!data || !data.length || !config) return null
  const keys = Object.keys(data[0] || {}) || []
  const axes = config.axes || []
  const values = config.values || []
  const legend = config.legend || []
  const chartType = props.chartType || 'bar'
  const axisField = keys.includes(axes[0]?.alias) ? axes[0].alias : axes[0].field || ''
  const axisTitle = axes[0]?.alias || axisField

  if (chartType === 'radar') {
    return buildRadarSpec(data, axisField, axisTitle, values)
  }
  

  if (chartType === 'point' && values.length >= 2) {
    return {
      $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
      title: '数据分析',
      width: 'container',
      height: props.height || 'container',
      data: { values: data },
      mark: { type: 'point', tooltip: true, filled: true, size: 100 },
      encoding: {
        x: {
          field: keys.includes(values[0].alias) ? values[0].alias : values[0].field,
          type: 'quantitative',
          title: values[0].alias || values[0].field,
        },
        y: {
          field: keys.includes(values[1].alias) ? values[1].alias : values[1].field,
          type: 'quantitative',
          title: values[1].alias || values[1].field,
        },
        color: axisField
          ? { field: axisField, type: 'nominal', title: axisTitle }
          : undefined,
      },
    }
  }

  const xField = axisField
  const xTitle = axisTitle

  // PIVOT 模式（有 legend）：Y 轴字段从实际数据中检测，而非从 config.field
  let yField: string
  let yTitle: string
  if (legend.length && data && data.length) {
    const axisKeys = new Set(axes.map((a: any) => a.alias || a.field))
    if (legend.length) legend.forEach((l: any) => axisKeys.add(l.alias || l.field))
    yField = Object.keys(data[0]).find(k => !axisKeys.has(k)) || ''
    yTitle = values[0]?.alias || yField
  } else {
    yField = values[0]?.field || ''
    yTitle = values[0]?.alias || yField
  }

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
    if (['line', 'area', 'point'].includes(chartType) && axes[0]?.aggregation && axes[0].aggregation !== 'source') {
      encoding.x.type = 'temporal'
    }
  }

  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
    title: '数据分析',
    width: 'container',
    height: props.height || 'container',
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

function handleFullscreenChange() {
  isFullscreen.value = document.fullscreenElement === chartContainer.value
  scheduleRender(80)
}

function handleWindowResize() {
  scheduleRender(30)
}

function scheduleRender(delay = 0) {
  if (renderTimer) {
    clearTimeout(renderTimer)
  }

  renderTimer = setTimeout(async () => {
    renderTimer = null
    await nextTick()
    await renderChart()
  }, delay)
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
  // if (props.spec && props.spec.data && props.spec.data.length) {
  //   spec = props.spec
  // }
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
    scheduleRender()
  },
  { immediate: true }
)

onMounted(() => {
  document.addEventListener('fullscreenchange', handleFullscreenChange)
  window.addEventListener('resize', handleWindowResize)

  if (typeof ResizeObserver !== 'undefined' && chartContainer.value) {
    resizeObserver = new ResizeObserver(() => {
      scheduleRender(30)
    })
    resizeObserver.observe(chartContainer.value)
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
  window.removeEventListener('resize', handleWindowResize)
  resizeObserver?.disconnect()

  if (renderTimer) {
    clearTimeout(renderTimer)
    renderTimer = null
  }
})

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

.vega-renderer.is-fullscreen,
.vega-renderer:fullscreen {
  width: 100vw;
  height: 100vh;
  min-height: 100vh;
  border-radius: 0;
  align-items: stretch;
  justify-content: flex-start;
  padding: 20px 24px 24px;
}

.vega-renderer.is-fullscreen .vega-container,
.vega-renderer:fullscreen .vega-container {
  height: 100%;
  min-height: 0;
}

.vega-renderer.is-fullscreen .chart-toolbar,
.vega-renderer:fullscreen .chart-toolbar {
  padding-left: 0;
  padding-right: 0;
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
