<template>
  <el-dialog v-model="visibleModel" title="保存到看板" width="400px" destroy-on-close>
    <el-form label-position="top">
      <el-form-item label="图表名称">
        <el-input v-model="localTitle" placeholder="输入图表名称" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="localDesc" type="textarea" :rows="2" placeholder="可选" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visibleModel = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { PivotConfig } from '@/types'

const props = withDefaults(defineProps<{
  visible: boolean
  chart?: any | null
  index?: number
}>(), {
  chart: null,
  index: 0,
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  save: [chart: {
    title: string
    description: string
    pivot_config: PivotConfig
    chart_type: string
    vega_spec: any
    data: any
  }]
}>()

const visibleModel = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const saving = ref(false)
const localTitle = ref('')
const localDesc = ref('')

watch(() => props.visible, (v) => {
  if (v && props.chart) {
    localTitle.value = props.chart.title || `图表 ${(props.index ?? 0) + 1}`
    localDesc.value = ''
  }
})

async function handleSave() {
  if (!props.chart) return
  saving.value = true
  try {
    emit('save', {
      title: localTitle.value || props.chart.title || '',
      description: localDesc.value,
      pivot_config: (props.chart.pivot_config || { filters: [], axes: [], legend: [], values: [] }) as PivotConfig,
      chart_type: props.chart.chart_type || 'bar',
      vega_spec: props.chart.vega_spec || null,
      data: props.chart.data || null,
    })
    visibleModel.value = false
  } finally {
    saving.value = false
  }
}
</script>
