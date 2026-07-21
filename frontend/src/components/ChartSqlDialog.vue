<template>
  <ModelDialog ref="modelRef" :title="title" width="600px" top="8vh" >
    <div class="sql-toolbar">
      <el-button v-if="content" size="small" @click="copyContent">
        <el-icon><DocumentCopy /></el-icon>
        复制
      </el-button>
    </div>
    <div class="sql-content">
      <pre><code>{{ content || '-- 无内容' }}</code></pre>
    </div>
  </ModelDialog>
</template>

<script setup lang="ts">
import { computed, ref, toRaw } from 'vue'
import { ElMessage } from 'element-plus'
import { DocumentCopy } from '@element-plus/icons-vue'
import ModelDialog from './ModelDialog.vue'

const modelRef = ref<InstanceType<typeof ModelDialog> | null>(null)
const content = ref('')
const title = ref('查看')

const open = (con?: string, type?: 'json' | 'sql') => {
  content.value = con || ''
  title.value = type === 'sql' ? '查看 SQL' : '查看配置'
  modelRef.value?.open()
}

async function copyContent() {
  if (!content.value) {
    ElMessage.info('无内容可复制')
    return
  }
  let copyCon = toRaw(content.value)
  if (typeof copyCon === 'object') {
    copyCon = JSON.stringify(copyCon)
  }
  try {
    await navigator.clipboard.writeText(copyCon)
    ElMessage.success('已复制')
  } catch {
    // fallback
    const ta = document.createElement('textarea')
    ta.value = content.value
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    ElMessage.success('已复制')
  }
}

defineExpose({
  open
})
</script>

<style scoped>
.sql-toolbar {
  display: flex;
  justify-content: flex-end;
  position: absolute;
  top: 11px;
  right: 45px;
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
