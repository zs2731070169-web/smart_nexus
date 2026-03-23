<template>
  <div class="chat-window">
    <!-- 顶部标题栏 -->
    <div class="window-header">
      <div class="header-title">
        <el-icon><ChatDotRound /></el-icon>
        <span>{{ sessionTitle }}</span>
      </div>
      <div v-if="isStreaming" class="header-status">
        <el-icon class="spin-icon"><Loading /></el-icon>
        <span>AI 正在思考...</span>
      </div>
      <el-button class="logout-btn" size="small" text @click="$emit('logout')">
        <el-icon><SwitchButton /></el-icon>
        退出
      </el-button>
    </div>

    <!-- 消息区 -->
    <div class="message-list" ref="messageListRef" @scroll="onMessageListScroll">
      <!-- 欢迎屏（空状态） -->
      <div v-if="messages.length === 0" class="welcome-screen">
        <el-icon class="welcome-icon"><Service /></el-icon>
        <h2 class="welcome-title">您好，我是 Smart Nexus 智能顾问</h2>
        <p class="welcome-desc">专注于电脑、手机、电视等设备的售后技术支持</p>
        <div class="quick-hints">
          <div
            v-for="hint in QUICK_HINTS"
            :key="hint"
            class="hint-chip"
            @click="fillInput(hint)"
          >
            {{ hint }}
          </div>
        </div>
      </div>

      <!-- 消息列表 -->
      <template v-for="msg in messages" :key="msg.id">
        <!-- 用户消息 -->
        <div v-if="msg.role === 'user'" class="msg-row user-row">
          <div class="msg-avatar user-avatar">
            <el-icon><User /></el-icon>
          </div>
          <div class="msg-bubble user-bubble">{{ msg.content }}</div>
        </div>

        <!-- AI 消息 -->
        <div v-else class="msg-row ai-row">
          <div class="msg-avatar ai-avatar">
            <el-icon><Service /></el-icon>
          </div>
          <div class="msg-body">
            <!-- 推理思考（THINKING） -->
            <div v-if="msg.thinking" class="thinking-block">
              <div
                class="thinking-header"
                @click="msg.thinkingExpanded = !msg.thinkingExpanded"
              >
                <el-icon><Aim /></el-icon>
                <span>推理过程</span>
                <el-icon class="toggle-icon">
                  <ArrowDown v-if="msg.thinkingExpanded" />
                  <ArrowRight v-else />
                </el-icon>
              </div>
              <div v-show="msg.thinkingExpanded" class="thinking-body">
                <pre>{{ msg.thinking }}</pre>
              </div>
            </div>

            <!-- 过程处理（PROCESSING） -->
            <div v-if="msg.processing" class="processing-block">
              <el-icon :class="{ 'spin-icon': msg.isStreaming && !msg.answer }">
                <Loading v-if="msg.isStreaming && !msg.answer" />
                <CircleCheck v-else />
              </el-icon>
              <span class="processing-text">{{ msg.processing }}</span>
            </div>

            <!-- 最终回答（ANSWER） -->
            <div
              v-if="msg.answer"
              class="answer-block markdown-body"
              v-html="renderMarkdown(msg.answer)"
            ></div>

            <!-- 流式初始占位 -->
            <div
              v-if="msg.isStreaming && !msg.thinking && !msg.processing && !msg.answer"
              class="typing-dots"
            >
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- 输入区 -->
    <div class="input-area">
      <div class="input-wrapper">
        <el-input
          ref="inputRef"
          v-model="inputText"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 5 }"
          placeholder="请输入您的问题...（Enter 发送，Shift+Enter 换行）"
          resize="none"
          :disabled="isStreaming"
          @keydown.enter.exact.prevent="sendMessage"
        />
        <el-button
          type="primary"
          :icon="Promotion"
          :disabled="!inputText.trim() || isStreaming"
          class="send-btn"
          @click="sendMessage"
        >
          发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, onMounted, onUnmounted } from 'vue'
import {
  ChatDotRound, Service, User, Loading, Aim,
  ArrowDown, ArrowRight, CircleCheck, Promotion, SwitchButton
} from '@element-plus/icons-vue'
import { marked } from 'marked'
import { streamChat } from '../../api/consultant'

// ===== Markdown 渲染配置 =====
const IMAGE_URL_RE = /\.(png|jpe?g|gif|webp|svg|bmp)(\?[^\s)]*)?$/i

marked.setOptions({ breaks: true, gfm: true })
marked.use({
  renderer: {
    link({ href, title, text }) {
      if (href && IMAGE_URL_RE.test(href)) {
        return `<img src="${href}" alt="${text || title || '图片'}" class="chat-img" />`
      }
      return `<a href="${href}"${title ? ` title="${title}"` : ''} target="_blank" rel="noopener">${text}</a>`
    }
  }
})

// ===== Props / Emits =====
const props = defineProps({
  sessionId: { type: String, required: true },
  sessionTitle: { type: String, default: '新对话' },
  preloadedMessages: { type: Array, default: null }
})

const emit = defineEmits(['session-named', 'logout'])

