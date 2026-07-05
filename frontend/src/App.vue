<template>
  <div id="app-container">
    <!-- 顶部栏（含导航菜单） -->
    <header class="app-header">
      <div class="header-left">
        <span class="app-logo">📊</span>
        <h1>柔性报表</h1>
      </div>
      <div class="header-right">
        <button type="button" class="top-mock-button" title="数据模拟" @click="handleMockBoardData">
          <el-icon :size="16"><Collection /></el-icon>
          <span>数据模拟</span>
        </button>
        <button type="button" class="top-create-button" title="新增" @click="handleCreateBoard">
          <el-icon :size="16"><Plus /></el-icon>
          <span>新增</span>
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
import { Collection, Plus } from '@element-plus/icons-vue'

const router = useRouter()

async function dispatchBoardEvent(eventName: 'board:create' | 'board:mock-data') {
  if (router.currentRoute.value.path !== '/board') {
    await router.push('/board')
    await nextTick()
  }
  window.dispatchEvent(new CustomEvent(eventName))
}

function handleCreateBoard() {
  void dispatchBoardEvent('board:create')
}

function handleMockBoardData() {
  void dispatchBoardEvent('board:mock-data')
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

.top-create-button {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 7px 14px;
  border: none;
  border-radius: 8px;
  text-decoration: none;
  color: #ffffff;
  font-size: 13px;
  font-weight: 600;
  background: #409eff;
  box-shadow: 0 6px 16px rgba(64, 158, 255, 0.2);
  transition: all 0.2s;
  cursor: pointer;
}

.top-mock-button {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 7px 14px;
  border: 1px solid #d9ecff;
  border-radius: 8px;
  color: #409eff;
  font-size: 13px;
  font-weight: 600;
  background: #f4f9ff;
  transition: all 0.2s;
  cursor: pointer;
}

.top-mock-button:hover {
  background: #e8f3ff;
  border-color: #bcdcff;
}

.top-create-button:hover {
  background: #337ecc;
  color: #ffffff;
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
