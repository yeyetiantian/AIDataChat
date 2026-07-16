<template>
  <div class="monitor-view">
    <!-- Stats 概览 -->
    <section class="stats-bar">
      <div class="stat-item">
        <span class="stat-value">{{ stats.total }}</span>
        <span class="stat-label">总 Trace</span>
      </div>
      <div class="stat-item stat-success">
        <span class="stat-value">{{ stats.success }}</span>
        <span class="stat-label">成功</span>
      </div>
      <div class="stat-item stat-error">
        <span class="stat-value">{{ stats.error }}</span>
        <span class="stat-label">失败</span>
      </div>
    </section>

    <!-- Tabs 切换 -->
    <el-tabs v-model="activeTab" class="monitor-tabs" @tab-change="handleTabChange">
      <el-tab-pane label="📈 流程图" name="graph" />
      <el-tab-pane label="💬 详细日志" name="logs" />
    </el-tabs>

    <div class="monitor-body">

      <!-- ====== Tab: 流程图 ====== -->
      <div v-show="activeTab === 'graph'" class="tab-content">
        <section class="monitor-section">
          <div class="section-header">
            <h3>Agent 流程图</h3>
            <div class="section-header-actions">
              <el-select
                v-model="graphTraceId"
                placeholder="选择 Trace（最后一个）"
                size="small"
                clearable
                style="width:260px"
                @change="renderDynamicGraph"
              >
                <el-option
                  v-for="t in traceList"
                  :key="t.id"
                  :label="`${t.request_message?.slice(0, 30) || '?'}... [${t.status}]`"
                  :value="t.id"
                />
              </el-select>
              <el-tooltip content="刷新流程图" placement="top">
                <el-button size="small" circle @click="refreshGraph">
                  <el-icon><Refresh /></el-icon>
                </el-button>
              </el-tooltip>
            </div>
          </div>
          <div class="graph-container">
            <div v-if="graphLoading" class="graph-loading">
              <el-icon class="is-loading" :size="28"><Loading /></el-icon>
              <span>加载流程图...</span>
            </div>
            <div v-show="!graphLoading" ref="mermaidRef" class="mermaid-wrapper" v-html="svgContent"></div>
            <div v-if="!graphLoading && !svgContent" class="graph-empty">
              <span>请选择一个 Trace 查看动态流程图</span>
            </div>
          </div>
          <div class="raw-code-section">
            <div class="raw-code-header">
              <span class="raw-code-label">Mermaid 原始代码</span>
              <el-button size="small" text @click="copyMermaidCode">
                {{ copyDone ? '已复制 ✓' : '复制代码' }}
              </el-button>
            </div>
            <pre class="raw-code-block"><code>{{ mermaidCode }}</code></pre>
          </div>
        </section>
      </div>

      <!-- ====== Tab: 详细日志（LangSmith 风格 Trace 视图） ====== -->
      <div v-show="activeTab === 'logs'" class="tab-content">
        <section class="monitor-section trace-section">
          <div class="section-header">
            <h3>Trace 日志</h3>
            <div class="section-header-actions">
              <el-select
                v-model="filterSessionId"
                placeholder="全部会话"
                size="small"
                clearable
                style="width:200px"
              >
                <el-option
                  v-for="s in sessionOptions"
                  :key="s.value"
                  :label="s.label"
                  :value="s.value"
                />
              </el-select>
              <el-button size="small" @click="refreshLogs">
                <el-icon><Refresh /></el-icon> 刷新
              </el-button>
            </div>
          </div>

          <!-- Trace 列表 -->
          <div class="trace-list">
            <div
              v-for="trace in filteredTraces"
              :key="trace.id"
              class="trace-card"
            >
              <!-- Trace 头部摘要 -->
              <div class="trace-header" @click="toggleTrace(trace)">
                <div class="trace-header-left">
                  <div
                    class="trace-status-dot"
                    :class="trace.status === 'success' ? 'trace-status-success' : 'trace-status-error'"
                  />
                  <div>
                    <div class="trace-title">{{ trace.requestMessage || trace.request_message || trace.id }}</div>
                    <div class="trace-meta">
                      <span class="trace-meta-item">{{ trace.time || trace.created_at }}</span>
                      <span class="trace-meta-divider">|</span>
                      <span class="trace-meta-item">ID: {{ trace.id }}</span>
                      <span class="trace-meta-divider">|</span>
                      <span class="trace-meta-item">{{ trace.rootSpan?.duration || trace.agent_name }}</span>
                    </div>
                  </div>
                </div>
                <div class="trace-header-right">
                  <span
                    class="trace-type-badge"
                    :class="trace.status === 'success' ? 'trace-type-agent' : 'trace-type-tool'"
                  >{{ trace.agent_name || 'Agent' }}</span>
                  <button
                    class="trace-expand-btn"
                    :class="{ 'is-expanded': trace._expanded }"
                    @click.stop="toggleTrace(trace)"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
                  </button>
                </div>
              </div>

              <!-- Trace 展开内容：递归 Span 树 -->
              <div v-if="trace._expanded" class="trace-body">
                <div v-if="!trace.rootSpan" class="trace-body-loading">
                  <el-icon class="is-loading" :size="16"><Loading /></el-icon>
                  <span>加载详情中...</span>
                </div>
                <TraceSpanNode
                  v-else
                  :span="trace.rootSpan"
                  :depth="0"
                  @toggle="onToggleSpan"
                />
              </div>
            </div>
          </div>

          <div v-if="filteredTraces.length === 0 && !loadingTraces" class="log-empty">
            暂无 Trace 日志记录
          </div>
          <div v-if="loadingTraces" class="log-empty">
            <el-icon class="is-loading" :size="20"><Loading /></el-icon>
            <span>加载中...</span>
          </div>
        </section>
      </div>

    </div>

    <!-- Span 详情弹窗 -->
    <el-dialog
      v-model="detailVisible"
      :title="detailTitle"
      width="860px"
      top="4vh"
      destroy-on-close
    >
      <div class="detail-body">
        <div class="detail-body-tabs">
          <button
            v-for="tab in spanDetailTabs"
            :key="tab.key"
            class="detail-body-tab"
            :class="{ active: activeSpanDetailTab === tab.key }"
            @click="activeSpanDetailTab = tab.key as typeof activeSpanDetailTab"
          >{{ tab.label }}</button>
        </div>

        <div v-if="activeSpanDetailTab === 'input'" class="detail-block">
          <div class="detail-block-label">Input</div>
          <pre class="detail-pre"><code>{{ formatJson(spanDetailItem?.input) }}</code></pre>
        </div>

        <div v-if="activeSpanDetailTab === 'output'" class="detail-block">
          <div class="detail-block-label">Output</div>
          <pre class="detail-pre"><code>{{ formatJson(spanDetailItem?.output) }}</code></pre>
        </div>

        <div v-if="activeSpanDetailTab === 'messages'" class="detail-block">
          <div class="detail-block-label">Messages ({{ spanDetailItem?.messages?.length || 0 }})</div>
          <div class="detail-messages">
            <div
              v-for="(msg, mi) in spanDetailItem?.messages || []"
              :key="mi"
              class="detail-msg"
              :class="'detail-msg--' + msg.role"
            >
              <div class="detail-msg-role">{{ msg.role }}</div>
              <pre class="detail-msg-content">{{ msg.content }}</pre>
            </div>
          </div>
        </div>

        <div v-if="activeSpanDetailTab === 'metadata'" class="detail-block">
          <div class="detail-block-label">Metadata</div>
          <pre class="detail-pre"><code>{{ formatJson(spanDetailMeta) }}</code></pre>
        </div>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Loading } from '@element-plus/icons-vue'
