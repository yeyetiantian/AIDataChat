<template>
  <div
    class="vega-renderer"
    :class="{ 'is-fullscreen': isFullscreen, 'reserve-side-legend-space': shouldReserveSideLegendSpace }"
    ref="chartContainer"
  >
    <div v-if="!hasRenderableSource" class="empty-state">
      <el-icon :size="48" color="#c0c4cc"><Histogram /></el-icon>
      <p>拖拽字段并点击查询生成图表</p>
    </div>

    <div v-else-if="!props.spec && props.data?.length === 0" class="empty-state">
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
      <div
        ref="vegaContainer"
        class="vega-container"
        :class="{ 'reserve-side-legend-space': shouldReserveSideLegendSpace }"
      ></div>
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
import {
  Handler as VegaTooltipHandler,
  formatValue as formatVegaTooltipValue,
} from 'vega-tooltip'

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

const chartContainer = ref<HTMLElement | null>(null)
const vegaContainer = ref<HTMLElement | null>(null)
const showDataDialog = ref(false)
const showSqlDialog = ref(false)
const embedResult = ref<any>(null)
const isFullscreen = ref(false)
let renderTimer: ReturnType<typeof setTimeout> | null = null
let resizeObserver: ResizeObserver | null = null
const DONUT_INNER_RADIUS = 100
const DATA_ZOOM_BRUSH_PARAM = 'dataZoomBrush'
const DEFAULT_VEGA_HEIGHT = 300
const DATA_ZOOM_MIN_HEIGHT = 260
const DATA_ZOOM_OVERVIEW_HEIGHT = 64
const DATA_ZOOM_OVERVIEW_MIN_HEIGHT = 32
const DATA_ZOOM_OVERVIEW_SHRINK_RATIO = 2 / 3
const DATA_ZOOM_SPACING = 10
const SIDE_LEGEND_LABEL_LIMIT = 140
const PIE_TOTAL_FIELD = '__pie_total__'
const PIE_PERCENT_FIELD = '__pie_percent__'
const TOOLTIP_NUMBER_FORMATTER = new Intl.NumberFormat('zh-CN', {
  maximumFractionDigits: 6,
})
const DEFAULT_VEGA_CATEGORY_COLORS = [
  '#4c78a8',
  '#f58518',
  '#e45756',
  '#72b7b2',
  '#54a24b',
  '#eeca3b',
  '#b279a2',
  '#ff9da6',
  '#9d755d',
  '#bab0ac',
]
const SHARED_TOOLTIP_CHART_TYPES = ['bar', 'line', 'area']

type SharedStackedBarTooltipRow = {
  label: string
  value: string
  color: string
}

type SharedStackedBarTooltipValue = {
  __sharedStackedBar: true
  title: string
  rows: SharedStackedBarTooltipRow[]
}

// 数据弹窗的列名：优先用 props.columns，否则从 data 首行取 key
const displayColumns = computed(() => {
  if (props.columns && props.columns.length) return props.columns
  if (props.data && props.data.length) return Object.keys(props.data[0])
  return []
})

const hasRenderableSource = computed(() => {
  return !!props.spec || !!props.data
})

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

function buildRightLegend(title?: string | null) {
  return {
    orient: 'right',
    direction: 'vertical',
    columns: 1,
    offset: 12,
    labelLimit: SIDE_LEGEND_LABEL_LIMIT,
    titleLimit: SIDE_LEGEND_LABEL_LIMIT,
    ...(title ? { title } : {}),
  }
}

