<template>
  <div class="config-panel">
    <!-- 字段列表（固定字段 + 信号字段并排，不收拢） -->
    <div class="panel-section">
      <div class="section-header">
        <span class="section-title">报表配置</span>
      </div>
      <div class="section-body">
        <div class="field-search">
          <el-input v-model="search" placeholder="搜索字段..." size="small" clearable prefix-icon="Search" />
        </div>
        <div class="field-groups-row">
          <div v-if="fixedFieldGroup" class="field-group-col">
            <div class="field-group-label">
              <span>{{ fixedFieldGroup.table_name_cn }}</span>
              <el-tag size="small" type="info" round>{{ fixedFieldGroup.fields.length }}</el-tag>
            </div>
            <div class="field-items">
              <div
                v-for="field in fixedFieldGroup.fields" :key="field.name"
                class="field-item" draggable="true"
                @dragstart="onDragStart($event, field)"
              >
                <span class="field-name">{{ field.alias_cn }}</span>
              </div>
            </div>
          </div>
          <div class="field-group-col">
            <div class="field-group-label">
              <span>信号列表</span>
              <el-tag size="small" type="info" round>{{ filteredSignalFields.length }}</el-tag>
            </div>
            <div class="field-items">
              <div v-if="filteredSignalFields.length === 0" class="zone-placeholder">暂无信号</div>
              <div
                v-for="field in filteredSignalFields" :key="field.name"
                class="field-item" draggable="true"
                @dragstart="onDragStart($event, field, true)"
              >
                <span class="field-name">{{ field.alias_cn }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="panel-section config-section">
      <div class="section-body config-body">
        <!-- 四象限拖拽区 2x2 网格 -->
          <!-- 筛选器 -->
          <div class="zone-card zone-card--filters" @dragover.prevent @drop="onDrop($event, 'filters')">
            <div class="zone-label">
              <el-icon size="14"><Filter /></el-icon> 筛选器 <el-tag v-if="filters.length" size="small" round>{{ filters.length }}</el-tag>
            </div>
            <div class="zone-body" :class="{ empty: filters.length === 0 }">
              <div v-if="filters.length === 0" class="zone-placeholder">拖入字段</div>
              <div
                v-for="(item, i) in filters" :key="i"
                class="zone-item"
                :class="{ 'zone-item--date-between': isDateBetweenFilter(item) }"
              >
                <span class="zone-item-field" :title="item.alias || item.field">{{ item.alias || item.field }}</span>
                <template v-if="isTimeFilterField(item.field)">
                  <el-select
                    :model-value="item.op"
                    size="small"
                    style="width:70px"
                    @update:model-value="(op) => onTimeFilterOpChange(item, op)"
                  >
                    <el-option label="=" value="=" /><el-option label="!=" value="!=" />
                    <el-option label=">" value=">" /><el-option label=">=" value=">=" />
                    <el-option label="&lt;" value="<" /><el-option label="&lt;=" value="<=" />
                    <el-option label="between" value="between" />
                  </el-select>
                  <el-date-picker
                    v-if="item.op !== 'between'"
                    v-model="item.value"
                    type="date"
                    value-format="YYYY-MM-DD"
                    size="small"
                    class="filter-date-picker"
                    placeholder="选择日期"
                    :disabled-date="getDisabledDateForField(item.field)"
                    @change="() => onFilterFieldChange(item)"
                  />
                  <div v-else-if="Array.isArray(item.value)" class="between-inputs">
                    <el-date-picker
                      v-model="item.value[0]"
                      type="date"
                      value-format="YYYY-MM-DD"
                      size="small"
                      class="filter-date-picker-sm"
                      placeholder="开始"
                      :disabled-date="getDisabledDateForField(item.field)"
                      @change="() => onFilterFieldChange(item)"
                    />
                    <span>~</span>
                    <el-date-picker
                      v-model="item.value[1]"
                      type="date"
                      value-format="YYYY-MM-DD"
                      size="small"
                      class="filter-date-picker-sm"
                      placeholder="结束"
                      :disabled-date="getDisabledDateForField(item.field)"
                      @change="() => onFilterFieldChange(item)"
                    />
                  </div>
                </template>
                <template v-else-if="isNumericFilterField(item.field)">
                  <el-select
                    :model-value="item.op"
                    size="small"
                    style="width:70px"
                    @update:model-value="(op) => onNumericFilterOpChange(item, op)"
                  >
                    <el-option label="=" value="=" /><el-option label="!=" value="!=" />
                    <el-option label=">" value=">" /><el-option label=">=" value=">=" />
                    <el-option label="&lt;" value="<" /><el-option label="&lt;=" value="<=" />
                    <el-option label="between" value="between" />
                  </el-select>
                  <el-input-number
                    v-if="item.op !== 'between'"
                    v-model="item.value"
                    :precision="1"
                    :step="0.1"
                    size="small"
                    class="filter-number-input"
                    controls-position="right"
                    :controls="false"
                    placeholder="值"
                    @blur="() => onFilterFieldChange(item)"
                  />
                  <div v-else-if="Array.isArray(item.value)" class="between-inputs">
                    <el-input-number
                      v-model="item.value[0]"
                      :precision="1"
                      :step="0.1"
                      size="small"
                      class="filter-number-input-sm"
                      :controls="false"
                      controls-position="right"
                      placeholder="最小"
                      @blur="() => onFilterFieldChange(item)"
                    />
                    <span>~</span>
                    <el-input-number
                      v-model="item.value[1]"
                      :precision="1"
                      :controls="false"
                      :step="0.1"
                      size="small"
                      class="filter-number-input-sm"
                      controls-position="right"
                      placeholder="最大"
                      @blur="() => onFilterFieldChange(item)"
                    />
                  </div>
                </template>
                <template v-else-if="isStringFilterField(item.field)">
                  <el-select
                    :model-value="item.op"
                    size="small"
                    style="width:70px"
                    @update:model-value="(op) => onStringFilterOpChange(item, op)"
                  >
                    <el-option label="=" value="=" /><el-option label="!=" value="!=" />
                    <el-option label=">" value=">" /><el-option label=">=" value=">=" />
                    <el-option label="&lt;" value="<" /><el-option label="&lt;=" value="<=" />
                    <el-option label="between" value="between" />
                  </el-select>
                  <el-input
                    v-if="item.op !== 'between'"
                    v-model="item.value"
                    size="small"
                    class="filter-text-input"
                    placeholder="值"
                    @blur="() => onFilterFieldChange(item)"
                  />
                  <div v-else-if="Array.isArray(item.value)" class="between-inputs">
                    <el-input v-model="item.value[0]" size="small" class="filter-text-input-sm" placeholder="开始" @blur="() => onFilterFieldChange(item)" />
                    <span>~</span>
                    <el-input v-model="item.value[1]" size="small" class="filter-text-input-sm" placeholder="结束" @blur="() => onFilterFieldChange(item)" />
                  </div>
                </template>
                <template v-else-if="isApiDropdownField(item.field)">
                  <el-select
                    :model-value="item.value"
                    multiple
                    collapse-tags
                    collapse-tags-tooltip
                    size="small"
                    class="filter-value-select"
                    placeholder="选择值"
                    @update:model-value="(val: string[]) => onApiFilterMultiChange(item, val)"
                  >
                    <el-option
                      v-for="opt in getFilterOptions(item.field)"
                      :key="opt.value === '' ? '__all__' : opt.value"
                      :label="opt.label"
                      :value="opt.value"
                    />
                  </el-select>
                </template>
                <template v-else>
                  <el-select
                    :model-value="item.value"
                    multiple
                    collapse-tags
                    collapse-tags-tooltip
                    size="small"
                    class="filter-value-select"
                    placeholder="选择值"
                    @update:model-value="(val: string[]) => onFilterMultiChange(item, val)"
                  >
                    <el-option
                      v-for="opt in getFilterOptions(item.field)"
                      :key="opt.value === '' ? '__all__' : opt.value"
                      :label="opt.label"
                      :value="opt.value"
                    />
                  </el-select>
                </template>
                <el-button size="small" type="danger" :icon="Delete" circle @click="removeItem(i, 'filters')" />
                <el-button
                  v-if="isResultViewField(item.field)"
                  size="small"
                  type="primary"
                  :icon="Document"
                  style="margin-left: 1px;"
                  circle
                  title="查看结果列表"
                  @click="resultDialogVisible = true"
                />
              </div>
            </div>
          </div>
        <div class="zones-grid">
          <!-- 轴 -->
          <div class="zone-card" @dragover.prevent @drop="onDrop($event, 'axes')">
            <div class="zone-label">
              <el-icon size="14"><DataAnalysis /></el-icon> 轴 <el-tag v-if="axes.length" size="small" round>{{ axes.length }}</el-tag>
            </div>
            <div class="zone-body" :class="{ empty: axes.length === 0 }">
              <div v-if="axes.length === 0" class="zone-placeholder">拖入字段</div>
              <div v-for="(item, i) in axes" :key="i" class="zone-item">
                <span class="zone-item-field">{{ item.alias || item.field }}</span>
                <el-select
                  v-if="isTimeFilterField(item.field)"
                  :model-value="item.aggregation ?? 'source'"
                  size="small"
                  style="width:68px"
                  @update:model-value="(v) => onAxisAggregationChange(item, v)"
                >
                  <el-option label="原始值" value="source" />
                  <el-option label="天" value="day" />
                  <el-option label="周" value="week" />
                  <el-option label="月" value="month" />
                </el-select>
                <el-button size="small" type="danger" :icon="Delete" circle @click="removeItem(i, 'axes')" />
              </div>
            </div>
          </div>
          <!-- 图例 -->
          <div class="zone-card" @dragover.prevent @drop="onDrop($event, 'legend')">
            <div class="zone-label">
              <el-icon size="14"><PieChart /></el-icon> 图例 <el-tag v-if="legend.length" size="small" round>{{ legend.length }}</el-tag>
            </div>
            <div class="zone-body" :class="{ empty: legend.length === 0 }">
              <div v-if="legend.length === 0" class="zone-placeholder">拖入字段</div>
              <div v-for="(item, i) in legend" :key="i" class="zone-item">
                <span class="zone-item-field">{{ item.alias || item.field }}</span>
                <el-button size="small" type="danger" :icon="Delete" circle @click="removeItem(i, 'legend')" />
              </div>
            </div>
          </div>
          
        </div>
<!-- 值 -->
          <div class="zone-card value" @dragover.prevent @drop="onDrop($event, 'values')">
            <div class="zone-label">
              <el-icon size="14"><Histogram /></el-icon> 值 <el-tag v-if="values.length" size="small" round>{{ values.length }}</el-tag>
            </div>
            <div class="zone-body" :class="{ empty: values.length === 0 }">
              <div v-if="values.length === 0" class="zone-placeholder">拖入字段</div>
              <div v-for="(item, i) in values" :key="i" class="zone-item">
                <span class="zone-item-field">{{ item.alias || item.field }}</span>
                <el-select v-model="item.aggregation" size="small" style="width:65px">
                  <el-option label="计数" value="count" /><el-option label="求和" value="sum" />
                  <el-option label="平均" value="avg" /><el-option label="最大" value="max" /><el-option label="最小" value="min" />
                </el-select>
                <el-select v-model="showAsMap[i]" size="small" style="width:75px" placeholder="显示" @change="(v:string) => onShowAsChange(i, v)">
                  <el-option label="原值" value="normal" />
                  <el-option label="列占比" value="column_percentage" />
                  <el-option label="占比" value="total_percentage" />
                  <el-option label="累计" value="running_total" />
                  <el-option label="排名" value="rank_desc" />
                </el-select>
                <el-button size="small" type="danger" :icon="Delete" circle @click="removeItem(i, 'values')" />
              </div>
            </div>
          </div>
        <!-- 排序 + Limit（在按钮上方） -->
        <div class="extra-row">
          <div class="extra-item">
            <label>排序</label>
            <el-select
              v-model="sortField"
              multiple
              collapse-tags
              collapse-tags-tooltip
              size="small"
              clearable
              placeholder="字段"
              style="width:160px"
            >
              <el-option v-for="o in sortOptions" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-select v-model="sortDir" size="small" style="width:60px">
              <el-option label="降序" value="desc" />
              <el-option label="升序" value="asc" />
            </el-select>
          </div>
          <!-- <div class="extra-item">
            <label>Limit</label>
            <el-input-number v-model="limitVal" :min="1" :max="100000" size="small" controls-position="right" style="width:90px" />
          </div> -->
          <div class="extra-item">
            <label>图表</label>
            <el-select v-model="chartType" size="small" style="width:90px">
              <el-option label="柱状图" value="bar" />
              <el-option label="折线图" value="line" />
              <el-option label="波形图" value="area" />
              <el-option label="散点图" value="point" />
              <el-option label="饼状图" value="pie" />
              <el-option label="雷达图" value="radar" />
            </el-select>
          </div>
        </div>

        <!-- HAVING 设置 -->
        <div v-if="false" class="having-section">
          <div class="having-head">
            <label>HAVING</label>
            <el-button size="small" link type="primary" @click="addHaving">+ 添加</el-button>
          </div>
          <div class="having-items">
<div v-if="having.length === 0" class="having-empty">无 HAVING 条件</div>
            <div v-for="(h, i) in having" :key="i" class="having-row">
              <el-input v-model="h.field" size="small" placeholder="字段/别名" style="width:80px" />
              <el-select v-model="h.op" size="small" style="width:60px">
                <el-option label="=" value="=" /><el-option label="!=" value="!=" />
                <el-option label=">" value=">" /><el-option label=">=" value=">=" />
                <el-option label="&lt;" value="<" /><el-option label="&lt;=" value="<=" />
              </el-select>
              <el-input v-model="h.value" size="small" placeholder="值" style="width:80px" />
              <el-button size="small" type="danger" :icon="Delete" circle @click="removeHaving(i)" />
            </div>
          </div>
        </div>

        <!-- 操作按钮（在最下边） -->
        <div class="zone-actions">
          <el-button size="small" type="primary" :loading="loading" @click="handleQuery">加载报表数据</el-button>
          <el-button size="small" @click="handleClear">清空</el-button>
        </div>
      </div>
    </div>
  </div>

  <ResultListDialog v-model="resultDialogVisible" />
</template>

<script setup lang="ts">
import { ref, reactive, computed, toRef, onBeforeUnmount, onMounted, watch } from 'vue'
import { Filter, DataAnalysis, PieChart, Histogram, Delete, Document } from '@element-plus/icons-vue'
import type {
  FieldDef,
  ZoneType,
  FilterItem,
  AxisItem,
  LegendItem,
  ValueItem,
  PivotConfig,
  RecommendChartResponse,
} from '@/types'
import {
  TIME_FILTER_FIELDS,
  NUMERIC_FILTER_FIELDS,
  STRING_FILTER_FIELDS,
  API_FILTER_FIELDS,
  API_DROPDOWN_FILTER_FIELDS,
  STATIC_DROPDOWN_DATA,
  SIGNAL_TRIGGER_FILTER_FIELDS,
} from '@/constants/filterDropdown'
import {
  fetchFilterSelectOptions,
  toSelectApiOp,
  toSelectApiValue,
  normalizeApiDate,
  clampDateToRange,
  type FilterSelectResponseItem,
} from '@/api/filterSelect'
import { RESULT_VIEW_FIELDS } from '@/constants/resultList'
import ResultListDialog from '@/components/ResultListDialog.vue'

interface DropdownOption {
  label: string
  value: string
}

const dropdownCache = reactive<Record<string, DropdownOption[]>>({})
const alarmTimeRange = reactive({ start: '', end: '' })
const signalFields = ref<FieldDef[]>([])
const resultDialogVisible = ref(false)
let filterSelectRequestId = 0
let signalListRequestId = 0
const latestRecommendedTop = ref<string | null>(null)
const latestRecommendKey = ref('')
let recommendTimer: ReturnType<typeof setTimeout> | null = null
let recommendRequestId = 0

export interface TableGroup {
  table_name: string
  table_name_cn: string
  fields: FieldDef[]
}

// ========== 唯一外部参数 ==========
const props = defineProps<{
  api: (config: any) => Promise<any>
}>()

// ========== stateData：全部内部状态 ==========
const stateData = reactive({
  // 字段列表
  groups: [] as TableGroup[],
  // 四象限
  filters: [] as FilterItem[],
  axes: [] as AxisItem[],
  legend: [] as LegendItem[],
  values: [] as ValueItem[],
  // 排序 / Limit / HAVING / 图表类型
  sortField: [] as string[],
  sortDir: 'desc' as string,
  limitVal: 1000,
  having: [] as { field: string; op: string; value: any }[],
  chartType: 'bar' as string,
  // 搜索
  search: '',
  // 显示方式
  showAsMap: {} as Record<number, string>,
  // 加载状态
  loading: false,
})

// 模板别名（保持对 stateData 的响应式引用）
const filters = computed(() => stateData.filters)
const axes = computed(() => stateData.axes)
const legend = computed(() => stateData.legend)
const values = computed(() => stateData.values)
const loading = computed(() => stateData.loading)
const search = toRef(stateData, 'search')
const showAsMap = stateData.showAsMap as Record<number, string>

// sortField / sortDir / limitVal / chartType（v-model 需要 ref）
const sortField = toRef(stateData, 'sortField')
const sortDir = toRef(stateData, 'sortDir')
const limitVal = toRef(stateData, 'limitVal')
const chartType = toRef(stateData, 'chartType')
const having = toRef(stateData, 'having')

// 排序选项（从 axes + values 推导）
const sortOptions = computed(() => [
  ...stateData.axes.map(a => ({ label: a.alias || a.field, value: a.alias || a.field })),
  ...stateData.values.map(v => ({ label: v.alias || `${v.aggregation?.toUpperCase() || ''}(${v.field})`, value: v.alias || v.field })),
])

// 左侧固定字段组（api/fields 第一个）
const fixedFieldGroup = computed(() => {
  const first = stateData.groups[0]
  if (!first) return null
  if (!stateData.search) return first
  const q = stateData.search.toLowerCase()
  const fields = first.fields.filter(f =>
    f.alias_cn.toLowerCase().includes(q) || f.name.toLowerCase().includes(q),
  )
  if (fields.length === 0) return null
  return { ...first, fields }
})

// 右侧信号列表
const filteredSignalFields = computed(() => {
  if (!stateData.search) return signalFields.value
  const q = stateData.search.toLowerCase()
  return signalFields.value.filter(f =>
    f.alias_cn.toLowerCase().includes(q) || f.name.toLowerCase().includes(q),
  )
})

// ========== 方法 ==========

function isSignalTriggerField(field: string): boolean {
  return (SIGNAL_TRIGGER_FILTER_FIELDS as readonly string[]).includes(field)
}

function toSignalFieldDef(name: string): FieldDef {
  return {
    name,
    alias_cn: name,
    category: 'dimension',
    data_type: 'string',
    source_table: '',
    description: '',
  }
}

function pruneStaleSignalItems(validNames: Set<string>, removedNames: string[]) {
  const isStale = (item: { field?: string; isSignal?: boolean }) =>
    !!item.isSignal && !!item.field && !validNames.has(item.field)

  const prevFilterCount = stateData.filters.length
  stateData.filters = stateData.filters.filter(f => !isStale(f))
  if (stateData.filters.length !== prevFilterCount) {
    syncFilterSelectOrders()
  }

  stateData.axes = stateData.axes.filter(a => !isStale(a))
  stateData.legend = stateData.legend.filter(l => !isStale(l))
  stateData.values = stateData.values.filter(v => !isStale(v))

  if (removedNames.length > 0) {
    const removedSet = new Set(removedNames)
    stateData.sortField = stateData.sortField.filter(sf => !removedSet.has(sf))
    stateData.having = stateData.having.filter(h => !removedSet.has(h.field))
  }
}

async function refreshSignalList() {
  const prevNames = signalFields.value.map(f => f.name)

  if (!stateData.filters.some(f => isSignalTriggerField(f.field))) {
    signalFields.value = []
    if (prevNames.length > 0) {
      pruneStaleSignalItems(new Set(), prevNames)
    }
    return
  }

  const requestId = ++signalListRequestId
  try {
    const resp = await fetchFilterSelectOptions({
      filters: buildSelectApiFilters(),
      focusField: 'signal',
    })
    if (requestId !== signalListRequestId) return

    const item = Array.isArray(resp)
      ? resp.find(r => r.field === 'signal') ?? resp[0]
      : resp

    const newNames = item?.signalList ?? []
    const validSet = new Set(newNames)
    const removedNames = prevNames.filter(n => !validSet.has(n))

    signalFields.value = newNames.map(toSignalFieldDef)

    if (removedNames.length > 0) {
      pruneStaleSignalItems(validSet, removedNames)
    }
  } catch (e) {
    console.error('[ConfigPanel] 获取信号列表失败', e)
  }
}

function isTimeFilterField(field: string): boolean {
  return (TIME_FILTER_FIELDS as readonly string[]).includes(field)
}

function isDateBetweenFilter(item: FilterItem): boolean {
  return isTimeFilterField(item.field) && item.op === 'between' && Array.isArray(item.value)
}

function isNumericFilterField(field: string): boolean {
  return (NUMERIC_FILTER_FIELDS as readonly string[]).includes(field)
}

function isStringFilterField(field: string): boolean {
  return (STRING_FILTER_FIELDS as readonly string[]).includes(field)
}

function isApiFilterField(field: string): boolean {
  return (API_FILTER_FIELDS as readonly string[]).includes(field)
}

function isApiDropdownField(field: string): boolean {
  return (API_DROPDOWN_FILTER_FIELDS as readonly string[]).includes(field)
}

function isStaticDropdownField(field: string): boolean {
  return !isTimeFilterField(field) && !isNumericFilterField(field) && !isStringFilterField(field) && !isApiDropdownField(field)
}

function isResultViewField(field: string): boolean {
  return (RESULT_VIEW_FIELDS as readonly string[]).includes(field)
}

function getFilterType(field: string): string {
  if (isTimeFilterField(field)) return 'date'
  if (isNumericFilterField(field)) return 'number'
  return 'string'
}

function syncFilterSelectOrders() {
  stateData.filters.forEach((item, index) => {
    item.select_order = index + 1
    item.filter_type = item.filter_type || getFilterType(item.field)
  })
}

function touchFilterSelectTs(item: FilterItem) {
  item.select_ts = String(Date.now())
}

function buildSelectApiFilters(): FilterItem[] {
  syncFilterSelectOrders()
  return stateData.filters.map(item => {
    const filterType = item.filter_type || getFilterType(item.field)
    return {
      field: item.field,
      op: toSelectApiOp(item.op, item.field, filterType),
      value: toSelectApiValue(item, filterType),
      select_ts: item.select_ts ?? '',
      select_order: item.select_order ?? 0,
      filter_type: filterType,
    }
  })
}

function applyAlarmTimeRange(startAlarmTime?: string, endAlarmTime?: string) {
  if (!startAlarmTime && !endAlarmTime) return
  alarmTimeRange.start = normalizeApiDate(startAlarmTime)
  alarmTimeRange.end = normalizeApiDate(endAlarmTime)
  clampAlarmTimeFilterValue()
}

function clampAlarmTimeFilterValue() {
  const item = stateData.filters.find(f => f.field === 'alarm_time')
  if (!item) return
  const { start, end } = alarmTimeRange
  if (!start && !end) return

  if (item.op === 'between' && Array.isArray(item.value)) {
    let v0 = item.value[0] ? clampDateToRange(String(item.value[0]), start, end) : (start || end || '')
    let v1 = item.value[1] ? clampDateToRange(String(item.value[1]), start, end) : (end || start || '')
    if (v0 && v1 && v0 > v1) v1 = v0
    item.value = [v0, v1]
    return
  }

  if (item.value) {
    item.value = clampDateToRange(String(item.value), start, end)
  } else if (start) {
    item.value = start
  }
}

// function intersectFilterDropdownValues(field: string) {
//   const item = stateData.filters.find(f => f.field === field)
//   if (!item || !isApiDropdownField(field) || !Array.isArray(item.value)) return
//
//   const validIds = new Set(
//     (dropdownCache[field] ?? []).map(o => o.value).filter(v => v !== ''),
//   )
//   const matched = item.value.filter(v => v !== '' && validIds.has(String(v)))
//   item.value = matched.length > 0 ? matched : ['']
// }

function getDisabledDateForField(field: string) {
  if (field !== 'alarm_time') return () => false
  return (date: Date) => {
    const { start, end } = alarmTimeRange
    if (!start && !end) return false
    const y = date.getFullYear()
    const m = String(date.getMonth() + 1).padStart(2, '0')
    const d = String(date.getDate()).padStart(2, '0')
    const current = `${y}-${m}-${d}`
    if (start && current < start) return true
    if (end && current > end) return true
    return false
  }
}

function applyFilterSelectResponseItem(resp: FilterSelectResponseItem) {
  applyAlarmTimeRange(resp.startAlarmTime, resp.endAlarmTime)

  if (isApiDropdownField(resp.field)) {
    dropdownCache[resp.field] = [
      { label: '全部', value: '' },
      ...(resp.dropDown ?? []).map(item => ({ label: item.name, value: item.id })),
    ]
    // intersectFilterDropdownValues(resp.field)
  }
}

async function refreshFilterSelectOptions(focusField: string) {
  if (!isApiFilterField(focusField) && !stateData.filters.some(f => isApiFilterField(f.field))) return

  const requestId = ++filterSelectRequestId
  try {
    const resp = await fetchFilterSelectOptions({
      filters: buildSelectApiFilters(),
      focusField,
    })
    if (requestId !== filterSelectRequestId) return

    if (Array.isArray(resp)) {
      resp.forEach(item => applyFilterSelectResponseItem(item))
    } else {
      applyFilterSelectResponseItem(resp)
    }
  } catch (e) {
    console.error('[ConfigPanel] 获取筛选联动数据失败', e)
  }
}

function onFilterFieldChange(item: FilterItem) {
  touchFilterSelectTs(item)
  syncFilterSelectOrders()
  refreshFilterSelectOptions(item.field)
  if (isSignalTriggerField(item.field)) {
    refreshSignalList()
  }
}

function getFilterOptions(field: string): DropdownOption[] {
  return dropdownCache[field] ?? [{ label: '全部', value: '' }]
}

async function loadFilterDropdown(field: string) {
  if (isApiDropdownField(field)) {
    await refreshFilterSelectOptions(field)
    return
  }
  if (dropdownCache[field]) return

  const labels = STATIC_DROPDOWN_DATA[field] ?? []
  dropdownCache[field] = [
    { label: '全部', value: '' },
    ...labels.map((label, i) => ({ label, value: String(i) })),
  ]
}

function onFilterMultiChange(item: FilterItem, val: string[]) {
  const prev: string[] = Array.isArray(item.value) ? [...item.value] : ['']

  if (val.length === 0) {
    item.value = ['']
    return
  }

  const added = val.filter(v => !prev.includes(v))

  if (added.includes('')) {
    item.value = ['']
  } else if (added.length > 0 && prev.includes('')) {
    item.value = val.filter(v => v !== '')
  } else {
    item.value = val
  }
}

function onApiFilterMultiChange(item: FilterItem, val: string[]) {
  onFilterMultiChange(item, val)
  onFilterFieldChange(item)
}

function formatNumericValue(val: unknown): string {
  if (val == null || val === '') return ''
  const num = Number(val)
  return Number.isNaN(num) ? '' : num.toFixed(1)
}

function parseNumericValue(val: unknown): number | null {
  if (val == null || val === '') return null
  const num = Number(val)
  return Number.isNaN(num) ? null : num
}

function getFieldAliasCn(fieldName: string): string {
  for (const group of stateData.groups) {
    const found = group.fields.find(f => f.name === fieldName)
    if (found) return found.alias_cn
  }
  return fieldName
}

function ensureFilterAlias(item: FilterItem): FilterItem {
  return { ...item, alias: item.alias || getFieldAliasCn(item.field) }
}

function normalizeRangeFilterValue(item: FilterItem): FilterItem {
  if (item.op === 'between') {
    const v = item.value
    if (Array.isArray(v)) {
      return { ...item, value: [normalizeApiDate(String(v[0] ?? '')) || '', normalizeApiDate(String(v[1] ?? '')) || ''] }
    }
    if (typeof v === 'string' && v.includes(',')) {
      const [a, b] = v.split(',')
      return { ...item, value: [normalizeApiDate(a) || '', normalizeApiDate(b) || ''] }
    }
    return { ...item, value: ['', ''] }
  }
  const normalized = normalizeApiDate(typeof item.value === 'string' ? item.value : '')
  return { ...item, value: normalized || '' }
}

function ensureFilterMeta(item: FilterItem, order: number): FilterItem {
  return {
    ...ensureFilterAlias(item),
    select_ts: item.select_ts ?? '',
    select_order: item.select_order ?? order,
    filter_type: item.filter_type ?? getFilterType(item.field),
  }
}

function normalizeFilterForUI(item: FilterItem, order = 1): FilterItem {
  const base = ensureFilterMeta(item, order)
  if (isTimeFilterField(base.field) || isStringFilterField(base.field)) {
    return ensureFilterMeta(normalizeRangeFilterValue(base), order)
  }
  if (isNumericFilterField(base.field)) {
    if (base.op === 'between') {
      const v = base.value
      if (Array.isArray(v)) {
        return ensureFilterMeta({ ...base, value: [parseNumericValue(v[0]), parseNumericValue(v[1])] }, order)
      }
      if (typeof v === 'string' && v.includes(',')) {
        const [a, b] = v.split(',')
        return ensureFilterMeta({ ...base, value: [parseNumericValue(a), parseNumericValue(b)] }, order)
      }
      return ensureFilterMeta({ ...base, value: [null, null] }, order)
    }
    return ensureFilterMeta({ ...base, value: parseNumericValue(base.value) }, order)
  }
  const op = base.op === '=' ? 'in' : (base.op || 'in')
  let values: string[]
  if (Array.isArray(base.value)) {
    values = base.value.map(String)
  } else if (typeof base.value === 'string' && base.value !== '') {
    values = base.value.split(',').map(s => s.trim())
  } else {
    values = ['']
  }
  if (values.length === 0) values = ['']
  return ensureFilterMeta({ ...base, op, value: values }, order)
}

function serializeFilterForApi(item: FilterItem): FilterItem {
  const filterType = item.filter_type ?? getFilterType(item.field)
  const meta = {
    select_ts: item.select_ts ?? '',
    select_order: item.select_order,
    filter_type: filterType,
  }
  if (isTimeFilterField(item.field) || isStringFilterField(item.field)) {
    if (item.op === 'between' && Array.isArray(item.value)) {
      return { field: item.field, op: item.op, value: item.value.join(','), ...meta }
    }
    return { field: item.field, op: item.op, value: item.value, ...meta }
  }
  if (isNumericFilterField(item.field)) {
    if (item.op === 'between' && Array.isArray(item.value)) {
      return { field: item.field, op: item.op, value: item.value.map(formatNumericValue).join(','), ...meta }
    }
    return { field: item.field, op: item.op, value: formatNumericValue(item.value), ...meta }
  }
  const arr = Array.isArray(item.value) ? item.value : [item.value]
  if (arr.length === 0 || (arr.length === 1 && arr[0] === '')) {
    return { field: item.field, op: 'in', value: '', ...meta }
  }
  return { field: item.field, op: 'in', value: arr.filter(v => v !== '').join(','), ...meta }
}

function onRangeFilterOpChange(item: FilterItem, op: string | number) {
  const opStr = String(op)
  if (opStr === 'between') {
    const v = item.value
    item.value = Array.isArray(v) ? [v[0] ?? '', v[1] ?? ''] : [v || '', '']
  } else if (Array.isArray(item.value)) {
    item.value = item.value[0] ?? ''
  }
  item.op = opStr
  onFilterFieldChange(item)
}

function onStringFilterOpChange(item: FilterItem, op: string | number) {
  onRangeFilterOpChange(item, op)
}

function onNumericFilterOpChange(item: FilterItem, op: string | number) {
  const opStr = String(op)
  if (opStr === 'between') {
    const v = item.value
    item.value = Array.isArray(v) ? [parseNumericValue(v[0]), parseNumericValue(v[1])] : [parseNumericValue(v), null]
  } else if (Array.isArray(item.value)) {
    item.value = parseNumericValue(item.value[0])
  }
  item.op = opStr
  onFilterFieldChange(item)
}

function onTimeFilterOpChange(item: FilterItem, op: string | number) {
  onRangeFilterOpChange(item, op)
}

function addHaving() {
  stateData.having.push({ field: '', op: '>=', value: '' })
}
function removeHaving(index: number) {
  stateData.having.splice(index, 1)
}

function onShowAsChange(index: number, val: string) {
  const item = stateData.values[index]
  if (item) {
    item.show_as = val === 'normal' ? undefined : { type: val as any }
  }
}

function ensureAxisAggregation(item: AxisItem): AxisItem {
  if (!isTimeFilterField(item.field)) return item
  const aggregation = item.aggregation ?? (item.group as AxisItem['aggregation']) ?? 'source'
  const { group, ...rest } = item
  return { ...rest, aggregation }
}

function onAxisAggregationChange(item: AxisItem, val: string) {
  item.aggregation = (val || 'source') as AxisItem['aggregation']
}

function onDragStart(event: DragEvent, field: FieldDef, fromSignal = false) {
  event.dataTransfer?.setData('application/json', JSON.stringify({
    name: field.name, alias_cn: field.alias_cn, category: field.category, data_type: field.data_type,
    isSignal: fromSignal,
  }))
  event.dataTransfer!.effectAllowed = 'move'
}

function onDrop(event: DragEvent, zone: ZoneType) {
  const raw = event.dataTransfer?.getData('application/json')
  if (!raw) return
  const field = JSON.parse(raw) as FieldDef & { isSignal?: boolean }
  const isSignal = !!field.isSignal
  if (zone === 'filters') {
    const isTime = isTimeFilterField(field.name)
    const isNumeric = isNumericFilterField(field.name)
    const isString = isStringFilterField(field.name)
    let newFilter: FilterItem
    const meta = {
      alias: field.alias_cn,
      select_ts: '',
      filter_type: getFilterType(field.name),
      isSignal,
    }
    if (isTime || isString) {
      newFilter = { field: field.name, op: '=', value: '', ...meta }
    } else if (isNumeric) {
      newFilter = { field: field.name, op: '=', value: null, ...meta }
    } else {
      newFilter = { field: field.name, op: 'in', value: [''], ...meta }
    }
    stateData.filters.push(newFilter)
    syncFilterSelectOrders()
    if (isStaticDropdownField(field.name)) {
      loadFilterDropdown(field.name)
    } else if (isApiFilterField(field.name)) {
      refreshFilterSelectOptions(field.name)
    }
    if (isSignalTriggerField(field.name)) {
      refreshSignalList()
    }
  } else if (zone === 'axes') {
    const axisItem: AxisItem = { field: field.name, alias: field.alias_cn, sort: 'asc', isSignal }
    if (isTimeFilterField(field.name)) axisItem.aggregation = 'source'
    stateData.axes.push(axisItem)
  } else if (zone === 'legend') {
    stateData.legend.push({ field: field.name, alias: field.alias_cn, isSignal })
  } else if (zone === 'values') {
    const id = `val_${stateData.values.length + 1}`
    const isMeasure = field.category === 'measure'
    stateData.values.push({
      id, field: field.name,
      aggregation: isMeasure ? 'sum' : 'count',
      alias: field.alias_cn,
      isSignal,
    })
  }
}

function removeItem(index: number, zone: ZoneType) {
  const arr = ({
    filters: stateData.filters,
    axes: stateData.axes,
    legend: stateData.legend,
    values: stateData.values,
  } as const)[zone]
  if (!arr) return
  const removedFilter = zone === 'filters' ? (arr[index] as FilterItem) : null
  arr.splice(index, 1)
  if (removedFilter && isSignalTriggerField(removedFilter.field)) {
    refreshSignalList()
  }
}

function buildPivotConfig(): PivotConfig {
  return {
    filters: stateData.filters.map(serializeFilterForApi),
    axes: stateData.axes.map(a => {
      const axis: { field: string; alias?: string; aggregation?: AxisItem['aggregation'] } = {
        field: a.field,
        alias: a.alias,
      }
      if (isTimeFilterField(a.field)) {
        axis.aggregation = a.aggregation ?? 'source'
      }
      return axis
    }),
    legend: stateData.legend.map(l => ({ field: l.field, alias: l.alias })),
    values: stateData.values.map(v => ({
      id: v.id,
      field: v.field,
      aggregation: v.aggregation,
      alias: v.alias,
      show_as: v.show_as,
    })),
    order_by: stateData.sortField.map(field => ({ field, direction: stateData.sortDir as 'asc' | 'desc' })),
    limit: stateData.limitVal,
    having: stateData.having.map(h => ({ field: h.field, op: h.op, value: h.value })),
    chart_type: stateData.chartType,
    grand_total: false,
    subtotals: false,
  }
}

function canRecommendChart() {
  return stateData.axes.length > 0 && stateData.values.length > 0
}

function getRecommendKey(config: PivotConfig) {
  return JSON.stringify({
    axes: config.axes,
    legend: config.legend,
    values: config.values,
  })
}

async function requestChartRecommendation(config: PivotConfig) {
  const requestId = ++recommendRequestId
  const recommendKey = getRecommendKey(config)

  try {
    const resp = await fetch('/api/recommend-chart', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config }),
    })

    if (!resp.ok) {
      const err = await resp.json().catch(() => null)
      throw new Error(err?.detail || '图表推荐失败')
    }

    const result: RecommendChartResponse = await resp.json()
    if (requestId !== recommendRequestId) return null

    if (result.top) {
      latestRecommendedTop.value = result.top
      latestRecommendKey.value = recommendKey
      stateData.chartType = result.top
      return result.top
    }
  } catch (e) {
    console.error('[ConfigPanel] 图表推荐失败', e)
  }

  if (requestId === recommendRequestId) {
    latestRecommendedTop.value = null
    latestRecommendKey.value = ''
  }
  return null
}

