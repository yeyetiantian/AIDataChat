<template>
  <div class="trace-span-node" :style="{ paddingLeft: depth * 20 + 'px' }">
    <div
      class="trace-span-card"
      :class="[
        'trace-span--' + span.status,
        { 'is-expanded': span._expanded },
      ]"
      @click="$emit('toggle', span)"
    >
      <!-- 左侧状态色条 -->
      <div class="trace-span-bar" :class="'trace-span-bar--' + span.status" />

      <div class="trace-span-body">
        <!-- 头部行 -->
        <div class="trace-span-header">
          <button class="trace-span-chevron" :class="{ 'is-open': span._expanded }" @click.stop="$emit('toggle', span)">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
          </button>

          <div class="trace-span-status-icon">
            <svg v-if="span.status === 'success'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#52c41a" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ff4d4f" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
          </div>

          <span class="trace-span-name">{{ span.name }}</span>

          <span class="trace-span-type-badge" :class="'trace-span-type--' + span.type">{{ span.type }}</span>

          <span v-if="span.tokens" class="trace-span-tokens">
            {{ span.tokens.input + span.tokens.output }} tokens
          </span>

          <span class="trace-span-duration">{{ span.duration }}</span>

          <span class="trace-span-time">{{ span.startTime }}</span>

          <!-- 查看详情按钮 -->
          <button
            class="trace-span-detail-btn"
            @click.stop="handleOpenDetail"
            title="查看完整详情"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          </button>
        </div>

        <!-- 展开内容 -->
        <div v-if="span._expanded" class="trace-span-content">
          <!-- 错误信息 -->
          <div v-if="span.error" class="trace-span-error">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <span>{{ span.error }}</span>
          </div>

          <!-- Messages (LLM) -->
          <div v-if="span.messages && span.messages.length > 0" class="trace-span-messages">
            <div
              v-for="(msg, mi) in span.messages"
              :key="mi"
              class="trace-span-msg"
              :class="'trace-span-msg--' + msg.role"
            >
              <div class="trace-span-msg-label">{{ msg.role }}</div>
              <pre class="trace-span-msg-text">{{ msg.content }}</pre>
            </div>
          </div>

          <!-- Input/Output 摘要 (非 LLM) -->
          <div v-if="!span.messages || span.messages.length === 0" class="trace-span-io">
            <div class="trace-span-io-row">
              <span class="trace-span-io-label">Input</span>
              <pre class="trace-span-io-text">{{ formatJsonPreview(span.input) }}</pre>
            </div>
            <div class="trace-span-io-row">
              <span class="trace-span-io-label">Output</span>
              <pre class="trace-span-io-text">{{ formatJsonPreview(span.output) }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 子节点 -->
    <div v-if="span._expanded && span.children.length > 0" class="trace-span-children">
      <TraceSpanNode
        v-for="child in span.children"
        :key="child.id"
        :span="child"
        :depth="depth + 1"
        @toggle="$emit('toggle', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
// 保持组件独立，避免从 Vue SFC 导入未导出的仅编译期类型。
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
  messages?: { role: 'system' | 'user' | 'assistant' | 'tool'; content: string }[]
  children: TraceSpan[]
  error?: string
  _expanded?: boolean
}

const props = defineProps<{
  span: TraceSpan
  depth: number
}>()

const emit = defineEmits<{
  toggle: [span: TraceSpan]
}>()

function formatJsonPreview(value: any): string {
  if (!value) return ''
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  if (text.length > 10000) return text.slice(0, 10000) + '...'
  return text
}

function handleOpenDetail() {
  window.dispatchEvent(new CustomEvent('trace:open-detail', { detail: props.span }))
}
</script>

<style scoped>
.trace-span-node {
  width: 100%;
}

.trace-span-card {
  display: flex;
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;
  transition: background 0.15s;
  margin: 2px 0;
  border: 1px solid transparent;
}

.trace-span-card:hover {
  background: #f8f9fb;
  border-color: #e8eaed;
}