function buildRadarSpec(
  data: Record<string, any>[],
  axisField: string,
  axisTitle: string,
  values: Array<Record<string, any>>,
  keys: string[],
) {
  const dimensions = data
    .map(row => String(row[axisField] ?? ''))
    .filter(Boolean)

  if (!dimensions.length || values.length < 2) return null

  const maxValue = Math.max(
    ...data.flatMap(row => values.map(value => Number(row[resolveFieldName(keys, value)] ?? 0))),
    1,
  )

  const angleStep = (Math.PI * 2) / dimensions.length
  const ringLevels = [0.25, 0.5, 0.75, 1]

  const polygonData = values.flatMap((value) => {
    const metricField = resolveFieldName(keys, value)
    const metric = value.alias || metricField
    const points = data.map((row, index) => {
      const angle = angleStep * index - Math.PI / 2
      const rawValue = Number(row[metricField] ?? 0)
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
          color: { field: '指标', type: 'nominal', title: '指标', legend: buildRightLegend('指标') },
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
  const axisField = resolveFieldName(keys, axes[0])
  const axisTitle = axes[0]?.alias || axisField
  const isTemporalAxis = hasTimeAxis(axes[0])
  const valueFieldNames = resolveValueFieldNames(keys, values)

  if (chartType === 'radar') {
    return buildRadarSpec(data, axisField, axisTitle, values, keys)
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
          ? { field: axisField, type: 'nominal', title: axisTitle, legend: buildRightLegend(axisTitle) }
          : undefined,
      },
    }
  }

  if (values.length > 1 && chartType !== 'pie') {
    const encoding: Record<string, any> = {
      y: { field: 'value', type: 'quantitative', title: '数值' },
      color: { field: 'key', type: 'nominal', title: '指标', legend: buildRightLegend('指标') },
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

  // PIVOT 模式（有 legend）：Y 轴字段从实际数据中检测，而非从 config.field
  let yField: string
  let yTitle: string
  if (legend.length && data && data.length) {
    const axisKeys = new Set(axes.map((a: any) => a.alias || a.field))
    if (legend.length) legend.forEach((l: any) => axisKeys.add(l.alias || l.field))
    yField = Object.keys(data[0]).find(k => !axisKeys.has(k)) || ''
    yTitle = values[0]?.alias || yField
  } else {
    yField = resolveFieldName(keys, values[0])
    yTitle = values[0]?.alias || yField
  }

  const encoding: any = {}
  if (chartType === 'pie') {
    if (xField) encoding.color = { field: xField, type: 'nominal', title: xTitle, legend: buildRightLegend(xTitle) }
    if (yField) encoding.theta = { field: yField, type: 'quantitative', title: yTitle }
  } else {
    if (xField) encoding.x = { field: xField, type: 'nominal', title: xTitle }
    if (yField) encoding.y = { field: yField, type: 'quantitative', title: yTitle }
    if (legend.length) {
      const lf = resolveFieldName(keys, legend[0])
      encoding.color = { field: lf, type: 'nominal', title: legend[0].alias || lf, legend: buildRightLegend(legend[0].alias || lf) }
    }
    if (['line', 'area', 'point'].includes(chartType) && isTemporalAxis) {
      encoding.x.type = 'temporal'
    }
  }

  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
    title: '数据分析',
    width: 'container',
    height: props.height || 'container',
    data: { values: data },
    mark: {
      type: chartType === 'pie' ? 'arc' : chartType,
      tooltip: true,
      point: chartType === 'line',
      ...(chartType === 'pie' ? { innerRadius: DONUT_INNER_RADIUS } : {}),
    },
    encoding,
  }
}

const canRender = computed(() => {
  return !!props.spec || !!(props.data && props.data.length > 0 && props.config)
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

function isArcMark(mark: unknown) {
  if (typeof mark === 'string') return mark === 'arc'
  return !!mark && typeof mark === 'object' && (mark as Record<string, any>).type === 'arc'
}

function applyDonutStyle(spec: Record<string, any>) {
  if (Array.isArray(spec.layer)) {
    spec.layer = spec.layer.map((layer: Record<string, any>) => applyDonutStyle(layer))
  }

  if (spec.spec && typeof spec.spec === 'object') {
    spec.spec = applyDonutStyle(spec.spec)
  }

  if (Array.isArray(spec.concat)) {
    spec.concat = spec.concat.map((item: Record<string, any>) => applyDonutStyle(item))
  }

  if (Array.isArray(spec.hconcat)) {
    spec.hconcat = spec.hconcat.map((item: Record<string, any>) => applyDonutStyle(item))
  }

  if (Array.isArray(spec.vconcat)) {
    spec.vconcat = spec.vconcat.map((item: Record<string, any>) => applyDonutStyle(item))
  }

  if (isArcMark(spec.mark) || spec.encoding?.theta) {
    const mark = typeof spec.mark === 'string'
      ? { type: spec.mark }
      : { ...(spec.mark || {}), type: spec.mark?.type || 'arc' }

    spec.mark = {
      ...mark,
      innerRadius: DONUT_INNER_RADIUS,
    }
  }

  return spec
}

function toDatumFieldExpr(field: string) {
  return `datum[${JSON.stringify(field)}]`
}

function normalizeTooltipEntries(tooltip: unknown) {
  if (Array.isArray(tooltip)) return [...tooltip]
  if (tooltip && typeof tooltip === 'object') return [tooltip]
  return []
}

function hasTooltipField(entries: any[], field: string) {
  return entries.some(entry => entry?.field === field)
}

function getSourceDataRows() {
  if (Array.isArray(props.data) && props.data.length) {
    return props.data
  }

  const specValues = props.spec?.data?.values
  if (Array.isArray(specValues) && specValues.length) {
    return specValues as Record<string, any>[]
  }

  return []
}

function normalizeCategoryValue(value: unknown) {
  if (value == null) return ''

  if (value instanceof Date) {
    return `date:${value.getTime()}`
  }

  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed) return ''

    if (/^\d{4}[-/]\d{2}[-/]\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?$/.test(trimmed)) {
      const timestamp = Date.parse(trimmed.replace(/\//g, '-'))
      if (Number.isFinite(timestamp)) {
        return `date:${timestamp}`
      }
    }

    return trimmed
  }

  if (typeof value === 'number' && Number.isFinite(value)) {
    return `num:${value}`
  }

  return String(value)
}

function formatTooltipTitle(value: unknown) {
  if (value instanceof Date) {
    return value.toLocaleString('zh-CN')
  }

  if (value == null || value === '') return '-'
  return String(value)
}

function toFiniteNumber(value: unknown) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

function formatTooltipMetricValue(value: unknown) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return TOOLTIP_NUMBER_FORMATTER.format(value)
  }

  const numeric = Number(value)
  if (value !== '' && value != null && Number.isFinite(numeric)) {
    return TOOLTIP_NUMBER_FORMATTER.format(numeric)
  }

  if (value == null || value === '') return '0'
  return String(value)
}

function appendTooltipMetric(
  tooltipValue: Record<string, any>,
  label: string,
  value: unknown,
) {
  const baseLabel = label || '值'
  let nextLabel = baseLabel
  let suffix = 2

  while (Object.prototype.hasOwnProperty.call(tooltipValue, nextLabel)) {
    nextLabel = `${baseLabel} (${suffix})`
    suffix += 1
  }

  tooltipValue[nextLabel] = formatTooltipMetricValue(value)
}

function resolveTooltipColorPalette(spec: Record<string, any> | null | undefined) {
  const barSpec = findPrimaryBarUnitSpec(spec)
  const paletteCandidates = [
    barSpec?.encoding?.color?.scale?.range,
    spec?.encoding?.color?.scale?.range,
    spec?.config?.range?.category,
  ]

  for (const candidate of paletteCandidates) {
    if (Array.isArray(candidate) && candidate.length && candidate.every(color => typeof color === 'string')) {
      return candidate as string[]
    }
  }

  return DEFAULT_VEGA_CATEGORY_COLORS
}

function buildTooltipColorMap(
  labels: string[],
  spec: Record<string, any> | null | undefined,
) {
  const palette = resolveTooltipColorPalette(spec)
  const colorMap = new Map<string, string>()

  labels.forEach((label, index) => {
    colorMap.set(label, palette[index % palette.length])
  })

  return colorMap
}

function isSharedStackedBarTooltipValue(value: unknown): value is SharedStackedBarTooltipValue {
  return !!value
    && typeof value === 'object'
    && (value as SharedStackedBarTooltipValue).__sharedStackedBar === true
    && Array.isArray((value as SharedStackedBarTooltipValue).rows)
}

function formatSharedStackedBarTooltipHtml(
  value: SharedStackedBarTooltipValue,
  sanitize: (value: unknown) => string,
) {
  const rowsHtml = value.rows.map((row) => {
    const color = sanitize(row.color)
    const label = sanitize(row.label)
    const metricValue = sanitize(row.value)

    return `
      <div style="display:flex;align-items:center;justify-content:space-between;gap:16px;padding-top:4px;">
        <div style="display:flex;align-items:center;gap:8px;min-width:0;text-align:left;">
          <span style="width:10px;height:10px;border-radius:999px;background:${color};flex-shrink:0;"></span>
          <span style="color:#606266;">${label}</span>
        </div>
        <span style="color:#303133;font-weight:600;text-align:right;white-space:nowrap;">${metricValue}</span>
      </div>
    `
  }).join('')

  return `
    <div style="min-width:220px;text-align:left;">
      <div style="font-size:16px;font-weight:700;color:#303133;padding-bottom:6px;">${sanitize(value.title)}</div>
      ${rowsHtml}
    </div>
  `
}

function buildSharedTooltipPayload(
  tooltipValue: Record<string, any>,
  spec: Record<string, any> | null | undefined,
) {
  const labels = Object.keys(tooltipValue).filter(key => key !== 'title')
  if (!labels.length) return null

  const colorMap = buildTooltipColorMap(labels, spec)

  return {
    __sharedStackedBar: true,
    title: String(tooltipValue.title || ''),
    rows: labels.map((label) => ({
      label,
      value: String(tooltipValue[label] ?? ''),
      color: colorMap.get(label) || DEFAULT_VEGA_CATEGORY_COLORS[0],
    })),
  } satisfies SharedStackedBarTooltipValue
}

function findPrimaryBarUnitSpec(spec: Record<string, any> | null | undefined): Record<string, any> | null {
  if (!spec || typeof spec !== 'object') return null

  const markType = typeof spec.mark === 'string' ? spec.mark : spec.mark?.type
  if (typeof markType === 'string' && SHARED_TOOLTIP_CHART_TYPES.includes(markType) && spec.encoding?.x && spec.encoding?.y) {
    return spec
  }

  if (Array.isArray(spec.layer)) {
    for (const layer of spec.layer) {
      const matchedSpec = findPrimaryBarUnitSpec(layer)
      if (matchedSpec) return matchedSpec
    }
  }

  if (spec.spec && typeof spec.spec === 'object') {
    const matchedSpec = findPrimaryBarUnitSpec(spec.spec)
    if (matchedSpec) return matchedSpec
  }

  for (const key of ['concat', 'hconcat', 'vconcat'] as const) {
    if (!Array.isArray(spec[key])) continue

    for (const child of spec[key]) {
      const matchedSpec = findPrimaryBarUnitSpec(child)
      if (matchedSpec) return matchedSpec
    }
  }

  return null
}

function resolveHoveredCategoryValue(
  datum: Record<string, any> | null | undefined,
  xField: string,
  fallbackKeys: string[] = [],
) {
  if (!datum) return null

  if (datum[xField] != null) {
    return datum[xField]
  }

  for (const key of fallbackKeys) {
    if (key && datum[key] != null) {
      return datum[key]
    }
  }

  return null
}

function buildSharedStackedBarTooltipFromConfig(datum: Record<string, any> | null | undefined) {
  const chartType = props.chartType || props.config?.chart_type || ''
  if (!SHARED_TOOLTIP_CHART_TYPES.includes(chartType) || !props.config) return null

  const sourceData = getSourceDataRows()
  if (!sourceData.length) return null

  const keys = Object.keys(sourceData[0] || {})
  const axes = props.config.axes || []
  const values = props.config.values || []
  const legend = props.config.legend || []

  if (!axes.length || (values.length <= 1 && !legend.length)) return null

  const xField = resolveFieldName(keys, axes[0])
  if (!xField) return null

  const hoveredXValue = resolveHoveredCategoryValue(datum, xField, [
    axes[0]?.alias || '',
    axes[0]?.field || '',
  ])
  if (hoveredXValue == null) return null

  const categoryKey = normalizeCategoryValue(hoveredXValue)
  const matchingRows = sourceData.filter(row => normalizeCategoryValue(row?.[xField]) === categoryKey)
  if (!matchingRows.length) return null

  const tooltipValue: Record<string, any> = {
    title: formatTooltipTitle(hoveredXValue),
  }

  if (values.length > 1) {
    for (const value of values) {
      const valueField = resolveFieldName(keys, value)
      if (!valueField) continue

      const totalValue = matchingRows.reduce((sum, row) => sum + toFiniteNumber(row?.[valueField]), 0)
      appendTooltipMetric(tooltipValue, value.alias || valueField, totalValue)
    }

    return Object.keys(tooltipValue).length > 1 ? tooltipValue : null
  }

  if (!legend.length) return null

  const legendField = resolveFieldName(keys, legend[0])
  if (!legendField) return null

  const axisKeys = new Set(axes.map((axis: any) => axis.alias || axis.field))
  legend.forEach((legendItem: any) => axisKeys.add(legendItem.alias || legendItem.field))
  const valueField = Object.keys(sourceData[0] || {}).find(key => !axisKeys.has(key))
    || resolveFieldName(keys, values[0])

  if (!valueField) return null

  const seriesOrder: string[] = []
  const seenSeries = new Set<string>()

  for (const row of sourceData) {
    const seriesLabel = String(row?.[legendField] ?? '')
    if (!seriesLabel || seenSeries.has(seriesLabel)) continue
    seenSeries.add(seriesLabel)
    seriesOrder.push(seriesLabel)
  }

  const seriesTotals = new Map<string, number>()
  for (const label of seriesOrder) {
    seriesTotals.set(label, 0)
  }

  for (const row of matchingRows) {
    const seriesLabel = String(row?.[legendField] ?? '')
    if (!seriesLabel) continue

    seriesTotals.set(seriesLabel, (seriesTotals.get(seriesLabel) || 0) + toFiniteNumber(row?.[valueField]))
  }

  for (const label of seriesOrder) {
    appendTooltipMetric(tooltipValue, label, seriesTotals.get(label) || 0)
  }

  return Object.keys(tooltipValue).length > 1 ? tooltipValue : null
}

function buildSharedStackedBarTooltipFromSpec(datum: Record<string, any> | null | undefined) {
  const chartType = props.chartType || props.config?.chart_type || ''
  if (chartType && !SHARED_TOOLTIP_CHART_TYPES.includes(chartType)) return null

  const sourceData = getSourceDataRows()
  if (!sourceData.length) return null

  const barSpec = findPrimaryBarUnitSpec(props.spec || null)
  if (!barSpec) return null

  const xField = barSpec?.encoding?.x?.field
  const yField = barSpec?.encoding?.y?.field
  const colorField = barSpec?.encoding?.color?.field

  if (typeof xField !== 'string' || typeof yField !== 'string' || typeof colorField !== 'string') {
    return null
  }

  const markType = typeof barSpec.mark === 'string' ? barSpec.mark : barSpec.mark?.type
  if (markType === 'bar' && barSpec.encoding?.y?.stack === null) {
    return null
  }

  const hoveredXValue = resolveHoveredCategoryValue(datum, xField)
  if (hoveredXValue == null) return null

  const categoryKey = normalizeCategoryValue(hoveredXValue)
  const matchingRows = sourceData.filter(row => normalizeCategoryValue(row?.[xField]) === categoryKey)
  if (!matchingRows.length) return null

  const tooltipValue: Record<string, any> = {
    title: formatTooltipTitle(hoveredXValue),
  }

  const foldTransform = Array.isArray(barSpec.transform)
    ? barSpec.transform.find((transform: Record<string, any>) => (
        Array.isArray(transform?.fold)
        && Array.isArray(transform?.as)
        && transform.as[0] === colorField
        && transform.as[1] === yField
      ))
    : null

  if (foldTransform?.fold?.length) {
    for (const field of foldTransform.fold) {
      if (typeof field !== 'string' || !field) continue

      const totalValue = matchingRows.reduce((sum, row) => sum + toFiniteNumber(row?.[field]), 0)
      appendTooltipMetric(tooltipValue, field, totalValue)
    }

    return Object.keys(tooltipValue).length > 1 ? tooltipValue : null
  }

  const seriesOrder: string[] = []
  const seenSeries = new Set<string>()

  for (const row of sourceData) {
    const seriesLabel = String(row?.[colorField] ?? '')
    if (!seriesLabel || seenSeries.has(seriesLabel)) continue
    seenSeries.add(seriesLabel)
    seriesOrder.push(seriesLabel)
  }

  const seriesTotals = new Map<string, number>()
  for (const label of seriesOrder) {
    seriesTotals.set(label, 0)
  }

  for (const row of matchingRows) {
    const seriesLabel = String(row?.[colorField] ?? '')
    if (!seriesLabel) continue

    seriesTotals.set(seriesLabel, (seriesTotals.get(seriesLabel) || 0) + toFiniteNumber(row?.[yField]))
  }

  for (const label of seriesOrder) {
    appendTooltipMetric(tooltipValue, label, seriesTotals.get(label) || 0)
  }

  return Object.keys(tooltipValue).length > 1 ? tooltipValue : null
}

function buildSharedStackedBarTooltipValue(datum: Record<string, any> | null | undefined) {
  return buildSharedStackedBarTooltipFromConfig(datum) || buildSharedStackedBarTooltipFromSpec(datum)
}

function applyPieTooltipEnhancement(spec: Record<string, any>) {
  if (Array.isArray(spec.layer)) {
    spec.layer = spec.layer.map((layer: Record<string, any>) => applyPieTooltipEnhancement(layer))
  }

  if (spec.spec && typeof spec.spec === 'object') {
    spec.spec = applyPieTooltipEnhancement(spec.spec)
  }

  if (Array.isArray(spec.concat)) {
    spec.concat = spec.concat.map((item: Record<string, any>) => applyPieTooltipEnhancement(item))
  }

  if (Array.isArray(spec.hconcat)) {
    spec.hconcat = spec.hconcat.map((item: Record<string, any>) => applyPieTooltipEnhancement(item))
  }

  if (Array.isArray(spec.vconcat)) {
    spec.vconcat = spec.vconcat.map((item: Record<string, any>) => applyPieTooltipEnhancement(item))
  }

  const thetaField = spec.encoding?.theta?.field
  if (typeof thetaField !== 'string' || !thetaField) {
    return spec
  }

  const colorField = spec.encoding?.color?.field
  const tooltipEntries = normalizeTooltipEntries(spec.encoding?.tooltip)

  if (colorField && !hasTooltipField(tooltipEntries, colorField)) {
    tooltipEntries.push({
      field: colorField,
      type: spec.encoding.color.type || 'nominal',
      title: spec.encoding.color.title || colorField,
    })
  }

  if (!hasTooltipField(tooltipEntries, thetaField)) {
    tooltipEntries.push({
      field: thetaField,
      type: spec.encoding.theta.type || 'quantitative',
      title: spec.encoding.theta.title || thetaField,
    })
  }

  if (!hasTooltipField(tooltipEntries, PIE_PERCENT_FIELD)) {
    tooltipEntries.push({
      field: PIE_PERCENT_FIELD,
      type: 'quantitative',
      title: '占比',
      format: '.1%',
    })
  }

  const transforms = Array.isArray(spec.transform) ? spec.transform : []
  spec.transform = [
    ...transforms.filter((transform: Record<string, any>) => {
      if (Array.isArray(transform?.joinaggregate)) {
        return !transform.joinaggregate.some((aggregate: Record<string, any>) => aggregate?.as === PIE_TOTAL_FIELD)
      }

      return transform?.as !== PIE_PERCENT_FIELD
    }),
    {
      joinaggregate: [{ op: 'sum', field: thetaField, as: PIE_TOTAL_FIELD }],
    },
    {
      calculate: `${toDatumFieldExpr(thetaField)} / ${toDatumFieldExpr(PIE_TOTAL_FIELD)}`,
      as: PIE_PERCENT_FIELD,
    },
  ]

  spec.encoding = {
    ...spec.encoding,
    tooltip: tooltipEntries,
  }

  return spec
}

function isDataZoomSupportedMark(mark: unknown) {
  if (typeof mark === 'string') return mark === 'line' || mark === 'area' || mark === 'point' || mark === 'bar'
  if (!mark || typeof mark !== 'object') return false
  const type = (mark as Record<string, any>).type
  return type === 'line' || type === 'area' || type === 'point' || type === 'bar'
}

function hasDataZoomSupportedMark(spec: Record<string, any>) {
  if (isDataZoomSupportedMark(spec.mark)) return true

  if (Array.isArray(spec.layer)) {
    return spec.layer.some((layer: Record<string, any>) => hasDataZoomSupportedMark(layer))
  }

  if (spec.spec && typeof spec.spec === 'object') {
    return hasDataZoomSupportedMark(spec.spec)
  }

  return false
}

function hasBarMark(spec: Record<string, any>) {
  if (typeof spec.mark === 'string' && spec.mark === 'bar') return true
  if (typeof spec.mark === 'object' && spec.mark?.type === 'bar') return true

  if (Array.isArray(spec.layer)) {
    return spec.layer.some((layer: Record<string, any>) => hasBarMark(layer))
  }

  if (spec.spec && typeof spec.spec === 'object') {
    return hasBarMark(spec.spec)
  }

  return false
}

function hasXEncoding(spec: Record<string, any>) {
  if (spec.encoding?.x) return true

  if (Array.isArray(spec.layer)) {
    return spec.layer.some((layer: Record<string, any>) => hasXEncoding(layer))
  }

  if (spec.spec && typeof spec.spec === 'object') {
    return hasXEncoding(spec.spec)
  }

  return false
}

function isCompositeSpec(spec: Record<string, any>) {
  return (
    Array.isArray(spec.vconcat) ||
    Array.isArray(spec.hconcat) ||
    Array.isArray(spec.concat) ||
    !!spec.facet ||
    !!spec.repeat
  )
}

function shouldApplyDataZoom(spec: Record<string, any>) {
  if (isCompositeSpec(spec) || !hasXEncoding(spec)) return false

  if (props.chartType) {
    return props.chartType === 'line' || props.chartType === 'area' || props.chartType === 'point' || props.chartType === 'bar'
  }

  return hasDataZoomSupportedMark(spec)
}

function isBarChart(spec: Record<string, any>) {
  if (props.chartType) return props.chartType === 'bar'

  return hasBarMark(spec)
}

function applyXDomainFromBrush(spec: Record<string, any>) {
  if (spec.encoding?.x) {
    spec.encoding.x = {
      ...spec.encoding.x,
      scale: {
        ...(spec.encoding.x.scale || {}),
        domain: { param: DATA_ZOOM_BRUSH_PARAM },
      },
    }
  }

  if (Array.isArray(spec.layer)) {
    spec.layer = spec.layer.map((layer: Record<string, any>) => applyXDomainFromBrush(layer))
  }

  if (spec.spec && typeof spec.spec === 'object') {
    spec.spec = applyXDomainFromBrush(spec.spec)
  }

  return spec
}

function applyFilterFromBrush(spec: Record<string, any>) {
  if (Array.isArray(spec.layer)) {
    if (spec.data) {
      const transforms = Array.isArray(spec.transform) ? spec.transform : []
      if (!transforms.some((transform: Record<string, any>) => transform?.filter?.param === DATA_ZOOM_BRUSH_PARAM)) {
        spec.transform = [...transforms, { filter: { param: DATA_ZOOM_BRUSH_PARAM } }]
      }
    } else {
      spec.layer = spec.layer.map((layer: Record<string, any>) => applyFilterFromBrush(layer))
    }
  } else if (spec.spec && typeof spec.spec === 'object') {
    spec.spec = applyFilterFromBrush(spec.spec)
  } else {
    const transforms = Array.isArray(spec.transform) ? spec.transform : []
    if (!transforms.some((transform: Record<string, any>) => transform?.filter?.param === DATA_ZOOM_BRUSH_PARAM)) {
      spec.transform = [...transforms, { filter: { param: DATA_ZOOM_BRUSH_PARAM } }]
    }
  }

  return spec
}

function applyOverviewStyle(spec: Record<string, any>) {
  delete spec.title

  if (spec.encoding?.x) {
    spec.encoding.x = {
      ...spec.encoding.x,
      axis: {
        ...(spec.encoding.x.axis || {}),
        grid: false,
        ticks: false,
        domain: false,
        labels: false,
        title: null,
      },
    }
  }

  if (spec.encoding?.y) {
    spec.encoding.y = {
      ...spec.encoding.y,
      axis: null,
    }
  }

  if (spec.encoding?.color) {
    spec.encoding.color = {
      ...spec.encoding.color,
      legend: null,
    }
  }

  if (spec.encoding?.size) {
    delete spec.encoding.size
  }

  if (spec.mark) {
    const mark = typeof spec.mark === 'string'
      ? { type: spec.mark }
      : { ...spec.mark }

    mark.tooltip = false
    mark.point = false
    mark.clip = true

    if (mark.type === 'line') {
      mark.opacity = mark.opacity ?? 0.75
      mark.strokeWidth = mark.strokeWidth ?? 1.4
    }

    if (mark.type === 'area') {
      mark.opacity = mark.opacity ?? 0.35
    }

    if (mark.type === 'point') {
      mark.opacity = mark.opacity ?? 0.45
      mark.size = Math.min(Number(mark.size || 36), 36)
      mark.filled = mark.filled ?? true
    }

    if (mark.type === 'bar') {
      mark.opacity = mark.opacity ?? 0.6
    }

    spec.mark = mark
  }

  if (Array.isArray(spec.layer)) {
    spec.layer = spec.layer.map((layer: Record<string, any>) => applyOverviewStyle(layer))
  }

  if (spec.spec && typeof spec.spec === 'object') {
    spec.spec = applyOverviewStyle(spec.spec)
  }

  return spec
}

function applySideLegendLayout(spec: Record<string, any>) {
  if (spec.encoding?.color && spec.encoding.color.legend !== null) {
    const currentLegend = spec.encoding.color.legend
    const legendOptions = currentLegend && typeof currentLegend === 'object' ? currentLegend : {}
    spec.encoding.color = {
      ...spec.encoding.color,
      legend: {
        ...buildRightLegend(spec.encoding.color.title),
        ...legendOptions,
      },
    }
  }

  if (Array.isArray(spec.layer)) {
    spec.layer = spec.layer.map((layer: Record<string, any>) => applySideLegendLayout(layer))
  }

  if (spec.spec && typeof spec.spec === 'object') {
    spec.spec = applySideLegendLayout(spec.spec)
  }

  if (Array.isArray(spec.concat)) {
    spec.concat = spec.concat.map((item: Record<string, any>) => applySideLegendLayout(item))
  }

  if (Array.isArray(spec.hconcat)) {
    spec.hconcat = spec.hconcat.map((item: Record<string, any>) => applySideLegendLayout(item))
  }

  if (Array.isArray(spec.vconcat)) {
    spec.vconcat = spec.vconcat.map((item: Record<string, any>) => applySideLegendLayout(item))
  }

  return spec
}

function hasVisibleColorLegend(spec: Record<string, any> | null | undefined): boolean {
  if (!spec || typeof spec !== 'object') return false

  if (spec.encoding?.color && spec.encoding.color.legend !== null) {
    return true
  }

  if (Array.isArray(spec.layer) && spec.layer.some((layer: Record<string, any>) => hasVisibleColorLegend(layer))) {
    return true
  }

  if (spec.spec && typeof spec.spec === 'object' && hasVisibleColorLegend(spec.spec)) {
    return true
  }

  if (Array.isArray(spec.concat) && spec.concat.some((item: Record<string, any>) => hasVisibleColorLegend(item))) {
    return true
  }

  if (Array.isArray(spec.hconcat) && spec.hconcat.some((item: Record<string, any>) => hasVisibleColorLegend(item))) {
    return true
  }

  if (Array.isArray(spec.vconcat) && spec.vconcat.some((item: Record<string, any>) => hasVisibleColorLegend(item))) {
    return true
  }

  return false
}

const shouldReserveSideLegendSpace = computed(() => {
  const chartType = props.chartType || props.config?.chart_type || ''
  if (!['bar', 'line', 'area', 'point'].includes(chartType)) return false

  if (hasVisibleColorLegend(props.spec)) return true

  return hasVisibleColorLegend(buildVegaSpec())
})

function resolveExplicitHeight(value?: number | string) {
  if (typeof value === 'number' && Number.isFinite(value)) return value

  if (typeof value !== 'string') return null

  const trimmed = value.trim()
  if (!trimmed) return null

  const matched = trimmed.match(/^(\d+(?:\.\d+)?)px$/i) || trimmed.match(/^(\d+(?:\.\d+)?)$/)
  if (!matched) return null

  const parsed = Number(matched[1])
  return Number.isFinite(parsed) ? parsed : null
}

function resolveBaseChartHeight() {
  const explicitHeight = resolveExplicitHeight(props.height)
  if (explicitHeight) return Math.max(explicitHeight, DATA_ZOOM_MIN_HEIGHT)

  // Non-fullscreen charts use the renderer's default visual height.
  // Reading the current rendered DOM height here causes a feedback loop
  // once dataZoom rewrites the spec height.
  if (!isFullscreen.value) {
    return DEFAULT_VEGA_HEIGHT
  }

  const fullscreenHeight = vegaContainer.value?.clientHeight || chartContainer.value?.clientHeight || DEFAULT_VEGA_HEIGHT
  return Math.max(fullscreenHeight, DATA_ZOOM_MIN_HEIGHT)
}

function resolveDataZoomHeights() {
  const totalHeight = resolveBaseChartHeight()
  const baseOverviewHeight = Math.min(DATA_ZOOM_OVERVIEW_HEIGHT, Math.max(48, Math.round(totalHeight * 0.22)))
  const overviewHeight = Math.max(
    DATA_ZOOM_OVERVIEW_MIN_HEIGHT,
    Math.round(baseOverviewHeight * DATA_ZOOM_OVERVIEW_SHRINK_RATIO),
  )
  const mainHeight = Math.max(totalHeight - overviewHeight - DATA_ZOOM_SPACING, 180)

  return {
    mainHeight,
    overviewHeight,
  }
}

function applyDataZoom(spec: Record<string, any>) {
  if (!shouldApplyDataZoom(spec)) return spec

  const mainSpec = isBarChart(spec)
    ? applyFilterFromBrush(cloneSpec(spec) || spec)
    : applyXDomainFromBrush(cloneSpec(spec) || spec)
  const overviewSpec = applyOverviewStyle(cloneSpec(spec) || spec)
  const { mainHeight, overviewHeight } = resolveDataZoomHeights()
  const chartTitle = spec.title

  delete mainSpec.title
  delete overviewSpec.title

  mainSpec.width = 'container'
  mainSpec.height = mainHeight
  overviewSpec.width = 'container'
  overviewSpec.height = overviewHeight

  if (Array.isArray(mainSpec.params)) {
    mainSpec.params = mainSpec.params.filter((param: Record<string, any>) => param?.name !== DATA_ZOOM_BRUSH_PARAM)
  }

  const overviewParams = Array.isArray(overviewSpec.params)
    ? overviewSpec.params.filter((param: Record<string, any>) => param?.name !== DATA_ZOOM_BRUSH_PARAM)
    : []

  overviewSpec.params = [
    ...overviewParams,
    {
      name: DATA_ZOOM_BRUSH_PARAM,
      select: { type: 'interval', encodings: ['x'] },
    },
  ]

  return {
    $schema: spec.$schema || 'https://vega.github.io/schema/vega-lite/v5.json',
    ...(chartTitle ? { title: chartTitle } : {}),
    width: 'container',
    resolve: {
      ...(spec.resolve || {}),
      legend: {
        ...(spec.resolve?.legend || {}),
        color: 'independent',
      },
    },
    spacing: DATA_ZOOM_SPACING,
    vconcat: [mainSpec, overviewSpec],
  }
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
  let spec = props.spec
    ? cloneSpec(props.spec)
    : cloneSpec(localSpec)

  if (!spec) return null

  spec = hydrateSpecData(spec)

  // 后端 spec 有时会引用原字段名，和前端实际收到的别名列不一致。
  // 这种情况下回退到前端用 data + config 重建的 spec，避免只显示坐标轴。
  if (props.spec && shouldFallbackToLocalSpec(spec, localSpec)) {
    spec = cloneSpec(localSpec)
    if (!spec) return null
    spec = hydrateSpecData(spec)
  }

  if (props.hideTitle) {
    delete spec.title
  }

  spec = applyDonutStyle(spec)
  spec = applyPieTooltipEnhancement(spec)
  spec = applyDataZoom(spec)
  spec = applySideLegendLayout(spec)

  return spec
}

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
  const spec = buildRenderableSpec()
  if (!spec || !vegaContainer.value) return

  try {
    vegaContainer.value.innerHTML = ''
    embedResult.value = null

    const plainSpec = JSON.parse(JSON.stringify(spec))
    const defaultTooltipHandler = new VegaTooltipHandler({
      formatTooltip: (tooltipValue, sanitize, maxDepth, baseURL) => {
        if (isSharedStackedBarTooltipValue(tooltipValue)) {
          return formatSharedStackedBarTooltipHtml(tooltipValue, sanitize)
        }

        return formatVegaTooltipValue(tooltipValue, sanitize, maxDepth, baseURL)
      },
    }).call

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
      tooltip: (handler: any, event: any, item: any, value: any) => {
        if (value == null || value === '' || !item?.datum) {
          defaultTooltipHandler(handler, event, item, null)
          return
        }

        const sharedTooltipData = buildSharedStackedBarTooltipValue(item?.datum)
        const sharedTooltipValue = sharedTooltipData
          ? buildSharedTooltipPayload(sharedTooltipData, plainSpec)
          : null

        defaultTooltipHandler(handler, event, item, sharedTooltipValue ?? value)
      },
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
  () => [
    props.spec ? JSON.stringify(props.spec) : null,
    props.data ? JSON.stringify(props.data) : null,
    props.config ? JSON.stringify(props.config) : null,
    props.chartType || '',
  ].join('|'),
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
  overflow: hidden;
}

.vega-renderer.reserve-side-legend-space {
  align-items: stretch;
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
  width: 100%;
  overflow: hidden;
  height: 300px;
}
:deep(.vega-container > svg) {
  width: 100%;
  height: 100%;
}

.vega-container.reserve-side-legend-space {
  /* width: calc(100% - clamp(128px, 16vw, 180px));
  max-width: calc(100% - clamp(128px, 16vw, 180px));
  align-self: flex-start;
  overflow: visible; */
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

.vega-renderer.is-fullscreen .vega-container.reserve-side-legend-space,
.vega-renderer:fullscreen .vega-container.reserve-side-legend-space {
  width: calc(100% - clamp(160px, 14vw, 220px));
  max-width: calc(100% - clamp(160px, 14vw, 220px));
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

<style>
  /* vega-tooltip 默认 z-index 1000, 低于 el-dialog 遮罩层 (~2000) */
  #vg-tooltip-element {
    z-index: 9999 !important;
  }
</style>
