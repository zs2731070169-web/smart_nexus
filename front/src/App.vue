<template>
  <div class="app-container">
    <!-- 左侧边栏 -->
    <aside class="app-sidebar">
      <div class="sidebar-header">
        <el-icon class="header-icon"><Monitor /></el-icon>
        <h1 class="header-title">Smart Nexus</h1>
        <p class="header-subtitle">电脑售后智能知识顾问</p>
      </div>
      <div class="sidebar-body">
        <UploadPanel />
      </div>
      <div class="sidebar-footer">
        <span>Powered by RAG</span>
      </div>
    </aside>
    <!-- 右侧聊天区 -->
    <main class="app-main">
      <ChatPanel />
    </main>
  </div>
</template>

<script>
import ChatPanel from './components/ChatPanel/ChatPanel.vue'
import UploadPanel from './components/UploadPanel/UploadPanel.vue'

export default {
  name: 'App',
  components: {
    ChatPanel,
    UploadPanel
  }
}
</script>

<style scoped>
.app-container {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* ========== 左侧边栏 ========== */
.app-sidebar {
  width: 300px;
  min-width: 300px;
  background: linear-gradient(180deg, #1a2a44 0%, #15202e 100%);
  color: #fff;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 32px 24px 24px;
  text-align: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.header-icon {
  font-size: 36px;
  color: #409eff;
  margin-bottom: 12px;
}

.header-title {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 1px;
  margin-bottom: 6px;
}

.header-subtitle {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.55);
}

.sidebar-body {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

.sidebar-footer {
  padding: 16px 24px;
  text-align: center;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.3);
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

/* ========== 右侧主区域 ========== */
.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: #f0f2f5;
}
</style>
