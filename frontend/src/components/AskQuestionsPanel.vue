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
      <el-select
        v-model="taskId"
        filterable
        remote
        :loading="taskLoading"
        :remote-method="onTaskSearch"
        placeholder="搜索任务..."
        clearable
        style="width:100%"
        @change="onTaskChange"
      >
        <el-option v-for="t in taskOptions" :key="t.value" :label="t.label" :value="t.value" />
      </el-select>
    </div>

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
            draggable="true"
            @dragstart="onDragStart($event, 'rule', r)"
          >
            {{ r.label }}
          </span>
        </div>
      </div>

      <div class="ref-section">
        <div class="ref-header">可用信号</div>
        <div v-if="signalLoading" class="ref-loading">加载中...</div>
        <div v-else-if="signalOptions.length === 0" class="ref-empty">暂无信号</div>
        <div v-else class="ref-tags">
          <span
            v-for="s in signalOptions"
            :key="s.value"
            class="ref-tag ref-tag-signal"
            draggable="true"
            @dragstart="onDragStart($event, 'signal', s)"
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

const DEFAULT_SLOT_MAP = [
  '生成饼图，分析规则产生报警的数量占比',
  '生成柱状图，统计每日报警数量，不同报警规则对应不同图例，X轴日期，Y轴报警时间计数',
  '生成雷达图，对比维度包括[平均值，最大值，最小值]，Y轴信号[]，X轴为规则，不要指定图例',
  '生成散点图，统计X轴信号[]与Y轴信号[]的报警值做对比',
  '生成面积图，Y轴信号[]，X轴报警时间，不指定图例，',
  '生成折线图，Y轴信号[]，X轴报警时间计数，不指定图例，'
]

// Chart count
const chartCount = ref(6)
const dateRange = ref<[String | null, String | null] | null>(['2025-08-29 00:00:00', '2025-09-04 23:59:59'])

// Task
const taskId = ref('')
const taskOptions = ref<OptionItem[]>([])
const taskLoading = ref(false)
let taskSearchTimer: any = null

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

function onTaskSearch(query: string) {
  clearTimeout(taskSearchTimer)
  taskSearchTimer = setTimeout(() => loadTasks(query), 300)
}

// Rules
const ruleOptions = ref<OptionItem[]>([])
const ruleLoading = ref(false)

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

// Signals
const signalOptions = ref<OptionItem[]>([])
const signalLoading = ref(false)

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
      }))
      chartSlots.value.forEach((x) => {
        if (x.dimension){ 
          x.dimension = randomSingle(x.dimension)
        }
      })
    }
  } catch {}
  signalLoading.value = false
}

function onTaskChange() {
  const tid = taskId.value
  if (tid) {
    loadRules()
    loadSignals()
  } else {
    ruleOptions.value = []
    signalOptions.value = []
  }
}
const randomSingle = (templateStr: string): string => {
  if (signalOptions.value.length < 1) return templateStr
  const allLabels = signalOptions.value.map(item => item.label);
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
    if (templateStr.includes('区域图')) return 5
    if (templateStr.includes('折线图')) return 6
    return 0
  }
  const num = getNum()
  if (num === 0) return templateStr
  return templateStr.replace(/(信号\s*)\[(.*?)\]/g, (match, prefix) => {
    return `${prefix}[${getRandomLabels(num)}]`
  })
}

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
.ref-tag.selected { box-shadow: 0 0 0 2px #2563eb inset; font-weight: 600; }
.ref-tag-rule {
  background: #e0f2fe;
  color: #0369a1;
  border: 1px solid #bae6fd;
}
.ref-tag-signal {
  background: #fae8ff;
  color: #a21caf;
  border: 1px solid #f5d0fe;
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

.chart-tabs { margin-bottom: 4px; }
.chart-tabs :deep(.el-tabs__item) {
  font-size: 11px;
  padding: 0 10px;
  height: 28px;
  line-height: 28px;
}
</style>
