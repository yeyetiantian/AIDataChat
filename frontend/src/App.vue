<template>
  <div id="app-container">
    <header class="app-header">
      <div class="header-left">
        <span class="app-logo">📊</span>
        <h1>柔性报表</h1>
      </div>
      <div class="header-right">
        <button
          type="button"
          class="header-action-button header-action-button--ai"
          title="AI 分析"
          @click="handleToggleAi"
        >
          <span class="header-action-icon">
            <el-icon :size="15"><ChatDotRound /></el-icon>
          </span>
          <span>AI 分析</span>
        </button>

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

        <button
          type="button"
          class="header-action-button header-action-button--danger"
          title="清空看板"
          @click="handleClearBoard"
        >
          <span>清空看板</span>
        </button>
      </div>
    </header>

    <div class="app-body">
      <main class="app-main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ChatDotRound, Collection } from '@element-plus/icons-vue'

const router = useRouter()

async function dispatchBoardEvent(eventName: 'board:mock-data' | 'board:clear-all' | 'board:toggle-ai') {
  if (router.currentRoute.value.path !== '/board') {
    await router.push('/board')
    await nextTick()
  }
  window.dispatchEvent(new CustomEvent(eventName))
}

function handleMockBoardData() {
  void dispatchBoardEvent('board:mock-data')
}

function handleClearBoard() {
  void dispatchBoardEvent('board:clear-all')
}

function handleToggleAi() {
  void dispatchBoardEvent('board:toggle-ai')
}
</script>

<style>
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
  align-items: center;
  gap: 10px;
}

.app-logo {
  font-size: 24px;
}

.app-header h1 {
  font-size: 17px;
  font-weight: 600;
  color: #303133;
}

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

.header-action-button--ai {
  border-color: #d7e8d0;
  color: #2f7d32;
  background: #f3faf1;
}

.header-action-button--ai:hover {
  background: #e8f6e4;
  border-color: #bfe0b4;
  box-shadow: 0 4px 10px rgba(47, 125, 50, 0.12);
}

.header-action-button--ai:focus-visible {
  box-shadow: 0 0 0 3px rgba(47, 125, 50, 0.16);
}

.header-action-button--danger {
  border-color: #f3c4c4;
  color: #d14343;
  background: #fff5f5;
}

.header-action-button--danger:hover {
  background: #ffeaea;
  border-color: #e9aaaa;
  box-shadow: 0 4px 10px rgba(209, 67, 67, 0.12);
}

.header-action-button--danger:focus-visible {
  box-shadow: 0 0 0 3px rgba(209, 67, 67, 0.18);
}

.app-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.app-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}
</style>
