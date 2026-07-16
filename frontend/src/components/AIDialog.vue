<template>
  <div class="ai-dialog" :class="{ 'fullscreen-mode': isFullscreen }">
    <!-- 侧边栏：历史记录 -->
    <aside class="dialog-sidebar" :class="{ 'sidebar-visible': sidebarOpen }">
      <div class="sidebar-inner">
        <div class="sidebar-header">
          <button class="sidebar-new-btn" @click="chatStore.newSession()">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            <span>新建对话</span>
          </button>
        </div>
        <div class="sidebar-list">
          <div v-if="chatStore.sessions.length === 0" class="sidebar-empty">暂无历史</div>
          <div
            v-for="s in chatStore.sessions"
            :key="s.id"
            class="sidebar-item"
            :class="{ active: s.id === chatStore.activeSessionId }"
            @click="handleSwitch(s.id)"
          >
            <svg class="sidebar-item-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
            <div class="sidebar-item-text">
              <span class="sidebar-item-title">{{ s.title }}</span>
              <span class="sidebar-item-time">{{ fmtTime(s.updatedAt) }}</span>
            </div>
            <button class="sidebar-item-del" @click.stop="chatStore.deleteSession(s.id)"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
          </div>
        </div>
      </div>
    </aside>


    <!-- 主面板 -->
    <div class="dialog-main">
      <!-- 顶栏 -->
      <div class="dialog-topbar">
        <div class="topbar-left">
          <button class="topbar-btn" v-show="isFullscreen" @click="sidebarOpen=!sidebarOpen" title="菜单">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
          </button>
          <span class="dialog-title">AI 数据分析</span>
        </div>
        <div class="topbar-right">
          <button class="topbar-btn" v-show="!isFullscreen" @click="historyOpen=!historyOpen" title="历史记录">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          </button>
          <button class="topbar-btn" v-show="!isFullscreen" @click="chatStore.newSession()" title="新建对话">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
          </button>
          <button class="topbar-btn" @click="toggleFullscreen" :title="isFullscreen?'退出全屏':'全屏'">
            <svg v-if="!isFullscreen" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M3 16v3a2 2 0 002 2h3"/></svg>
            <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3v3a2 2 0 01-2 2H3m18 0h-3a2 2 0 01-2-2V3m0 18v-3a2 2 0 012-2h3M3 16h3a2 2 0 012 2v3"/></svg>
          </button>
          <button class="topbar-btn" @click="$emit('close')" title="关闭">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
      </div>
      <!-- 历史下拉 -->
      <div class="history-dropdown-wrapper">
        <div v-if="historyOpen" class="history-dropdown-overlay" @click="historyOpen=false" />
        <div class="history-dropdown" :class="{ 'is-open': historyOpen }">

          <div class="hd-list">
            <div v-for="s in chatStore.sessions" :key="s.id" class="hd-item" :class="{ active: s.id===chatStore.activeSessionId }" @click="chatStore.switchSession(s.id); historyOpen=false">
              <svg class="hd-ico" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
              <span class="hd-title">{{ s.title }}</span>
              <button class="hd-del" @click.stop="chatStore.deleteSession(s.id)"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
            </div>
          </div>
        </div>
      </div>

      <!-- 消息区 -->
      <div class="dialog-messages" ref="msgsRef">
        <div v-if="chatStore.messages.length===0" class="empty-state">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity=".4"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
          <div class="empty-title">小小助手驾到</div>
          <div class="empty-desc">有什么需要问我吗？</div>
        </div>

        <div v-for="(msg,i) in chatStore.messages" :key="i" class="msg-row" :class="msg.role">
          <div class="msg-avatar">
            <div class="avt" :class="msg.role==='user'?'avt-user':'avt-ai'">
              <svg v-if="msg.role==='user'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a4 4 0 014 4v2a4 4 0 01-8 0V6a4 4 0 014-4z"/><path d="M5.5 14h13"/><path d="M12 14v8"/></svg>
            </div>
          </div>
          <div class="msg-bubble">
            <div class="msg-text">{{ msg.content }}</div>
            <!-- 交互式问卷 -->
            <div v-if="msg.ask_questions?.length && msg.role === 'assistant'" class="msg-questions">
              <AskQuestionsPanel
                :prompt="msg.content"
                :questions="msg.ask_questions"
                @submit="handleQuestionSubmit($event, msg)"
                @cancel="() => {}"
              />
            </div>
            <div v-if="msg.charts?.length" class="msg-charts">
              <div v-for="(ch,ci) in msg.charts" :key="ci" class="chart-card">
                <div class="chart-card-hd">
                  <span class="chart-card-title">{{ ch.title }}</span>
                  <div class="chart-card-actions">
                    <button title="查看数据" @click="openData(ch)"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg></button>
                    <button title="查看配置" @click="openCfg(ch)"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg></button>
                    <button title="查看SQL" @click="openSql(ch)"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg></button>
                    <button title="保存到看板" @click="openSave(ch)"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z"/></svg></button>
                    <button title="全屏查看" @click="toggleFullscreenChart(i, ci)"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M3 16v3a2 2 0 002 2h3"/></svg></button>
                  </div>
                </div>
                <div class="chart-card-body">
                  <div v-if="ch.error" class="chart-err">{{ ch.error }}</div>
                  <VegaLiteRenderer v-else :ref="el=>setRR(`c_${i}_${ci}`,el)" :data="ch.data" :config="ch.pivot_config" :chart-type="ch.chart_type" :hide-toolbar="true" :hide-title="true" />
                </div>
              </div>
              <div class="msg-charts-footer" v-if="msg.charts.length > 1">
                <button class="import-all-btn" @click="quickImportAllCharts(msg.charts)">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l-2 6h4l-2 6m0 0l-2-6h4l-2-6"/><path d="M5 21h14"/></svg>
                  一键导入全部（{{ msg.charts.length }} 个图表）
                </button>
              </div>
            </div>
            <div v-if="msg.rules?.length" class="msg-rules">
              <article v-for="(rule, ri) in msg.rules" :key="ri" class="rule-card">
                <div class="rule-card-head">
                  <strong>{{ rule.name || '未命名' }}</strong>
                </div>
                <div v-if="rule.reason" class="rule-reason">{{ rule.reason }}</div>
                <div v-if="rule.applicable_signals?.length" class="rule-section">
                  <span class="rule-label">适用信号</span>
                  <span v-for="sig in rule.applicable_signals" :key="sig" class="rule-chip">{{ sig }}</span>
                </div>
                <div v-if="rule.usage_example" class="rule-example">
                  <span class="rule-label">示例</span>
                  <code>{{ rule.usage_example }}</code>
                </div>
              </article>
            </div>
            <!-- DTC 查询结果 -->
            <DtcQueryResult
              v-if="msg.query_result"
              :query-result="msg.query_result"
              @view-sql="openQuerySql"
            />
            <div v-if="msg.suggestions?.length" class="msg-sugs">
              <button v-for="sg in msg.suggestions" :key="sg" class="sug-chip" @click="sendText(sg)">{{ sg }}</button>
            </div>
          </div>
        </div>

        <div v-if="chatStore.loading" class="msg-row assistant">
          <div class="msg-avatar"><div class="avt avt-ai"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l1.5 5.5L19 9l-5.5 1.5L12 16l-1.5-5.5L5 9l5.5-1.5z"/></svg></div></div>
          <div class="msg-bubble"><span class="typing">···</span></div>
        </div>
        <div ref="scrollAnchor" />
      </div>

      <!-- 输入区 -->
      <div class="dialog-input">
        <div class="input-wrap">
          <textarea ref="taRef" v-model="inputText" class="input-ta" :placeholder="chatStore.mode==='chart'?'描述分析需求，如：按车型统计报警次数':'描述需求，如：有哪些速度相关规则'" rows="1" @keydown.enter.prevent="handleSend" @input="autoSize" />
          <button class="send-btn" :disabled="!inputText.trim()||chatStore.loading" @click="handleSend">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          </button>
        </div>
      </div>
    </div>

    <ChartDataDialog ref="dataDialogRef" />
    <ChartSqlDialog ref="sqlDialogRef" />
    <SaveToBoardDialog ref="saveDialogRef" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatStore } from '@/stores/useChatStore'
