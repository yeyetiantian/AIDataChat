<template>
  <div class="ask-panel">
    <div class="ask-prompt">{{ prompt }}</div>
    
    <div v-for="(q, idx) in questions" :key="q.id" class="ask-item">
      <div class="ask-label">
        <span class="ask-number">{{ idx + 1 }}</span>
        <span>{{ q.question }}</span>
        <span v-if="!q.required" class="ask-optional">（可选）</span>
      </div>

      <!-- select: 单选 -->
      <el-select
        v-if="q.type === 'select'"
        v-model="answers[q.id]"
        :placeholder="q.placeholder || '请选择'"
        clearable
        :filterable="q.options.length > 5"
        style="width:100%"
        @change="onAnswer"
      >
        <el-option
          v-for="opt in q.options"
          :key="opt.value"
          :label="(opt.recommended ? '⭐ ' : '') + opt.label"
          :value="opt.value"
        />
      </el-select>

      <!-- multi_select: 多选 -->
      <el-checkbox-group
        v-else-if="q.type === 'multi_select'"
        v-model="answers[q.id]"
        style="width:100%"
        @change="onAnswer"
      >
        <el-checkbox
          v-for="opt in q.options"
          :key="opt.value"
          :label="opt.value"
          :value="opt.value"
        >
          {{ (opt.recommended ? '⭐ ' : '') + opt.label }}
        </el-checkbox>
      </el-checkbox-group>

      <!-- input: 文本输入 -->
      <el-input
        v-else
        v-model="answers[q.id]"
        :placeholder="q.placeholder || '请输入...'"
        :rows="2"
        type="textarea"
        @input="onAnswer"
      />
    </div>

    <div class="ask-actions">
      <el-button size="small" @click="$emit('cancel')">取消</el-button>
      <el-button type="primary" size="small" :disabled="!allRequiredFilled" @click="submitAnswers">
        确认
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface QuestionOption {
  label: string
  value: string
  recommended?: boolean
}

interface QuestionItem {
  id: string
  question: string
  type: 'select' | 'multi_select' | 'input'
  options: QuestionOption[]
  placeholder?: string
  required?: boolean
}

const props = defineProps<{
  prompt: string
  questions: QuestionItem[]
}>()

const emit = defineEmits<{
  submit: [answers: Record<string, any>]
  cancel: []
}>()

const answers = ref<Record<string, any>>({})

// 初始化默认值
for (const q of props.questions) {
  if (q.type === 'multi_select') {
    answers.value[q.id] = answers.value[q.id] || []
  } else {
    answers.value[q.id] = answers.value[q.id] || ''
  }
  // 自动填充推荐选项
  if (q.type === 'select' && !answers.value[q.id]) {
    const recommended = q.options.find(o => o.recommended)
    if (recommended) answers.value[q.id] = recommended.value
  }
}

const allRequiredFilled = computed(() => {
  return props.questions.every(q => {
    if (!q.required) return true
    const val = answers.value[q.id]
    if (q.type === 'multi_select') return Array.isArray(val) && val.length > 0
    return val !== '' && val !== null && val !== undefined
  })
})

function onAnswer() {
  // 触发响应式更新
}

function submitAnswers() {
  const result: Record<string, any> = {}
  for (const q of props.questions) {
    const val = answers.value[q.id]
    if (q.type === 'multi_select') {
      result[q.id] = Array.isArray(val) ? val : []
    } else {
      result[q.id] = val || ''
    }
  }
  emit('submit', result)
}
</script>

<style scoped>
.ask-panel {
  margin-top: 8px;
  padding: 12px 14px;
  border: 1px solid #e0e7ff;
  border-radius: 10px;
  background: #f8faff;
}

.ask-prompt {
  font-size: 13px;
  color: #374151;
  margin-bottom: 12px;
  line-height: 1.5;
}

.ask-item {
  margin-bottom: 12px;
}

.ask-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #4b5563;
  margin-bottom: 6px;
}

.ask-number {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #6366f1;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.ask-optional {
  font-size: 11px;
  color: #9ca3af;
}

.ask-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
  padding-top: 10px;
  border-top: 1px solid #e5e7eb;
}
</style>
