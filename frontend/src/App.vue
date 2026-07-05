<template>
  <div id="app-container">
    <!-- 顶部栏（含导航菜单） -->
    <header class="app-header">
      <div class="header-left">
        <span class="app-logo">📊</span>
        <h1>柔性报表</h1>
      </div>
      <div class="header-right">
        <router-link to="/board" class="top-nav-item" active-class="nav-active" title="看板">
          <el-icon :size="18"><Collection /></el-icon>
          <span>看板</span>
        </router-link>
        <router-link to="/set" class="top-nav-item" active-class="nav-active" title="数据分析">
          <el-icon :size="18"><Histogram /></el-icon>
          <span>配置</span>
        </router-link>
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
import { Histogram, Collection } from '@element-plus/icons-vue'
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
  gap: 4px;
}

.top-nav-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  border-radius: 6px;
  text-decoration: none;
  color: #909399;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s;
}

.top-nav-item:hover {
  background: #f0f2f5;
  color: #409eff;
}

.nav-active {
  background: #ecf5ff;
  color: #409eff;
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
