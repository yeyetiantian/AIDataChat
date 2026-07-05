<template>
  <div class="vega-renderer" ref="chartContainer">
    <div v-if="!canRender" class="empty-state">
      <el-icon :size="48" color="#c0c4cc"><Histogram /></el-icon>
      <p>拖拽字段并点击查询生成图表</p>
    </div>

    <template v-else>
      <!-- 工具栏 -->
      <div class="chart-toolbar">
        <span v-if="props.executionTimeMs != null" class="exec-time">
          耗时 {{ props.executionTimeMs }}ms
        </span>
        <div class="toolbar-actions">
          <el-button size="small" text @click="showDataDialog = true">查看数据</el-button>
          <el-button v-if="props.sql" size="small" text @click="showSqlDialog = true">查看 SQL</el-button>
          <el-button size="small" text @click="toggleFullscreen">全屏</el-button>
        </div>
      </div>

      <!-- 图表容器 -->
      <div ref="vegaContainer" class="vega-container"></div>

      <!-- 建议标签 -->
      <div v-if="suggestions.length" class="chart-suggestions">
        <el-tag
          v-for="s in suggestions" :key="s"
          size="small"
          class="suggest-tag"
          @click="$emit('suggest', s)"
        >
          {{ s }}
        </el-tag>
      </div>
    </template>

    <!-- SQL 弹窗 -->
    <el-dialog v-model="showSqlDialog" title="SQL" width="70%" top="5vh" destroy-on-close>
      <pre class="sql-pre">{{ props.sql || '' }}</pre>
    </el-dialog>

    <!-- 数据弹窗 -->
    <el-dialog v-model="showDataDialog" title="查询数据" width="80%" top="5vh" destroy-on-close>
      <el-table
        v-if="props.data"
        :data="props.data"
        border stripe size="small" max-height="600" style="width: 100%"
      >
        <el-table-column
          v-for="col in displayColumns" :key="col"
          :prop="col" :label="col" min-width="100"
        />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, nextTick } from 'vue'
import { Histogram } from '@element-plus/icons-vue'
import embed from 'vega-embed'

const props = defineProps<{
  data?: Record<string, any>[] | null
  config?: Record<string, any> | null
  chartType?: string
  loading?: boolean
  columns?: string[]
  sql?: string | null
  executionTimeMs?: number
}>()

const emit = defineEmits<{
  suggest: [text: string]
}>()

const chartContainer = ref<HTMLElement | null>(null)
const vegaContainer = ref<HTMLElement | null>(null)
const showDataDialog = ref(false)
const showSqlDialog = ref(false)

// 数据弹窗的列名：优先用 props.columns，否则从 data 首行取 key
const displayColumns = computed(() => {
  if (props.columns && props.columns.length) return props.columns
  if (props.data && props.data.length) return Object.keys(props.data[0])
  return []
})

/**
 * 根据 data / config / chartType 构建 Vega-Lite spec
 *
 * 两种数据模式：
 *   - 无 legend：轴(alias) × 值(field)，单列直接引用
 *   - 有 legend：PIVOT 展开，数据列名为 {legend_value}_{value_alias}，
 *                用 fold 变换将多列展开为 key-value 对
 */
function buildVegaSpec(): Record<string, any> | null {
  const data = props.data
  const config = props.config
  if (!data || !data.length || !config) return null

  const axes = config.axes || []
  const values = config.values || []
  const legend = config.legend || []
  const chartType = props.chartType || 'bar'

  const xField = axes[0]?.alias || axes[0]?.field || ''
  const xTitle = axes[0]?.alias || xField
  const mark = { type: chartType === 'pie' ? 'arc' : chartType, tooltip: true, point: chartType === 'line' }

  // —— 有 legend（PIVOT 模式）：数据列名是 {legend_value}_{value_alias} ——
  if (legend.length) {
    const legendName = legend[0]?.alias || legend[0]?.field || ''
    // 已知列：轴列 + 图例原始字段 + 值字段
    const knownCols = new Set([
      xField,
      legendName,
      ...axes.map((a: any) => a.alias || a.field),
      ...legend.map((l: any) => l.alias || l.field),
    ])
    // 数据中实际的值列 = 所有列 - 已知列
    const valueCols = Object.keys(data[0]).filter(k => !knownCols.has(k))
    if (!valueCols.length) return null

    const encoding: any = {
      x: { field: xField, type: 'nominal', title: xTitle },
      y: { field: 'value', type: 'quantitative', title: values[0]?.alias || '数值' },
      color: { field: 'key', type: 'nominal', title: legendName },
    }

    return {
      $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
      title: '数据分析',
      width: 'container',
      height: 'container',
      data: { values: data },
      transform: [{ fold: valueCols, as: ['key', 'value'] }],
      mark,
      encoding,
    }
  }

  // —— 无 legend（简单 GROUP BY）：直接引用列名 ——
  const yField = values[0]?.field || values[0]?.alias || ''
  const yTitle = values[0]?.alias || yField

  const encoding: any = {}
  if (chartType === 'pie') {
    if (xField) encoding.color = { field: xField, type: 'nominal', title: xTitle }
    if (yField) encoding.theta = { field: yField, type: 'quantitative', title: yTitle }
  } else {
    if (xField) encoding.x = { field: xField, type: 'nominal', title: xTitle }
    if (yField) encoding.y = { field: yField, type: 'quantitative', title: yTitle }
    if (chartType === 'line' && axes[0]?.group) {
      encoding.x.type = 'temporal'
    }
  }

  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
    title: '数据分析',
    width: 'container',
    height: 260,
    data: { values: data },
    mark,
    encoding,
  }
}