import { useChartStore, MAX_BOARD_CHARTS } from '@/stores/useChartStore'
import { useBoardStore } from '@/stores/useBoardStore'
import VegaLiteRenderer from './VegaLiteRenderer.vue'
import AskQuestionsPanel from './AskQuestionsPanel.vue'
import ChartDataDialog from './ChartDataDialog.vue'
import ChartSqlDialog from './ChartSqlDialog.vue'
import SaveToBoardDialog from './SaveToBoardDialog.vue'
import DtcQueryResult from './DtcQueryResult.vue'

const chatStore = useChatStore()
const chartStore = useChartStore()
const boardStore = useBoardStore()

const sidebarOpen = ref(false)
const historyOpen = ref(false)
const isFullscreen = ref(false)
const inputText = ref('')
const taRef = ref<HTMLTextAreaElement|null>(null)
const scrollAnchor = ref<HTMLElement|null>(null)
const dataDialogRef = ref<any>(null)
const sqlDialogRef = ref<any>(null)
const saveDialogRef = ref<any>(null)

const rendererRefs = ref<Record<string,any>>({})

function openQuerySql(sql: string) {
  sqlDialogRef.value?.open(sql, 'sql')
}

async function quickImportAllCharts(charts: any[]) {
  const title = `AI 导入 ${new Date().toLocaleDateString('zh-CN')} ${new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`
  const newBoard = await boardStore.createBoard(title)
  if (!newBoard) {
    ElMessage.warning(boardStore.error || '创建看板失败')
    return
  }
  const bid = newBoard.id
  try {
    await chartStore.fetchCharts(bid)
    const available = MAX_BOARD_CHARTS - chartStore.charts.length
    if (available <= 0) {
      ElMessage.warning(`看板已满（最多 ${MAX_BOARD_CHARTS} 个图表）`)
      return
    }
    const toImport = charts.slice(0, available)
    let successCount = 0
    for (const ch of toImport) {
      const chartTitle = ch.title || `图表 ${successCount + 1}`
      const ok = await chartStore.saveChart(
        chartTitle,
        ch.pivot_config || { filters: [], axes: [], legend: [], values: [] },
        ch.content || '',
        ch.chart_type || 'bar',
        null,
        ch.data || null,
        bid,
      )
      if (ok) successCount++
    }
    if (successCount > 0) {
      ElMessage.success(`已创建看板「${title}」，成功导入 ${successCount} 个图表`)
    } else {
      ElMessage.warning(chartStore.error || '导入失败')
    }
    if (toImport.length < charts.length) {
      ElMessage.warning(`看板容量不足，仅导入 ${toImport.length} 个`)
    }
  } catch (e: any) {
    ElMessage.error(e.message || '导入失败')
  }
}

