<template>
  <div class="board-view">
    <section class="board-workspace">
      <div class="board-main">
        <div v-if="previewResult" class="preview-panel">
          <div class="preview-header">
            <div class="preview-copy">
              <strong>当前预览</strong>
              <span>通过右侧透视表配置生成，可直接保存到看板</span>
            </div>
            <div class="preview-actions">
              <el-button size="small" @click="clearPreview">清空预览</el-button>
              <el-button size="small" type="primary" @click="openSaveDialog">保存到看板</el-button>
            </div>
          </div>
          <div class="preview-chart">
            <VegaLiteRenderer
              :data="previewResult.data"
              :config="previewConfig"
              :chart-type="previewConfig?.chart_type || 'bar'"
              :columns="previewResult.columns"
              :sql="previewResult.sql"
              :execution-time-ms="previewResult.execution_time_ms"
            />
          </div>
        </div>

        <div class="board-list-wrap">
          <ChartBoard @edit="loadToAnalysis" />
        </div>
      </div>

      <button
        type="button"
        class="sidebar-toggle"
        :class="{ 'is-open': showConfigPanel }"
        @click="showConfigPanel = !showConfigPanel"
      >
        <el-icon :size="16">
          <ArrowRightBold v-if="showConfigPanel" />
          <ArrowLeftBold v-else />
        </el-icon>
      </button>

      <aside class="board-sidebar" :class="{ 'is-open': showConfigPanel }">
        <div class="board-sidebar-inner">
          <ConfigPanel v-if="showConfigPanel" :api="pivotApi" />
        </div>
      </aside>
    </section>

    <!-- AI 对话按钮 -->
    <el-button
      :type="showAiDialog ? 'success' : 'default'"
      circle
      size="large"
      class="board-ai-button"
      :style="{ right: showConfigPanel ? '392px' : '24px' }"
      @click="showAiDialog = !showAiDialog"
    >
      <el-icon :size="20"><ChatDotRound /></el-icon>
    </el-button>

    <!-- AI 对话弹窗 -->
    <el-dialog
      v-model="showAiDialog"
      title="AI 对话分析"
      width="600px"
      top="5vh"
      destroy-on-close
    >
      <AIDialog @save="handleSaveToBoard" />
    </el-dialog>

    <el-dialog v-model="showSaveDialog" title="保存到看板" width="400px">
      <el-form label-position="top">
        <el-form-item label="图表名称">
          <el-input v-model="saveTitle" placeholder="输入图表名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="saveDesc" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSaveDialog = false">取消</el-button>
        <el-button type="primary" :loading="chartStore.loading" @click="handlePreviewSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { MAX_BOARD_CHARTS, useChartStore } from '@/stores/useChartStore'
import type { SavedChart } from '@/stores/useChartStore'
import type { PivotConfig, PivotResponse } from '@/types'
import ChartBoard from '@/components/ChartBoard.vue'
import AIDialog from '@/components/AIDialog.vue'
import ConfigPanel from '@/components/ConfigPanel.vue'
import VegaLiteRenderer from '@/components/VegaLiteRenderer.vue'
import { ArrowLeftBold, ArrowRightBold, ChatDotRound } from '@element-plus/icons-vue'

const router = useRouter()
const chartStore = useChartStore()

const showAiDialog = ref(false)
const showConfigPanel = ref(false)
const previewResult = ref<PivotResponse | null>(null)
const previewConfig = ref<any>(null)
const showSaveDialog = ref(false)
const saveTitle = ref('')
const saveDesc = ref('')

function loadToAnalysis(chart: SavedChart) {
  void chart
  router.push('/set')
}