const canRender = computed(() => {
  return props.data && props.data.length > 0 && props.config
})

// 根据当前图表生成 3 个相关建议
const suggestions = computed(() => {
  const result: string[] = []
  const config = props.config
  const axes = config?.axes || []
  const legend = config?.legend || []
  const values = config?.values || []
  if (!axes.length || !values.length) return result

  const chartType = props.chartType || 'bar'
  const xField = axes[0]?.alias || axes[0]?.field || ''
  const xTitle = axes[0]?.alias || xField

  // 1. 筛选第一个数据值（如果有有效数据）
  if (props.data?.length && xField) {
    const firstVal = props.data[0][xField]
    if (firstVal) {
      result.push(`只看"${firstVal}"的数据`)
    }
  }

  // 2. 切换图表类型
  const nextType: Record<string, string> = { bar: 'line', line: 'pie', pie: 'area', area: 'bar', point: 'line', radar: 'bar' }
  const typeName: Record<string, string> = { bar: '柱状图', line: '折线图', pie: '饼状图', area: '波形图', point: '散点图', radar: '雷达图' }
  const nt = nextType[chartType] || 'bar'
  result.push(`改成${typeName[nt] || nt}`)

  // 3. 按时间趋势 / 规则类型分组
  if (!legend.length) {
    result.push(`按时间趋势查看`)
  } else {
    result.push(`只看${values[0]?.alias || '数值'}最高的`)
  }

  return result
})

function toggleFullscreen() {
  const el = chartContainer.value
  if (!el) return
  if (document.fullscreenElement) {
    document.exitFullscreen()
  } else {
    el.requestFullscreen()
  }
}

async function renderChart() {
  const spec = buildVegaSpec()
  if (!spec || !vegaContainer.value) return

  try {
    vegaContainer.value.innerHTML = ''

    const plainSpec = JSON.parse(JSON.stringify(spec))

    console.log('Vega-Lite spec:', plainSpec)

    await embed(vegaContainer.value, plainSpec, {
      actions: {
        export: { svg: true, png: true },
        source: false,
        compiled: false,
        editor: false,
      },
      tooltip: true,
    })
  } catch (e) {
    console.error('Vega-Lite 渲染失败:', e)
  }
}

watch(
  () => props.data ? JSON.stringify(props.data) + '|' + JSON.stringify(props.config) + '|' + (props.chartType || '') : null,
  async () => {
    await nextTick()
    await renderChart()
  }
)

onMounted(async () => {
  await nextTick()
  if (canRender.value) {
    await renderChart()
  }
})
</script>

<style scoped>
.vega-renderer {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: white;
  border-radius: 8px;
  padding: 0;
  min-height: 300px;
  overflow: hidden;
}

.empty-state {
  text-align: center;
  color: #c0c4cc;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
}

.empty-state p {
  font-size: 14px;
}

.chart-toolbar {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  flex-shrink: 0;
}

.toolbar-actions {
  display: flex;
  gap: 4px;
  align-items: center;
}

.exec-time {
  color: #909399;
  font-size: 12px;
}

.vega-container {
  flex: 1;
  width: 100%;
  overflow: hidden;
  padding: 0 16px 16px;
}

.sql-pre {
  background: #1f2937;
  color: #e5e7eb;
  padding: 12px;
  font-size: 12px;
  border-radius: 4px;
  overflow: auto;
  max-height: 320px;
  line-height: 1.55;
}

.chart-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 4px 16px 12px;
  width: 100%;
  justify-content: center;
}

.suggest-tag {
  cursor: pointer;
  border-color: #f5d0d0 !important;
  color: #d93a3a !important;
  background: #fff5f5 !important;
  font-size: 12px;
  border-radius: 12px;
  padding: 0 10px;
  transition: all 0.2s;
}
.suggest-tag:hover {
  background: #d93a3a !important;
  color: #fff !important;
  border-color: #d93a3a !important;
}
</style>