function scheduleChartRecommendation() {
  if (recommendTimer) {
    clearTimeout(recommendTimer)
    recommendTimer = null
  }

  if (!canRecommendChart()) {
    latestRecommendedTop.value = null
    latestRecommendKey.value = ''
    return
  }

  const config = buildPivotConfig()
  recommendTimer = setTimeout(() => {
    recommendTimer = null
    void requestChartRecommendation(config)
  }, 250)
}

async function handleQuery() {
  stateData.loading = true
  try {
    if (canRecommendChart()) {
      const recommendConfig = buildPivotConfig()
      const currentRecommendKey = getRecommendKey(recommendConfig)
      if (latestRecommendKey.value !== currentRecommendKey || !latestRecommendedTop.value) {
        await requestChartRecommendation(recommendConfig)
      }
    }

    const config = buildPivotConfig()
    await props.api(config)
  } finally {
    stateData.loading = false
  }
}

function handleClear() {
  stateData.filters = []
  stateData.axes = []
  stateData.legend = []
  stateData.values = []
  stateData.sortField = []
  stateData.sortDir = 'desc'
  stateData.limitVal = 1000
  stateData.having = []
  stateData.chartType = 'bar'
  signalFields.value = []
  latestRecommendedTop.value = null
  latestRecommendKey.value = ''
}

