<template>
  <div id="app-container">
    <header class="app-header">
      <!-- 左侧：标题 + 模拟数据展示 -->
      <div class="header-left">
        <span class="app-logo">📊</span>
        <h1>柔性报表</h1>
        <div class="header-board-divider"></div>

        <button
          type="button"
          class="header-action-button header-action-button--primary"
          title="数据模拟"
          @click="handleMockBoardData"
        >
          <span class="header-action-icon">
            <el-icon :size="15"><Collection /></el-icon>
          </span>
          <span>模拟数据展示</span>
        </button>
      </div>
      <div class="header-right" style="position:relative;">
        <div class="header-tabs-wrap">
          <button class="header-tab-add" @click="handleCreateBoard" title="新建柔性报表">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          </button>
          <template v-for="b in boardList" :key="b.id">
            <div
              class="header-tab"
              :class="{ active: b.id === activeBoardId }"
              @click="switchBoard(b.id)"
              @contextmenu.prevent="openTabMenu($event, b)"
            >
              <span class="header-tab-name">{{ b.name }}</span>
              <button class="header-tab-more" @click.stop="openTabMenu($event, b)" title="更多操作">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/></svg>
              </button>
            </div>
          </template>
        </div>

        <!-- 监控入口 -->
        <router-link v-if="showMonitor" to="/monitor" class="header-monitor-btn" title="Agent 监控面板">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z"/>
            <path d="M2 17l10 5 10-5"/>
            <path d="M2 12l10 5 10-5"/>
          </svg>
          <span class="header-monitor-label">监控</span>
        </router-link>

        <!-- 用户显示（始终可见） -->
        <button
          type="button"
          class="header-user-btn"
          @click="userOpen=!userOpen"
          title="切换用户"
          :disabled="!showMonitor"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
          <span class="header-user-name">{{ chatStore.user?.username || '用户' }}</span>
        </button>

        <!-- 用户切换下拉（仅 check_user=true 时显示） -->
        <div v-if="showMonitor && userOpen" class="user-dropdown-overlay" @click="userOpen=false"></div>
        <div v-if="showMonitor" class="user-dropdown" :class="{ 'is-open': userOpen }">
          <div v-for="u in userList" :key="u.id" class="ud-item" :class="{ active: u.username === chatStore.user?.username }" @click="handleSwitchUser(u)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            <span>{{ u.username }}</span>
          </div>
        </div>
      </div>
    </header>

    <!-- 看板 Tab 右键菜单 -->
    <Teleport to="body">
      <div v-if="tabMenuVisible" class="tab-menu-overlay" @click="closeTabMenu" @contextmenu.prevent="closeTabMenu"></div>
      <div v-if="tabMenuVisible" class="tab-menu-popup" :style="tabMenuStyle">
        <div class="tab-menu-item" @click="handleRenameBoard(tabMenuBoard)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          <span>重命名</span>
        </div>
        <div class="tab-menu-item tab-menu-item--danger" @click="handleDeleteBoard(tabMenuBoard)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
          <span>删除</span>
        </div>
      </div>
    </Teleport>

    <!-- 浮动 AI 按钮（右下角圆形） -->
    <button
      type="button"
      class="ai-float-btn"
      title="AI 分析"
      @click="showAiDialog = true"
    >
      <el-icon :size="24"><MagicStick /></el-icon>
    </button>

    <!-- AI 对话弹窗 -->
    <el-dialog v-model="showAiDialog" top="5vh" destroy-on-close :show-close="false" class="ai-full-dialog">
      <AIDialog @close="showAiDialog = false" />
    </el-dialog>

    <div class="app-body">
      <main class="app-main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useChatStore } from '@/stores/useChatStore'
import { useBoardStore } from '@/stores/useBoardStore'
import AIDialog from '@/components/AIDialog.vue'
import { MagicStick, Collection } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()

function handleMockBoardData() {
  if (router.currentRoute.value.path !== '/board') {
    router.push('/board')
    nextTick(() => window.dispatchEvent(new CustomEvent('board:mock-data')))
    return
  }
  window.dispatchEvent(new CustomEvent('board:mock-data'))
}

