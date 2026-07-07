import type {
  AxisItem,
  CalculatedField,
  CalculatedItem,
  FieldDef,
  FilterItem,
  FilterOnAgg,
  OrderBy,
  Pagination,
  PivotConfig,
  RequestMeta,
  TopN,
  ValueItem,
} from '@/types'
import { normalizeApiDate } from '@/api/filterSelect'
import { NUMERIC_FILTER_FIELDS, STRING_FILTER_FIELDS, TIME_FILTER_FIELDS } from '@/constants/filterDropdown'

export interface TableGroupLike {
  table_name: string
  table_name_cn: string
  fields: FieldDef[]
}

export interface ImportedPivotConfigResult {
  config: PivotConfig
  warnings: string[]
}

const EXTRA_IMPORT_FIELDS: FieldDef[] = [
  {
    name: 'trigger_time',
    alias_cn: '触发时间',
    data_type: 'TIMESTAMP',
    source_table: '',
    description: '兼容外部透视查询请求的触发时间字段',
    category: 'time',
  },
]

const TIME_FIELDS = new Set<string>([...TIME_FILTER_FIELDS, 'trigger_time'])
const NUMERIC_FIELDS = new Set<string>(NUMERIC_FILTER_FIELDS)
const STRING_FIELDS = new Set<string>(STRING_FILTER_FIELDS)
const VALID_SHOW_AS_TYPES = new Set([
  'normal',
  'column_percentage',
  'row_percentage',
  'total_percentage',
  'difference',
  'running_total',
  'rank_asc',
  'rank_desc',
])
const VALID_TIME_AGGREGATIONS = new Set([
  'source',
  'day',
  'week',
  'month',
  'year',
  'quarter',
  'hour',
])
const VALID_CHART_TYPES = new Set(['bar', 'line', 'area', 'point', 'pie', 'radar'])

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}

function normalizeToken(value: unknown): string | undefined {
  if (value == null) return undefined
  const text = String(value).trim()
  if (!text) return undefined
  if (text === 'None' || text === 'null' || text === 'undefined') return undefined
  return text
}

function toBoolean(value: unknown, fallback = false): boolean {
  if (typeof value === 'boolean') return value
  const text = normalizeToken(value)?.toLowerCase()
  if (text === 'true') return true
  if (text === 'false') return false
  return fallback
}

function toPositiveInteger(value: unknown, fallback: number): number {
  const num = Number(value)
  return Number.isFinite(num) && num > 0 ? Math.trunc(num) : fallback
}

function normalizeDirection(value: unknown): 'asc' | 'desc' | undefined {
  const text = normalizeToken(value)?.toLowerCase()
  if (text === 'asc' || text === 'desc') return text
  return undefined
}

function inferFilterType(field: string, explicit: unknown, op: string, value: unknown): string {
  const explicitType = normalizeToken(explicit)
  if (explicitType) return explicitType
  if (TIME_FIELDS.has(field)) return 'date'
  if (NUMERIC_FIELDS.has(field)) return 'number'
  if (STRING_FIELDS.has(field)) return 'string'
  if (op === 'between') {
    const values = Array.isArray(value)
      ? value
      : typeof value === 'string' && value.includes(',')
        ? value.split(',')
        : []
    if (values.length >= 2 && values.every(item => !!normalizeApiDate(String(item ?? '')))) {
      return 'date'
    }
  }
  return ''
}

function normalizeDateValue(value: unknown): string {
  const text = normalizeToken(value) ?? ''
  return normalizeApiDate(text) || text
}

function normalizeFilterValue(field: string, op: string, filterType: string, value: unknown): any {
  if (op === 'between') {
    if (Array.isArray(value)) {
      if (filterType === 'date') return value.slice(0, 2).map(normalizeDateValue)
      if (filterType === 'number') return value.slice(0, 2).map(item => {
        const num = Number(item)
        return Number.isFinite(num) ? num : null
      })
      return value.slice(0, 2).map(item => normalizeToken(item) ?? '')
    }
    if (typeof value === 'string' && value.includes(',')) {
      return normalizeFilterValue(field, op, filterType, value.split(','))
    }
    return filterType === 'number' ? [null, null] : ['', '']
  }

  if (filterType === 'date') {
    if (Array.isArray(value)) return normalizeDateValue(value[0])
    return normalizeDateValue(value)
  }

  if (filterType === 'number') {
    const source = Array.isArray(value) ? value[0] : value
    const num = Number(source)
    return Number.isFinite(num) ? num : null
  }

  if (filterType === 'string') {
    if (Array.isArray(value)) return normalizeToken(value[0]) ?? ''
    return normalizeToken(value) ?? ''
  }

  if (Array.isArray(value)) {
    return value.map(item => String(item))
  }
  if (typeof value === 'string' && value.includes(',')) {
    return value
      .split(',')
      .map(item => item.trim())
      .filter(item => item !== '')
  }
  return normalizeToken(value) ? [String(value)] : ['']
}

