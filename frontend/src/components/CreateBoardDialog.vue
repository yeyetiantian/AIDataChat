<template>
  <el-dialog v-model="visible" title="创建数据看板" width="520px" top="8vh" destroy-on-close>
    <div class="board-wizard">
      <!-- Step 1: 看板基本信息 -->
      <div v-if="step === 1" class="wizard-step">
        <div class="step-title">看板名称</div>
        <el-input v-model="boardName" placeholder="输入看板名称，如：车辆违规监控看板" maxlength="50" show-word-limit />
        
        <div class="step-title" style="margin-top:16px">图表数量</div>
        <el-radio-group v-model="chartCount">
          <el-radio-button :value="2">2 个</el-radio-button>
          <el-radio-button :value="3">3 个</el-radio-button>
          <el-radio-button :value="4">4 个</el-radio-button>
          <el-radio-button :value="5">5 个</el-radio-button>
          <el-radio-button :value="6">6 个</el-radio-button>
        </el-radio-group>
        
        <div class="step-title" style="margin-top:16px">关联任务（可选）</div>
        <el-select v-model="selectedTask" filterable clearable placeholder="搜索并选择任务" style="width:100%">
          <el-option v-for="t in taskOptions" :key="t.TASK_ID" :label="t.TASK_NAME" :value="t.TASK_ID" />
        </el-select>
      </div>
      
      <!-- Step 2: 图表类型配置 -->
      <div v-if="step === 2" class="wizard-step">
        <div class="step-title">选择每个图表的分析方向</div>
        <div class="chart-config-list">
          <div v-for="(cfg, idx) in chartConfigs" :key="idx" class="chart-config-item">
            <div class="chart-config-index">{{ idx + 1 }}</div>
            <div class="chart-config-fields">
              <el-input v-model="cfg.description" :placeholder="'图表' + (idx+1) + '：如各车型报警次数'" size="small" />
            </div>
          </div>
        </div>
      </div>
      
      <!-- Step 3: 确认 -->
      <div v-if="step === 3" class="wizard-step">
        <div class="step-title">确认看板配置</div>
        <div class="confirm-info">
          <div class="confirm-row"><span class="confirm-label">看板名称</span><span class="confirm-value">{{ boardName || '未命名看板' }}</span></div>
          <div class="confirm-row"><span class="confirm-label">图表数量</span><span class="confirm-value">{{ chartCount }} 个</span></div>
          <div class="confirm-row" v-if="selectedTaskName"><span class="confirm-label">关联任务</span><span class="confirm-value">{{ selectedTaskName }}</span></div>
        </div>
        <div class="confirm-charts">
          <div v-for="(cfg, idx) in chartConfigs" :key="idx" class="confirm-chart-item">
            <span class="confirm-chart-num">{{ idx + 1 }}</span>
            <span>{{ cfg.description || '未填写' }}</span>
          </div>
        </div>
      </div>
    </div>
    
    <template #footer>
      <el-button v-if="step > 1" @click="step--">上一步</el-button>
      <el-button v-if="step < 3" type="primary" :disabled="!canNext" @click="step++">下一步</el-button>
      <el-button v-if="step === 3" type="primary" @click="handleSubmit">生成看板</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

const emit = defineEmits<{ send: [msg: string] }>()

const visible = ref(false)
const step = ref(1)
const boardName = ref('')
const chartCount = ref(3)
const selectedTask = ref<number | null>(null)
const selectedTaskName = ref('')
const taskOptions = ref<any[]>([])
const chartConfigs = ref<{ description: string }[]>([])

const canNext = computed(() => {
  if (step.value === 1) return boardName.value.trim().length > 0
  return true
})

watch(chartCount, (n) => {
  while (chartConfigs.value.length < n) {
    chartConfigs.value.push({ description: '' })
  }
  if (chartConfigs.value.length > n) {
    chartConfigs.value = chartConfigs.value.slice(0, n)
  }
})

watch(selectedTask, async (id) => {
  if (!id) { selectedTaskName.value = ''; return }
  const t = taskOptions.value.find(t => t.TASK_ID === id)
  selectedTaskName.value = t?.TASK_NAME || ''
})

function open() {
  step.value = 1
  boardName.value = ''
  chartCount.value = 3
  selectedTask.value = null
  selectedTaskName.value = ''
  chartConfigs.value = [{ description: '' }, { description: '' }, { description: '' }]
  // 加载任务列表
  fetch('/api/fields').then(r => r.json()).catch(() => {})
  fetchTasks()
  visible.value = true
}

async function fetchTasks() {
  try {
    const r = await fetch('/api/chat/traces/sessions/list')
  } catch {}
  try {
    const r = await fetch('/api/monitor/traces/sessions/list')
  } catch {}
}

function handleSubmit() {
  // 构建用户消息
  const descs = chartConfigs.value.map((c, i) => `图表${i+1}：${c.description || '自动生成'}`).join('；')
  let msg = `创建一个看板"${boardName.value || '未命名'}"，包含 ${chartCount.value} 个图表`
  if (selectedTask.value) msg += `，关联任务 ${selectedTaskName.value}（TASK_ID=${selectedTask.value}）`
  msg += `。\n需求：${descs}`
  
  visible.value = false
  emit('send', msg)
}

defineExpose({ open })
</script>

<style scoped>
.board-wizard { min-height: 200px; }
.wizard-step { padding: 4px 0; }
.step-title { font-size: 14px; font-weight: 600; color: #303133; margin-bottom: 8px; }
.chart-config-list { display: flex; flex-direction: column; gap: 8px; }
.chart-config-item { display: flex; align-items: center; gap: 10px; }
.chart-config-index { width: 24px; height: 24px; border-radius: 50%; background: #409eff; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; flex-shrink: 0; }
.chart-config-fields { flex: 1; }
.confirm-info { background: #f6f8fa; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; }
.confirm-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #f0f0f0; font-size: 13px; }
.confirm-row:last-child { border-bottom: none; }
.confirm-label { color: #909399; }
.confirm-value { color: #303133; font-weight: 500; }
.confirm-charts { display: flex; flex-direction: column; gap: 6px; }
.confirm-chart-item { display: flex; align-items: center; gap: 8px; padding: 6px 10px; background: #f6f8fa; border-radius: 6px; font-size: 13px; }
.confirm-chart-num { width: 20px; height: 20px; border-radius: 50%; background: #e8eaed; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 600; color: #606266; flex-shrink: 0; }
</style>
