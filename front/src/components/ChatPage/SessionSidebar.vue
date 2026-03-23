<template>
  <aside class="session-sidebar">
    <!-- 品牌头部 -->
    <div class="sidebar-brand">
      <el-icon class="brand-icon"><Monitor /></el-icon>
      <div>
        <h1 class="brand-name">Smart Nexus</h1>
        <p class="brand-slogan">设备售后智能顾问</p>
      </div>
    </div>

    <!-- 新建对话 -->
    <div class="sidebar-section">
      <el-button class="new-chat-btn" :icon="Plus" @click="$emit('new-session')">
        新建对话
      </el-button>
    </div>

    <!-- 当前会话列表 -->
    <div class="sidebar-sessions">
      <p class="section-label">全部会话</p>
      <div
        v-for="session in sessions"
        :key="session.id"
        class="session-item"
        :class="{ active: session.id === activeSessionId }"
        @click="$emit('select-session', session.id)"
      >
        <el-icon class="session-icon"><ChatDotRound /></el-icon>
        <span class="session-title">{{ session.title }}</span>
      </div>
    </div>

    <!-- 工具区 -->
    <div class="sidebar-tools">
      <div class="tool-item" @click="$emit('open-upload')">
        <el-icon><FolderAdd /></el-icon>
        <span>知识库管理</span>
      </div>
    </div>

    <!-- 用户信息 -->
    <div class="sidebar-user">
      <div class="user-info">
        <el-icon><User /></el-icon>
        <span class="user-phone">{{ maskedPhone }}</span>
      </div>

    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import {
  Monitor, Plus, ChatDotRound, Clock, FolderAdd, User, SwitchButton
} from '@element-plus/icons-vue'

const props = defineProps({
  sessions: { type: Array, required: true },
  activeSessionId: { type: String, required: true },
  userPhone: { type: String, default: '' }
})

defineEmits(['new-session', 'select-session', 'open-history', 'open-upload'])

const maskedPhone = computed(() =>
  props.userPhone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2')
)
</script>

<style scoped>
.session-sidebar {
  width: 260px;
  min-width: 260px;
  background: #eef1f6;
  border-right: 1px solid #dde1e7;
  color: #303133;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ===== 品牌头部 ===== */
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 24px 20px 20px;
  border-bottom: 1px solid #dde1e7;
}

.brand-icon {
  font-size: 30px;
  color: #409eff;
  flex-shrink: 0;
}

.brand-name {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.5px;
  margin-bottom: 2px;
  color: #303133;
}

.brand-slogan {
  font-size: 11px;
  color: #909399;
}

/* ===== 新建按钮 ===== */
.sidebar-section {
  padding: 14px 12px 8px;
}

.new-chat-btn {
  width: 100%;
  background: #fff;
  border: 1px solid #dde1e7;
  color: #409eff;
  border-radius: 8px;
}

.new-chat-btn:hover {
  background: #ecf5ff;
  border-color: #409eff;
}

/* ===== 会话列表 ===== */
.sidebar-sessions {
  flex: 1;
  overflow-y: auto;
  padding: 4px 12px;
}

.section-label {
  font-size: 11px;
  color: #b0b3be;
  padding: 6px 8px 4px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
  overflow: hidden;
}

.session-item:hover {
  background: rgba(0, 0, 0, 0.04);
}

.session-item.active {
  background: #e0eaf8;
}

.session-icon {
  font-size: 14px;
  color: #b0b3be;
  flex-shrink: 0;
}

.session-item.active .session-icon {
  color: #409eff;
}

.session-title {
  font-size: 13px;
  color: #606266;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-item.active .session-title {
  color: #1a5fa8;
  font-weight: 500;
}

/* ===== 工具区 ===== */
.sidebar-tools {
  padding: 8px 12px;
  border-top: 1px solid #dde1e7;
}

.tool-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 10px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: #606266;
  transition: all 0.15s;
}

.tool-item:hover {
  background: rgba(0, 0, 0, 0.04);
  color: #303133;
}

.tool-item .el-icon {
  font-size: 15px;
}

/* ===== 用户信息 ===== */
.sidebar-user {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-top: 1px solid #dde1e7;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #909399;
}

.user-phone {
  font-family: 'Courier New', monospace;
  letter-spacing: 0.5px;
}

</style>