// ========== 暴露给父组件的方法 ==========
defineExpose({
  setDefaultValues: (config: PivotConfig) => {
    if (config.filters) {
      stateData.filters = config.filters.map((f, i) => normalizeFilterForUI(f, i + 1))
      syncFilterSelectOrders()
      config.filters.forEach(f => {
        if (isStaticDropdownField(f.field)) loadFilterDropdown(f.field)
      })
      const apiField = config.filters.find(f => isApiFilterField(f.field))?.field
      if (apiField) refreshFilterSelectOptions(apiField)
      if (config.filters.some(f => isSignalTriggerField(f.field))) {
        refreshSignalList()
      }
    }
    if (config.axes) stateData.axes = config.axes.map(ensureAxisAggregation)
    if (config.legend) stateData.legend = config.legend
    if (config.values) stateData.values = config.values
    if (config.chart_type) stateData.chartType = config.chart_type
  },
  resetConfig: handleClear,
})

watch(
  () => JSON.stringify({
    axes: stateData.axes,
    legend: stateData.legend,
    values: stateData.values,
  }),
  () => {
    scheduleChartRecommendation()
  },
)

// ========== 初始化：获取字段列表 ==========
onMounted(async () => {
  try {
    const resp = await fetch('/api/fields')
    if (resp.ok) {
      stateData.groups = await resp.json()
      stateData.filters = stateData.filters.map((f, i) => ensureFilterMeta(ensureFilterAlias(f), i + 1))
    }
  } catch (e) {
    console.error('[ConfigPanel] 获取字段列表失败', e)
  }
})

