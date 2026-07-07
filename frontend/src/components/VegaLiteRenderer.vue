<template>
  <div class="vega-renderer" :class="{ 'is-fullscreen': isFullscreen }" ref="chartContainer">
    <div v-if="!hasRenderableSource" class="empty-state">
      <el-icon :size="48" color="#c0c4cc"><Histogram /></el-icon>
      <p>拖拽字段并点击查询生成图表</p>
    </div>

    <div v-else-if="!props.spec && props.data?.length === 0 && !shouldRenderRadarPlaceholder" class="empty-state">
      <el-icon :size="48" color="#c0c4cc"><Histogram /></el-icon>
      <p>暂无数据</p>
    </div>

    <template v-else-if="canRender">
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

      <div v-if="chartNotice" class="chart-notice">
        {{ chartNotice }}
      </div>

      <div ref="vegaContainer" class="vega-container"></div>
    </template>

    <el-dialog v-model="showSqlDialog" title="SQL" width="70%" top="5vh" destroy-on-close>
      <pre class="sql-pre">{{ props.sql || '' }}</pre>
    </el-dialog>

    <el-dialog v-model="showDataDialog" title="查询数据" width="80%" top="5vh" destroy-on-close>
      <el-table
        v-if="props.data"
        :data="props.data"
        border
        stripe
        size="small"
        max-height="600"
        style="width: 100%"
      >
        <el-table-column
          v-for="col in displayColumns"
          :key="col"
          :prop="col"
          :label="col"
          min-width="100"
        />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
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
  hideTitle?: boolean
  height?: number | string
}>()

type RadarMetric = {
  field: string
  label: string
}

type RadarPoint = {
  metric: string
  dimension: string
  rawValue: number
  order: number
  x: number
  y: number
}

type RadarChartState = {
  notice: string
  spec: Record<string, any> | null
}

const DEFAULT_RADAR_DIMENSIONS = ['维度1', '维度2', '维度3', '维度4', '维度5']
const RADAR_DOMAIN = [-1.25, 1.25]

const chartContainer = ref<HTMLElement | null>(null)
const vegaContainer = ref<HTMLElement | null>(null)
const showDataDialog = ref(false)
const showSqlDialog = ref(false)
const embedResult = ref<any>(null)
const isFullscreen = ref(false)
let renderTimer: ReturnType<typeof setTimeout> | null = null
let resizeObserver: ResizeObserver | null = null

const displayColumns = computed(() => {
  if (props.columns && props.columns.length) return props.columns
  if (props.data && props.data.length) return Object.keys(props.data[0])
  return []
})

const resolvedChartType = computed(() => props.chartType || props.config?.chart_type || 'bar')

function resolveFieldName(
  keys: string[],
  item?: { field?: string, alias?: string },
) {
  if (!item) return ''
  const alias = item.alias || ''
  if (alias && keys.includes(alias)) return alias
  return item.field || alias
}

function hasTimeAxis(axis?: { aggregation?: string, group?: string }) {
  const grouping = axis?.aggregation || axis?.group
  return !!grouping && grouping !== 'source'
}

function resolveValueFieldNames(keys: string[], values: Array<Record<string, any>>) {
  return values
    .map(value => resolveFieldName(keys, value))
    .filter((field): field is string => !!field)
}

function buildRadarGeometry(dimensions: string[]) {
  const angleStep = (Math.PI * 2) / dimensions.length
  const ringLevels = [0.25, 0.5, 0.75, 1]

  const ringData = ringLevels.flatMap(level => {
    const points = dimensions.map((_, index) => {
      const angle = angleStep * index - Math.PI / 2
      return {
        ring: `${Math.round(level * 100)}%`,
        order: index,
        x: Number((Math.cos(angle) * level).toFixed(6)),
        y: Number((Math.sin(angle) * level).toFixed(6)),
      }
    })

    return points.length ? [...points, { ...points[0], order: points.length }] : points
  })

  const axisData = dimensions.map((dimension, index) => {
    const angle = angleStep * index - Math.PI / 2
    return {
      dimension,
      x1: 0,
      y1: 0,
      x2: Number((Math.cos(angle) * 1.05).toFixed(6)),
      y2: Number((Math.sin(angle) * 1.05).toFixed(6)),
      labelX: Number((Math.cos(angle) * 1.18).toFixed(6)),
      labelY: Number((Math.sin(angle) * 1.18).toFixed(6)),
    }
  })

  return { ringData, axisData }
}

