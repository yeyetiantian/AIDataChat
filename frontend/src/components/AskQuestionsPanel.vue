<template>
  <div class="ask-panel">
    <!-- 图表数量 -->
    <div class="ask-item">
      <div class="ask-label">需要展示多少个图表？</div>
      <el-select v-model="chartCount" style="width:100%" @change="onChartCountChange">
        <el-option v-for="n in 4" :key="n" :label="(2 + n) + '个'" :value="2 + n"
          ><span v-if="2+n===6">⭐ </span>{{ 2 + n }}个</el-option
        >
      </el-select>
    </div>

    <!-- 任务选择 -->
    <div class="ask-item">
      <div class="ask-label">关联哪个任务？（任务变更会随机重置信号[]中的信号）</div>
      <div class="task-select-trigger" @click="taskDialogVisible = true">
        <span v-if="selectedTaskLabel" class="task-selected">{{ selectedTaskLabel }}</span>
        <span v-else class="task-placeholder">点击选择任务...</span>
      </div>
    </div>

    <!-- 任务选择弹窗 -->
    <el-dialog
      v-model="taskDialogVisible"
      title="选择任务"
      width="420px"
      top="10vh"
      :close-on-click-modal="true"
    >
      <el-input
        v-model="taskSearchKeyword"
        placeholder="搜索任务名称或ID..."
        clearable
        size="small"
        @input="onTaskSearchInput"
      />
      <div class="task-list" v-loading="taskLoading">
        <div
          v-for="t in taskOptions"
          :key="t.value"
          class="task-list-item"
          :class="{ active: taskId === t.value }"
          @click="selectTask(t)"
        >
          <span class="task-list-name">{{ t.name }}</span>
          <span class="task-list-id">#{{ t.value }}</span>
        </div>
        <div v-if="!taskLoading && taskOptions.length === 0" class="task-list-empty">
          暂无匹配任务
        </div>
      </div>
    </el-dialog>

    <!-- 可用规则 + 信号（紧凑标签，可拖拽） -->
    <template v-if="taskId">
      <div class="ref-section">
        <div class="ref-header">可用规则</div>
        <div v-if="ruleLoading" class="ref-loading">加载中...</div>
        <div v-else-if="ruleOptions.length === 0" class="ref-empty">暂无规则</div>
        <div v-else class="ref-tags">
          <span
            v-for="r in ruleOptions"
            :key="r.value"
            class="ref-tag ref-tag-rule"
            :class="{ selected: selectedRules.includes(r.value) }"
            draggable="true"
            @dragstart="onDragStart($event, 'rule', r)"
            @click="onRuleClick(r)"
          >
            {{ r.label }}
          </span>
        </div>
      </div>

      <div class="ref-section">
        <div class="ref-header">可用信号</div>
        <div v-if="signalLoading" class="ref-loading">加载中...</div>
        <div v-else-if="filteredSignals.length === 0" class="ref-empty">暂无信号</div>
        <div v-else class="ref-tags">
          <span
            v-for="s in filteredSignals"
            :key="s.value"
            class="ref-tag ref-tag-signal"
            :class="{ selected: selectedSignals.includes(s.value) }"
            draggable="true"
            @dragstart="onDragStart($event, 'signal', s)"
            @click="onSignalClick(s)"
          >
            {{ s.label }}
          </span>
        </div>
      </div>
    </template>
     <!-- 时间范围选择 -->
    <div class="ask-item">
      <div class="ask-label">需要什么时间范围？</div>
      <el-date-picker
        v-model="dateRange"
        type="datetimerange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD HH:mm:ss"
        style="width:100%"
        :disabled-date="disabledDate"
      />
    </div>
      
    <!-- 图表配置槽（Tab 切换） -->
    <template v-if="chartCount > 0">
      <div class="ask-item">
        <div class="ask-label">图表配置</div>
      </div>
      <el-tabs v-model="activeChartTab" type="card" class="chart-tabs">
        <el-tab-pane
          v-for="(slot, idx) in chartSlots"
          :key="idx"
          :label="`图表${idx + 1}`"
          :name="String(idx)"
        >
          <div class="chart-slot">
            <div
              class="drop-textarea-wrap"
              :class="{ 'drag-over': dragOverIdx === idx }"
              @dragover.prevent="dragOverIdx = idx"
              @dragleave="dragOverIdx = -1"
              @drop="onDrop($event, idx)"
            >
              <textarea
                ref="slotTextareas"
                v-model="slot.dimension"
                class="slot-textarea"
                placeholder="描述图表维度，或将规则/信号拖入此处插入文本中"
                rows="3"
              />
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </template>

    <div class="ask-actions">
      <el-button size="small" @click="$emit('cancel')">取消</el-button>
      <el-button type="primary" size="small" :disabled="!allRequiredFilled" @click="submitAnswers">
        确认
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

