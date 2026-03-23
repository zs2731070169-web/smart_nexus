<template>
  <div class="title-bar">
    <!-- 可拖动区域 + 标题 -->
    <div class="title-drag">
      <span class="title-name">Smart Nexus</span>
    </div>

    <!-- 窗口控制按钮 -->
    <div class="title-controls">
      <!-- 最小化 -->
      <button class="ctrl-btn" title="最小化" @click="minimize">
        <svg width="10" height="1" viewBox="0 0 10 1">
          <line x1="0" y1="0.5" x2="10" y2="0.5" stroke="currentColor" stroke-width="1.5" />
        </svg>
      </button>

      <!-- 最大化 / 还原 -->
      <button class="ctrl-btn" :title="isMaximized ? '向下还原' : '最大化'" @click="toggleMaximize">
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          <rect v-if="!isMaximized" x="1" y="1" width="8" height="8" rx="0.5"
            stroke="currentColor" stroke-width="1.5" />
          <g v-else>
            <rect x="3" y="0" width="7" height="7" rx="0.5" stroke="currentColor" stroke-width="1.3" />
            <path d="M0 3 L0 10 L7 10 L7 7" stroke="currentColor" stroke-width="1.3" fill="none" />
          </g>
        </svg>
      </button>

      <!-- 关闭 -->
      <button class="ctrl-btn ctrl-close" title="关闭" @click="close">
        <svg width="10" height="10" viewBox="0 0 10 10">
          <line x1="1" y1="1" x2="9" y2="9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
          <line x1="9" y1="1" x2="1" y2="9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const isMaximized = ref(false)
let removeListener = null

const minimize = () => window.electronAPI?.minimize()
const toggleMaximize = () => window.electronAPI?.maximize()
const close = () => window.electronAPI?.close()

onMounted(async () => {
  isMaximized.value = (await window.electronAPI?.isMaximized()) ?? false
  removeListener = window.electronAPI?.onMaximizeChange((val) => {
    isMaximized.value = val
  })
})

onUnmounted(() => {
  removeListener?.()
})
</script>

<style scoped>
.title-bar {
  display: flex;
  align-items: center;
  height: 38px;
  background: #f0f2f5;
  border-bottom: 1px solid #dde1e7;
  flex-shrink: 0;
  user-select: none;
}

.title-drag {
  flex: 1;
  height: 100%;
  display: flex;
  align-items: center;
  padding-left: 16px;
  -webkit-app-region: drag;
}

.title-name {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  letter-spacing: 0.5px;
}

.title-controls {
  display: flex;
  height: 100%;
  -webkit-app-region: no-drag;
}

.ctrl-btn {
  width: 46px;
  height: 100%;
  border: none;
  background: transparent;
  color: #606266;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, color 0.15s;
}

.ctrl-btn:hover {
  background: rgba(0, 0, 0, 0.07);
  color: #303133;
}

.ctrl-close:hover {
  background: #e81123;
  color: #fff;
}
</style>