function setRR(k:string, inst:any) {
  if (inst && typeof inst.exportPng==='function') rendererRefs.value[k]=inst
}
function autoSize() {
  const el=taRef.value; if(!el) return
  el.style.height='auto'; el.style.height=Math.min(el.scrollHeight,200)+'px'
}
function handleSend() {
  const m=inputText.value.trim(); if(!m||chatStore.loading) return
  inputText.value=''
  if(taRef.value) taRef.value.style.height='auto'
  chatStore.sendMessage(m)
  scrollToBottom()
}
function sendText(t:string) {
  if(chatStore.loading) return
  inputText.value=t; handleSend()
}
function handleSwitch(id:string) {
  chatStore.switchSession(id)
  scrollToBottom()
}

function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value
}

/**
 * 用户提交问卷答案 → 发给 AI 继续处理
 * 提交格式：[问卷提交] + 中文排版，展示图表槽配置
 * 提交后隐藏问卷面板不可再次发送
 */
async function handleQuestionSubmit(answers: Record<string, any>, msg: any) {
  msg.ask_questions = []
  msg.pending_step = null
  chatStore.sendMessage(answers.result, {
    dashboardDraft: {
      goal: '报警分析总览',
      task_id: Number(answers.taskId),
      chart_count: Number(answers.chartCount),
      chart_slots: answers.slots
    },
  })
  scrollToBottom()
}

function toggleFullscreenChart(msgIdx: number, chartIdx: number) {
  const key = 'c_' + msgIdx + '_' + chartIdx
  rendererRefs.value[key]?.toggleFullscreen()
}

function scrollToBottom() {
  nextTick(()=>scrollAnchor.value?.scrollIntoView({behavior:'smooth'}))
}

function openData(ch:any) { 
  dataDialogRef.value?.open(ch.data)
}
function openCfg(ch:any) { 
  sqlDialogRef.value?.open(ch.pivot_config, 'json')
}
function openSql(ch:any) { 
  sqlDialogRef.value?.open(ch.sql, 'sql')
}
function openSave(ch:any) { 
  saveDialogRef.value?.open(ch)
 }

function fmtTime(ts:string) {
  const d=new Date(ts), n=new Date()
  if(d.toDateString()===n.toDateString()) return `今天 ${d.toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})}`
  const y=new Date(n); y.setDate(y.getDate()-1)
  if(d.toDateString()===y.toDateString()) return `昨天 ${d.toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})}`
  return d.toLocaleDateString('zh-CN')
}

watch(isFullscreen,(val)=>{ sidebarOpen.value=val })
watch(()=>chatStore.messages.length,()=>scrollToBottom())
</script>