interface OptionItem {
  label: string
  value: string
  name?: string
}

interface ChartSlot {
  dimension: string
}

const emit = defineEmits<{
  submit: [msg: Record<string, any>]
  cancel: []
}>()

interface RawSignalItem {
  label: string
  value: string
  rule_ids?: number[]
}

const DEFAULT_SLOT_MAP = [
  '生成饼图，分析规则产生报警的数量占比',
  '生成柱状图，统计每日报警数量，X轴日期，Y轴报警时间计数，用规则做图例',
  '生成雷达图，对比维度包括[平均值，最大值，最小值]，Y轴信号[]，X轴为规则',
  '生成散点图，统计X轴信号[]与Y轴信号[]的报警值做对比',
  '生成面积图，Y轴信号[]，X轴报警时间',
  '生成折线图，Y轴信号[]，X轴报警时间按天计数'
]

// Chart count
const chartCount = ref(6)
const dateRange = ref<[String | null, String | null] | null>(['2025-08-29 00:00:00', '2025-09-04 23:59:59'])

/** 限制日期选择范围为 2025-05-29 ~ 2026-07-01 */
const disabledDate = (time: Date) => {
  const min = new Date('2025-05-29 00:00:00').getTime()
  const max = new Date('2026-07-01 23:59:59').getTime()
  return time.getTime() < min || time.getTime() > max
}

// Task
const taskId = ref('')
const taskOptions = ref<OptionItem[]>([])
const taskLoading = ref(false)
const taskDialogVisible = ref(false)
const taskSearchKeyword = ref('')
let taskSearchTimer: any = null

/** 已选任务的显示标签 */
const selectedTaskLabel = computed(() => {
  if (!taskId.value) return ''
  const t = taskOptions.value.find(o => o.value === taskId.value)
  return t ? t.label : ''
})

async function loadTasks(keyword: string = '') {
  taskLoading.value = true
  try {
    const url = keyword ? `/api/functions/tasks?keyword=${encodeURIComponent(keyword)}` : '/api/functions/tasks'
    const r = await fetch(url)
    if (r.ok) {
      const data = await r.json()
      taskOptions.value = data.map((t: any) => ({
        label: `${t.TASK_NAME}(${t.TASK_ID})`,
        name: t.TASK_NAME,
        value: String(t.TASK_ID),
      }))
    }
  } catch {}
  taskLoading.value = false
}

function onTaskSearchInput() {
  clearTimeout(taskSearchTimer)
  taskSearchTimer = setTimeout(() => loadTasks(taskSearchKeyword.value), 300)
}

function selectTask(task: OptionItem) {
  if (task.value !== taskId.value) {
    taskId.value = task.value
    onTaskChange()
  }
  taskDialogVisible.value = false
}

// Rules
const ruleOptions = ref<OptionItem[]>([])
const ruleLoading = ref(false)
const selectedRules = ref<string[]>([])

async function loadRules() {
  if (!taskId.value) return
  ruleLoading.value = true
  try {
    const r = await fetch(`/api/functions/rules?task_id=${taskId.value}`)
    if (r.ok) {
      const data = await r.json()
      ruleOptions.value = data.map((item: any) => ({
        label: item.RULE_NAME,
        value: String(item.TASK_RULE_ID),
      }))
    }
  } catch {}
  ruleLoading.value = false
}

/** 点击规则切换选中态，选中后信号列表按该规则筛选 */
function onRuleClick(rule: OptionItem) {
  const idx = selectedRules.value.indexOf(rule.value)
  if (idx >= 0) {
    selectedRules.value.splice(idx, 1)
  } else {
    selectedRules.value.push(rule.value)
  }
  selectedRules.value = [...selectedRules.value] // trigger reactivity
}

// Signals
const signalOptions = ref<RawSignalItem[]>([])
const signalLoading = ref(false)
const selectedSignals = ref<string[]>([])

/** 根据选中规则过滤后的信号列表 */
const filteredSignals = computed(() => {
  if (selectedRules.value.length === 0) return signalOptions.value
  return signalOptions.value.filter(s => {
    if (!s.rule_ids || s.rule_ids.length === 0) return true
    return selectedRules.value.some(rid => s.rule_ids!.includes(Number(rid)))
  })
})