function createRadarSpec(
  axisTitle: string,
  dimensions: string[],
  polygonData: RadarPoint[] = [],
): Record<string, any> {
  const { ringData, axisData } = buildRadarGeometry(dimensions)
  const layers: Record<string, any>[] = [
    {
      data: { values: ringData },
      mark: { type: 'line', color: '#e5e7eb', strokeWidth: 1 },
      encoding: {
        x: { field: 'x', type: 'quantitative', axis: null, scale: { domain: RADAR_DOMAIN } },
        y: { field: 'y', type: 'quantitative', axis: null, scale: { domain: RADAR_DOMAIN } },
        detail: { field: 'ring', type: 'nominal' },
        order: { field: 'order', type: 'ordinal' },
      },
    },
    {
      data: { values: axisData },
      mark: { type: 'rule', color: '#d1d5db', strokeWidth: 1 },
      encoding: {
        x: { field: 'x1', type: 'quantitative', axis: null, scale: { domain: RADAR_DOMAIN } },
        y: { field: 'y1', type: 'quantitative', axis: null, scale: { domain: RADAR_DOMAIN } },
        x2: { field: 'x2' },
        y2: { field: 'y2' },
      },
    },
  ]

  if (polygonData.length) {
    layers.push(
      {
        data: { values: polygonData },
        mark: { type: 'line', interpolate: 'linear-closed', strokeWidth: 2.2, opacity: 0.9 },
        encoding: {
          x: { field: 'x', type: 'quantitative', axis: null, scale: { domain: RADAR_DOMAIN } },
          y: { field: 'y', type: 'quantitative', axis: null, scale: { domain: RADAR_DOMAIN } },
          color: { field: 'metric', type: 'nominal', title: '指标' },
          detail: { field: 'metric', type: 'nominal' },
          order: { field: 'order', type: 'ordinal' },
          tooltip: [
            { field: 'metric', type: 'nominal', title: '指标' },
            { field: 'dimension', type: 'nominal', title: axisTitle },
            { field: 'rawValue', type: 'quantitative', title: '数值' },
          ],
        },
      },
      {
        data: { values: polygonData },
        transform: [{ filter: `datum.order < ${dimensions.length}` }],
        mark: { type: 'point', filled: true, size: 70 },
        encoding: {
          x: { field: 'x', type: 'quantitative', axis: null, scale: { domain: RADAR_DOMAIN } },
          y: { field: 'y', type: 'quantitative', axis: null, scale: { domain: RADAR_DOMAIN } },
          color: { field: 'metric', type: 'nominal', legend: null },
          tooltip: [
            { field: 'metric', type: 'nominal', title: '指标' },
            { field: 'dimension', type: 'nominal', title: axisTitle },
            { field: 'rawValue', type: 'quantitative', title: '数值' },
          ],
        },
      },
    )
  }

  layers.push({
    data: { values: axisData },
    mark: { type: 'text', fontSize: 12, fill: '#4b5563', align: 'center', baseline: 'middle' },
    encoding: {
      x: { field: 'labelX', type: 'quantitative', axis: null, scale: { domain: RADAR_DOMAIN } },
      y: { field: 'labelY', type: 'quantitative', axis: null, scale: { domain: RADAR_DOMAIN } },
      text: { field: 'dimension', type: 'nominal' },
    },
  })

  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
    title: '数据分析',
    width: 'container',
    height: props.height || 'container',
    background: '#ffffff',
    padding: 24,
    autosize: { type: 'fit', contains: 'padding' },
    layer: layers,
    config: {
      view: { stroke: null },
    },
  }
}

