<script setup>
import { computed } from 'vue'
import {
  Monitor, Plus, ChatDotRound, Clock, FolderAdd, User, SwitchButton, Delete
} from '@element-plus/icons-vue'

defineProps({
  sessions: { type: Array, required: true },
  activeSessionId: { type: String, required: true },
})

defineEmits(['new-session', 'select-session', 'delete-session', 'open-history', 'open-upload'])
</script>

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
        <el-icon class="session-delete" @click.stop="$emit('delete-session', session.id)"><Delete /></el-icon>
      </div>
    </div>

    <!-- 工具区 -->
    <div class="sidebar-tools">
      <div class="tool-item" @click="$emit('open-upload')">
        <el-icon><FolderAdd /></el-icon>
        <span>知识库管理</span>
      </div>
    </div>
  </aside>
</template>

<style scoped lang="scss">
$primary: #409eff;
$border: #dde1e7;
$text-primary: #303133;
$text-secondary: #606266;
$text-hint: #909399;

.session-sidebar {
  width: 260px;
  min-width: 260px;
  background: #eef1f6;
  border-right: 1px solid $border;
  color: $text-primary;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  // 品牌头部
  .sidebar-brand {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 24px 20px 20px;
    border-bottom: 1px solid $border;

    .brand-icon {
      font-size: 30px;
      color: $primary;
      flex-shrink: 0;
    }

    .brand-name {
      font-size: 17px;
      font-weight: 700;
      letter-spacing: 0.5px;
      margin-bottom: 2px;
      color: $text-primary;
    }

    .brand-slogan {
      font-size: 11px;
      color: $text-hint;
    }
  }

  // 新建按钮
  .sidebar-section {
    padding: 14px 12px 8px;

    .new-chat-btn {
      width: 100%;
      background: #fff;
      border: 1px solid $border;
      color: $primary;
      border-radius: 8px;

      &:hover {
        background: #ecf5ff;
        border-color: $primary;
      }
    }
  }

  // 会话列表
  .sidebar-sessions {
    flex: 1;
    overflow-y: auto;
    padding: 4px 12px;

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

      &:hover {
        background: rgba(0, 0, 0, 0.04);

        .session-delete {
          color: #b0b3be;
        }
      }

      &.active {
        background: #e0eaf8;

        .session-icon { color: $primary; }
        .session-title { color: #1a5fa8; font-weight: 500; }
      }

      .session-icon {
        font-size: 14px;
        color: #b0b3be;
        flex-shrink: 0;
      }

      .session-title {
        font-size: 13px;
        color: $text-secondary;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .session-delete {
        font-size: 18px;
        color: transparent;
        flex-shrink: 0;
        margin-left: auto;
        padding: 2px 3px;
        border-radius: 4px;
        transition: color 0.15s, background 0.15s;

        &:hover {
          color: #f56c6c !important;
          background: rgba(245, 108, 108, 0.1);
        }
      }
    }
  }

  // 工具区
  .sidebar-tools {
    padding: 8px 12px;
    border-top: 1px solid $border;

    .tool-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 9px 10px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 13px;
      color: $text-secondary;
      transition: all 0.15s;

      &:hover {
        background: rgba(0, 0, 0, 0.04);
        color: $text-primary;
      }

      .el-icon {
        font-size: 15px;
      }
    }
  }
}
</style>