function normalizeFilterItem(item: unknown, index: number): FilterItem | null {
  if (!isRecord(item)) return null
  const field = normalizeToken(item.field)
  if (!field) return null

  const op = normalizeToken(item.op) ?? 'in'
  const filterType = inferFilterType(field, item.filter_type, op, item.value)

  return {
    field,
    op,
    value: normalizeFilterValue(field, op, filterType, item.value),
    alias: normalizeToken(item.alias),
    select_ts: normalizeToken(item.select_ts) ?? '',
    select_order: toPositiveInteger(item.select_order, index + 1),
    filter_type: filterType,
  }
}

function normalizeAxisItem(item: unknown): AxisItem | null {
  if (!isRecord(item)) return null
  const field = normalizeToken(item.field)
  if (!field) return null

  const aggregation = normalizeToken(item.aggregation) ?? normalizeToken(item.group)
  const axis: AxisItem = {
    field,
    alias: normalizeToken(item.alias),
  }

  if (aggregation && TIME_FIELDS.has(field) && VALID_TIME_AGGREGATIONS.has(aggregation)) {
    axis.aggregation = aggregation as AxisItem['aggregation']
  }

  const sort = normalizeDirection(item.sort)
  if (sort) axis.sort = sort

  return axis
}

function normalizeLegendItem(item: unknown): { field: string; alias?: string } | null {
  if (!isRecord(item)) return null
  const field = normalizeToken(item.field)
  if (!field) return null
  return {
    field,
    alias: normalizeToken(item.alias),
  }
}

function normalizeShowAs(value: unknown) {
  if (!isRecord(value)) return undefined
  const type = normalizeToken(value.type)
  if (!type || !VALID_SHOW_AS_TYPES.has(type)) return undefined
  const normalizedType = type as NonNullable<ValueItem['show_as']>['type']
  return {
    type: normalizedType,
    base_field: normalizeToken(value.base_field),
    running_field: normalizeToken(value.running_field),
    partition_field: normalizeToken(value.partition_field),
  }
}

function normalizeValueItem(item: unknown, index: number): ValueItem | null {
  if (!isRecord(item)) return null

  const id = normalizeToken(item.id) ?? `val_${index + 1}`
  const field = normalizeToken(item.field)
  const aggregation = normalizeToken(item.aggregation) as ValueItem['aggregation'] | undefined
  const alias = normalizeToken(item.alias)
  const expr = normalizeToken(item.expr)

  return {
    id,
    field,
    aggregation,
    alias,
    expr,
    show_as: normalizeShowAs(item.show_as),
  }
}

function normalizeAggFilterItem(item: unknown): FilterOnAgg | null {
  if (!isRecord(item)) return null
  const field = normalizeToken(item.field)
  const op = normalizeToken(item.op)
  if (!field || !op) return null
  return {
    field,
    op,
    value: item.value,
  }
}

function normalizeAggFilterList(value: unknown): FilterOnAgg[] {
  if (!Array.isArray(value)) return []
  return value
    .map(normalizeAggFilterItem)
    .filter((item): item is FilterOnAgg => item !== null)
}

function normalizeCalculatedFields(value: unknown): CalculatedField[] {
  if (!Array.isArray(value)) return []
  return value
    .map(item => {
      if (!isRecord(item)) return null
      const name = normalizeToken(item.name)
      const formula = normalizeToken(item.formula)
      if (!name || !formula) return null
      return { name, formula }
    })
    .filter((item): item is CalculatedField => item !== null)
}

function normalizeCalculatedItems(value: unknown): CalculatedItem[] {
  if (!Array.isArray(value)) return []
  return value
    .map(item => {
      if (!isRecord(item)) return null
      const name = normalizeToken(item.name)
      const field = normalizeToken(item.field)
      const formula = normalizeToken(item.formula)
      if (!name || !field || !formula) return null
      return { name, field, formula }
    })
    .filter((item): item is CalculatedItem => item !== null)
}

