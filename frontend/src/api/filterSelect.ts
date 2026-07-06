import type { FilterItem } from '@/types'

export const FILTER_SELECT_API = 'http://127.0.0.1:8080/api2/pivot/select'

export interface FilterSelectDropdownItem {
  id?: string
  /** VIN */
  name: string
  /** 泛亚编号 */
  vinPatacId?: string
  /** RMU模块号 */
  rmuCode?: string
}

export function getFilterDropdownItemValue(item: FilterSelectDropdownItem): string {
  return String(item.id ?? item.name ?? '')
}

export function toFilterDropdownOption(
  item: FilterSelectDropdownItem,
  field?: string,
): { label: string; value: string } {
  const value = getFilterDropdownItemValue(item)
  let label = item.name
  if (field === 'vehicle' && item.vinPatacId) {
    label = `${item.vinPatacId}-${item.name}`
  }
  return { label, value }
}

export interface FilterSelectPayloadItem {
  field: string
  op: string
  value: unknown[]
  select_ts?: string
  select_order?: number
  filter_type?: string
}

export interface FilterSelectRequest {
  filters: FilterSelectPayloadItem[]
  focusField: string
  keyword?: string
}

export type FilterSelectResponse = FilterSelectResponseItem | FilterSelectResponseItem[]

export interface FilterSelectResponseItem {
  field: string
  dropDown?: FilterSelectDropdownItem[] | null
  startAlarmTime?: string
  endAlarmTime?: string
  signalList?: string[]
}

export async function fetchFilterSelectOptions(body: FilterSelectRequest): Promise<FilterSelectResponse> {
  const resp = await fetch(FILTER_SELECT_API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!resp.ok) {
    throw new Error(`筛选下拉接口请求失败: ${resp.status}`)
  }
  return resp.json()
}

/** UI 操作符 → 联动接口操作符 */
export function toSelectApiOp(op: string, field: string, filterType: string): string {
  if (filterType === 'date' && op === 'between') return 'between'
  const map: Record<string, string> = {
    '=': 'in',
    '!=': 'in',
    '>': 'gt',
    '>=': 'gte',
    '<': 'lt',
    '<=': 'lte',
    between: 'between',
    in: 'in',
  }
  return map[op] ?? op
}

/** 日期字符串归一化为 YYYY-MM-DD */
export function normalizeApiDate(val?: string): string {
  if (!val) return ''
  if (/^\d{4}-\d{2}-\d{2}/.test(val)) return val.slice(0, 10)
  const digits = val.replace(/\D/g, '')
  if (digits.length >= 8) {
    return `${digits.slice(0, 4)}-${digits.slice(4, 6)}-${digits.slice(6, 8)}`
  }
  return ''
}

/** 日期格式化为联动接口值，如 2026-07-05 */
export function formatDateForSelectApi(val: string): string {
  return normalizeApiDate(val)
}

/** 将日期限制在 [start, end] 范围内 */
export function clampDateToRange(dateStr: string, start: string, end: string): string {
  const d = normalizeApiDate(dateStr)
  if (!d) return start || end || ''
  if (start && d < start) return start
  if (end && d > end) return end
  return d
}

export function toSelectApiValue(item: FilterItem, filterType: string): unknown[] {
  const { field, op, value } = item

  if (filterType === 'string' && (field === 'task' || field === 'rule_name' || field === 'vehicle')) {
    const arr = Array.isArray(value) ? value : value != null && value !== '' ? [value] : []
    return arr.filter(v => v !== '' && v != null).map(String)
  }

  if (filterType === 'date') {
    if (op === 'between' && Array.isArray(value)) {
      return value.filter(v => v != null && v !== '').map(v => formatDateForSelectApi(String(v)))
    }
    if (value != null && value !== '') return [formatDateForSelectApi(String(value))]
    return []
  }

  if (filterType === 'number') {
    if (op === 'between' && Array.isArray(value)) {
      return value.filter(v => v != null && v !== '').map(v => Number(v))
    }
    if (value != null && value !== '') return [Number(value)]
    return []
  }

  if (op === 'between' && Array.isArray(value)) {
    return value.filter(v => v != null && v !== '')
  }
  if (Array.isArray(value)) {
    return value.filter(v => v !== '' && v != null)
  }
  if (value != null && value !== '') return [value]
  return []
}