/** 点击信号切换选中态 */
function onSignalClick(signal: RawSignalItem) {
  const idx = selectedSignals.value.indexOf(signal.value)
  if (idx >= 0) {
    selectedSignals.value.splice(idx, 1)
  } else {
    selectedSignals.value.push(signal.value)
  }
  selectedSignals.value = [...selectedSignals.value] // trigger reactivity
}

async function loadSignals() {
  if (!taskId.value) return
  signalLoading.value = true
  try {
    const r = await fetch(`/api/functions/signals?task_id=${taskId.value}`)
    if (r.ok) {
      const data = await r.json()
      signalOptions.value = data.map((s: any) => ({
        label: `${s.signal_name}`,
        value: s.signal_name,
        rule_ids: s.rule_ids,
      })).filter(x => !(x.value?.includes('(') || x.value?.includes(')')))
    }
  } catch {}
  signalLoading.value = false
}

function onTaskChange() {
  const tid = taskId.value
  selectedRules.value = []
  selectedSignals.value = []
  if (tid) {
    loadRules()
    loadSignals()
  } else {
    ruleOptions.value = []
    signalOptions.value = []
  }
}
const randomSingle = (templateStr: string): string => {
  if (filteredSignals.value.length < 1) return templateStr
  const allLabels = filteredSignals.value.map(item => item.label);
  const getRandomLabels = (n: number) => {
    const copy = [...allLabels];
    const takeNum = Math.min(n, copy.length);
    const result: string[] = [];
    for (let i = 0; i < takeNum; i++) {
        const randomIdx = Math.floor(Math.random() * copy.length);
        result.push(copy.splice(randomIdx, 1)[0]);
    }
    return result.join(',');
  }
  const getNum = () => {
    if (templateStr.includes('雷达图')) return 5
    if (templateStr.includes('散点图')) return 1
    if (templateStr.includes('面积图')) return 5
    if (templateStr.includes('折线图')) return 6
    return 0
  }
  const num = getNum()
  if (num === 0) return templateStr
  return templateStr.replace(/(信号\s*)\[(.*?)\]/g, (match, prefix) => {
    return `${prefix}[${getRandomLabels(num)}]`
  })
}

const setChartText = () => {
  chartSlots.value.forEach((x) => {
    if (x.dimension){ 
      x.dimension = randomSingle(x.dimension)
    }
  })
}

watch(() => filteredSignals.value.length, () => setChartText())

// Chart slots
const chartSlots = ref<ChartSlot[]>([])
const activeChartTab = ref('0')
const slotTextareas = ref<(HTMLTextAreaElement | null)[]>([])
const dragOverIdx = ref(-1)

function onChartCountChange() {
  const n = chartCount.value
  while (chartSlots.value.length < n) {
    chartSlots.value.push({ dimension: '' })
  }
  while (chartSlots.value.length > n) {
    chartSlots.value.pop()
  }
  if (parseInt(activeChartTab.value) >= n) {
    activeChartTab.value = String(n - 1)
  }
  chartSlots.value.forEach((x, i) => {
    if (!x.dimension){ 
      x.dimension = randomSingle(DEFAULT_SLOT_MAP[i])
    }
  })
}

// Initialize
onChartCountChange()
loadTasks()

// Drag & drop to textarea
let dragInsertText = ''

function onDragStart(e: DragEvent, type: string, item: OptionItem) {
  dragInsertText = `${item.label}`
  e.dataTransfer?.setData('text/plain', dragInsertText)
}

function onDrop(e: DragEvent, slotIdx: number) {
  dragOverIdx.value = -1
  const slot = chartSlots.value[slotIdx]
  if (!slot) return

  const textarea = slotTextareas.value[slotIdx]
  if (!textarea) {
    slot.dimension += (slot.dimension ? '\n' : '') + dragInsertText
    return
  }

  const text = textarea.value
  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  if (start !== undefined) {
    slot.dimension = text.substring(0, start) + dragInsertText + text.substring(end)
    requestAnimationFrame(() => {
      const pos = start + dragInsertText.length
      textarea.setSelectionRange(pos, pos)
      textarea.focus()
    })
  } else {
    slot.dimension += (slot.dimension ? '\n' : '') + dragInsertText
  }
  dragInsertText = ''
}

// Validation
const allRequiredFilled = computed(() => {
  if (!taskId.value) return false
  return chartCount.value > 0
})