// ===== 快捷提示 =====
const QUICK_HINTS = [
  '电脑蓝屏怎么解决？',
  '手机无法开机怎么办？',
  '查找附近维修站',
  '驱动安装失败如何处理？'
]

// ===== 消息工厂 =====
let msgIdCounter = 0

const createUserMessage = (content) => {
  return { id: ++msgIdCounter, role: 'user', content }
}

const createAiMessage = () => {
  return reactive({
    id: ++msgIdCounter,
    role: 'assistant',
    thinking: '',
    processing: '',
    answer: '',
    isStreaming: true,
    thinkingExpanded: true
  })
}

// ===== 消息持久化（防止页面意外刷新丢失进行中的对话） =====
const STORAGE_KEY = `smart_nexus_chat_${props.sessionId}`

/**
 * 从 sessionStorage 恢复消息；优先级高于 preloadedMessages，
 * 确保窗口切换/页面刷新后已接收内容不丢失
 */
const initMessages = () => {
  try {
    const saved = sessionStorage.getItem(STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      // AI 消息还原为 reactive 对象，isStreaming 统一重置为 false
      return parsed.map(msg =>
        msg.role === 'assistant'
          ? reactive({ ...msg, isStreaming: false })
          : msg
      )
    }
  } catch { /* 解析失败则忽略，使用默认值 */ }
  return props.preloadedMessages?.map(msg => ({ ...msg })) ?? []
}

/** 将当前消息快照写入 sessionStorage */
const saveMessages = () => {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages.value))
  } catch { /* 存储失败忽略（如隐私模式或空间不足） */ }
}

// ===== 状态 =====
const messages = ref(initMessages())
const inputText = ref('')
const isStreaming = ref(false)
const messageListRef = ref(null)
// 用户是否主动上翻（true 时跳过自动滚底）
const userScrolledUp = ref(false)

const onMessageListScroll = () => {
  const el = messageListRef.value
  if (!el) return
  // 距底部超过 80px 则认为用户主动上翻
  userScrolledUp.value = el.scrollTop + el.clientHeight < el.scrollHeight - 80
}

const scrollToBottom = () => {
  if (userScrolledUp.value) return
  nextTick(() => {
    const el = messageListRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

const inputRef = ref(null)

const fillInput = (text) => {
  inputText.value = text
  nextTick(() => inputRef.value?.focus())
}

const renderMarkdown = (content) => {
  return content ? marked.parse(content) : ''
}

const sendMessage = async () => {
  const query = inputText.value.trim()
  if (!query || isStreaming.value) return

  // 发送新消息时重置上翻状态，确保滚到最新回复
  userScrolledUp.value = false

  if (messages.value.length === 0) {
    emit('session-named', query.slice(0, 20))
  }

  messages.value.push(createUserMessage(query))
  inputText.value = ''

  const aiMsg = createAiMessage()
  messages.value.push(aiMsg)
  isStreaming.value = true
  scrollToBottom()

  try {
    for await (const event of streamChat(query, props.sessionId)) {
      const { data, status, metadata } = event

      if (status === 'FINISHED') {
        const reason = metadata?.finished_reason
        if (reason === 'EXCEPTION') {
          if (!aiMsg.answer) {
            aiMsg.answer = `处理过程中发生错误：${metadata?.error_message || '未知错误'}`
          }
        } else if (reason === 'MAX_TOKEN') {
          aiMsg.answer += '\n\n*（已达到最大输出长度限制）*'
        }
        break
      }

      if (data?.message_type !== 'delta') continue

      const { render_type, data: text } = data
      if (render_type === 'THINKING') {
        aiMsg.thinking += text
      } else if (render_type === 'PROCESSING') {
        aiMsg.processing += text
      } else if (render_type === 'ANSWER') {
        if (!aiMsg.answer) aiMsg.thinkingExpanded = false
        aiMsg.answer += text
      }
      scrollToBottom()
    }
  } catch {
    aiMsg.answer = '抱歉，对话服务出现异常，请稍后重试。'
  } finally {
    aiMsg.isStreaming = false
    isStreaming.value = false
    scrollToBottom()
    saveMessages()
  }
}

onMounted(() => {
  // 切换到其他应用窗口时立即保存，防止页面意外刷新丢失消息
  window.addEventListener('blur', saveMessages)
})

onUnmounted(() => {
  window.removeEventListener('blur', saveMessages)
  saveMessages() // 切换会话时保存当前消息状态
  isStreaming.value = false
})
</script>

<style scoped>
.chat-window {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #f8f9fb;
}

/* ===== 顶部栏 ===== */
.window-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  flex-shrink: 0;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #1a2a44;
}

.header-title .el-icon {
  font-size: 18px;
  color: #409eff;
}

.header-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #909399;
}

/* ===== 消息区 ===== */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px 24px 12px;
}

/* 欢迎屏 */
.welcome-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 300px;
  text-align: center;
  color: #909399;
}

.welcome-icon {
  font-size: 56px;
  color: #409eff;
  margin-bottom: 16px;
  opacity: 0.8;
}