function buildRadarState(): RadarChartState | null {
  if (resolvedChartType.value !== 'radar' || !props.config) return null

  const data = props.data || []
  const keys = Object.keys(data[0] || {})
  const axes = props.config.axes || []
  const values = props.config.values || []
  const axisField = resolveFieldName(keys, axes[0])
  const axisTitle = axes[0]?.alias || axisField || '维度'
  const issues: string[] = []

  const metrics: RadarMetric[] = values
    .map((value) => {
      const field = resolveFieldName(keys, value)
      if (!field) return null
      return {
        field,
        label: value.alias || field,
      }
    })
    .filter((metric): metric is RadarMetric => !!metric)

  const seenDimensions = new Set<string>()
  const dimensionRows = axisField
    ? data.flatMap((row) => {
        const label = String(row[axisField] ?? '').trim()
        if (!label || seenDimensions.has(label)) return []
        seenDimensions.add(label)
        return [{ label, row }]
      })
    : []
  const dimensions = dimensionRows.map(item => item.label)
  const displayDimensions = dimensions.length ? dimensions : DEFAULT_RADAR_DIMENSIONS

  if (!axisField) {
    issues.push('缺少维度字段')
  } else if (!dimensions.length) {
    issues.push(`维度“${axisTitle}”没有可用数据`)
  }

  if (metrics.length < 2) {
    issues.push(`至少需要 2 个数值指标，当前仅 ${metrics.length} 个`)
  }

  if (issues.length) {
    return {
      notice: `雷达图生成条件不足：${issues.join('；')}。已显示空雷达图。`,
      spec: createRadarSpec(axisTitle, displayDimensions),
    }
  }

  const numericValues = dimensionRows.flatMap(({ row }) =>
    metrics
      .map(metric => Number(row[metric.field]))
      .filter(value => Number.isFinite(value))
      .map(value => Math.max(value, 0)),
  )
  const maxValue = numericValues.length ? Math.max(...numericValues) : 0

  if (!maxValue) {
    return {
      notice: '雷达图生成条件不足：指标值全部为空、非数值或为 0。已显示空雷达图。',
      spec: createRadarSpec(axisTitle, displayDimensions),
    }
  }

  const angleStep = (Math.PI * 2) / dimensions.length
  const polygonData = metrics.flatMap((metric) => {
    const points = dimensionRows.map(({ label, row }, index) => {
      const angle = angleStep * index - Math.PI / 2
      const numericValue = Number(row[metric.field])
      const rawValue = Number.isFinite(numericValue) ? numericValue : 0
      const ratio = Math.max(rawValue, 0) / maxValue

      return {
        metric: metric.label,
        dimension: label,
        rawValue,
        order: index,
        x: Number((Math.cos(angle) * ratio).toFixed(6)),
        y: Number((Math.sin(angle) * ratio).toFixed(6)),
      }
    })

    return points.length ? [...points, { ...points[0], order: points.length }] : points
  })

  return {
    notice: '',
    spec: createRadarSpec(axisTitle, dimensions, polygonData),
  }
}

const radarChartState = computed(() => buildRadarState())

const shouldRenderRadarPlaceholder = computed(() => {
  return resolvedChartType.value === 'radar' && !!radarChartState.value?.spec
})

const hasRenderableSource = computed(() => {
  return !!props.spec || !!props.data || shouldRenderRadarPlaceholder.value
})

const chartNotice = computed(() => radarChartState.value?.notice || '')

function buildVegaSpec(): Record<string, any> | null {
  if (resolvedChartType.value === 'radar') {
    return radarChartState.value?.spec || null
  }

  const data = props.data || []
  const config = props.config
  if (!data.length || !config) return null

  const keys = Object.keys(data[0] || {})
  const axes = config.axes || []
  const values = config.values || []
  const legend = config.legend || []
  const chartType = resolvedChartType.value
  const axisField = resolveFieldName(keys, axes[0])
  const axisTitle = axes[0]?.alias || axisField
  const isTemporalAxis = hasTimeAxis(axes[0])
  const valueFieldNames = resolveValueFieldNames(keys, values)

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
          field: valueFieldNames[0],
          type: 'quantitative',
          title: values[0].alias || values[0].field,
        },
        y: {
          field: valueFieldNames[1],
          type: 'quantitative',
          title: values[1].alias || values[1].field,
        },
        color: axisField
          ? { field: axisField, type: 'nominal', title: axisTitle }
          : undefined,
      },
    }
  }

  if (values.length > 1 && chartType !== 'pie') {
    const encoding: Record<string, any> = {
      y: { field: 'value', type: 'quantitative', title: '数值' },
      color: { field: 'key', type: 'nominal', title: '指标' },
    }

    if (axisField) {
      encoding.x = {
        field: axisField,
        type: isTemporalAxis && ['line', 'area'].includes(chartType) ? 'temporal' : 'nominal',
        title: axisTitle,
      }
    }

    return {
      $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
      title: '数据分析',
      width: 'container',
      height: props.height || 'container',
      data: { values: data },
      transform: [{ fold: valueFieldNames, as: ['key', 'value'] }],
      mark: { type: chartType, tooltip: true, point: chartType === 'line' },
      encoding,
    }
  }

  const xField = axisField
  const xTitle = axisTitle

  let yField = ''
  let yTitle = ''
  if (legend.length && data.length) {
    const axisKeys = new Set(axes.map((axis: any) => axis.alias || axis.field))
    legend.forEach((item: any) => axisKeys.add(item.alias || item.field))
    yField = Object.keys(data[0]).find(key => !axisKeys.has(key)) || ''
    yTitle = values[0]?.alias || yField
  } else {
    yField = resolveFieldName(keys, values[0])
    yTitle = values[0]?.alias || yField
  }

  const encoding: Record<string, any> = {}
  if (chartType === 'pie') {
    if (xField) encoding.color = { field: xField, type: 'nominal', title: xTitle }
    if (yField) encoding.theta = { field: yField, type: 'quantitative', title: yTitle }
  } else {
    if (xField) encoding.x = { field: xField, type: 'nominal', title: xTitle }
    if (yField) encoding.y = { field: yField, type: 'quantitative', title: yTitle }
    if (legend.length) {
      const legendField = resolveFieldName(keys, legend[0])
      encoding.color = { field: legendField, type: 'nominal', title: legend[0].alias || legendField }
    }
    if (['line', 'area', 'point'].includes(chartType) && isTemporalAxis && encoding.x) {
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
  return !!props.spec || !!(props.data && props.data.length > 0 && props.config) || shouldRenderRadarPlaceholder.value
})