import mermaid from 'mermaid'
import TraceSpanNode from '@/components/TraceSpanNode.vue'

/* ========== 类型定义 ========== */

interface TraceMessage {
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: string
}

interface TraceSpan {
  id: string
  name: string
  type: 'agent' | 'llm' | 'chain' | 'tool'
  status: 'success' | 'error'
  startTime: string
  endTime?: string
  duration: string
  durationMs?: number
  tokens?: { input: number; output: number }
  input: any
  output: any
  messages?: TraceMessage[]
  children: TraceSpan[]
  error?: string
  _expanded?: boolean
}

interface TraceSummary {
  id: string
  session_id: string
  request_message: string
  requestMessage: string
  agent_name: string
  status: string
  created_at: string
  time: string
  rootSpan: TraceSpan | null
  root_span?: TraceSpan
  _expanded?: boolean
  _detailLoaded?: boolean
}

interface MonitorStats {
  total: number
  success: number
  error: number
}

/* ========== 初始化 Mermaid ========== */

mermaid.initialize({
  startOnLoad: false,
  theme: 'default',
  securityLevel: 'loose',
  flowchart: { useMaxWidth: true, htmlLabels: true, curve: 'basis' },
})

/* ========== 统计数据 ========== */

const stats = ref<MonitorStats>({ total: 0, success: 0, error: 0 })

