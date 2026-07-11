<template>
  <ModelDialog ref="modelRef" title="保存到看板" width="400px">
    <el-form label-position="top">
      <el-form-item label="图表名称">
        <el-input v-model="formData.title" placeholder="输入图表名称" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="formData.description" type="textarea" :rows="2" placeholder="可选" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </template>
  </ModelDialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { PivotConfig } from '@/types'
import ModelDialog from './ModelDialog.vue'
import { useBoardStore } from '@/stores/useBoardStore.ts';
import { ElMessage } from 'element-plus';
import { MAX_BOARD_CHARTS, useChartStore } from '@/stores/useChartStore.ts';

const chartStore = useChartStore()
const boardStore = useBoardStore()

const modelRef = ref<InstanceType<typeof ModelDialog> | null>(null)
const saving = ref(false)
const formData = ref({
  title: '',
  description: '',
  pivot_config: {} as PivotConfig,
  chart_type: '',
  vega_spec: null,
  data: null,
})

const open = (data: any) => {
  formData.value = {
    title: data.title || '',
    description: data.content || '',
    pivot_config: data.pivot_config || { filters: [], axes: [], legend: [], values: [] },
    chart_type: data.chart_type || 'bar',
    vega_spec: data.vega_spec || null,
    data: data.data || null,
  }
  modelRef.value?.open()
}

const close = () => {
  formData.value = {
    title: '',
    description: '',
    pivot_config: {} as PivotConfig,
    chart_type: '',
    vega_spec: null,
    data: null,
  }
  modelRef.value?.close()
}


async function handleSave() {
  if(!formData.value.title.trim()) return
  saving.value=true
  try {
    const bid=boardStore.activeBoardId; 
    if(!bid){
      ElMessage.warning('请先选择一个看板');
      return
    }
    await chartStore.fetchCharts(bid)
    if(chartStore.charts.length>=MAX_BOARD_CHARTS) { 
      ElMessage.warning(`看板最多 ${MAX_BOARD_CHARTS} 个`); 
      return 
    }
    const title = formData.value.title.trim()
    const ok=await chartStore.saveChart(title, formData.value.pivot_config, formData.value.description, formData.value.chart_type||'bar', null, formData.value.data, bid)
    if(!ok) { 
      ElMessage.warning(chartStore.error||'保存失败'); return 
    }
    ElMessage.success('已保存到看板');
    close()
  } finally { saving.value=false }
}

defineExpose({
  open,
})
</script>