function cloneSpec(spec: Record<string, any> | null | undefined) {
  return spec ? JSON.parse(JSON.stringify(spec)) : null
}

function hydrateSpecData(spec: Record<string, any>) {
  if (
    props.data?.length &&
    (!spec.data || !Array.isArray(spec.data.values) || spec.data.values.length === 0)
  ) {
    spec.data = {
      ...(spec.data || {}),
      values: props.data,
    }
  }

  return spec
}

function collectDerivedFields(transforms: any[] = []) {
  const derivedFields = new Set<string>()

  for (const transform of transforms) {
    const asValue = transform?.as
    if (Array.isArray(asValue)) {
      asValue.forEach(field => {
        if (typeof field === 'string' && field) derivedFields.add(field)
      })
      continue
    }

    if (typeof asValue === 'string' && asValue) {
      derivedFields.add(asValue)
    }
  }

  return derivedFields
}

function hasRequiredEncodingFields(
  spec: Record<string, any>,
  dataKeys: string[],
  inheritedTransforms: any[] = [],
) {
  const transforms = [
    ...inheritedTransforms,
    ...(Array.isArray(spec.transform) ? spec.transform : []),
  ]
  const derivedFields = collectDerivedFields(transforms)

  if (Array.isArray(spec.layer) && spec.layer.length > 0) {
    return spec.layer.every(layer => hasRequiredEncodingFields(layer, dataKeys, transforms))
  }

  const encoding = spec.encoding || {}
  const requiredFields = [encoding.y?.field, encoding.theta?.field]
    .filter((field): field is string => typeof field === 'string' && field.length > 0)

  if (!requiredFields.length) return true

  return requiredFields.every(field => dataKeys.includes(field) || derivedFields.has(field))
}

function shouldFallbackToLocalSpec(spec: Record<string, any>, localSpec: Record<string, any> | null) {
  if (!localSpec || !props.data?.length || !props.config) return false
  const dataKeys = Object.keys(props.data[0] || {})
  return !hasRequiredEncodingFields(spec, dataKeys)
}

function buildRenderableSpec(): Record<string, any> | null {
  const localSpec = buildVegaSpec()
  const preferLocalSpec = resolvedChartType.value === 'radar' && !!localSpec
  let spec = preferLocalSpec
    ? cloneSpec(localSpec)
    : props.spec
      ? cloneSpec(props.spec)
      : cloneSpec(localSpec)

  if (!spec) return null

  spec = hydrateSpecData(spec)

  if (!preferLocalSpec && props.spec && shouldFallbackToLocalSpec(spec, localSpec)) {
    spec = cloneSpec(localSpec)
    if (!spec) return null
    spec = hydrateSpecData(spec)
  }

  if (props.hideTitle) {
    delete spec.title
  }

  return spec
}

function toggleFullscreen() {
  const el = chartContainer.value
  if (!el) return

  if (document.fullscreenElement) {
    void document.exitFullscreen()
  } else {
    void el.requestFullscreen()
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
  if (!vegaContainer.value) return

  const spec = buildRenderableSpec()
  if (!spec) {
    vegaContainer.value.innerHTML = ''
    embedResult.value = null
    return
  }

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
  } catch (error) {
    console.error('Vega-Lite 渲染失败:', error)
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
  () => [
    props.spec ? JSON.stringify(props.spec) : null,
    props.data ? JSON.stringify(props.data) : null,
    props.config ? JSON.stringify(props.config) : null,
    props.chartType || '',
  ].join('|'),
  async () => {
    scheduleRender()
  },
  { immediate: true },
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

.chart-notice {
  width: calc(100% - 32px);
  margin: 0 16px 8px;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid #fdba74;
  background: #fff7ed;
  color: #9a3412;
  font-size: 12px;
  line-height: 1.5;
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

.vega-renderer.is-fullscreen .chart-notice,
.vega-renderer:fullscreen .chart-notice {
  width: 100%;
  margin-left: 0;
  margin-right: 0;
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