onBeforeUnmount(() => {
  if (recommendTimer) {
    clearTimeout(recommendTimer)
  }
})
</script>

<style scoped>
.config-panel {
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 100%;
}

.panel-section {
  background: white;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  overflow: hidden;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 14px;
  cursor: pointer;
  user-select: none;
  background: #fafafa;
  border-bottom: 1px solid #ebeef5;
}
.section-header:hover {
  background: #f0f2f5;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.section-toggle {
  font-size: 10px;
  color: #c0c4cc;
}

.section-body {
  padding: 6px 10px 10px;
}

.config-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* 字段列表内联样式 */
.field-search {
  padding-bottom: 6px;
}

.field-groups-row {
  display: flex;
  gap: 8px;
}

.field-group-col {
  flex: 1;
  min-width: 0;
  border: 1px solid #f2f3f5;
  border-radius: 6px;
  overflow: hidden;
}

.field-group-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 5px 8px;
  font-size: 11px;
  font-weight: 600;
  color: #303133;
  background: #fafafa;
  border-bottom: 1px solid #f2f3f5;
  position: sticky;
  top: 0;
  z-index: 1;
}

.field-group-label:hover {
  background: #f0f2f5;
}

.group-meta {
  display: flex;
  align-items: center;
  gap: 4px;
}