function formattedMsgFn() {
  // 获取任务名称
  const taskOpt = taskOptions.value?.find((o: any) => String(o.value) === String(taskId.value))
  const taskLabel = taskOpt?.name
  const dateLabel = dateRange.value?.join(' 到 ')
  const ruleLabel = selectedRules.value.join('、')

  const lines: string[] = ['📊 看板需求确认']
  lines.push(`图表数量：**${chartCount.value}**`)

  const slots: any[] = []
  // 每个图表的配置
  for (let i = 0; i < chartSlots.value.length; i ++) {
    const slot = chartSlots.value[i]
    const desc = slot.dimension ? `${slot.dimension}，关联任务：${taskLabel}，数据筛选时间从${dateLabel}` : ''
    lines.push(`-图表${i + 1}：（${desc}）`)
    slots.push({
      index: i + 1,
      description: desc
    })
  }

  const formattedMsg = '[问卷提交]\n' + lines.join('\n')
  
  return { result: formattedMsg, slots }
}

function submitAnswers() {
  const { result, slots } = formattedMsgFn()
  emit('submit', {
    result: result,
    taskId: taskId.value,
    chartCount: chartCount.value,
    slots: slots
  })
}
</script>

<style scoped>
.ask-panel {
  margin-top: 4px;
  padding: 8px 10px;
  border: 1px solid #e0e7ff;
  border-radius: 8px;
  background: #f8faff;
}
.ask-item { margin-bottom: 8px; }
.ask-label {
  font-size: 12px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 4px;
}

/* Reference section (rules/signals) */
.ref-section {
  margin-bottom: 6px;
}
.ref-header {
  font-size: 11px;
  font-weight: 600;
  color: #6b7280;
  margin-bottom: 3px;
}
.ref-loading, .ref-empty {
  font-size: 11px;
  color: #9ca3af;
  padding: 4px 0;
}
.ref-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  max-height: 120px;
  overflow-y: auto;
}
.ref-tag {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  cursor: grab;
  white-space: nowrap;
  user-select: none;
  transition: transform .1s;
}
.ref-tag:active { cursor: grabbing; transform: scale(.95); }
.ref-tag-rule {
  background: #e0f2fe;
  color: #0369a1;
  border: 1px solid #bae6fd;
  cursor: pointer;
}
.ref-tag-rule.selected {
  color: #2563eb;
  background: #8fd2ff;
  font-weight: 600;
}
.ref-tag-signal {
  background: #fae8ff;
  color: #a21caf;
  border: 1px solid #f5d0fe;
  cursor: pointer;
}
.ref-tag-signal.selected {
  color: #7c1d8e;
  background: #e9d5ff;
  font-weight: 600;
  border-color: #a21caf;
}

/* Chart slot */
.chart-slot {
  margin-bottom: 4px;
}
.chart-tabs { margin-bottom: 4px; }
.chart-tabs :deep(.el-tabs__item) {
  font-size: 11px; padding: 0 10px; height: 28px; line-height: 28px;
}

/* Drop textarea */
.drop-textarea-wrap {
  border: 1px dashed #d1d5db;
  border-radius: 6px;
  padding: 4px;
  transition: border-color .15s, background .15s;
}
.drop-textarea-wrap.drag-over {
  border-color: #6366f1;
  background: #eef2ff;
}
.slot-textarea {
  width: 100%;
  border: none;
  outline: none;
  resize: vertical;
  font-size: 12px;
  line-height: 1.5;
  font-family: inherit;
  padding: 4px;
  color: #374151;
  background: transparent;
}
.slot-textarea::placeholder { color: #9ca3af; }

.ask-actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid #e5e7eb;
}

/* Task select trigger */
.task-select-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-size: 12px;
  transition: border-color .15s;
  min-height: 28px;
}
.task-select-trigger:hover {
  border-color: #6366f1;
}
.task-selected {
  color: #374151;
  font-weight: 500;
}
.task-placeholder {
  color: #9ca3af;
}
.task-select-trigger::after {
  content: '';
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-top: 5px solid #9ca3af;
  flex-shrink: 0;
}

/* Task dialog list */
.task-list {
  margin-top: 10px;
  max-height: 360px;
  overflow-y: auto;
}
.task-list-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background .1s;
}
.task-list-item:hover {
  background: #eef2ff;
}
.task-list-item.active {
  background: #e0e7ff;
  font-weight: 600;
}
.task-list-name {
  font-size: 13px;
  color: #374151;
}
.task-list-id {
  font-size: 11px;
  color: #9ca3af;
}
.task-list-empty {
  text-align: center;
  color: #9ca3af;
  padding: 20px 0;
  font-size: 12px;
}

.chart-tabs { margin-bottom: 4px; }
.chart-tabs :deep(.el-tabs__item) {
  font-size: 11px;
  padding: 0 10px;
  height: 28px;
  line-height: 28px;
}
</style>