/* ---------- 看板切换 ---------- */
const boardStore = useBoardStore()
onMounted(() => { boardStore.fetchBoards() })
const boardList = computed(() => boardStore.boards)
const activeBoardId = computed(() => boardStore.activeBoardId)

function switchBoard(id: number) {
  const rp = router.currentRoute.value.path
  if (rp !== '/board') { router.push('/board'); void nextTick(() => boardStore.switchBoard(id)); return }
  boardStore.switchBoard(id)
}
async function handleCreateBoard() {
  await boardStore.createBoard('新柔性报表')
}

/* ---------- Tab 右键菜单 ---------- */
const tabMenuVisible = ref(false)
const tabMenuStyle = ref({ left: '0px', top: '0px' })
const tabMenuBoard = ref<any>(null)

function openTabMenu(event: MouseEvent, board: any) {
  tabMenuBoard.value = board
  const x = Math.min(event.clientX, window.innerWidth - 180)
  const y = Math.min(event.clientY, window.innerHeight - 120)
  tabMenuStyle.value = { left: x + 'px', top: y + 'px' }
  tabMenuVisible.value = true
}

function closeTabMenu() {
  tabMenuVisible.value = false
  tabMenuBoard.value = null
}

async function handleRenameBoard(board: any) {
  closeTabMenu()
  try {
    const { value } = await ElMessageBox.prompt('请输入新名称', '重命名柔性报表', {
      inputValue: board.name,
      inputPattern: /\S+/,
      inputErrorMessage: '名称不能为空',
    })
    if (value && value.trim()) {
      await boardStore.updateBoard(board.id, { name: value.trim() })
      ElMessage.success('柔性报表已重命名')
    }
  } catch { /* 取消 */ }
}

