<template>
  <el-config-provider :locale="zhCn">
    <div class="app-shell">
      <!-- 仅 Electron 环境显示自定义标题栏 -->
      <TitleBar v-if="isElectron" />
      <LoginPage v-if="!authStore.isLoggedIn" class="app-content" />
      <ChatPage v-else class="app-content" />
    </div>
  </el-config-provider>
</template>

<script setup>
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { authStore } from './store/auth'
import LoginPage from './components/LoginPage/LoginPage.vue'
import ChatPage from './components/ChatPage/ChatPage.vue'
import TitleBar from './components/TitleBar/TitleBar.vue'

const isElectron = typeof window !== 'undefined' && !!window.electronAPI
</script>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.app-content {
  flex: 1;
  overflow: hidden;
  min-height: 0;
}
</style>