<style scoped>
/* ====== 布局 ====== */
.ai-dialog {
  display: flex;
  height: 100%;
  background: #fff;
  color: #1f2937;
  font-size: 14px;
  position: relative;
  overflow: hidden;
}

.ai-dialog.fullscreen-mode {
  position: fixed;
  inset: 0;
  z-index: 9998;
  background: #fff;
}

/* ====== 侧边栏 ====== */
.dialog-sidebar {
  width: 0;
  flex-shrink: 0;
  background: #f7f7f8;
  border-right: 1px solid #e5e5e5;
  transition: width 0.2s ease;
  overflow: hidden;
}

.dialog-sidebar.sidebar-visible {
  width: 240px;
}

.sidebar-inner {
  width: 240px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 10px;
  border-bottom: 1px solid #e5e5e5;
}

.sidebar-new-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #fff;
  color: #374151;
  font-size: 13px;
  cursor: pointer;
  transition: background .15s;
}

.sidebar-new-btn:hover { background: #f3f4f6; }

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px 0;
}

.sidebar-empty {
  text-align: center;
  color: #9ca3af;
  font-size: 12px;
  padding: 20px;
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 7px 10px;
  margin: 1px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background .15s;
}

.sidebar-item:hover { background: #e5e7eb; }
.sidebar-item.active { background: #e5e7eb; }

.sidebar-item-icon {
  flex-shrink: 0;
  color: #6b7280;
}

.sidebar-item-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.sidebar-item-title {
  font-size: 13px;
  color: #1f2937;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-item-time {
  font-size: 11px;
  color: #9ca3af;
}

.sidebar-item-del {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  opacity: 0;
  transition: opacity .15s;
}

.sidebar-item:hover .sidebar-item-del { opacity: 1; }
.sidebar-item-del:hover { background: #f3f4f6; color: #ef4444; }


/* ====== 主面板 ====== */
.dialog-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* ====== 顶栏 ====== */
.dialog-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 2px;
}

.topbar-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  transition: background .15s;
}

.dialog-title { font-size: 14px; font-weight: 600; color: #1f2937; margin-left: 4px; }
.topbar-btn:hover { background: #f3f4f6; color: #374151; }

.mode-selector {
  display: flex;
  background: #f3f4f6;
  border-radius: 6px;
  padding: 2px;
}

.mode-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border: none;
  border-radius: 5px;
  background: transparent;
  color: #6b7280;
  font-size: 12px;
  cursor: pointer;
  transition: all .15s;
  white-space: nowrap;
}

.mode-btn.active {
  background: #fff;
  color: #1f2937;
  box-shadow: 0 1px 2px rgba(0,0,0,.08);
}

.mode-btn:hover:not(.active) { color: #374151; }

/* ====== 消息区 ====== */
.dialog-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  gap: 12px;
  color: #9ca3af;
}

.empty-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.empty-desc { font-size: 13px; }

.empty-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  max-width: 360px;
}

.empty-chip {
  padding: 5px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #fff;
  color: #374151;
  font-size: 12px;
  cursor: pointer;
  transition: all .15s;
}

.empty-chip:hover { background: #f3f4f6; border-color: #d1d5db; }

/* 消息 */
.msg-row {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  max-width: 760px;
  padding: 0 8px;
}

.msg-avatar { flex-shrink: 0; }

.avt {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avt-user { background: #3b82f6; color: #fff; }
.avt-ai { background: #8b5cf6; color: #fff; }

.msg-bubble {
  max-width: calc(100% - 42px);
  min-width: 0;
}

.msg-text {
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.msg-row.user .msg-text {
  background: #f0f4ff;
  padding: 8px 14px;
  border-radius: 14px 4px 14px 14px;
}

/* 图表卡片 */
.msg-charts {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.msg-charts-footer {
  display: flex;
  justify-content: center;
  padding-top: 2px;
}

.import-all-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  border: 1px dashed #3b82f6;
  border-radius: 8px;
  background: #f0f7ff;
  color: #3b82f6;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all .15s;
}

.import-all-btn:hover {
  background: #3b82f6;
  color: #fff;
  border-color: #3b82f6;
}

.chart-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  overflow: hidden;
}

.chart-card-hd {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  border-bottom: 1px solid #f3f4f6;
}

.chart-card-title { font-size: 12px; font-weight: 600; color: #374151; }

.chart-card-actions {
  display: flex;
  gap: 2px;
}

.chart-card-actions button {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 5px;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  transition: all .15s;
}

.chart-card-actions button:hover { background: #f3f4f6; color: #3b82f6; }

.chart-card-body { min-height: 180px; }

.chart-err {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 28px;
  color: #9ca3af;
  font-size: 13px;
  background: #fafafa;
}

.msg-sugs {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.sug-chip {
  padding: 3px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #fff;
  color: #374151;
  font-size: 12px;
  cursor: pointer;
  transition: all .15s;
}

.sug-chip:hover { background: #f3f4f6; border-color: #d1d5db; }

.typing { animation: blink 1.4s infinite; font-size: 24px; letter-spacing: 2px; }

@keyframes blink {
  0%,80%,100% { opacity: .3; }
  40% { opacity: 1; }
}

/* ====== 输入区 ====== */
.dialog-input {
  flex-shrink: 0;
  padding: 10px 16px 12px;
  border-top: 1px solid #f0f0f0;
}

.input-wrap {
  max-width: 760px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid #d1d5db;
  border-radius: 14px;
  transition: border-color .15s, box-shadow .15s;
}

.input-wrap:focus-within {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59,130,246,.12);
}

.input-ta {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  font-size: 13px;
  line-height: 1.5;
  font-family: inherit;
  color: #1f2937;
  background: transparent;
  max-height: 200px;
}

.input-ta::placeholder { color: #9ca3af; }

.send-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 50%;
  background: #3b82f6;
  color: #fff;
  cursor: pointer;
  transition: background .15s;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) { background: #2563eb; }
.send-btn:disabled { background: #e5e7eb; color: #9ca3af; cursor: not-allowed; }

/* ====== 公共 ====== */
.code-block {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 14px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.6;
  overflow: auto;
  max-height: 60vh;
  white-space: pre-wrap;
  word-break: break-all;
}

.code-block.sql { font-family: 'SF Mono','Menlo','Consolas',monospace; }




/* ====== 历史下拉 ====== */
.history-dropdown-wrapper {
  position: relative;
}

.history-dropdown-overlay {
  position: fixed;
  inset: 0;
  z-index: 98;
}

.history-dropdown {
  position: absolute;
  top: 4px;
  right: 0;
  width: 240px;
  max-height: 50vh;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0,0,0,.12);
  z-index: 99;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  opacity: 0;
  pointer-events: none;
  transform: translateY(-4px);
  transition: all .2s ease;
}

.history-dropdown.is-open {
  opacity: 1;
  pointer-events: auto;
  transform: translateY(0);
}

.hd-header { padding: 8px; border-bottom: 1px solid #f0f0f0; }

.hd-new-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #fff;
  color: #374151;
  font-size: 13px;
  cursor: pointer;
  transition: background .15s;
}

.hd-new-btn:hover { background: #f3f4f6; }

.hd-list { flex: 1; overflow-y: auto; padding: 4px 0; }

.hd-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  margin: 1px 6px;
  border-radius: 6px;
  cursor: pointer;
  transition: background .15s;
}

.hd-item:hover { background: #f3f4f6; }
.hd-item.active { background: #e5e7eb; }

.hd-ico { flex-shrink: 0; color: #6b7280; }

.hd-title {
  flex: 1; min-width: 0;
  font-size: 13px; color: #1f2937;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.hd-del {
  flex-shrink: 0;
  width: 22px; height: 22px;
  display: flex; align-items: center; justify-content: center;
  border: none; border-radius: 4px;
  background: transparent; color: #9ca3af;
  cursor: pointer; opacity: 0;
  transition: opacity .15s;
}

.hd-item:hover .hd-del { opacity: 1; }
.hd-del:hover { background: #f3f4f6; color: #ef4444; }

/* ====== 规则函数推荐 ====== */
.msg-rules { display: grid; gap: 8px; margin-top: 8px; }
.rule-card {
  padding: 8px 10px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}
.rule-card-head { margin-bottom: 4px; }
.rule-card-head strong { font-size: 15px; color: #2563eb; font-family: 'Menlo', monospace; }
.rule-reason { margin: 4px 0; color: #334155; font-size: 12px; line-height: 1.5; }
.rule-section { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; margin-top: 6px; }
.rule-label { color: #64748b; font-size: 11px; font-weight: 600; margin-right: 2px; }
.rule-chip { padding: 2px 6px; border-radius: 4px; background: #e0f2fe; color: #075985; font-size: 11px; }
.rule-example { margin-top: 6px; }
.rule-example code {
  display: block;
  padding: 5px 8px;
  margin-top: 2px;
  border-radius: 4px;
  background: #1e293b;
  color: #a5f3fc;
  font-size: 11px;
  line-height: 1.4;
  white-space: pre-wrap;
  word-break: break-all;
}
.rule-example .rule-label { display: block; }

</style>