async function fetchStats() {
  try {
    const resp = await fetch('/api/monitor/stats')
    if (resp.ok) stats.value = await resp.json()
  } catch { /* ignore */ }
}

/* ========== Tabs ========== */

const activeTab = ref<'graph' | 'logs'>('graph')

function handleTabChange(name: string | number) {
  if (name === 'graph' && traceList.value.length === 0) {
    fetchTraceList()
  } else if (name === 'logs' && traces.value.length === 0) {
    fetchRealTraces()
  }
}

/* ========== 动态流程图（基于真实 Trace 数据） ========== */

const graphTraceId = ref('')
const graphLoading = ref(false)
const mermaidRef = ref<HTMLElement | null>(null)
const svgContent = ref('')
const mermaidCode = ref('')
const copyDone = ref(false)
const traceList = ref<TraceSummary[]>([])

async function fetchTraceList() {
  try {
    const resp = await fetch('/api/monitor/traces?limit=50&offset=0')
    if (resp.ok) {
      const data = await resp.json()
      traceList.value = (data.traces || []).map((t: any) => ({
        ...t,
        requestMessage: t.request_message || t.id,
        time: t.created_at || '',
      }))
    }
  } catch { /* ignore */ }
}

/** 从 Span 树生成 Mermaid 流程图 */
function spanToMermaid(span: TraceSpan, parentId: string | null): string[] {
  const lines: string[] = []
  const nodeId = span.id || `s_${Math.random().toString(36).slice(2, 8)}`
  const statusEmoji = span.status === 'error' ? '❌' : '✅'
  const nodeLabel = `${statusEmoji} ${span.name}\\n(${span.duration || '-'})`
  lines.push(`  ${nodeId}["${nodeLabel}"]`)

  if (parentId) {
    lines.push(`  ${parentId} --> ${nodeId}`)
  }

  for (const child of span.children || []) {
    lines.push(...spanToMermaid(child, nodeId))
  }

  return lines
}

async function renderDynamicGraph() {
  if (!graphTraceId.value) return
  graphLoading.value = true
  svgContent.value = ''

  try {
    const resp = await fetch(`/api/monitor/traces/${graphTraceId.value}`)
    if (!resp.ok) throw new Error('Failed to fetch trace')
    const data = await resp.json()
    const rootSpan: TraceSpan = data.root_span || data.rootSpan

    if (!rootSpan) {
      mermaidCode.value = 'graph TD\n  EMPTY["无 Span 数据"]'
      const { svg } = await mermaid.render('agent-dynamic-flow', mermaidCode.value)
      svgContent.value = svg
      return
    }

    const lines: string[] = ['graph TD']
    lines.push(...spanToMermaid(rootSpan, null))
    mermaidCode.value = lines.join('\n')

    const { svg } = await mermaid.render('agent-dynamic-flow', mermaidCode.value)
    svgContent.value = svg
  } catch (e) {
    console.error('Dynamic graph error:', e)
    mermaidCode.value = `graph TD\n  ERROR["渲染失败: ${e}"]`
    try {
      const { svg } = await mermaid.render('agent-dynamic-flow', mermaidCode.value)
      svgContent.value = svg
    } catch {}
  } finally {
    graphLoading.value = false
  }
}

