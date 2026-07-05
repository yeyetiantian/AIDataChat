<template>
  <div class="board-view">
    <ChartBoard
      @edit="loadToAnalysis"
    />

    <!-- AI 对话按钮 -->
    <el-button
      :type="showAiDialog ? 'success' : 'default'"
      circle
      size="large"
      style="position: fixed; right: 24px; bottom: 24px; z-index: 1000; box-shadow: 0 4px 12px rgba(0,0,0,0.15);"
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
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useChartStore } from '@/stores/useChartStore'
import type { SavedChart } from '@/stores/useChartStore'
import type { PivotConfig } from '@/types'
import ChartBoard from '@/components/ChartBoard.vue'
import AIDialog from '@/components/AIDialog.vue'
import { ChatDotRound } from '@element-plus/icons-vue'

const router = useRouter()
const chartStore = useChartStore()

const showAiDialog = ref(false)

function loadToAnalysis(chart: SavedChart) {
  router.push('/')
}

async function handleSaveToBoard(chart: Omit<SavedChart, 'id' | 'created_at' | 'updated_at'>) {
  await chartStore.saveChart(chart.title, chart.pivot_config as PivotConfig, chart.description || '', chart.chart_type, chart.data)
  showAiDialog.value = false
}
</script>

<style scoped>
.board-view {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}
</style>