.group-arrow {
  font-size: 10px;
  color: #c0c4cc;
}

.field-items {
  padding: 2px 4px;
  height: 150px;
  overflow-y: auto;
}

.field-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 3px 6px;
  margin: 1px 0;
  border-radius: 4px;
  cursor: grab;
  font-size: 11px;
  color: #303133;
  transition: all 0.15s;
}

.field-item:hover {
  background: #ecf5ff;
  color: #409eff;
}

.field-item:active {
  cursor: grabbing;
  background: #d9ecff;
}

.field-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
}

/* 四象限 2x2 网格 */
.zones-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.zone-card {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  height: 100px;
}

.zone-card--filters {
  height: auto;
  min-height: 100px;
}

.config-section .section-body {
  padding: 6px 8px 8px;
}

.zone-card:hover {
  border-color: #409eff;
}

.zone-label {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 500;
  color: #606266;
  background: #fafafa;
  border-bottom: 1px solid #ebeef5;
  border-radius: 6px 6px 0 0;
}

.zone-body {
  padding: 4px 6px;
  min-height: 28px;
}

.zone-body.empty {
  display: flex;
  align-items: center;
  justify-content: center;
}

.zone-placeholder {
  color: #c0c4cc;
  font-size: 11px;
}

.zone-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  margin: 2px 0;
  background: #f0f9eb;
  border-radius: 4px;
  font-size: 12px;
  justify-content: flex-start;
}