.trace-span-card.is-expanded {
  background: #f8f9fb;
  border-color: #e8eaed;
}

/* 左侧状态色条 */
.trace-span-bar {
  width: 3px;
  flex-shrink: 0;
}

.trace-span-bar--success {
  background: #52c41a;
}

.trace-span-bar--error {
  background: #ff4d4f;
}

.trace-span-body {
  flex: 1;
  min-width: 0;
  padding: 6px 8px;
}

.trace-span-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  line-height: 1.4;
}

.trace-span-chevron {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: none;
  border-radius: 3px;
  background: transparent;
  color: #909399;
  cursor: pointer;
  flex-shrink: 0;
  padding: 0;
  transition: all 0.15s;
}

.trace-span-chevron:hover {
  background: #e8eaed;
  color: #303133;
}

.trace-span-chevron.is-open svg {
  transform: rotate(90deg);
}

.trace-span-chevron svg {
  transition: transform 0.2s ease;
}

.trace-span-status-icon {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
}

.trace-span-name {
  font-weight: 600;
  color: #1f2937;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.trace-span-type-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.3px;
  text-transform: uppercase;
  flex-shrink: 0;
}

.trace-span-type--llm {
  background: #f0fdf4;
  color: #16a34a;
}

.trace-span-type--tool {
  background: #fff7ed;
  color: #ea580c;
}

.trace-span-type--chain {
  background: #f5f3ff;
  color: #7c3aed;
}

.trace-span-type--agent {
  background: #f0f5ff;
  color: #409eff;
}

.trace-span-tokens {
  font-size: 11px;
  color: #909399;
  flex-shrink: 0;
}

.trace-span-duration {
  font-size: 12px;
  color: #606266;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.trace-span-time {
  font-size: 11px;
  color: #909399;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.trace-span-detail-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: #909399;
  cursor: pointer;
  flex-shrink: 0;
  padding: 0;
  transition: all 0.15s;
  margin-left: auto;
}

.trace-span-detail-btn:hover {
  background: #e8eaed;
  color: #409eff;
}

/* 展开内容 */
.trace-span-content {
  margin-top: 6px;
  padding-left: 24px;
}

.trace-span-error {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 6px 10px;
  background: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 4px;
  font-size: 12px;
  color: #cf1322;
  margin-bottom: 8px;
}

.trace-span-error svg {
  flex-shrink: 0;
  margin-top: 1px;
}

/* Messages */
.trace-span-messages {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.trace-span-msg {
  border: 1px solid #e8eaed;
  border-radius: 6px;
  overflow: hidden;
}

.trace-span-msg--system {
  border-color: #d0c4f0;
  background: #faf8ff;
}

.trace-span-msg--user {
  border-color: #b3d4fc;
  background: #f5f9ff;
}

.trace-span-msg--assistant {
  border-color: #b7eb8f;
  background: #f6ffed;
}

.trace-span-msg--tool {
  border-color: #ffd591;
  background: #fff7e6;
}

.trace-span-msg-label {
  padding: 3px 10px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid inherit;
}

.trace-span-msg--system .trace-span-msg-label { color: #7c3aed; }
.trace-span-msg--user .trace-span-msg-label { color: #1a73e8; }
.trace-span-msg--assistant .trace-span-msg-label { color: #16a34a; }
.trace-span-msg--tool .trace-span-msg-label { color: #ea580c; }

.trace-span-msg-text {
  padding: 6px 10px;
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  color: #374151;
  max-height: 200px;
  overflow-y: auto;
}

/* Input/Output 摘要 */
.trace-span-io {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.trace-span-io-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.trace-span-io-label {
  font-size: 10px;
  font-weight: 700;
  color: #909399;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.trace-span-io-text {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  color: #374151;
  background: #f6f8fa;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  padding: 6px 8px;
  max-height: 150px;
  overflow-y: auto;
}

/* 子节点容器 */
.trace-span-children {
  position: relative;
}
</style>