async function handleDeleteBoard(board: any) {
  closeTabMenu()
  if (boardStore.boards.length <= 1) {
    ElMessage.warning('至少保留一个柔性报表')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定要删除柔性报表"${board.name}"及其所有图表吗？`,
      '确认删除柔性报表',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    const ok = await boardStore.deleteBoard(board.id)
    if (ok) ElMessage.success('柔性报表已删除')
    else ElMessage.warning(boardStore.error || '删除失败')
  } catch { /* 取消 */ }
}

const chatStore = useChatStore()
const showAiDialog = ref(false)

const userOpen = ref(false)
const userList = computed(() => chatStore.userList)

/* 监控面板仅在 URL 带 mt=1 时可见（支持 hash query 和 full query） */
const showMonitor = computed(() => {
  return route?.query?.m || import.meta.env.MODE === 'lock'
})

async function handleSwitchUser(u: {id:number;username:string;role:string}) {
  userOpen.value = false
  await chatStore.login(u.username, u.id)
}

onMounted(() => { chatStore.init() })
</script>

<style>
.header-user-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  background: #f3f4f6;
  color: #374151;
  font-size: 13px;
  white-space: nowrap;
}
.header-user-name {
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  width: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background-color: #f5f7fa;
}

#app-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  height: 52px;
  background: white;
  border-bottom: 1px solid #e4e7ed;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: stretch;
  gap: 0;
  height: 100%;
}

.app-logo {
  display: flex;
  align-items: center;
  font-size: 24px;
}

.app-header h1 {
  display: flex;
  align-items: center;
  white-space: nowrap;
  font-size: 17px;
  font-weight: 600;
  color: #303133;
}

.header-board-divider {
  width: 1px;
  height: 24px;
  background: #e4e7ed;
  margin: 0 10px;
  align-self: center;
}

.header-tabs-wrap {
  display: flex;
  align-items: center;
  gap: 2px;
  min-width: 0;
  overflow-x: auto;
  height: 100%;
}

.header-tabs-wrap::-webkit-scrollbar { height: 0; }

.header-tab-add {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  border: 1px dashed #c0c4cc;
  background: transparent;
  color: #909399;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.15s;
}
.header-tab-add:hover { border-color: #409eff; color: #409eff; background: #ecf5ff; }

.header-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
  height: 32px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: #606266;
  background: transparent;
  transition: all 0.15s;
  white-space: nowrap;
  user-select: none;
}
.header-tab:hover { background: #e3e6ea; color: #303133; }
.header-tab.active { background: #ecf5ff; color: #409eff; font-weight: 600; }

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-action-button {
  appearance: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 14px;
  border: 1px solid #dcdfe6;
  border-radius: 10px;
  background: #fff;
  color: #303133;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease, background-color 0.2s ease;
}

.header-action-button:hover {
  transform: translateY(-1px);
}

.header-action-button:focus-visible {
  outline: none;
}

.header-action-icon {
  width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.header-action-button--primary {
  border-color: #d9ecff;
  color: #409eff;
  background: #f4f9ff;
}

.header-action-button--primary:hover {
  background: #e8f3ff;
  border-color: #bcdcff;
  box-shadow: 0 4px 10px rgba(64, 158, 255, 0.12);
}

.header-action-button--primary:focus-visible {
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.18);
}

/* 浮动 AI 按钮 */
.ai-float-btn {
  position: fixed;
  bottom: 32px;
  right: 32px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);
  color: #fff;
  cursor: pointer;
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.25s ease;
}

.ai-float-btn:hover {
  transform: translateY(-3px) scale(1.06);
  box-shadow: 0 10px 30px rgba(99, 102, 241, 0.55);
}

.ai-float-btn:active {
  transform: scale(0.92);
}

.ai-float-btn::after {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
  opacity: 0;
  z-index: -1;
  transition: opacity 0.3s;
}

.ai-float-btn:hover::after {
  opacity: 0.25;
  filter: blur(8px);
}

.app-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.user-dropdown-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
}

.user-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  width: 200px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0,0,0,.12);
  z-index: 1001;
  opacity: 0;
  pointer-events: none;
  transform: translateY(-4px);
  transition: all .2s ease;
}

.user-dropdown.is-open {
  opacity: 1;
  pointer-events: auto;
  transform: translateY(0);
}

.ud-current {
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 12px;
  color: #6b7280;
}

.ud-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin: 2px 6px;
  border-radius: 6px;
  font-size: 13px;
  color: #1f2937;
  cursor: pointer;
  transition: background .15s;
}

.ud-item:hover { background: #f3f4f6; }
.ud-item.active { background: #e5e7eb; font-weight: 600; }

.header-user-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: none;
  border-radius: 6px;
  background: #f3f4f6;
  color: #374151;
  font-size: 13px;
  cursor: pointer;
  transition: background .15s;
}
.header-user-btn:hover { background: #e5e7eb; }

.header-monitor-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  background: #f0f5ff;
  color: #409eff;
  font-size: 13px;
  text-decoration: none;
  transition: background .15s;
  white-space: nowrap;
}
.header-monitor-btn:hover { background: #d9ecff; }
.header-monitor-label { font-weight: 500; }


.app-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* Tab 右键菜单 */
.header-tab-more {
  display: none;
  width: 16px;
  height: 16px;
  border-radius: 3px;
  border: none;
  background: transparent;
  cursor: pointer;
  align-items: center;
  justify-content: center;
  color: #909399;
  flex-shrink: 0;
  transition: all 0.15s;
  padding: 0;
}
.header-tab:hover .header-tab-more { display: inline-flex; }
.header-tab-more:hover { background: #d9dce1; color: #409eff; }

.tab-menu-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
}

.tab-menu-popup {
  position: fixed;
  z-index: 2001;
  min-width: 140px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
  padding: 4px;
  overflow: hidden;
}

.tab-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin: 2px 0;
  border-radius: 6px;
  font-size: 13px;
  color: #1f2937;
  cursor: pointer;
  transition: background 0.15s;
}
.tab-menu-item:hover { background: #f3f4f6; }
.tab-menu-item--danger { color: #d14343; }
.tab-menu-item--danger:hover { background: #fff5f5; }

</style>