async function refreshGraph() {
  await fetchTraceList()
  if (traceList.value.length > 0 && !graphTraceId.value) {
    graphTraceId.value = traceList.value[0].id
  }
  await renderDynamicGraph()
  ElMessage.success('流程图已刷新')
}

async function copyMermaidCode() {
  try {
    await navigator.clipboard.writeText(mermaidCode.value)
    copyDone.value = true
    setTimeout(() => { copyDone.value = false }, 2000)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选中复制')
  }
}

/* ========== Trace 日志（从 API 加载） ========== */

const traces = ref<TraceSummary[]>([])
const loadingTraces = ref(false)
const filterSessionId = ref('')
const sessionOptions = ref<{ value: string; label: string }[]>([])

const filteredTraces = computed(() => {
  if (!filterSessionId.value) return traces.value
  return traces.value.filter(t => t.session_id === filterSessionId.value)
})

/** 从后端加载 trace 摘要列表（不加载详情，点击展开时按需加载） */
async function fetchRealTraces() {
  loadingTraces.value = true
  try {
    const resp = await fetch('/api/monitor/traces?limit=50&offset=0')
    if (!resp.ok) throw new Error('Failed')
    const data = await resp.json()
    const summaries = data.traces || []

    traces.value = summaries.map((s: any) => ({
      ...s,
      requestMessage: s.request_message || s.id,
      time: s.created_at || '',
      rootSpan: null as TraceSpan | null,
      _expanded: false,
      _detailLoaded: false,
    }))

    // Update session filter options
    const seen = new Map<string, string>()
    for (const t of traces.value) {
      if (t.session_id && !seen.has(t.session_id)) {
        seen.set(t.session_id, t.requestMessage.slice(0, 40))
      }
    }
    sessionOptions.value = Array.from(seen.entries()).map(([value, label]) => ({ value, label }))
  } catch (e) {
    console.error('Failed to load traces:', e)
    ElMessage.error('加载 Trace 日志失败')
  } finally {
    loadingTraces.value = false
  }
}

async function toggleTrace(trace: TraceSummary) {
  if (!trace._expanded && !trace._detailLoaded) {
    // 点击展开，按需加载详情
    try {
      const detailResp = await fetch(`/api/monitor/traces/${trace.id}`)
      if (detailResp.ok) {
        const detail = await detailResp.json()
        const rootSpan: TraceSpan = detail.root_span || detail.rootSpan
        trace.rootSpan = rootSpan || { id: 'empty', name: 'No Data', type: 'chain', status: 'success', startTime: '', duration: '', input: null, output: null, children: [] } as TraceSpan
      }
    } catch { /* ignore */ }
    trace._detailLoaded = true
  }
  trace._expanded = !trace._expanded
}

function onToggleSpan(span: TraceSpan) {
  span._expanded = !span._expanded
}

async function refreshLogs() {
  await fetchRealTraces()
  ElMessage.success('Trace 日志已刷新')
}

/* ========== Span 详情弹窗 ========== */

const detailVisible = ref(false)
const spanDetailItem = ref<TraceSpan | null>(null)
const activeSpanDetailTab = ref<'input' | 'output' | 'messages' | 'metadata'>('input')

