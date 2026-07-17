<template>
  <div
    ref="chartContainer"
    class="vega-renderer"
    :class="{ 'is-fullscreen': isFullscreen }"
  >
    <div v-if="!hasRenderableSource" class="empty-state">
      <el-icon :size="48" color="#c0c4cc"><Histogram /></el-icon>
      <p>拖拽字段并点击查询生成图表</p>
    </div>

    <div v-else-if="!canRender" class="empty-state">
      <el-icon :size="48" color="#c0c4cc"><Histogram /></el-icon>
      <p>暂无可展示的数据</p>
    </div>

    <template v-else>
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

      <div
        ref="chartViewport"
        class="vega-container"
        :style="viewportStyle"
      ></div>
    </template>

    <el-dialog v-model="showSqlDialog" title="SQL" width="70%" top="5vh" destroy-on-close>
      <pre class="sql-pre">{{ props.sql || '' }}</pre>
    </el-dialog>

    <el-dialog v-model="showDataDialog" title="查询数据" width="80%" top="5vh" destroy-on-close>
      <el-table
        v-if="tableRows.length"
        :data="tableRows"
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
      <div v-else class="empty-dialog">暂无数据</div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Histogram } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

type Row = Record<string, any>
type FieldLike = { field?: string; alias?: string; aggregation?: string; group?: string }
type ValueLike = { field?: string; alias?: string; id?: string }
type ChartOption = echarts.EChartsOption

