<template>
  <el-dialog v-model="visibleModel" :title="title" width="700px" top="8vh" destroy-on-close>
    <div class="sql-toolbar">
      <el-button size="small" @click="copyContent">
        <el-icon><DocumentCopy /></el-icon>
        复制
      </el-button>
    </div>
    <div class="sql-content">
      <pre><code>{{ content || '-- 无内容' }}</code></pre>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { DocumentCopy } from '@element-plus/icons-vue'

const props = withDefaults(defineProps<{
  visible: boolean
  content?: string | null
  title?: string
  lang?: string
}>(), {
  content: '',
  title: '查看',
  lang: 'sql',
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const visibleModel = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

async function copyContent() {
  if (!props.content) {
    ElMessage.info('无内容可复制')
    return
  }
  try {
    await navigator.clipboard.writeText(props.content)
    ElMessage.success('已复制')
  } catch {
    // fallback
    const ta = document.createElement('textarea')
    ta.value = props.content
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    ElMessage.success('已复制')
  }
}
</script>

<style scoped>
.sql-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.sql-content {
  background: #1e1e1e;
  border-radius: 6px;
  padding: 16px;
  max-height: 60vh;
  overflow: auto;
}

.sql-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 13px;
  line-height: 1.6;
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
  color: #d4d4d4;
}

.sql-content code {
  background: none;
  color: inherit;
  padding: 0;
}
</style>
