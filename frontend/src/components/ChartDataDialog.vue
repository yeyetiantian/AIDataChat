<template>
  <el-dialog v-model="visibleModel" :title="title" width="80%" top="5vh" destroy-on-close>
    <div class="data-toolbar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索数据..."
        clearable
        size="small"
        style="width: 240px"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <span class="data-count">共 {{ filteredData.length }} 条</span>
    </div>
    <div class="data-table-wrap">
      <el-table
        :data="filteredData"
        border
        stripe
        height="55vh"
        size="small"
        style="width: 100%"
      >
        <el-table-column
          v-for="col in columns"
          :key="col"
          :prop="col"
          :label="col"
          min-width="140"
          show-overflow-tooltip
        />
      </el-table>
      <div v-if="!columns.length && data?.length === 0" class="data-empty">
        <el-icon :size="32" color="#c0c4cc"><FolderOpened /></el-icon>
        <p>暂无数据</p>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Search, FolderOpened } from '@element-plus/icons-vue'

const props = withDefaults(defineProps<{
  visible: boolean
  data?: Record<string, any>[] | null
  title?: string
}>(), {
  data: () => [],
  title: '查看数据',
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const visibleModel = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const searchQuery = ref('')

const columns = computed(() => {
  if (!props.data || props.data.length === 0) return []
  return Object.keys(props.data[0])
})

const filteredData = computed(() => {
  if (!props.data || props.data.length === 0) return []
  if (!searchQuery.value.trim()) return props.data
  const q = searchQuery.value.trim().toLowerCase()
  return props.data.filter(row =>
    Object.values(row).some(val =>
      String(val ?? '').toLowerCase().includes(q)
    )
  )
})
</script>

<style scoped>
.data-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.data-count {
  font-size: 13px;
  color: #909399;
}

.data-table-wrap {
  position: relative;
}

.data-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 0;
  color: #c0c4cc;
  gap: 8px;
}

.data-empty p {
  font-size: 14px;
  margin: 0;
}
</style>