const props = defineProps<{
  spec?: Record<string, any> | null
  data?: Row[] | null
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
const chartViewport = ref<HTMLElement | null>(null)
const showDataDialog = ref(false)
const showSqlDialog = ref(false)
const isFullscreen = ref(false)

const NUMBER_FORMATTER = new Intl.NumberFormat('zh-CN', {
  maximumFractionDigits: 6,
})

const COLOR_PALETTE = [
  '#5470c6',
  '#91cc75',
  '#fac858',
  '#ee6666',
  '#73c0de',
  '#3ba272',
  '#fc8452',
  '#9a60b4',
  '#ea7ccc',
]

const DEFAULT_HEIGHT = 300
const MIN_HEIGHT = 240
const DATA_ZOOM_THRESHOLD = 12
const LEGEND_MAX_TEXT_WIDTH = 18

let chartInstance: echarts.ECharts | null = null
let renderTimer: ReturnType<typeof setTimeout> | null = null
let resizeObserver: ResizeObserver | null = null

const tableRows = computed(() => getSourceDataRows())

const displayColumns = computed(() => {
  if (props.columns?.length) return props.columns
  const rows = tableRows.value
  if (rows.length) return Object.keys(rows[0] || {})
  return []
})

const hasRenderableSource = computed(() => {
  return !!props.spec || tableRows.value.length > 0
})

const canRender = computed(() => {
  return !!buildChartOption()
})

const viewportStyle = computed(() => {
  const explicitHeight = resolveExplicitHeight(props.height)
  if (explicitHeight && !isFullscreen.value) {
    return {
      height: `${Math.max(explicitHeight, MIN_HEIGHT)}px`,
    }
  }

  return {}
})

function getSourceDataRows(): Row[] {
  if (Array.isArray(props.data) && props.data.length) {
    return props.data
  }

  const specValues = props.spec?.data?.values
  if (Array.isArray(specValues) && specValues.length) {
    return specValues as Row[]
  }

  return []
}

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

function resolveFieldName(keys: string[], item?: FieldLike | ValueLike) {
  if (!item) return ''

  const candidates = [item.alias, item.field].filter((value): value is string => !!value)
  for (const candidate of candidates) {
    if (keys.includes(candidate)) return candidate
  }

  return candidates[0] || ''
}

function resolveValueFieldNames(keys: string[], values: ValueLike[]) {
  return values
    .map(value => resolveFieldName(keys, value))
    .filter((field): field is string => !!field)
}

function hasTimeAxis(axis?: FieldLike) {
  const grouping = axis?.aggregation || axis?.group
  return !!grouping && grouping !== 'source'
}

function toNumberOrNull(value: unknown) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

function toNumberOrZero(value: unknown) {
  return toNumberOrNull(value) ?? 0
}

function formatNumber(value: unknown) {
  const numeric = toNumberOrNull(value)
  if (numeric == null) return '-'
  return NUMBER_FORMATTER.format(numeric)
}

function normalizeText(value: unknown) {
  if (value == null || value === '') return '-'
  return String(value)
}

function getTextDisplayWidth(text: string) {
  return Array.from(text).reduce((width, char) => {
    return width + (char.charCodeAt(0) <= 0x7f ? 1 : 2)
  }, 0)
}

function truncateLegendLabel(value: unknown, maxWidth = LEGEND_MAX_TEXT_WIDTH) {
  const text = normalizeText(value)
  if (getTextDisplayWidth(text) <= maxWidth) return text

  let currentWidth = 0
  const chars: string[] = []

  for (const char of Array.from(text)) {
    const charWidth = char.charCodeAt(0) <= 0x7f ? 1 : 2
    if (currentWidth + charWidth > maxWidth - 3) break
    chars.push(char)
    currentWidth += charWidth
  }

  return `${chars.join('')}...`
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function buildLegendOption(option: Record<string, any>) {
  return {
    ...option,
    formatter: (name: string) => truncateLegendLabel(name),
    tooltip: {
      show: true,
      confine: true,
      formatter: (param: any) => {
        const name = typeof param === 'string' ? param : param?.name
        return escapeHtml(normalizeText(name))
      },
    },
  }
}

function toTimeValue(value: unknown) {
  if (value instanceof Date) return value.getTime()
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value > 1e11 ? value : null
  }

  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  if (!trimmed) return null

  const normalized = trimmed.replace(/\//g, '-')
  const timestamp = Date.parse(normalized)
  return Number.isFinite(timestamp) ? timestamp : null
}

function isNumericLike(value: unknown) {
  if (typeof value === 'number') return Number.isFinite(value)
  if (typeof value !== 'string') return false
  const trimmed = value.trim()
  return trimmed !== '' && Number.isFinite(Number(trimmed))
}

function normalizeAxisKey(value: unknown) {
  const timeValue = toTimeValue(value)
  if (timeValue != null) return `t:${timeValue}`

  if (isNumericLike(value)) {
    return `n:${Number(value)}`
  }

  return `s:${String(value ?? '')}`
}

function extractSpecTitle(spec?: Record<string, any> | null) {
  const rawTitle = spec?.title
  if (!rawTitle) return ''
  if (typeof rawTitle === 'string') return rawTitle
  if (typeof rawTitle?.text === 'string') return rawTitle.text
  return ''
}

function getChartTitle() {
  if (props.hideTitle) return ''
  return extractSpecTitle(props.spec) || '数据分析'
}

function normalizeChartType(type?: string | null) {
  switch (type) {
    case 'bar':
    case 'line':
    case 'area':
    case 'point':
    case 'pie':
    case 'radar':
      return type
    default:
      return 'bar'
  }
}

function getMarkType(spec?: Record<string, any> | null): string {
  if (!spec) return ''

  const mark = spec.mark
  if (typeof mark === 'string') return mark
  if (mark && typeof mark === 'object' && typeof mark.type === 'string') {
    return mark.type
  }

  if (Array.isArray(spec.layer)) {
    for (const layer of spec.layer) {
      const nestedType = getMarkType(layer)
      if (nestedType) return nestedType
    }
  }

  return ''
}

function deriveChartTypeFromSpec(spec?: Record<string, any> | null) {
  const markType = getMarkType(spec)
  if (markType === 'arc' || spec?.encoding?.theta) return 'pie'
  if (markType === 'line') return 'line'
  if (markType === 'area') return 'area'
  if (markType === 'point') return 'point'
  if (markType === 'bar') return 'bar'
  return ''
}

function getEffectiveChartType() {
  return normalizeChartType(
    props.chartType
    || props.config?.chart_type
    || deriveChartTypeFromSpec(props.spec)
    || 'bar',
  )
}

function buildTitleOption() {
  const title = getChartTitle()
  if (!title) return undefined

  return {
    text: title,
    left: 'center',
    top: 8,
    textStyle: {
      fontSize: 14,
      fontWeight: 600,
      color: '#303133',
    },
  }
}

function buildCartesianGrid(top: number, bottom: number) {
  return {
    left: 72,
    right: 36,
    top,
    bottom,
    containLabel: true,
  }
}

function buildAxisNameTextStyle() {
  return {
    color: '#606266',
    fontSize: 12,
  }
}

function detectAxisType(values: unknown[], preferredTime = false, preferredValue = false): 'category' | 'time' | 'value' {
  const sample = values.filter(value => value != null && value !== '').slice(0, 24)

  if (preferredTime && sample.some(value => toTimeValue(value) != null)) {
    return 'time'
  }

  if (sample.length > 0 && sample.every(value => toTimeValue(value) != null)) {
    return 'time'
  }

  if (preferredValue && sample.length > 0 && sample.every(value => isNumericLike(value))) {
    return 'value'
  }

  return 'category'
}

function collectOrderedAxisValues(rows: Row[], axisField: string, axisType: 'category' | 'time' | 'value') {
  if (!axisField) {
    return rows.map((_, index) => `项目 ${index + 1}`)
  }

  const values = rows.map(row => row?.[axisField])
  if (axisType === 'time') {
    return Array.from(
      new Map(
        values
          .map(value => {
            const timestamp = toTimeValue(value)
            if (timestamp == null) return null
            return [timestamp, value] as const
          })
          .filter((entry): entry is readonly [number, unknown] => !!entry)
          .sort((a, b) => a[0] - b[0]),
      ).values(),
    )
  }

  if (axisType === 'value') {
    return Array.from(
      new Map(
        values
          .map(value => {
            const numeric = toNumberOrNull(value)
            if (numeric == null) return null
            return [numeric, value] as const
          })
          .filter((entry): entry is readonly [number, unknown] => !!entry)
          .sort((a, b) => a[0] - b[0]),
      ).values(),
    )
  }

  const ordered: unknown[] = []
  const seen = new Set<string>()

  for (const value of values) {
    const key = normalizeAxisKey(value)
    if (seen.has(key)) continue
    seen.add(key)
    ordered.push(value)
  }

  return ordered
}

function buildCategoryIndex(values: unknown[]) {
  const index = new Map<string, number>()
  values.forEach((value, position) => {
    index.set(normalizeAxisKey(value), position)
  })
  return index
}

function normalizeContinuousSeriesData(data: any[]) {
  const grouped = new Map<number, number>()

  for (const point of data) {
    if (!Array.isArray(point) || point.length < 2) continue

    const xValue = Number(point[0])
    const yValue = toNumberOrNull(point[1])
    if (!Number.isFinite(xValue) || yValue == null) continue

    grouped.set(xValue, (grouped.get(xValue) || 0) + yValue)
  }

  return Array.from(grouped.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([xValue, yValue]) => [xValue, yValue])
}

function simplifyWideSeriesName(field: string, values: ValueLike[]) {
  const labels = values
    .map(value => value.alias || value.field || value.id)
    .filter((label): label is string => !!label)

  for (const label of labels) {
    const suffix = `_${label}`
    if (field.endsWith(suffix) && field.length > suffix.length) {
      return field.slice(0, -suffix.length)
    }
  }

  return field
}

function inferValueField(keys: string[], axisField: string, legendField = '') {
  const excluded = new Set([axisField, legendField].filter(Boolean))
  return keys.find(key => !excluded.has(key)) || ''
}

function buildAxisTooltipFormatter() {
  return (params: any) => {
    const items = Array.isArray(params) ? params : [params]
    const header = items[0]?.axisValueLabel || items[0]?.name || ''
    const lines = items
      .filter((item: any) => item && item.seriesName)
      .map((item: any) => {
        const rawValue = Array.isArray(item.value) ? item.value[item.value.length - 1] : item.value
        return `${item.marker}${item.seriesName}: ${formatNumber(rawValue)}`
      })

    return [header, ...lines].filter(Boolean).join('<br/>')
  }
}

function buildItemTooltipFormatter(xName: string, yName: string) {
  return (param: any) => {
    const rawRow = param?.data?.raw as Row | undefined
    if (!rawRow) {
      const value = Array.isArray(param?.value) ? param.value : [param?.value]
      return [
        param?.seriesName || '',
        `${xName}: ${normalizeText(value[0])}`,
        `${yName}: ${formatNumber(value[1])}`,
      ].filter(Boolean).join('<br/>')
    }

    return [
      param?.seriesName || '',
      `${xName}: ${normalizeText(rawRow.__x_label ?? rawRow[xName] ?? param?.value?.[0])}`,
      `${yName}: ${formatNumber(rawRow.__y_value ?? param?.value?.[1])}`,
    ].filter(Boolean).join('<br/>')
  }
}

function buildCartesianBaseOption(args: {
  chartType: 'bar' | 'line' | 'area'
  xAxisType: 'category' | 'time' | 'value'
  xAxisName: string
  xAxisData?: unknown[]
  yAxisName: string
  series: Array<{ name: string; data: any[] }>
  showLegend: boolean
  shouldStack: boolean
  enableDataZoom: boolean
}): ChartOption {
  const realSeriesType = args.chartType === 'area' ? 'line' : args.chartType
  const titleOption = buildTitleOption()
  const normalizedSeries = args.series.map(series => ({
    ...series,
    data: args.xAxisType === 'category'
      ? series.data
      : normalizeContinuousSeriesData(series.data),
  }))
  const xAxis: any = {
    type: args.xAxisType,
    name: args.xAxisName,
    nameLocation: 'middle',
    nameGap: args.enableDataZoom ? 52 : 36,
    nameTextStyle: buildAxisNameTextStyle(),
    boundaryGap: args.chartType === 'bar',
    data: args.xAxisType === 'category' ? args.xAxisData : undefined,
    axisLabel: args.xAxisType === 'time'
      ? {
          formatter: (value: number) => {
            return new Date(value).toLocaleString('zh-CN', {
              hour12: false,
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
            })
          },
        }
      : { hideOverlap: true },
  }

  return {
    color: COLOR_PALETTE,
    animationDuration: 300,
    title: titleOption,
    legend: args.showLegend
      ? buildLegendOption({
          type: 'scroll',
          top: titleOption ? 34 : 8,
          left: 12,
          right: 12,
        })
      : undefined,
    grid: buildCartesianGrid(
      args.showLegend ? (titleOption ? 84 : 52) : (titleOption ? 52 : 20),
      args.enableDataZoom ? 92 : 56,
    ),
    tooltip: {
      trigger: args.xAxisType === 'category' || args.xAxisType === 'time' ? 'axis' : 'item',
      confine: true,
      formatter: buildAxisTooltipFormatter(),
    },
    xAxis,
    yAxis: {
      type: 'value',
      name: args.yAxisName,
      nameLocation: 'middle',
      nameGap: 56,
      nameTextStyle: buildAxisNameTextStyle(),
      splitLine: {
        lineStyle: {
          color: '#ebeef5',
        },
      },
      axisLabel: {
        formatter: (value: number) => formatNumber(value),
      },
    },
    dataZoom: args.enableDataZoom
      ? [
          {
            type: 'inside',
            xAxisIndex: 0,
          },
          {
            type: 'slider',
            xAxisIndex: 0,
            height: 18,
            bottom: 14,
          },
        ]
      : undefined,
    series: normalizedSeries.map(series => ({
      name: series.name,
      type: realSeriesType,
      data: series.data,
      stack: args.shouldStack ? 'total' : undefined,
      smooth: false,
      showSymbol: realSeriesType !== 'line' || series.data.length <= 80,
      areaStyle: args.chartType === 'area' ? { opacity: 0.2 } : undefined,
      emphasis: {
        focus: 'series',
      },
    })),
  }
}

function buildWidePivotCartesianOption(
  rows: Row[],
  keys: string[],
  axisField: string,
  axisTitle: string,
  values: ValueLike[],
  chartType: 'bar' | 'line' | 'area',
  axisType: 'category' | 'time' | 'value',
) {
  const seriesFields = keys.filter(key => key !== axisField)
  if (!seriesFields.length) return null

  const axisValues = collectOrderedAxisValues(rows, axisField, axisType)
  const categoryIndex = buildCategoryIndex(axisValues)

  const series = seriesFields.map(field => ({
    name: simplifyWideSeriesName(field, values),
    data: axisType === 'category' ? Array(axisValues.length).fill(null) : [] as any[],
  }))

  const seriesFieldIndex = new Map(seriesFields.map((field, index) => [field, index]))

  for (const row of rows) {
    const axisValue = row?.[axisField]
    const axisKey = normalizeAxisKey(axisValue)
    const axisPosition = categoryIndex.get(axisKey)
    if (axisPosition == null && axisType === 'category') continue

    seriesFields.forEach(field => {
      const targetSeries = series[seriesFieldIndex.get(field) || 0]
      const numericValue = toNumberOrNull(row?.[field])
      if (numericValue == null) return

      if (axisType === 'category') {
        const current = targetSeries.data[axisPosition!]
        targetSeries.data[axisPosition!] = current == null ? numericValue : Number(current) + numericValue
        return
      }

      const axisNumeric = axisType === 'time' ? toTimeValue(axisValue) : toNumberOrNull(axisValue)
      if (axisNumeric == null) return

      targetSeries.data.push([axisNumeric, numericValue])
    })
  }

  return buildCartesianBaseOption({
    chartType,
    xAxisType: axisType,
    xAxisName: axisTitle,
    xAxisData: axisType === 'category' ? axisValues : undefined,
    yAxisName: values[0]?.alias || '值',
    series,
    showLegend: series.length > 1,
    shouldStack: chartType === 'bar' || chartType === 'area',
    enableDataZoom: axisValues.length > DATA_ZOOM_THRESHOLD,
  })
}

function buildTallLegendCartesianOption(
  rows: Row[],
  axisField: string,
  axisTitle: string,
  legendField: string,
  valueField: string,
  valueTitle: string,
  chartType: 'bar' | 'line' | 'area',
  axisType: 'category' | 'time' | 'value',
) {
  const axisValues = collectOrderedAxisValues(rows, axisField, axisType)
  const categoryIndex = buildCategoryIndex(axisValues)
  const legendValues = Array.from(
    new Set(
      rows
        .map(row => normalizeText(row?.[legendField]))
        .filter(label => label !== '-'),
    ),
  )

  const series = legendValues.map(label => ({
    name: label,
    data: axisType === 'category' ? Array(axisValues.length).fill(null) : [] as any[],
  }))

  const seriesIndex = new Map(legendValues.map((label, index) => [label, index]))

  for (const row of rows) {
    const legendLabel = normalizeText(row?.[legendField])
    const targetSeries = series[seriesIndex.get(legendLabel) || 0]
    const numericValue = toNumberOrNull(row?.[valueField])
    if (numericValue == null) continue

    const axisValue = row?.[axisField]
    if (axisType === 'category') {
      const axisPosition = categoryIndex.get(normalizeAxisKey(axisValue))
      if (axisPosition == null) continue
      const current = targetSeries.data[axisPosition]
      targetSeries.data[axisPosition] = current == null ? numericValue : Number(current) + numericValue
      continue
    }

    const axisNumeric = axisType === 'time' ? toTimeValue(axisValue) : toNumberOrNull(axisValue)
    if (axisNumeric == null) continue
    targetSeries.data.push([axisNumeric, numericValue])
  }

  return buildCartesianBaseOption({
    chartType,
    xAxisType: axisType,
    xAxisName: axisTitle,
    xAxisData: axisType === 'category' ? axisValues : undefined,
    yAxisName: valueTitle,
    series,
    showLegend: series.length > 1,
    shouldStack: chartType === 'bar' || chartType === 'area',
    enableDataZoom: axisValues.length > DATA_ZOOM_THRESHOLD,
  })
}

function buildMultiValueCartesianOption(
  rows: Row[],
  axisField: string,
  axisTitle: string,
  valueFields: string[],
  valueTitles: string[],
  chartType: 'bar' | 'line' | 'area',
  axisType: 'category' | 'time' | 'value',
) {
  const axisValues = collectOrderedAxisValues(rows, axisField, axisType)
  const categoryIndex = buildCategoryIndex(axisValues)

  const series = valueFields.map((field, index) => ({
    name: valueTitles[index] || field,
    data: axisType === 'category' ? Array(axisValues.length).fill(null) : [] as any[],
  }))

  for (const row of rows) {
    const axisValue = row?.[axisField]
    const axisPosition = axisType === 'category'
      ? categoryIndex.get(normalizeAxisKey(axisValue))
      : null
    const axisNumeric = axisType === 'category'
      ? null
      : (axisType === 'time' ? toTimeValue(axisValue) : toNumberOrNull(axisValue))

    valueFields.forEach((field, index) => {
      const numericValue = toNumberOrNull(row?.[field])
      if (numericValue == null) return

      if (axisType === 'category') {
        if (axisPosition == null) return
        const current = series[index].data[axisPosition]
        series[index].data[axisPosition] = current == null ? numericValue : Number(current) + numericValue
        return
      }

      if (axisNumeric == null) return
      series[index].data.push([axisNumeric, numericValue])
    })
  }

  return buildCartesianBaseOption({
    chartType,
    xAxisType: axisType,
    xAxisName: axisTitle,
    xAxisData: axisType === 'category' ? axisValues : undefined,
    yAxisName: valueTitles.length === 1 ? valueTitles[0] : '值',
    series,
    showLegend: series.length > 1,
    shouldStack: chartType === 'bar' || chartType === 'area',
    enableDataZoom: axisValues.length > DATA_ZOOM_THRESHOLD,
  })
}

function buildSingleValueCartesianOption(
  rows: Row[],
  axisField: string,
  axisTitle: string,
  valueField: string,
  valueTitle: string,
  chartType: 'bar' | 'line' | 'area',
  axisType: 'category' | 'time' | 'value',
) {
  const axisValues = collectOrderedAxisValues(rows, axisField, axisType)
  const categoryIndex = buildCategoryIndex(axisValues)
  const data = axisType === 'category' ? Array(axisValues.length).fill(null) : [] as any[]

  for (const row of rows) {
    const numericValue = toNumberOrNull(row?.[valueField])
    if (numericValue == null) continue

    const axisValue = row?.[axisField]
    if (axisType === 'category') {
      const axisPosition = categoryIndex.get(normalizeAxisKey(axisValue))
      if (axisPosition == null) continue
      const current = data[axisPosition]
      data[axisPosition] = current == null ? numericValue : Number(current) + numericValue
      continue
    }

    const axisNumeric = axisType === 'time' ? toTimeValue(axisValue) : toNumberOrNull(axisValue)
    if (axisNumeric == null) continue
    data.push([axisNumeric, numericValue])
  }

  return buildCartesianBaseOption({
    chartType,
    xAxisType: axisType,
    xAxisName: axisTitle,
    xAxisData: axisType === 'category' ? axisValues : undefined,
    yAxisName: valueTitle,
    series: [{
      name: valueTitle,
      data,
    }],
    showLegend: false,
    shouldStack: false,
    enableDataZoom: axisValues.length > DATA_ZOOM_THRESHOLD,
  })
}

function buildCartesianOptionFromConfig(
  rows: Row[],
  config: Record<string, any>,
  chartType: 'bar' | 'line' | 'area',
) {
  const keys = Object.keys(rows[0] || {})
  const axes = (config.axes || []) as FieldLike[]
  const legend = (config.legend || []) as FieldLike[]
  const values = (config.values || []) as ValueLike[]

  const axisField = resolveFieldName(keys, axes[0]) || keys[0] || ''
  const axisTitle = axes[0]?.alias || axisField || '分类'
  const legendField = resolveFieldName(keys, legend[0])
  const hasLegendFieldInData = !!legendField && keys.includes(legendField)
  const valueFields = resolveValueFieldNames(keys, values)
  const valueTitles = values.map(value => value.alias || value.field || value.id || '值')
  const axisType = chartType === 'bar'
    ? 'category'
    : detectAxisType(
        rows.map(row => row?.[axisField]),
        hasTimeAxis(axes[0]),
        chartType === 'line' || chartType === 'area',
      )

  if (legend.length > 0 && !hasLegendFieldInData) {
    return buildWidePivotCartesianOption(rows, keys, axisField, axisTitle, values, chartType, axisType)
  }

  if (legendField) {
    const valueField = valueFields[0] || inferValueField(keys, axisField, legendField)
    if (!valueField) return null
    return buildTallLegendCartesianOption(
      rows,
      axisField,
      axisTitle,
      legendField,
      valueField,
      valueTitles[0] || valueField,
      chartType,
      axisType,
    )
  }

  if (valueFields.length > 1) {
    return buildMultiValueCartesianOption(rows, axisField, axisTitle, valueFields, valueTitles, chartType, axisType)
  }

  const valueField = valueFields[0] || inferValueField(keys, axisField)
  if (!valueField) return null

  return buildSingleValueCartesianOption(
    rows,
    axisField,
    axisTitle,
    valueField,
    valueTitles[0] || valueField,
    chartType,
    axisType,
  )
}

function buildPieOptionFromConfig(rows: Row[], config: Record<string, any>) {
  const keys = Object.keys(rows[0] || {})
  const axes = (config.axes || []) as FieldLike[]
  const values = (config.values || []) as ValueLike[]
  const valueFields = resolveValueFieldNames(keys, values)
  const axisField = resolveFieldName(keys, axes[0]) || keys[0] || ''
  const valueField = valueFields[0] || inferValueField(keys, axisField)
  if (!axisField || !valueField) return null

  const pieData = rows.map(row => ({
    name: normalizeText(row?.[axisField]),
    value: toNumberOrZero(row?.[valueField]),
  }))

  const titleOption = buildTitleOption()

  return {
    color: COLOR_PALETTE,
    animationDuration: 300,
    title: titleOption,
    tooltip: {
      trigger: 'item',
      confine: true,
      formatter: (param: any) => {
        return `${param.marker}${param.name}: ${formatNumber(param.value)} (${param.percent || 0}%)`
      },
    },
    legend: buildLegendOption({
      type: 'scroll',
      top: titleOption ? 34 : 8,
      left: 12,
      right: 12,
    }),
    series: [
      {
        name: values[0]?.alias || valueField,
        type: 'pie',
        radius: ['40%', '72%'],
        center: ['50%', '60%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 6,
          borderColor: '#fff',
          borderWidth: 2,
        },
        label: {
          formatter: (param: any) => `${param.name}\n${param.percent || 0}%`,
        },
        emphasis: {
          scale: true,
          scaleSize: 8,
        },
        data: pieData,
      },
    ],
  } satisfies ChartOption
}

function buildRadarOptionFromConfig(rows: Row[], config: Record<string, any>) {
  const keys = Object.keys(rows[0] || {})
  const axes = (config.axes || []) as FieldLike[]
  const values = (config.values || []) as ValueLike[]
  const axisField = resolveFieldName(keys, axes[0])
  const valueFields = resolveValueFieldNames(keys, values)
  if (!axisField || valueFields.length === 0) return null

  const indicators = rows.map(row => {
    const maxValue = Math.max(
      ...valueFields.map(field => toNumberOrZero(row?.[field])),
      1,
    )

    return {
      name: normalizeText(row?.[axisField]),
      max: Math.max(1, Math.ceil(maxValue * 1.15)),
    }
  })

  const seriesData = valueFields.map((field, index) => ({
    name: values[index]?.alias || field,
    value: rows.map(row => toNumberOrZero(row?.[field])),
  }))

  const titleOption = buildTitleOption()

  return {
    color: COLOR_PALETTE,
    animationDuration: 300,
    title: titleOption,
    legend: buildLegendOption({
      type: 'scroll',
      top: titleOption ? 34 : 8,
      left: 12,
      right: 12,
    }),
    tooltip: {
      trigger: 'item',
      confine: true,
      formatter: (param: any) => {
        const valuesList = Array.isArray(param?.value) ? param.value : []
        const lines = indicators.map((indicator, index) => {
          return `${indicator.name}: ${formatNumber(valuesList[index])}`
        })

        return [param?.seriesName || param?.name || '', ...lines].join('<br/>')
      },
    },
    radar: {
      radius: '62%',
      center: ['50%', '56%'],
      indicator: indicators,
      splitArea: {
        areaStyle: {
          color: ['rgba(84, 112, 198, 0.04)', 'rgba(84, 112, 198, 0.02)'],
        },
      },
    },
    series: [
      {
        type: 'radar',
        data: seriesData.map(item => ({
          ...item,
          areaStyle: {
            opacity: 0.08,
          },
        })),
        emphasis: {
          focus: 'series',
        },
      },
    ],
  } satisfies ChartOption
}

function buildScatterOption(args: {
  rows: Row[]
  xField: string
  yField: string
  xName: string
  yName: string
  seriesField?: string
}) {
  const xValues = args.rows.map(row => row?.[args.xField])
  const xAxisType = detectAxisType(xValues, xValues.some(value => toTimeValue(value) != null), xValues.some(value => isNumericLike(value)))

  const seriesNames = args.seriesField
    ? Array.from(
        new Set(
          args.rows
            .map(row => normalizeText(row?.[args.seriesField || '']))
            .filter(label => label !== '-'),
        ),
      )
    : [args.yName]

  const series = seriesNames.map(name => ({
    name,
    type: 'scatter' as const,
    symbolSize: 9,
    data: [] as any[],
    emphasis: {
      focus: 'series' as const,
    },
  }))

  const seriesIndex = new Map(seriesNames.map((name, index) => [name, index]))

  for (const row of args.rows) {
    const yValue = toNumberOrNull(row?.[args.yField])
    if (yValue == null) continue

    const rawXValue = row?.[args.xField]
    const xValue = xAxisType === 'time'
      ? toTimeValue(rawXValue)
      : xAxisType === 'value'
        ? toNumberOrNull(rawXValue)
        : normalizeText(rawXValue)

    if (xValue == null) continue

    const seriesName = args.seriesField ? normalizeText(row?.[args.seriesField]) : args.yName
    const targetSeries = series[seriesIndex.get(seriesName) || 0]

    targetSeries.data.push({
      value: [xValue, yValue],
      raw: {
        ...row,
        __x_label: rawXValue,
        __y_value: yValue,
      },
    })
  }

  const titleOption = buildTitleOption()
  const enableDataZoom = series.some(item => item.data.length > DATA_ZOOM_THRESHOLD)
  const xAxis: any = {
    type: xAxisType,
    name: args.xName,
    nameLocation: 'middle',
    nameGap: enableDataZoom ? 52 : 36,
    nameTextStyle: buildAxisNameTextStyle(),
    axisLabel: xAxisType === 'time'
      ? {
          formatter: (value: number) => {
            return new Date(value).toLocaleString('zh-CN', {
              hour12: false,
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
            })
          },
        }
      : undefined,
  }

  return {
    color: COLOR_PALETTE,
    animationDuration: 300,
    title: titleOption,
    legend: series.length > 1
      ? buildLegendOption({
          type: 'scroll',
          top: titleOption ? 34 : 8,
          left: 12,
          right: 12,
        })
      : undefined,
    grid: buildCartesianGrid(
      series.length > 1 ? (titleOption ? 84 : 52) : (titleOption ? 52 : 20),
      enableDataZoom ? 92 : 56,
    ),
    tooltip: {
      trigger: 'item',
      confine: true,
      formatter: buildItemTooltipFormatter(args.xName, args.yName),
    },
    xAxis,
    yAxis: {
      type: 'value',
      name: args.yName,
      nameLocation: 'middle',
      nameGap: 56,
      nameTextStyle: buildAxisNameTextStyle(),
      splitLine: {
        lineStyle: {
          color: '#ebeef5',
        },
      },
      axisLabel: {
        formatter: (value: number) => formatNumber(value),
      },
    },
    dataZoom: enableDataZoom && xAxisType !== 'value'
      ? [
          { type: 'inside', xAxisIndex: 0 },
          { type: 'slider', xAxisIndex: 0, height: 18, bottom: 14 },
        ]
      : undefined,
    series,
  } satisfies ChartOption
}

function buildScatterOptionFromConfig(rows: Row[], config: Record<string, any>) {
  const keys = Object.keys(rows[0] || {})
  const axes = (config.axes || []) as FieldLike[]
  const legend = (config.legend || []) as FieldLike[]
  const values = (config.values || []) as ValueLike[]

  if (values.length >= 2) {
    const xField = resolveFieldName(keys, values[0])
    const yField = resolveFieldName(keys, values[1])
    if (!xField || !yField) return null

    const seriesField = resolveFieldName(keys, legend[0]) || (() => {
      const candidate = resolveFieldName(keys, axes[0])
      if (candidate && candidate !== xField && candidate !== yField) return candidate
      return ''
    })()

    return buildScatterOption({
      rows,
      xField,
      yField,
      xName: values[0]?.alias || xField,
      yName: values[1]?.alias || yField,
      seriesField,
    })
  }

  const xField = resolveFieldName(keys, axes[0])
  const yField = resolveFieldName(keys, values[0]) || inferValueField(keys, xField)
  if (!xField || !yField) return null

  return buildScatterOption({
    rows,
    xField,
    yField,
    xName: axes[0]?.alias || xField,
    yName: values[0]?.alias || yField,
    seriesField: resolveFieldName(keys, legend[0]),
  })
}

function buildOptionFromSpec(rows: Row[], spec: Record<string, any>, fallbackType: string) {
  const encoding = spec.encoding || {}
  const inferredType = normalizeChartType(deriveChartTypeFromSpec(spec) || fallbackType)
  const xField = typeof encoding?.x?.field === 'string' ? encoding.x.field : ''
  const yField = typeof encoding?.y?.field === 'string' ? encoding.y.field : ''
  const colorField = typeof encoding?.color?.field === 'string' ? encoding.color.field : ''
  const thetaField = typeof encoding?.theta?.field === 'string' ? encoding.theta.field : ''

  if (inferredType === 'pie' && thetaField) {
    return buildPieOptionFromConfig(rows, {
      axes: [{ field: colorField, alias: encoding?.color?.title || colorField }],
      values: [{ field: thetaField, alias: encoding?.theta?.title || thetaField }],
      chart_type: 'pie',
    })
  }

  if (inferredType === 'point' && xField && yField) {
    return buildScatterOption({
      rows,
      xField,
      yField,
      xName: encoding?.x?.title || xField,
      yName: encoding?.y?.title || yField,
      seriesField: colorField,
    })
  }

  const foldTransform = Array.isArray(spec.transform)
    ? spec.transform.find((transform: Record<string, any>) => Array.isArray(transform?.fold))
    : null

  if ((inferredType === 'bar' || inferredType === 'line' || inferredType === 'area') && foldTransform?.fold?.length) {
    return buildCartesianOptionFromConfig(rows, {
      axes: xField ? [{ field: xField, alias: encoding?.x?.title || xField }] : [],
      values: foldTransform.fold.map((field: string) => ({ field, alias: field })),
      chart_type: inferredType,
    }, inferredType)
  }

  if (inferredType === 'bar' || inferredType === 'line' || inferredType === 'area') {
    return buildCartesianOptionFromConfig(rows, {
      axes: xField ? [{ field: xField, alias: encoding?.x?.title || xField }] : [],
      legend: colorField ? [{ field: colorField, alias: encoding?.color?.title || colorField }] : [],
      values: yField ? [{ field: yField, alias: encoding?.y?.title || yField }] : [],
      chart_type: inferredType,
    }, inferredType)
  }

  return null
}

function buildChartOption() {
  const rows = getSourceDataRows()
  if (!rows.length) return null

  const chartType = getEffectiveChartType()

  if (props.config) {
    if (chartType === 'pie') {
      const pieOption = buildPieOptionFromConfig(rows, props.config)
      if (pieOption) return pieOption
    }

    if (chartType === 'radar') {
      const radarOption = buildRadarOptionFromConfig(rows, props.config)
      if (radarOption) return radarOption
    }

    if (chartType === 'point') {
      const scatterOption = buildScatterOptionFromConfig(rows, props.config)
      if (scatterOption) return scatterOption
    }

    if (chartType === 'bar' || chartType === 'line' || chartType === 'area') {
      const cartesianOption = buildCartesianOptionFromConfig(rows, props.config, chartType)
      if (cartesianOption) return cartesianOption
    }
  }

  if (props.spec) {
    return buildOptionFromSpec(rows, props.spec, chartType)
  }

  return null
}

function ensureChartInstance() {
  if (!chartViewport.value) return null
  if (!chartInstance) {
    chartInstance = echarts.init(chartViewport.value, undefined, {
      renderer: 'canvas',
    })
  }
  return chartInstance
}

function disposeChart() {
  chartInstance?.dispose()
  chartInstance = null
}

function toggleFullscreen() {
  const element = chartContainer.value
  if (!element) return

  if (document.fullscreenElement) {
    void document.exitFullscreen()
    return
  }

  void element.requestFullscreen()
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

async function renderChart() {
  const option = buildChartOption()
  if (!option) {
    chartInstance?.clear()
    return
  }

  const instance = ensureChartInstance()
  if (!instance) return

  instance.setOption(option, true)
  instance.resize()
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
  if (!chartInstance) return
  const url = chartInstance.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: '#ffffff',
  })
  downloadUrl(url, normalizeFileName(fileName))
}

async function exportSvg(fileName = 'chart.svg') {
  if (!chartInstance) return

  const maybeSvgUrl = chartInstance.getDataURL({
    type: 'svg',
    backgroundColor: '#ffffff',
  } as any)

  if (typeof maybeSvgUrl === 'string' && maybeSvgUrl.startsWith('data:image/svg+xml')) {
    downloadUrl(maybeSvgUrl, normalizeFileName(fileName))
    return
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

watch(
  () => [
    props.spec,
    props.data,
    props.config,
    props.chartType,
    props.height,
    props.hideTitle,
  ],
  () => {
    scheduleRender()
  },
  { deep: true, immediate: true },
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

  disposeChart()
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

.empty-state p,
.empty-dialog {
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
  min-height: 300px;
  overflow: hidden;
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