function normalizeTopN(value: unknown): TopN | undefined {
  if (!isRecord(value)) return undefined
  const by = normalizeToken(value.by)
  if (!by) return undefined
  return {
    enabled: toBoolean(value.enabled, false),
    count: toPositiveInteger(value.count, 10),
    by,
    type: normalizeToken(value.type) === 'bottom' ? 'bottom' : 'top',
  }
}

function normalizePagination(value: unknown): Pagination | undefined {
  if (!isRecord(value)) return undefined
  return {
    page: toPositiveInteger(value.page, 1),
    pageSize: toPositiveInteger(value.pageSize, 100),
  }
}

function normalizeOrderBy(
  value: unknown,
  fallbackField: string | undefined,
  warnings: string[],
): { orderBy: OrderBy[]; requestMeta?: RequestMeta } {
  if (Array.isArray(value)) {
    const orderBy = value
      .map(item => {
        if (!isRecord(item)) return null
        const field = normalizeToken(item.field)
        const direction = normalizeDirection(item.direction)
        if (!field || !direction) return null
        return { field, direction }
      })
      .filter((item): item is OrderBy => item !== null)

    if (orderBy.length > 0) {
      return {
        orderBy,
        requestMeta: {
          imported_from: 'query_request',
          order_by_mode: 'array',
        },
      }
    }
  }

  const direction = normalizeDirection(value)
  if (!direction) return { orderBy: [] }
  if (!fallbackField) {
    warnings.push('检测到字符串形式的 order_by，但没有可回显的排序字段，已仅保留排序方向。')
    return {
      orderBy: [],
      requestMeta: {
        imported_from: 'query_request',
        order_by_mode: 'direction',
      },
    }
  }

  return {
    orderBy: [{ field: fallbackField, direction }],
    requestMeta: {
      imported_from: 'query_request',
      order_by_mode: 'direction',
    },
  }
}

function getImportSource(payload: unknown): Record<string, unknown> {
  if (isRecord(payload) && isRecord(payload.config)) return payload.config
  return isRecord(payload) ? payload : {}
}

export function injectExtraImportFields<T extends TableGroupLike>(groups: T[]): T[] {
  if (!Array.isArray(groups) || groups.length === 0) return groups

  const nextGroups = groups.map(group => ({
    ...group,
    fields: [...group.fields],
  })) as T[]

  const existingFields = new Set(
    nextGroups.flatMap(group => group.fields.map(field => field.name)),
  )
  const missingFields = EXTRA_IMPORT_FIELDS.filter(field => !existingFields.has(field.name))

  if (missingFields.length === 0) return nextGroups

  nextGroups[0].fields.push(...missingFields)
  return nextGroups
}

export function normalizeImportedPivotRequest(payload: unknown): ImportedPivotConfigResult {
  const warnings: string[] = []
  const source = getImportSource(payload)

  const filters = Array.isArray(source.filters)
    ? source.filters
      .map((item, index) => normalizeFilterItem(item, index))
      .filter((item): item is FilterItem => item !== null)
    : []

  const axes = Array.isArray(source.axes)
    ? source.axes
      .map(normalizeAxisItem)
      .filter((item): item is AxisItem => item !== null)
    : []

  const legend = Array.isArray(source.legend)
    ? source.legend
      .map(normalizeLegendItem)
      .filter((item): item is { field: string; alias?: string } => item !== null)
    : []

  const values = Array.isArray(source.values)
    ? source.values
      .map((item, index) => normalizeValueItem(item, index))
      .filter((item): item is ValueItem => item !== null)
    : []

  const fallbackOrderField = values[0]?.alias || values[0]?.field || axes[0]?.alias || axes[0]?.field
  const { orderBy, requestMeta } = normalizeOrderBy(source.order_by, fallbackOrderField, warnings)

  const chartType = normalizeToken(source.chart_type)
  const config: PivotConfig = {
    filters,
    axes,
    legend,
    values,
    row_filters: normalizeAggFilterList(source.row_filters),
    col_filters: normalizeAggFilterList(source.col_filters),
    order_by: orderBy,
    pagination: normalizePagination(source.pagination),
    grand_total: toBoolean(source.grand_total, false),
    subtotals: toBoolean(source.subtotals, false),
    chart_type: chartType && VALID_CHART_TYPES.has(chartType) ? chartType : 'bar',
    limit: toPositiveInteger(source.limit, 1000),
    having: normalizeAggFilterList(source.having),
    top_n: normalizeTopN(source.top_n),
    calculated_fields: normalizeCalculatedFields(source.calculated_fields),
    calculated_items: normalizeCalculatedItems(source.calculated_items),
    request_meta: requestMeta,
  }

  return { config, warnings }
}