.welcome-title {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.welcome-desc {
  font-size: 14px;
  color: #909399;
  margin-bottom: 28px;
}

.quick-hints {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  max-width: 520px;
}

.hint-chip {
  padding: 8px 16px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 20px;
  font-size: 13px;
  color: #606266;
  cursor: pointer;
  transition: all 0.2s;
}

.hint-chip:hover {
  border-color: #409eff;
  color: #409eff;
  background: #ecf5ff;
}

/* 消息行 */
.msg-row {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  max-width: 85%;
}

.user-row {
  flex-direction: row-reverse;
  margin-left: auto;
}

.ai-row {
  margin-right: auto;
}

/* 头像 */
.msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 18px;
}

.ai-avatar {
  background: #409eff;
  color: #fff;
}

.user-avatar {
  background: #409eff;
  color: #fff;
}

/* 用户气泡 */
.msg-bubble {
  padding: 10px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.user-bubble {
  background: #409eff;
  color: #fff;
  border-top-right-radius: 4px;
}

/* AI 消息体 */
.msg-body {
  flex: 1;
  min-width: 0;
}

/* ===== 推理过程（THINKING） ===== */
.thinking-block {
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  margin-bottom: 8px;
  overflow: hidden;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
  color: #909399;
  user-select: none;
  transition: background 0.15s;
}

.thinking-header:hover {
  background: #ebeef5;
}

.thinking-header .el-icon {
  font-size: 14px;
  color: #b0b3be;
}

.toggle-icon {
  margin-left: auto;
  font-size: 12px;
}

.thinking-body {
  border-top: 1px solid #e4e7ed;
  padding: 10px 14px;
}

.thinking-body pre {
  font-size: 12px;
  color: #606266;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Courier New', 'Microsoft YaHei', monospace;
  margin: 0;
}

/* ===== 过程处理（PROCESSING） ===== */
.processing-block {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  background: #f0f9ff;
  border: 1px solid #b3d8ff;
  border-radius: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  color: #409eff;
}

.processing-block .el-icon {
  flex-shrink: 0;
  margin-top: 1px;
  font-size: 15px;
}

.processing-text {
  line-height: 1.5;
  word-break: break-word;
}

/* ===== 最终回答（ANSWER） ===== */
.answer-block {
  background: #fff;
  border-radius: 8px;
  padding: 12px 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  font-size: 14px;
  color: #303133;
  line-height: 1.7;
  word-break: break-word;
}

/* ===== Markdown 内容样式 ===== */
.markdown-body :deep(p) { margin: 0 0 8px 0; }
.markdown-body :deep(p:last-child) { margin-bottom: 0; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { margin: 4px 0 8px 0; padding-left: 20px; }
.markdown-body :deep(li) { margin-bottom: 3px; }
.markdown-body :deep(strong) { font-weight: 600; }

.markdown-body :deep(code) {
  background: #f0f2f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  color: #c7254e;
  font-family: 'Courier New', monospace;
}

.markdown-body :deep(pre) {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
}

.markdown-body :deep(pre code) {
  background: none;
  color: inherit;
  padding: 0;
}

.markdown-body :deep(h1), .markdown-body :deep(h2),
.markdown-body :deep(h3), .markdown-body :deep(h4) {
  margin: 12px 0 6px;
  font-weight: 600;
}

.markdown-body :deep(blockquote) {
  border-left: 3px solid #409eff;
  padding-left: 12px;
  color: #606266;
  margin: 8px 0;
}

.markdown-body :deep(table) { border-collapse: collapse; margin: 8px 0; width: 100%; }
.markdown-body :deep(th), .markdown-body :deep(td) {
  border: 1px solid #e4e7ed;
  padding: 6px 10px;
  text-align: left;
}
.markdown-body :deep(th) { background: #f5f7fa; font-weight: 600; }

.markdown-body :deep(.chat-img) {
  max-width: 100%;
  max-height: 400px;
  border-radius: 8px;
  margin: 8px 0;
  display: block;
}

/* ===== 跳动加载点 ===== */
.typing-dots {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 12px 16px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  width: fit-content;
}

.typing-dots span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #409eff;
  animation: typing-bounce 1.4s ease-in-out infinite;
}

.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing-bounce {
  0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
  30% { opacity: 1; transform: scale(1); }
}

/* ===== 输入区 ===== */
.input-area {
  padding: 16px 24px;
  background: #fff;
  border-top: 1px solid #e4e7ed;
  flex-shrink: 0;
}

.input-wrapper {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.input-wrapper :deep(.el-textarea__inner) {
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 14px;
  line-height: 1.5;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}

.send-btn {
  height: 40px;
  border-radius: 8px;
  flex-shrink: 0;
}

/* ===== 动画 ===== */
.spin-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.logout-btn {
  color: rgb(33, 33, 33) !important;
  font-size: 12px;
  padding: 4px 8px;
}

.logout-btn:hover {
  color: #f56c6c !important;
  background: rgba(245, 108, 108, 0.08) !important;
}
</style>