const spanDetailTabs = computed(() => {
  const tabs: any[] = [
    { key: 'input' as const, label: 'Input' },
    { key: 'output' as const, label: 'Output' },
  ]
  if (spanDetailItem.value?.messages?.length) {
    tabs.push({ key: 'messages' as const, label: `Messages (${spanDetailItem.value.messages.length})` })
  }
  tabs.push({ key: 'metadata' as const, label: 'Metadata' })
  return tabs
})

const spanDetailMeta = computed(() => {
  const item = spanDetailItem.value
  if (!item) return {}
  return {
    span_id: item.id,
    type: item.type,
    status: item.status,
    start_time: item.startTime,
    end_time: item.endTime,
    duration: item.duration,
    duration_ms: item.durationMs,
    tokens: item.tokens,
    error: item.error,
  }
})

const detailTitle = ref('')

function handleTraceOpenDetail(e: CustomEvent) {
  openSpanDetail(e.detail as TraceSpan)
}

function openSpanDetail(span: TraceSpan) {
  spanDetailItem.value = span
  activeSpanDetailTab.value = span.messages?.length ? 'messages' : 'input'
  detailTitle.value = `${span.name} — ${span.type.toUpperCase()}`
  detailVisible.value = true
}

/* ========== 工具函数 ========== */

function formatJson(value: any): string {
  if (!value) return ''
  if (typeof value === 'string') {
    try { return JSON.stringify(JSON.parse(value), null, 2) } catch { return value }
  }
  return JSON.stringify(value, null, 2)
}

/* ========== 生命周期 ========== */

onMounted(async () => {
  await fetchStats()
  window.addEventListener('trace:open-detail', handleOpenDetailEvent)
  // 默认加载流程图 trace 列表
  await fetchTraceList()
  if (traceList.value.length > 0) {
    graphTraceId.value = traceList.value[0].id
    await renderDynamicGraph()
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('trace:open-detail', handleOpenDetailEvent)
})

function handleOpenDetailEvent(e: Event) {
  const span = (e as CustomEvent).detail
  if (span) openSpanDetail(span)
}
</script>

<style scoped>
.monitor-view {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
  padding: 16px 24px 20px;
  gap: 12px;
}

/* ====== Stats Bar ====== */

.stats-bar {
  display: flex;
  gap: 16px;
  flex-shrink: 0;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 80px;
  padding: 10px 20px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  gap: 2px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: #909399;
}

.stat-success .stat-value { color: #67c23a; }
.stat-error .stat-value { color: #f56c6c; }

/* ====== Tabs ====== */

.monitor-tabs {
  flex-shrink: 0;
  background: #fff;
  border-radius: 10px 10px 0 0;
  padding: 0 16px;
  border: 1px solid #e4e7ed;
  border-bottom: none;
}

:deep(.monitor-tabs .el-tabs__header) {
  margin-bottom: 0;
}

:deep(.monitor-tabs .el-tabs__nav-wrap::after) {
  display: none;
}

:deep(.monitor-tabs .el-tabs__item) {
  font-size: 14px;
  font-weight: 500;
  height: 44px;
  padding: 0 20px;
}

/* ====== Body / Tab content ====== */

.monitor-body {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.tab-content {
  flex: 1;
  overflow-y: auto;
  padding-top: 12px;
  display: flex;
  flex-direction: column;
}

.monitor-section {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 12px;
}

.section-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.section-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ====== Graph ====== */

.graph-container {
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e8eaed;
  border-radius: 8px;
  background: #fafbfc;
  overflow-x: auto;
  padding: 16px;
}

.graph-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #909399;
  font-size: 13px;
}

.graph-empty {
  color: #909399;
  font-size: 14px;
  padding: 40px 0;
}

.mermaid-wrapper {
  width: 100%;
  display: flex;
  justify-content: center;
}

.graph-render-error {
  color: #f56c6c;
  font-size: 13px;
  padding: 20px;
}

.raw-code-section {
  margin-top: 12px;
}

.raw-code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.raw-code-label {
  font-size: 12px;
  font-weight: 600;
  color: #606266;
}

.raw-code-block {
  background: #f6f8fa;
  border: 1px solid #e8eaed;
  border-radius: 6px;
  padding: 10px 14px;
  margin: 0;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.5;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  max-height: 180px;
  overflow-y: auto;
}

.raw-code-block code {
  white-space: pre;
}

/* ====== Trace Section ====== */

.trace-section {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.trace-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ====== Trace Card ====== */

.trace-card {
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  background: #fafbfc;
  transition: box-shadow 0.15s;
}

.trace-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.trace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  cursor: pointer;
  user-select: none;
  background: #fff;
  border-bottom: 1px solid transparent;
  transition: background 0.15s;
}

.trace-header:hover {
  background: #f8f9fb;
}

.trace-header-left {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.trace-status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 4px;
}

.trace-status-success {
  background: #52c41a;
  box-shadow: 0 0 0 2px rgba(82, 196, 26, 0.15);
}

.trace-status-error {
  background: #ff4d4f;
  box-shadow: 0 0 0 2px rgba(255, 77, 79, 0.15);
}

.trace-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.4;
}

.trace-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
  font-size: 12px;
  color: #909399;
}

.trace-meta-divider {
  color: #dcdfe6;
}

.trace-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.trace-type-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.3px;
  text-transform: uppercase;
}