.zone-item-field {
  flex: 0 1 88px;
  max-width: 120px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
  color: #303133;
  font-size: 12px;
}

.zone-item > .el-button {
  flex-shrink: 0;
  margin-left: auto;
}

.zone-item--date-between {
  flex-wrap: wrap;
  align-items: center;
  row-gap: 4px;
}

.zone-item--date-between .zone-item-field {
  order: 1;
  flex: 1 1 0;
  max-width: calc(100% - 52px);
}

.zone-item--date-between > .el-button {
  order: 2;
  margin-left: 0;
}

.zone-item--date-between > .el-button:first-of-type {
  margin-left: auto;
}

.zone-item--date-between::after {
  content: '';
  order: 3;
  flex-basis: 100%;
  height: 0;
}

.zone-item--date-between > .el-select {
  order: 4;
  flex-shrink: 0;
  width: 82px !important;
}

.zone-item--date-between > .between-inputs {
  order: 5;
  flex: 1 1 0;
  min-width: 0;
}

.between-inputs {
  display: flex;
  align-items: center;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.filter-value-select {
  flex: 1;
  min-width: 0;
}

.filter-date-picker {
  flex: 1;
  min-width: 0;
}

.filter-date-picker-sm {
  flex: 1 1 0;
  min-width: 96px;
}

.filter-date-picker-sm :deep(.el-input__wrapper) {
  padding-left: 6px;
  padding-right: 6px;
}

.filter-number-input {
  flex: 1;
  min-width: 0;
}

.filter-number-input-sm {
  flex: 1;
  min-width: 0;
}

.filter-text-input {
  flex: 1;
  min-width: 0;
}

.filter-text-input-sm {
  flex: 1;
  min-width: 0;
}

.zone-actions {
  display: flex;
  gap: 6px;
  padding-top: 4px;
}

.zone-actions .el-button {
  flex: 1;
}

/* 排序 + Limit */
.extra-row {
  display: flex;
  gap: 8px;
  padding-top: 6px;
  flex-wrap: wrap;
}

.extra-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.extra-item label {
  font-size: 11px;
  color: #606266;
  white-space: nowrap;
}

/* HAVING */
.having-section {
  padding-top: 6px;
  border-top: 1px solid #ebeef5;
  margin-top: 6px;
}

.having-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.having-head label {
  font-size: 11px;
  font-weight: 600;
  color: #606266;
}

.having-empty {
  font-size: 11px;
  color: #c0c4cc;
  padding: 4px 0;
  font-style: italic;
}

.having-items {
  height: 60px;
  overflow-y: auto;
}

.having-row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 0;
}
</style>
