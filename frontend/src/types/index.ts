/** Pivot 配置类型定义（与后端 PivotConfig 对应） */

export interface FilterItem {
  field: string
  op: string
  value: any
  alias?: string
}

export interface AxisItem {
  field: string
  alias?: string
  group?: 'raw' | 'year' | 'quarter' | 'month' | 'week' | 'day' | 'hour'
  sort?: 'asc' | 'desc'
}

export interface LegendItem {
  field: string
  alias?: string
}

export interface ShowAs {
  type: 'normal' | 'column_percentage' | 'row_percentage' | 'total_percentage'
    | 'difference' | 'running_total' | 'rank_asc' | 'rank_desc'
  base_field?: string
  running_field?: string
  partition_field?: string
}

export interface ValueItem {
  id: string
  field?: string
  aggregation?: 'count' | 'sum' | 'avg' | 'min' | 'max' | 'count_distinct'
  alias?: string
  expr?: string
  show_as?: ShowAs
}

export interface FilterOnAgg {
  field: string
  op: string
  value: any
}

export interface TopN {
  enabled: boolean
  count: number
  by: string
  type: 'top' | 'bottom'
}

export interface OrderBy {
  field: string
  direction: 'asc' | 'desc'
}

export interface Pagination {
  page: number
  pageSize: number
}

export interface CalculatedField {
  name: string
  formula: string
}

export interface CalculatedItem {
  name: string
  field: string
  formula: string
}

export interface PivotConfig {
  filters: FilterItem[]
  axes: AxisItem[]
  legend: LegendItem[]
  values: ValueItem[]
  row_filters?: FilterOnAgg[]
  col_filters?: FilterOnAgg[]
  top_n?: TopN
  order_by?: OrderBy[]
  pagination?: Pagination
  grand_total?: boolean
  subtotals?: boolean
  chart_type?: string
  limit?: number
  having?: FilterOnAgg[]
  calculated_fields?: CalculatedField[]
  calculated_items?: CalculatedItem[]
}

export interface RecommendChartItem {
  type: string
  score: number
  reason: string
}

export interface RecommendChartResponse {
  recommendations: RecommendChartItem[]
  top: string
}

export interface PivotResponse {
  data: Record<string, any>[]
  columns: string[]
  total: number
  vega_spec: Record<string, any>
  config: PivotConfig
  sql?: string
  execution_time_ms: number
}

export interface FieldDef {
  name: string
  alias_cn: string
  data_type: string
  source_table: string
  description: string
  category: 'id' | 'dimension' | 'measure' | 'time' | 'status' | 'file' | 'ext'
  example_values?: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  vega_spec?: Record<string, any>
  pivot_config?: PivotConfig
}

/** 四象限拖拽区域类型 */
export type ZoneType = 'filters' | 'axes' | 'legend' | 'values'