.trace-type-agent {
  background: #f0f5ff;
  color: #409eff;
}

.trace-type-tool {
  background: #fff7ed;
  color: #ea580c;
}

.trace-expand-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: #909399;
  cursor: pointer;
  transition: all 0.15s;
}

.trace-expand-btn:hover {
  background: #e8eaed;
  color: #303133;
}

.trace-expand-btn.is-expanded svg {
  transform: rotate(90deg);
}

.trace-expand-btn svg {
  transition: transform 0.2s ease;
}

.trace-body {
  padding: 0;
}

.trace-body-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px;
  color: #909399;
  font-size: 13px;
}

.log-empty {
  padding: 48px 0;
  text-align: center;
  color: #909399;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

/* ====== Span Detail Dialog ====== */

.detail-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 68vh;
  overflow-y: auto;
}

.detail-body-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid #e8eaed;
  padding-bottom: 0;
  flex-shrink: 0;
}

.detail-body-tab {
  appearance: none;
  padding: 8px 16px;
  border: none;
  background: transparent;
  color: #606266;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: all 0.15s;
}

.detail-body-tab:hover { color: #303133; }
.detail-body-tab.active { color: #409eff; border-bottom-color: #409eff; }

.detail-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detail-block-label {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  padding-bottom: 4px;
  border-bottom: 1px solid #f0f0f0;
}

.detail-pre {
  background: #f6f8fa;
  border: 1px solid #e8eaed;
  border-radius: 6px;
  padding: 12px 16px;
  font-size: 13px;
  line-height: 1.5;
  overflow-x: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  color: #374151;
}

.detail-messages { display: flex; flex-direction: column; gap: 8px; }

.detail-msg {
  border: 1px solid #e8eaed;
  border-radius: 8px;
  overflow: hidden;
}

.detail-msg--system { border-color: #e0d4fc; background: #f8f6ff; }
.detail-msg--user { border-color: #b3d4fc; background: #f5f9ff; }
.detail-msg--assistant { border-color: #b7eb8f; background: #f6ffed; }
.detail-msg--tool { border-color: #ffd591; background: #fff7e6; }

.detail-msg-role {
  padding: 6px 12px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid inherit;
  color: #606266;
}

.detail-msg--system .detail-msg-role { color: #7c3aed; }
.detail-msg--user .detail-msg-role { color: #1a73e8; }
.detail-msg--assistant .detail-msg-role { color: #16a34a; }
.detail-msg--tool .detail-msg-role { color: #ea580c; }

.detail-msg-content {
  padding: 10px 12px;
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  color: #374151;
}
</style>