async function pivotApi(config: any) {
  previewConfig.value = config
  try {
    const resp = await fetch('/api/pivot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    })

    if (!resp.ok) {
      const err = await resp.json()
      throw new Error(err.detail || '查询失败')
    }

    previewResult.value = await resp.json()
  } catch (e: any) {
    ElMessage.error(e.message || '查询失败')
  }
}

async function handleSaveToBoard(chart: Omit<SavedChart, 'id' | 'created_at' | 'updated_at'>) {
  const saved = await chartStore.saveChart(chart.title, chart.pivot_config as PivotConfig, chart.description || '', chart.chart_type, chart.data)
  if (!saved) {
    ElMessage.warning(chartStore.error || `看板最多只能保存 ${MAX_BOARD_CHARTS} 个`)
    return
  }
  showAiDialog.value = false
}

function clearPreview() {
  previewResult.value = null
  previewConfig.value = null
}

function openSaveDialog() {
  if (!previewResult.value || !previewConfig.value) return
  if (!saveTitle.value.trim()) {
    saveTitle.value = '未命名图表'
  }
  showSaveDialog.value = true
}

async function handlePreviewSave() {
  if (!previewResult.value || !previewConfig.value || !saveTitle.value.trim()) return

  const saved = await chartStore.saveChart(
    saveTitle.value,
    previewConfig.value as PivotConfig,
    saveDesc.value,
    previewConfig.value?.chart_type || 'bar',
    previewResult.value.data,
  )

  if (!saved) {
    ElMessage.warning(chartStore.error || `看板最多只能保存 ${MAX_BOARD_CHARTS} 个`)
    return
  }

  showSaveDialog.value = false
  saveTitle.value = ''
  saveDesc.value = ''
}
</script>

<style scoped>
.board-view {
  flex: 1;
  overflow: hidden;
  padding: 0;
  position: relative;
}

.board-workspace {
  height: 100%;
  display: flex;
  position: relative;
  overflow: hidden;
}

.board-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.24s ease;
}

.preview-panel {
  margin: 12px 12px 0;
  background: #ffffff;
  border: 1px solid #e8edf5;
  border-radius: 14px;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
  overflow: hidden;
  flex-shrink: 0;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 1px solid #edf2f7;
}

.preview-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.preview-copy strong {
  font-size: 15px;
  color: #303133;
}

.preview-copy span {
  font-size: 12px;
  color: #909399;
}

.preview-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.preview-chart {
  height: 380px;
  padding: 0 16px 16px;
}

.board-list-wrap {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.board-sidebar {
  width: 0;
  flex-shrink: 0;
  overflow: hidden;
  background: #f5f7fa;
  border-left: 1px solid transparent;
  transition: width 0.24s ease, border-color 0.24s ease;
}

.board-sidebar.is-open {
  width: 368px;
  border-left-color: #e4e7ed;
}

.board-sidebar-inner {
  width: 368px;
  height: 100%;
  padding: 10px 10px 10px 12px;
  overflow-y: auto;
}

.sidebar-toggle {
  position: absolute;
  top: 50%;
  right: 0;
  transform: translate(50%, -50%);
  width: 30px;
  height: 64px;
  border: 1px solid #dbe4f0;
  border-radius: 16px;
  background: #ffffff;
  color: #409eff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
  z-index: 20;
  cursor: pointer;
  transition: right 0.24s ease, background 0.2s ease, color 0.2s ease;
}

.sidebar-toggle:hover {
  background: #409eff;
  color: #ffffff;
}

.sidebar-toggle.is-open {
  right: 368px;
}

.board-ai-button {
  position: fixed;
  bottom: 24px;
  z-index: 1000;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  transition: right 0.24s ease;
}

@media (max-width: 1100px) {
  .preview-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .preview-chart {
    height: 320px;
  }
}

@media (max-width: 960px) {
  .board-sidebar {
    position: absolute;
    top: 0;
    right: 0;
    height: 100%;
    z-index: 15;
    box-shadow: -12px 0 24px rgba(15, 23, 42, 0.08);
  }

  .board-sidebar.is-open {
    width: min(368px, calc(100vw - 48px));
  }

  .board-sidebar-inner {
    width: min(368px, calc(100vw - 48px));
  }

  .sidebar-toggle.is-open {
    right: min(368px, calc(100vw - 48px));
  }

  .board-ai-button {
    right: 24px !important;
  }
}
</style>
